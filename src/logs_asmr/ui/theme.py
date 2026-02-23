"""Centralized visual theme — Catppuccin Mocha palette + shared stylesheets."""

from __future__ import annotations

from PyQt6.QtGui import QColor


class Color:
    """Catppuccin Mocha color palette."""

    CRUST = "#11111b"
    BASE = "#1e1e2e"
    MANTLE = "#181825"
    SURFACE0 = "#313244"
    SURFACE1 = "#45475a"
    SURFACE2 = "#585b70"
    TEXT = "#cdd6f4"
    SUBTEXT0 = "#a6adc8"
    OVERLAY1 = "#abb2bf"
    OVERLAY0 = "#6c7086"
    DIM_TEXT = "#636d83"
    BLUE = "#89b4fa"
    LAVENDER = "#b4befe"
    RED = "#e06c75"
    GREEN = "#a6e3a1"
    YELLOW = "#e5c07b"
    FLAMINGO = "#f38ba8"
    PEACH = "#fab387"
    MAROON = "#e78a4e"
    SAPPHIRE = "#61afef"

    RED_HOVER = "#c95f67"
    RED_PRESSED = "#b35259"
    GREEN_HOVER = "#8fd48a"
    GREEN_PRESSED = "#79c574"
    CATCHUP_BG = "#45273a"
    CATCHUP_HOVER = "#5a2f47"


class HighlightColor:
    """Pre-built QColor instances for the log highlighter."""

    ERROR = QColor(Color.RED)
    WARN = QColor(Color.YELLOW)
    INFO = QColor(Color.OVERLAY1)
    DEBUG = QColor(Color.DIM_TEXT)
    TIMESTAMP = QColor(Color.SAPPHIRE)


class Size:
    """Sizing constants."""

    BAR_HEIGHT = 28
    BORDER_RADIUS = 3
    CHIP_RADIUS = 12
    FONT_SIZE_SM = 11
    FONT_SIZE_MD = 12
    INPUT_PADDING_V = 3
    INPUT_PADDING_H = 6


UI_FONT_FAMILY = '"Inter", "SF Pro Text", "Segoe UI", "Helvetica Neue", sans-serif'
MONO_FONT_FAMILY = '"Menlo", "Consolas", "Monaco", monospace'


# ---------------------------------------------------------------------------
# Badge color mapping
# ---------------------------------------------------------------------------

BADGE_COLORS: dict[str, tuple[str, str]] = {
    "connected": (Color.MAROON, Color.BASE),
    "paused": (Color.OVERLAY0, Color.TEXT),
    "dropping": (Color.FLAMINGO, Color.BASE),
    "sampling": (Color.PEACH, Color.BASE),
    "reconnecting": (Color.PEACH, Color.BASE),
    "disconnected": (Color.OVERLAY0, Color.TEXT),
}
BADGE_DEFAULT_COLORS: tuple[str, str] = (Color.OVERLAY0, Color.TEXT)


# ---------------------------------------------------------------------------
# Global application stylesheet
# ---------------------------------------------------------------------------


