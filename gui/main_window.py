"""Главное окно приложения PSP Toolkit с поддержкой переключения тем."""

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
)

from gui.cso_converter import CSOConverterWidget
from gui.iso_editor import ISOEditorWidget
from gui.ps1_builder import PS1BuilderWidget
from gui.sfo_editor import SFOEditorWidget
from gui.theme import set_theme


class MainWindow(QMainWindow):
    """Основное окно PSP Toolkit с модульной системой вкладок."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PSP Toolkit v0.1.0")
        self.resize(1120, 740)

        self._setup_ui()

    def _setup_ui(self) -> None:
        menubar = self.menuBar()

        # Меню Файл
        menu_file = menubar.addMenu("&Файл")
        action_exit = menu_file.addAction("Выход")
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)

        # Меню Вид (Переключение тем)
        menu_view = menubar.addMenu("&Вид")
        menu_theme = menu_view.addMenu("Тема оформления")

        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        action_dark = QAction("PlayStation Dark (Тёмная)", self, checkable=True)
        action_dark.setChecked(True)
        action_dark.triggered.connect(lambda: set_theme("dark"))
        theme_group.addAction(action_dark)
        menu_theme.addAction(action_dark)

        action_ps1 = QAction("PS1 Classic (Серая ретро)", self, checkable=True)
        action_ps1.triggered.connect(lambda: set_theme("ps1"))
        theme_group.addAction(action_ps1)
        menu_theme.addAction(action_ps1)

        # Меню Помощь
        menu_help = menubar.addMenu("&Помощь")
        action_about = menu_help.addAction("О программе")
        action_about.triggered.connect(self._show_about)

        # Система вкладок
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.sfo_editor = SFOEditorWidget()
        self.tabs.addTab(self.sfo_editor, "SFO Editor")

        self.iso_editor = ISOEditorWidget()
        self.tabs.addTab(self.iso_editor, "ISO Editor")

        self.cso_converter = CSOConverterWidget()
        self.tabs.addTab(self.cso_converter, "CSO Converter")

        self.ps1_builder = PS1BuilderWidget()
        self.tabs.addTab(self.ps1_builder, "PS1 Builder")

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готов к работе")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "О программе PSP Toolkit",
            "<b>PSP Toolkit v0.1.0</b><br><br>"
            "Универсальный инструмент для работы с собственными образами и данными PlayStation Portable.<br>"
            "Разработано на Python и PySide6.",
        )