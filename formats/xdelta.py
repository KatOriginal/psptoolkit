"""Потоковый упаковщик и применитель патчей XDelta3 (VCDIFF) для PSP ISO."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable, Optional, Union
import urllib.request
import zipfile

from core.exceptions import PatchFormatError
from core.iso_rebuilder import ISORebuilder
from formats.iso import ISOFile, ISOReader
from formats.sfo import SFO

XDELTA_OFFICIAL_URL = "https://github.com/jmacd/xdelta-gpl/releases/download/v3.0.11/xdelta3-3.0.11-x86_64.exe.zip"


class XDeltaPatcher:
    """Утилита применения патчей XDelta к образам ISO и отдельным файлам."""

    @staticmethod
    def find_xdelta_binary() -> Optional[Path]:
        project_root = Path(__file__).resolve().parent.parent
        candidates = [
            project_root / "tools" / "xdelta3.exe",
            project_root / "xdelta3.exe",
            Path(r"C:\Program Files\7-Zip\xdelta3.exe"),
        ]

        which_path = shutil.which("xdelta3") or shutil.which("xdelta")
        if which_path:
            candidates.insert(0, Path(which_path))

        for c in candidates:
            if c and c.exists():
                return c
        return None

    @staticmethod
    def download_xdelta_binary(dest_folder: Optional[Path] = None) -> Path:
        project_root = Path(__file__).resolve().parent.parent
        target_dir = dest_folder or (project_root / "tools")
        target_dir.mkdir(parents=True, exist_ok=True)
        final_exe = target_dir / "xdelta3.exe"

        if final_exe.exists():
            return final_exe

        temp_zip = target_dir / "xdelta_download.zip"
        try:
            urllib.request.urlretrieve(XDELTA_OFFICIAL_URL, temp_zip)
            with zipfile.ZipFile(temp_zip, "r") as zf:
                for member in zf.namelist():
                    if member.lower().endswith(".exe"):
                        with zf.open(member) as src, open(final_exe, "wb") as dst:
                            dst.write(src.read())
                        break
            if not final_exe.exists():
                raise PatchFormatError("Не удалось извлечь xdelta3.exe из архива")
            return final_exe
        finally:
            if temp_zip.exists():
                temp_zip.unlink(missing_ok=True)

    @staticmethod
    def apply_file_patch(
        source_file: Path,
        patch_file: Path,
        output_file: Path,
        xdelta_exe: Optional[Path] = None,
        force_checksum: bool = False,
    ) -> None:
        """Применение xdelta3 к файлу с поддержкой обхода контрольной суммы (-n)."""
        exe = xdelta_exe or XDeltaPatcher.find_xdelta_binary()
        if not exe or not exe.exists():
            exe = XDeltaPatcher.download_xdelta_binary()

        output_file.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(exe),
            "-d",  # decode
            "-f",  # force overwrite
        ]
        if force_checksum:
            cmd.append("-n")  # Отключение проверки контрольной суммы

        cmd.extend([
            "-s", str(source_file),
            str(patch_file),
            str(output_file),
        ])

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            err = res.stderr or res.stdout
            # Если упало из-за несовпадения суммы и мы еще не пробовали -n: пробуем автоматически!
            if not force_checksum and "checksum mismatch" in err.lower():
                return XDeltaPatcher.apply_file_patch(
                    source_file=source_file,
                    patch_file=patch_file,
                    output_file=output_file,
                    xdelta_exe=exe,
                    force_checksum=True,
                )
            raise PatchFormatError(f"Ошибка xdelta3:\n{err}")

    @staticmethod
    def apply_to_iso(
        source_iso: Union[str, Path],
        patch_path: Union[str, Path],
        output_iso: Union[str, Path],
        force_checksum: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Интеллектуальное применение xdelta к ISO образу."""
        src_iso = Path(source_iso)
        patch = Path(patch_path)
        out_iso = Path(output_iso)

        if not src_iso.exists():
            raise FileNotFoundError(f"Файл ISO не найден: {src_iso}")
        if not patch.exists():
            raise FileNotFoundError(f"Файл патча не найден: {patch}")

        xdelta_exe = XDeltaPatcher.find_xdelta_binary()
        if not xdelta_exe:
            if progress_callback:
                progress_callback(0, 100, "Загрузка xdelta3.exe с GitHub...")
            xdelta_exe = XDeltaPatcher.download_xdelta_binary()

        patch_size = patch.stat().st_size

        # Если патч весит больше 30 МБ (как наш на 425 МБ) — это 100% патч НА ВЕСЬ ОБРАЗ ISO!
        if patch_size > 30 * 1024 * 1024:
            if progress_callback:
                progress_callback(15, 100, "Применение патча к образу ISO (может занять 20-30 сек)...")
            XDeltaPatcher.apply_file_patch(
                source_file=src_iso,
                patch_file=patch,
                output_file=out_iso,
                xdelta_exe=xdelta_exe,
                force_checksum=force_checksum,
            )
            return

        # Для небольших патчей проверяем внутренние файлы
        temp_dir = Path(tempfile.mkdtemp(prefix="umd_xdelta_"))
        try:
            with ISOReader(src_iso) as reader:
                candidates: list[tuple[str, ISOFile]] = []
                boot_entry = reader.find_entry("PSP_GAME/SYSDIR/BOOT.BIN")
                if isinstance(boot_entry, ISOFile):
                    candidates.append(("BOOT.BIN", boot_entry))

                eboot_entry = reader.find_entry("PSP_GAME/SYSDIR/EBOOT.BIN")
                if isinstance(eboot_entry, ISOFile):
                    candidates.append(("EBOOT.BIN", eboot_entry))

                for name, entry in candidates:
                    if progress_callback:
                        progress_callback(20, 100, f"Проверка соответствия с {name}...")

                    temp_src = temp_dir / f"orig_{name}"
                    temp_dst = temp_dir / f"patched_{name}"
                    reader.extract_file(entry, temp_src)

                    try:
                        XDeltaPatcher.apply_file_patch(
                            source_file=temp_src,
                            patch_file=patch,
                            output_file=temp_dst,
                            xdelta_exe=xdelta_exe,
                            force_checksum=force_checksum,
                        )
                        entry.replacement_path = temp_dst
                        if name == "BOOT.BIN" and isinstance(eboot_entry, ISOFile):
                            eboot_entry.replacement_path = temp_dst

                        ISORebuilder.rebuild(reader, out_iso, progress_callback, cancel_check)
                        return
                    except PatchFormatError:
                        continue

            # Фоллбэк на целый образ
            if progress_callback:
                progress_callback(30, 100, "Применение патча ко всему образу ISO...")
            XDeltaPatcher.apply_file_patch(
                source_file=src_iso,
                patch_file=patch,
                output_file=out_iso,
                xdelta_exe=xdelta_exe,
                force_checksum=force_checksum,
            )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)