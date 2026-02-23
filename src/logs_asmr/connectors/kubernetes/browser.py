"""Kubernetes source browser — context/namespace/pod/container tree."""

from __future__ import annotations

import logging

from logs_asmr.connectors.base import SourceBrowser, SourceNode
from logs_asmr.models.source import Source
from logs_asmr.ui import theme

logger = logging.getLogger("logs_asmr.connectors.kubernetes.browser")


class KubernetesBrowser(SourceBrowser):
    """Browse Kubernetes namespaces, pods, and containers."""

    def __init__(self, db=None) -> None:
        super().__init__(db)
        self._context = self._get_pref("context")
        self._v1 = None

    def connector_id(self) -> str:
        return "kubernetes"

    def display_name(self) -> str:
        return "Kubernetes"

    def _get_api(self):  # noqa: ANN201
        """Load kubeconfig and return a CoreV1Api client, caching across calls."""
        if self._v1 is not None:
            return self._v1

        from kubernetes import client, config

        # Use new_client_from_config to get an isolated ApiClient instead of
        # load_kube_config which mutates the global default Configuration.
        kwargs = {}
        if self._context:
            kwargs["context"] = self._context
        api_client = config.new_client_from_config(**kwargs)
        self._v1 = client.CoreV1Api(api_client=api_client)
        return self._v1

    def _reset_api(self) -> None:
        """Clear cached API client (e.g. when context changes)."""
        self._v1 = None

    def fetch_root_nodes(self) -> list[SourceNode]:
        """Fetch namespaces for the current context."""
        try:
            v1 = self._get_api()
            namespaces = v1.list_namespace()
        except Exception as e:
            logger.warning("Cannot list K8s namespaces: %s", e)
            self._reset_api()
            return []

        return [
            SourceNode(
                label=ns.metadata.name,
                data={"namespace": ns.metadata.name},
                node_type="namespace",
            )
            for ns in namespaces.items
        ]

    def fetch_children(self, node: SourceNode) -> list[SourceNode]:
        if node.node_type == "namespace":
            return self._fetch_pods(node.data["namespace"])
        if node.node_type == "pod":
            return self._fetch_containers(node)
        return []

    def _fetch_pods(self, namespace: str) -> list[SourceNode]:
        try:
            v1 = self._get_api()
            pods = v1.list_namespaced_pod(namespace=namespace)
        except Exception as e:
            logger.warning("Cannot list pods in %s: %s", namespace, e)
            self._reset_api()
            return []

        return [
            SourceNode(
                label=pod.metadata.name,
                data={"namespace": namespace, "pod": pod.metadata.name},
                node_type="pod",
            )
            for pod in pods.items
        ]

    def _fetch_containers(self, node: SourceNode) -> list[SourceNode]:
        try:
            v1 = self._get_api()
            pod = v1.read_namespaced_pod(
                name=node.data["pod"],
                namespace=node.data["namespace"],
            )
        except Exception as e:
            logger.warning("Cannot read pod %s: %s", node.data.get("pod"), e)
            self._reset_api()
            return []

        containers = []
        for c in pod.spec.containers or []:
            containers.append(
                SourceNode(
                    label=c.name,
                    data={
                        "namespace": node.data["namespace"],
                        "pod": node.data["pod"],
                        "container": c.name,
                    },
                    node_type="container",
                    is_selectable=True,
                )
            )
        return containers

    def build_source(self, node: SourceNode) -> Source:
        namespace = node.data.get("namespace", "default")
        pod = node.data.get("pod", "")
        container = node.data.get("container", "")
        return Source(
            connector="kubernetes",
            params={
                "context": self._context,
                "namespace": namespace,
                "pod": pod,
                "container": container,
            },
            label=f"{namespace}/{pod}/{container}" if container else f"{namespace}/{pod}",
        )

    def create_header_widget(self, parent=None):  # noqa: ANN201
        """Context selector combo."""
        from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout

        from logs_asmr.connectors.base import HeaderWidget

        widget = HeaderWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(2)

        ctx_label = QLabel("Context")
        ctx_label.setStyleSheet(theme.label_style())
        layout.addWidget(ctx_label)

        context_combo = QComboBox()

        # Populate contexts from kubeconfig
        try:
            from kubernetes import config

            contexts, active = config.list_kube_config_contexts()
            for ctx in contexts:
                context_combo.addItem(ctx["name"], ctx["name"])

            # Prefer saved context from DB, then active kubeconfig context
            saved = self._context
            if saved:
                idx = context_combo.findData(saved)
                if idx >= 0:
                    context_combo.setCurrentIndex(idx)
            elif active:
                idx = context_combo.findData(active["name"])
                if idx >= 0:
                    context_combo.setCurrentIndex(idx)
        except Exception:
            context_combo.addItem("(no kubeconfig found)")

        def on_context_changed(idx: int) -> None:
            self._context = context_combo.currentData() or ""
            self._set_pref("context", self._context)
            self._reset_api()
            widget.refresh_requested.emit()

        context_combo.currentIndexChanged.connect(on_context_changed)
        layout.addWidget(context_combo)

        # Set initial context
        self._context = context_combo.currentData() or ""

        return widget

    @classmethod
    def is_available(cls) -> bool:
        try:
            import kubernetes  # noqa: F401

            return True
        except ImportError:
            return False

    @classmethod
    def missing_deps_message(cls) -> str:
        return "Install kubernetes SDK: pip install logs-asmr[kubernetes]"
