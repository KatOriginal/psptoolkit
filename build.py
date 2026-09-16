"""Скрипт компиляции UMD Studio в автономный исполняемый файл UMDStudio.exe."""

from pathlib import Path
import subprocess
import sys


def build_executable() -> None:
    print("=" * 60)
    print("Запуск сборки UMD Studio в автономный .exe")
    print("=" * 60)

    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller не установлен. Выполняется установка...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    import PyInstaller.__main__

    project_root = Path(__file__).resolve().parent
    main_script = project_root / "main.py"

    params = [
        str(main_script),
        "--name=UMDStudio",       # Название итогового бинарника
        "--onefile",              # Собрать в единый exe файл
        "--windowed",             # Без черного окна консоли
        "--clean",                # Очистить кэш
        f"--paths={project_root}",
        "--hidden-import=core",
        "--hidden-import=core.ps1_builder",
        "--hidden-import=core.iso_rebuilder",
        "--hidden-import=formats",
        "--hidden-import=formats.sfo",
        "--hidden-import=formats.iso",
        "--hidden-import=formats.cso",
        "--hidden-import=formats.pbp",
        "--hidden-import=formats.cue",
        "--hidden-import=gui",
        "--hidden-import=gui.widgets",
        "--noconfirm",
    ]

    print(f"[*] Сборка из: {main_script}")
    PyInstaller.__main__.run(params)

    exe_path = project_root / "dist" / "UMDStudio.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 60)
        print("[+] СБОРКА УСПЕШНО ЗАВЕРШЕНА!")
        print(f"[+] Итоговый файл: {exe_path}")
        print(f"[+] Размер: {size_mb:.1f} МБ")
        print("=" * 60)
    else:
        print("\n[-] Ошибка: файл exe не был найден в dist/")


if __name__ == "__main__":
    build_executable()