def app_stylesheet() -> str:
    """Return a global stylesheet applied once via QApplication.setStyleSheet()."""
    R = Size.BORDER_RADIUS
    SM = Size.FONT_SIZE_SM
    MD = Size.FONT_SIZE_MD
    PV = Size.INPUT_PADDING_V
    PH = Size.INPUT_PADDING_H
    return f"""
/* ── Base ── */
QWidget {{
    background: {Color.BASE};
    color: {Color.TEXT};
    font-family: {UI_FONT_FAMILY};
    font-size: {MD}px;
}}
QMainWindow {{
    background: {Color.BASE};
}}

/* ── Labels ── */
QLabel {{
    background: transparent;
    font-size: {MD}px;
}}

/* ── Line edits ── */
QLineEdit {{
    background: {Color.SURFACE0};
    color: {Color.TEXT};
    border: 1px solid {Color.SURFACE1};
    border-radius: {R}px;
    padding: {PV}px {PH}px;
    font-size: {MD}px;
    selection-background-color: {Color.SURFACE1};
}}
QLineEdit:focus {{
    border-color: {Color.BLUE};
}}
QLineEdit::placeholder {{
    color: {Color.OVERLAY0};
}}

/* ── Combo boxes ── */
QComboBox {{
    background: {Color.SURFACE0};
    color: {Color.TEXT};
    border: 1px solid {Color.SURFACE1};
    border-radius: {R}px;
    padding: {PV}px {PH}px;
    font-size: {MD}px;
}}
QComboBox:focus {{
    border-color: {Color.BLUE};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background: {Color.SURFACE0};
    color: {Color.TEXT};
    selection-background-color: {Color.SURFACE1};
    border: 1px solid {Color.SURFACE1};
}}

/* ── Push buttons ── */
QPushButton {{
    border: 1px solid {Color.SURFACE1};
    border-radius: {R}px;
    background: {Color.SURFACE0};
    color: {Color.TEXT};
    padding: 0 10px;
    font-size: {MD}px;
}}
QPushButton:hover {{
    background: {Color.SURFACE1};
}}
QPushButton:pressed {{
    background: {Color.SURFACE2};
}}
QPushButton:checked {{
    background: {Color.SURFACE1};
    border-color: {Color.BLUE};
}}

/* ── Check boxes ── */
QCheckBox {{
    color: {Color.TEXT};
    spacing: 6px;
    font-size: {MD}px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {Color.SURFACE2};
    border-radius: 3px;
    background: {Color.SURFACE0};
}}
QCheckBox::indicator:checked {{
    background: {Color.BLUE};
    border-color: {Color.BLUE};
}}

/* ── Tab widget ── */
QTabWidget::pane {{
    border: 1px solid {Color.SURFACE0};
    background: {Color.BASE};
}}
QTabBar::tab {{
    background: {Color.MANTLE};
    color: {Color.SUBTEXT0};
    border: 1px solid {Color.SURFACE0};
    padding: 4px 12px;
    margin-right: 2px;
    border-top-left-radius: {R}px;
    border-top-right-radius: {R}px;
}}
QTabBar::tab:selected {{
    background: {Color.BASE};
    color: {Color.TEXT};
    border-bottom-color: {Color.BASE};
}}
QTabBar::tab:hover:!selected {{
    background: {Color.SURFACE0};
}}

/* ── Dialogs ── */
QDialog {{
    background: {Color.BASE};
}}
QMessageBox {{
    background: {Color.BASE};
}}
QInputDialog {{
    background: {Color.BASE};
}}

/* ── Group boxes ── */
QGroupBox {{
    border: 1px solid {Color.SURFACE0};
    border-radius: {R}px;
    margin-top: 8px;
    padding-top: 14px;
    color: {Color.TEXT};
    font-size: {MD}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    color: {Color.SUBTEXT0};
}}

/* ── List widgets ── */
QListWidget {{
    background: {Color.SURFACE0};
    color: {Color.TEXT};
    border: 1px solid {Color.SURFACE1};
    border-radius: {R}px;
    font-size: {MD}px;
}}
QListWidget::item:selected {{
    background: {Color.SURFACE1};
}}
QListWidget::item:hover {{
    background: {Color.SURFACE1};
}}

/* ── Sliders ── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {Color.SURFACE1};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: {Color.BLUE};
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {Color.LAVENDER};
}}
QSlider::sub-page:horizontal {{
    background: {Color.BLUE};
    border-radius: 2px;
}}

/* ── Scroll bars (vertical) ── */
QScrollBar:vertical {{
    background: {Color.MANTLE};
    width: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {Color.SURFACE1};
    min-height: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: {Color.SURFACE2};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

/* ── Scroll bars (horizontal) ── */
QScrollBar:horizontal {{
    background: {Color.MANTLE};
    height: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {Color.SURFACE1};
    min-width: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {Color.SURFACE2};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ── Status bar ── */
QStatusBar {{
    background: {Color.CRUST};
    color: {Color.SUBTEXT0};
    font-size: {SM}px;
    border-top: 1px solid {Color.SURFACE0};
}}
QStatusBar QLabel {{
    color: {Color.SUBTEXT0};
    font-size: {SM}px;
}}

/* ── Splitter ── */
QSplitter::handle {{
    background: {Color.SURFACE0};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ── Dock widget ── */
QDockWidget {{
    color: {Color.TEXT};
    titlebar-close-icon: none;
}}
QDockWidget::title {{
    background: {Color.MANTLE};
    padding: 4px 8px;
    border-bottom: 1px solid {Color.SURFACE0};
    font-size: {SM}px;
    color: {Color.SUBTEXT0};
}}

/* ── Tooltips ── */
QToolTip {{
    background: {Color.SURFACE0};
    color: {Color.TEXT};
    border: 1px solid {Color.SURFACE1};
    padding: 4px 6px;
    font-size: {SM}px;
}}

/* ── Dialog button box ── */
QDialogButtonBox QPushButton {{
    min-width: 70px;
    padding: 4px 16px;
}}
"""


