"""Per-sound volume control widget."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget


class VolumeSlider(QWidget):
    """Labeled volume slider."""

    volume_changed = pyqtSignal(float)  # 0.0 to 1.0

    def __init__(self, label: str, initial: float = 0.5, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setFixedWidth(70)
        layout.addWidget(self._label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(int(initial * 100))
        self._slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self._slider)

        self._value_label = QLabel(f"{int(initial * 100)}%")
        self._value_label.setFixedWidth(40)
        layout.addWidget(self._value_label)

    def _on_value_changed(self, value: int) -> None:
        self._value_label.setText(f"{value}%")
        self.volume_changed.emit(value / 100.0)

    def set_value(self, volume: float) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(int(volume * 100))
        self._slider.blockSignals(False)
        self._value_label.setText(f"{int(volume * 100)}%")
