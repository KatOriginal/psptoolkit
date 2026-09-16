"""Главная точка входа для запуска приложения UMD Studio."""

from pathlib import Path
import sys

# Гарантируем корректный импорт модулей приложения
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402
from gui.main_window import MainWindow  # noqa: E402
from gui.theme import set_theme  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("UMD Studio")
    app.setOrganizationName("UMDStudio")

    # По умолчанию тёмная тема
    set_theme("dark")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())