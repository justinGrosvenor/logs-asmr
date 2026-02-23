"""CloudWatch source browser — profile/region selection + log group/stream tree."""

from __future__ import annotations

import logging

from logs_asmr.connectors.base import SourceBrowser, SourceNode
from logs_asmr.connectors.cloudwatch.credentials import (
    CredentialStore,
    discover_aws_profiles,
    get_default_region,
    get_regions_for_profile,
)
from logs_asmr.connectors.cloudwatch.log_groups import LogGroupFetcher
from logs_asmr.models.source import Source
from logs_asmr.ui import theme

logger = logging.getLogger("logs_asmr.connectors.cloudwatch.browser")

# Region display names for settings dialog
AWS_REGIONS = [
    ("US East (N. Virginia)", "us-east-1"),
    ("US East (Ohio)", "us-east-2"),
    ("US West (N. California)", "us-west-1"),
    ("US West (Oregon)", "us-west-2"),
    ("Europe (Ireland)", "eu-west-1"),
    ("Europe (London)", "eu-west-2"),
    ("Europe (Frankfurt)", "eu-central-1"),
    ("Europe (Paris)", "eu-west-3"),
    ("Europe (Stockholm)", "eu-north-1"),
    ("Asia Pacific (Tokyo)", "ap-northeast-1"),
    ("Asia Pacific (Seoul)", "ap-northeast-2"),
    ("Asia Pacific (Singapore)", "ap-southeast-1"),
    ("Asia Pacific (Sydney)", "ap-southeast-2"),
    ("Asia Pacific (Mumbai)", "ap-south-1"),
    ("Canada (Central)", "ca-central-1"),
    ("South America (Sao Paulo)", "sa-east-1"),
]


