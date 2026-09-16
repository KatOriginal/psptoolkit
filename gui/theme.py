"""Фирменные темы оформления для PSP Toolkit: PlayStation Dark и PS1 Classic."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

DARK_STYLESHEET = """
/* ================= PlayStation Dark ================= */
QWidget {
    background-color: #121318;
    color: #e2e2ec;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #121318;
}

QMenuBar {
    background-color: #181920;
    color: #e2e2ec;
    border-bottom: 1px solid #272936;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #0070D1;
    color: #ffffff;
    border-radius: 4px;
}

QMenu {
    background-color: #1a1b24;
    color: #e2e2ec;
    border: 1px solid #2f3242;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item:selected {
    background-color: #0070D1;
    color: #ffffff;
    border-radius: 4px;
}

QMenu::separator {
    height: 1px;
    background: #2f3242;
    margin: 4px 6px;
}

QTabWidget::pane {
    border: 1px solid #272936;
    background-color: #16171f;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background-color: #181920;
    color: #9295a8;
    padding: 9px 24px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #272936;
    border-bottom: none;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #20222c;
    color: #ffffff;
}

QTabBar::tab:selected {
    background-color: #16171f;
    color: #ffffff;
    border-bottom: 3px solid #0070D1;
}

QGroupBox {
    background-color: #181922;
    border: 1px solid #272936;
    border-radius: 8px;
    margin-top: 18px;
    padding-top: 14px;
    font-weight: bold;
    color: #63b3ed;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background-color: #181922;
}

QPushButton {
    background-color: #222430;
    color: #e2e2ec;
    border: 1px solid #333648;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2c2f40;
    border-color: #0070D1;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #0070D1;
    border-color: #0070D1;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #171820;
    color: #555768;
    border-color: #22232c;
}

QTableWidget, QTreeWidget {
    background-color: #14151c;
    border: 1px solid #272936;
    border-radius: 6px;
    gridline-color: #20222e;
    color: #e2e2ec;
    selection-background-color: #15325b;
    selection-color: #ffffff;
    alternate-background-color: #171821;
}

QHeaderView::section {
    background-color: #1c1d27;
    color: #a0a3b8;
    padding: 6px;
    border: none;
    border-right: 1px solid #272936;
    border-bottom: 1px solid #272936;
    font-weight: bold;
}

QLineEdit {
    background-color: #14151c;
    border: 1px solid #2f3242;
    border-radius: 6px;
    padding: 6px 10px;
    color: #ffffff;
}

QLineEdit:focus {
    border: 1px solid #0070D1;
    background-color: #171822;
}

QProgressBar {
    background-color: #14151c;
    border: 1px solid #272936;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0070D1;
    border-radius: 5px;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #252735;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #0070D1;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #0070D1;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #90caf9;
}

QRadioButton {
    color: #e2e2ec;
    spacing: 8px;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #4a4d64;
    background-color: #14151c;
}

QRadioButton::indicator:checked {
    background-color: #0070D1;
    border-color: #0070D1;
}

QScrollBar:vertical {
    border: none;
    background: #121318;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2b2d3d;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #3b3e54;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QStatusBar {
    background-color: #14151c;
    color: #8c8f9f;
    border-top: 1px solid #20222e;
}
"""

PS1_CLASSIC_STYLESHEET = """
/* ================= PlayStation 1 Classic Grey ================= */
QWidget {
    background-color: #c2c2ca;
    color: #1d1e24;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #c2c2ca;
}

QMenuBar {
    background-color: #b5b5be;
    color: #1d1e24;
    border-bottom: 1px solid #9e9ea8;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #92929e;
    color: #ffffff;
    border-radius: 4px;
}

QMenu {
    background-color: #d0d0d8;
    color: #1d1e24;
    border: 1px solid #92929e;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item:selected {
    background-color: #00439c;
    color: #ffffff;
    border-radius: 4px;
}

QMenu::separator {
    height: 1px;
    background: #a2a2ae;
    margin: 4px 6px;
}

QTabWidget::pane {
    border: 1px solid #9696a0;
    background-color: #ceced6;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background-color: #b0b0ba;
    color: #4a4b56;
    padding: 9px 24px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #9696a0;
    border-bottom: none;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #bebec8;
    color: #111115;
}

QTabBar::tab:selected {
    background-color: #ceced6;
    color: #00439c;
    border-bottom: 3px solid #00439c;
}

QGroupBox {
    background-color: #cbcbd4;
    border: 1px solid #9a9aa4;
    border-radius: 8px;
    margin-top: 18px;
    padding-top: 14px;
    font-weight: bold;
    color: #00439c;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background-color: #cbcbd4;
}

QPushButton {
    background-color: #b5b5be;
    color: #1d1e24;
    border: 1px solid #8e8e98;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #c4c4cd;
    border-color: #00439c;
    color: #000000;
}

QPushButton:pressed {
    background-color: #00439c;
    border-color: #00439c;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #bababe;
    color: #7a7a84;
    border-color: #a8a8b0;
}

QTableWidget, QTreeWidget {
    background-color: #dfdfe6;
    border: 1px solid #9696a0;
    border-radius: 6px;
    gridline-color: #bababe;
    color: #1d1e24;
    selection-background-color: #00439c;
    selection-color: #ffffff;
    alternate-background-color: #d6d6de;
}

QHeaderView::section {
    background-color: #b8b8c2;
    color: #2b2c36;
    padding: 6px;
    border: none;
    border-right: 1px solid #9a9aa4;
    border-bottom: 1px solid #9a9aa4;
    font-weight: bold;
}

QLineEdit {
    background-color: #e8e8f0;
    border: 1px solid #8c8c96;
    border-radius: 6px;
    padding: 6px 10px;
    color: #111116;
}

QLineEdit:focus {
    border: 1px solid #00439c;
    background-color: #ffffff;
}

QProgressBar {
    background-color: #b0b0ba;
    border: 1px solid #8c8c96;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #00439c;
    border-radius: 5px;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #9e9ea8;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #00439c;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #00439c;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #90caf9;
}

QRadioButton {
    color: #1d1e24;
    spacing: 8px;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #787884;
    background-color: #e2e2ec;
}

QRadioButton::indicator:checked {
    background-color: #00439c;
    border-color: #00439c;
}

QScrollBar:vertical {
    border: none;
    background: #b5b5be;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #8e8e98;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #6e6e78;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QStatusBar {
    background-color: #b5b5be;
    color: #383944;
    border-top: 1px solid #9a9aa4;
}
"""

CURRENT_THEME = "dark"


def set_theme(theme_name: str) -> None:
    """Установить тему ('dark' или 'ps1')."""
    global CURRENT_THEME
    app = QApplication.instance()
    if not app:
        return

    CURRENT_THEME = theme_name
    if theme_name == "ps1":
        app.setStyleSheet(PS1_CLASSIC_STYLESHEET)
    else:
        app.setStyleSheet(DARK_STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))