def section_heading_style() -> str:
    """Uppercase dim label for filter drawer section headings."""
    return (
        f"QLabel {{ color: {Color.OVERLAY0}; font-size: {Size.FONT_SIZE_SM}px;"
        f" font-weight: 600; letter-spacing: 1px; padding: 0; margin: 0; }}"
    )


# ---------------------------------------------------------------------------
# Per-widget override stylesheets
# ---------------------------------------------------------------------------


def label_style() -> str:
    return (
        f"QLabel {{ color: {Color.SUBTEXT0}; font-size: {Size.FONT_SIZE_SM}px;"
        f" padding: 0; margin: 0; }}"
    )


def combo_style_with_margin() -> str:
    return (
        f"QComboBox {{ padding: 4px 8px; margin: 6px 6px 0 6px; }}"
    )


def tail_btn_live_style() -> str:
    return (
        f"QPushButton {{"
        f"  border: 1px solid {Color.RED}; border-radius: {Size.BORDER_RADIUS}px;"
        f"  background: {Color.RED}; color: {Color.BASE};"
        f"  padding: 0 10px; font-size: {Size.FONT_SIZE_MD}px; font-weight: 600;"
        f"}}"
        f"QPushButton:hover {{ background: {Color.RED_HOVER}; }}"
        f"QPushButton:pressed {{ background: {Color.RED_PRESSED}; }}"
    )


def tail_btn_paused_style() -> str:
    return (
        f"QPushButton {{"
        f"  border: 1px solid {Color.GREEN}; border-radius: {Size.BORDER_RADIUS}px;"
        f"  background: {Color.GREEN}; color: {Color.BASE};"
        f"  padding: 0 10px; font-size: {Size.FONT_SIZE_MD}px; font-weight: 600;"
        f"}}"
        f"QPushButton:hover {{ background: {Color.GREEN_HOVER}; }}"
        f"QPushButton:pressed {{ background: {Color.GREEN_PRESSED}; }}"
    )


def catchup_btn_style() -> str:
    return (
        f"QPushButton {{"
        f"  border: 1px solid {Color.FLAMINGO}; border-radius: {Size.BORDER_RADIUS}px;"
        f"  background: {Color.CATCHUP_BG}; color: {Color.FLAMINGO};"
        f"  padding: 0 10px; font-size: {Size.FONT_SIZE_MD}px;"
        f"}}"
        f"QPushButton:hover {{ background: {Color.CATCHUP_HOVER}; }}"
    )


def badge_style(bg: str, fg: str) -> str:
    return (
        f"QLabel {{"
        f"  background: {bg}; color: {fg};"
        f"  border-radius: {Size.BORDER_RADIUS}px; padding: 0 8px;"
        f"  font-size: {Size.FONT_SIZE_SM}px; font-weight: 600;"
        f"}}"
    )


def action_bar_style() -> str:
    return (
        f"ActionBar {{ background: {Color.MANTLE};"
        f" border-bottom: 1px solid {Color.SURFACE0}; }}"
    )


def tree_view_style() -> str:
    return (
        f"QTreeView {{"
        f"  background-color: {Color.MANTLE}; color: {Color.TEXT};"
        f"  border: none;"
        f"  font-size: {Size.FONT_SIZE_MD}px;"
        f"}}"
        f"QTreeView::item {{ padding: 1px 0; }}"
        f"QTreeView::item:hover {{ background-color: {Color.SURFACE0}; }}"
        f"QTreeView::item:selected {{ background-color: {Color.SURFACE1}; }}"
    )


def panel_background() -> str:
    return f"background-color: {Color.MANTLE};"


def log_view_style() -> str:
    return (
        f"QPlainTextEdit {{"
        f"  background-color: {Color.BASE};"
        f"  color: {Color.TEXT};"
        f"  selection-background-color: {Color.SURFACE1};"
        f"  border: none;"
        f"}}"
    )


def chip_style() -> str:
    return (
        f"QPushButton {{"
        f"  border: 1px solid {Color.SURFACE1}; border-radius: {Size.CHIP_RADIUS}px;"
        f"  padding: 2px 10px; font-size: {Size.FONT_SIZE_SM}px;"
        f"  background-color: {Color.SURFACE0}; color: {Color.TEXT};"
        f"}}"
        f"QPushButton:checked {{"
        f"  background-color: {Color.BLUE}; color: {Color.BASE};"
        f"  border-color: {Color.BLUE};"
        f"}}"
        f"QPushButton:hover {{"
        f"  border-color: {Color.BLUE};"
        f"}}"
    )


def drop_count_style() -> str:
    return f"QLabel {{ color: {Color.FLAMINGO}; font-weight: bold; }}"


def subtext_style() -> str:
    return f"color: {Color.SUBTEXT0};"