class CloudWatchBrowser(SourceBrowser):
    """Browses CloudWatch log groups and streams."""

    def __init__(self, db=None) -> None:
        super().__init__(db)
        self._fetcher = LogGroupFetcher()
        self._store = CredentialStore()
        self._profile = self._get_pref("profile")
        self._region = self._get_pref("region")
        self._initial_region = self._region  # used once during first header widget init

    def connector_id(self) -> str:
        return "cloudwatch"

    def display_name(self) -> str:
        return "AWS CloudWatch"

    def set_profile_region(self, profile: str, region: str) -> None:
        self._profile = profile
        self._region = region

    def fetch_root_nodes(self) -> list[SourceNode]:
        """Fetch log groups for the current profile/region."""
        if not self._profile or not self._region:
            return []
        groups = self._fetcher.list_log_groups(self._profile, self._region)
        nodes = []
        for name, arn in groups:
            nodes.append(
                SourceNode(
                    label=name,
                    data={"log_group": name, "log_group_arn": arn},
                    node_type="group",
                    is_selectable=True,
                )
            )
        return nodes

    def fetch_children(self, node: SourceNode) -> list[SourceNode]:
        """Fetch log streams for a log group node."""
        if node.node_type != "group":
            return []
        log_group = node.data.get("log_group", "")
        streams = self._fetcher.list_log_streams(
            self._profile, self._region, log_group
        )
        return [
            SourceNode(
                label=name,
                data={
                    "log_group": log_group,
                    "log_group_arn": node.data.get("log_group_arn", ""),
                    "log_stream": name,
                },
                node_type="stream",
                is_selectable=True,
            )
            for name in streams
        ]

    def build_source(self, node: SourceNode) -> Source:
        log_group = node.data.get("log_group", "")
        log_stream = node.data.get("log_stream", "")
        label = log_group
        if log_stream:
            label = f"{log_group} / {log_stream}"
        return Source(
            connector="cloudwatch",
            params={
                "profile": self._profile,
                "region": self._region,
                "log_group": log_group,
                "log_stream": log_stream,
                "log_group_arn": node.data.get("log_group_arn", ""),
            },
            label=label,
        )

    def create_header_widget(self, parent=None):  # noqa: ANN201
        """Returns profile/region selector widget for the CloudWatch tab header."""
        from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout

        from logs_asmr.connectors.base import HeaderWidget

        widget = HeaderWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(2)

        prof_label = QLabel("Profile")
        prof_label.setStyleSheet(theme.label_style())
        layout.addWidget(prof_label)
        profile_combo = QComboBox()
        profile_combo.setToolTip("AWS Profile")
        layout.addWidget(profile_combo)

        layout.addSpacing(4)

        region_label = QLabel("Region")
        region_label.setStyleSheet(theme.label_style())
        layout.addWidget(region_label)
        region_combo = QComboBox()
        region_combo.setToolTip("AWS Region")
        layout.addWidget(region_combo)

        # Store references for external access
        widget.profile_combo = profile_combo
        widget.region_combo = region_combo

        # Populate profiles
        self._populate_profiles(profile_combo)

        # Wire signals
        profile_combo.currentIndexChanged.connect(
            lambda idx: self._on_profile_selected(profile_combo, region_combo, idx, widget)
        )
        region_combo.currentIndexChanged.connect(
            lambda idx: self._on_region_selected(region_combo, idx, widget)
        )

        # Trigger initial selection — prefer saved profile from DB
        if profile_combo.count() > 0:
            saved_idx = profile_combo.findData(self._profile) if self._profile else -1
            if saved_idx >= 0:
                profile_combo.setCurrentIndex(saved_idx)
            else:
                profile_combo.setCurrentIndex(0)
            self._on_profile_selected(
                profile_combo, region_combo, profile_combo.currentIndex(), widget
            )
        else:
            self._profile = ""
            self._region = ""

        return widget

    def _populate_profiles(self, combo) -> None:  # noqa: ANN001
        combo.blockSignals(True)
        combo.clear()

        aws_profiles = discover_aws_profiles()
        for name in aws_profiles:
            combo.addItem(f"{name} (AWS)", name)

        for name in self._store.list_profiles():
            combo.addItem(name, name)

        combo.blockSignals(False)

    def _on_profile_selected(self, profile_combo, region_combo, index: int, widget=None) -> None:  # noqa: ANN001
        if index < 0:
            return
        profile = profile_combo.currentData()
        if not profile:
            return

        self._profile = profile
        self._set_pref("profile", profile)
        default_region = get_default_region(profile)
        regions = get_regions_for_profile(profile)

        region_combo.blockSignals(True)
        region_combo.clear()
        for region in regions:
            region_combo.addItem(region, region)

        # On first load, prefer saved region from DB; after that use profile default
        initial = self._initial_region
        self._initial_region = ""  # consume it — only used once
        saved_idx = region_combo.findData(initial) if initial else -1
        if saved_idx >= 0:
            region_combo.setCurrentIndex(saved_idx)
        elif (default_idx := region_combo.findData(default_region)) >= 0:
            region_combo.setCurrentIndex(default_idx)
        else:
            region_combo.setCurrentIndex(0)
        region_combo.blockSignals(False)

        self._on_region_selected(region_combo, region_combo.currentIndex(), widget)

    def _on_region_selected(self, region_combo, index: int, widget=None) -> None:  # noqa: ANN001
        if index < 0:
            return
        region = region_combo.currentData()
        if region:
            self._region = region
            self._set_pref("region", region)
        if widget is not None:
            widget.refresh_requested.emit()

    def has_settings(self) -> bool:
        return True

    def create_settings_widget(self, parent=None):  # noqa: ANN201
        """Return the credential management widget for settings."""
        from logs_asmr.connectors.cloudwatch.settings_widgets import CredentialsTab

        return CredentialsTab(self._store, parent=parent)

    @classmethod
    def is_available(cls) -> bool:
        try:
            import boto3  # noqa: F401

            return True
        except ImportError:
            return False

    @classmethod
    def missing_deps_message(cls) -> str:
        return "Install boto3: pip install logs-asmr[cloudwatch]"
