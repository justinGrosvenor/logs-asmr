"""CloudWatch credential management widgets for settings dialog."""

from __future__ import annotations

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from logs_asmr.connectors.cloudwatch.browser import AWS_REGIONS
from logs_asmr.connectors.cloudwatch.credentials import (
    CredentialStore,
    KeyringError,
    Profile,
    discover_aws_profiles,
)

logger = logging.getLogger("logs_asmr.connectors.cloudwatch.settings_widgets")


class CredentialsTab(QWidget):
    """Tab for managing AWS credential profiles."""

    profile_changed = pyqtSignal()

    def __init__(self, store: CredentialStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self.last_added_profile: str | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Saved Profiles:"))
        self._profile_list = QListWidget()
        layout.addWidget(self._profile_list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Profile...")
        self._add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self._add_btn)

        self._edit_btn = QPushButton("Edit...")
        self._edit_btn.clicked.connect(self._on_edit)
        self._edit_btn.setEnabled(False)
        btn_row.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._profile_list.currentItemChanged.connect(self._on_selection_changed)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._profile_list.clear()
        for name in discover_aws_profiles():
            self._profile_list.addItem(f"{name} (AWS CLI)")
        for name in self._store.list_profiles():
            self._profile_list.addItem(name)

    def _on_selection_changed(self) -> None:
        item = self._profile_list.currentItem()
        has_selection = item is not None
        is_custom = has_selection and not item.text().endswith("(AWS CLI)")
        self._edit_btn.setEnabled(is_custom)
        self._delete_btn.setEnabled(is_custom)

    def _on_add(self) -> None:
        dialog = _ProfileEditDialog(self._store, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.last_added_profile = dialog.profile_name()
            self._refresh_list()
            self.profile_changed.emit()

    def _on_edit(self) -> None:
        item = self._profile_list.currentItem()
        if not item:
            return
        name = item.text()
        profile = self._store.get_profile(name)
        if profile:
            dialog = _ProfileEditDialog(self._store, profile=profile, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._refresh_list()
                self.profile_changed.emit()

    def _on_delete(self) -> None:
        item = self._profile_list.currentItem()
        if not item:
            return
        name = item.text()
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Remove profile '{name}'?\n\n"
            "Credentials will be removed from the system keychain.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._store.delete_profile(name)
            except KeyringError:
                QMessageBox.critical(
                    self,
                    "Keyring Error",
                    "Could not delete profile — the system keyring is unavailable.\n\n"
                    "Check your keyring/keychain configuration.",
                )
                return
            self._refresh_list()
            self.profile_changed.emit()


class _ProfileEditDialog(QDialog):
    """Dialog for adding or editing a credential profile."""

    def __init__(
        self,
        store: CredentialStore,
        profile: Profile | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._editing = profile is not None

        self.setWindowTitle("Edit Profile" if self._editing else "Add Profile")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self._name_edit = QLineEdit()
        if profile:
            self._name_edit.setText(profile.name)
            self._name_edit.setReadOnly(True)
        layout.addRow("Profile Name:", self._name_edit)

        self._access_key_edit = QLineEdit()
        if profile:
            self._access_key_edit.setText(profile.access_key_id)
        layout.addRow("Access Key ID:", self._access_key_edit)

        self._secret_key_edit = QLineEdit()
        self._secret_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        if profile:
            self._secret_key_edit.setText(profile.secret_access_key)
        layout.addRow("Secret Access Key:", self._secret_key_edit)

        self._region_combo = QComboBox()
        for display_name, region_code in AWS_REGIONS:
            self._region_combo.addItem(f"{display_name} ({region_code})", region_code)
        if profile:
            for i in range(self._region_combo.count()):
                if self._region_combo.itemData(i) == profile.region:
                    self._region_combo.setCurrentIndex(i)
                    break
        layout.addRow("Region:", self._region_combo)

        self._endpoint_edit = QLineEdit()
        self._endpoint_edit.setPlaceholderText("e.g., http://localhost:9000")
        if profile:
            self._endpoint_edit.setText(profile.endpoint_url)
        layout.addRow("Endpoint URL (optional):", self._endpoint_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def profile_name(self) -> str:
        return self._name_edit.text().strip()

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        access_key = self._access_key_edit.text().strip()
        secret_key = self._secret_key_edit.text().strip()
        region = self._region_combo.currentData()
        endpoint_url = self._endpoint_edit.text().strip()

        if not name or not access_key or not secret_key:
            QMessageBox.warning(self, "Missing Fields", "Please fill in all fields.")
            return

        profile = Profile(
            name=name,
            access_key_id=access_key,
            secret_access_key=secret_key,
            region=region,
            endpoint_url=endpoint_url,
        )
        try:
            self._store.save_profile(profile)
        except KeyringError:
            QMessageBox.critical(
                self,
                "Keyring Error",
                "Could not save profile — the system keyring is unavailable.\n\n"
                "Check your keyring/keychain configuration.",
            )
            return
        self.accept()
