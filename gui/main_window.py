"""Главное окно приложения UMD Studio."""

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
)

from gui.cso_converter import CSOConverterWidget
from gui.iso_editor import ISOEditorWidget
from gui.patcher import PatcherWidget
from gui.ps1_builder import PS1BuilderWidget
from gui.sfo_editor import SFODialog
from gui.theme import set_theme


class MainWindow(QMainWindow):
    """Основное окно UMD Studio с чистой модульной системой вкладок."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("UMD Studio v0.1")
        self.resize(1140, 750)

        self._setup_ui()

    def _setup_ui(self) -> None:
        menubar = self.menuBar()

        # 1. Меню Файл
        menu_file = menubar.addMenu("&Файл")
        action_exit = menu_file.addAction("Выход")
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)

        # 2. Меню Вид (Переключение тем оформления)
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

        # 3. Меню Инструменты (Редактор SFO вынесен сюда)
        menu_tools = menubar.addMenu("&Инструменты")
        action_sfo = menu_tools.addAction("Редактор PARAM.SFO...")
        action_sfo.triggered.connect(self._open_sfo_tool)

        # 4. Меню Помощь
        menu_help = menubar.addMenu("&Помощь")
        action_about = menu_help.addAction("О программе")
        action_about.triggered.connect(self._show_about)

        # Главные рабочие вкладки (UMD Editor теперь встречает пользователя первым!)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.umd_editor = ISOEditorWidget()
        self.tabs.addTab(self.umd_editor, "UMD Editor")

        self.umd_convertor = CSOConverterWidget()
        self.tabs.addTab(self.umd_convertor, "UMD Convertor")

        self.umd_patcher = PatcherWidget()
        self.tabs.addTab(self.umd_patcher, "UMD Patcher")

        self.ps1_builder = PS1BuilderWidget()
        self.tabs.addTab(self.ps1_builder, "PS1 Builder")

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готов к работе")

    def _open_sfo_tool(self) -> None:
        """Открытие редактора PARAM.SFO в отдельном диалоговом окне."""
        dlg = SFODialog(self)
        dlg.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "О программе UMD Studio",
            "<b>UMD Studio v0.2.0-dev</b><br><br>"
            "Универсальный инструмент для работы с образами дисков, ресурсами и данными PlayStation Portable.<br>"
            "Разработано на Python и PySide6.",
        )