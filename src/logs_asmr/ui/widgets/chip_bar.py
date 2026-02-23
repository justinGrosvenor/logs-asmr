"""Horizontal bar of toggleable chip/tag buttons."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from logs_asmr.ui import theme


class ChipBar(QWidget):
    """A horizontal row of toggleable chip buttons."""

    selection_changed = pyqtSignal(set)  # set of selected chip labels

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._chips: dict[str, QPushButton] = {}
        self._layout.addStretch()

    def set_chips(self, labels: list[str], all_selected: bool = True) -> None:
        """Replace all chips with the given labels."""
        # Clear existing
        for btn in self._chips.values():
            self._layout.removeWidget(btn)
            btn.deleteLater()
        self._chips.clear()

        # Remove stretch
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new chips
        for label in labels:
            self._add_chip(label, selected=all_selected)
        self._layout.addStretch()

    def add_chip(self, label: str, selected: bool = True) -> None:
        """Add a single chip if it doesn't already exist."""
        if label in self._chips:
            return
        # Insert before the stretch
        self._add_chip(label, selected=selected)

    def _add_chip(self, label: str, selected: bool = True) -> None:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(selected)
        btn.setFixedHeight(26)
        btn.setStyleSheet(theme.chip_style())
        btn.toggled.connect(lambda _: self._on_toggled())
        # Insert before the stretch
        idx = self._layout.count() - 1
        if idx < 0:
            idx = 0
        self._layout.insertWidget(idx, btn)
        self._chips[label] = btn

    def _on_toggled(self) -> None:
        selected = {label for label, btn in self._chips.items() if btn.isChecked()}
        self.selection_changed.emit(selected)

    def selected(self) -> set[str]:
        return {label for label, btn in self._chips.items() if btn.isChecked()}

