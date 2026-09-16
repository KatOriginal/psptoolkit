"""Установщик модификаций и фанатских переводов из ZIP, 7Z, RAR и папок."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable, Optional, Union
import zipfile

from core.exceptions import PatchFormatError
from core.iso_rebuilder import ISORebuilder
from formats.iso import ISOFile, ISOReader
from formats.xdelta import XDeltaPatcher


def _find_7zip() -> Optional[str]:
    candidates = [
        shutil.which("7z"),
        shutil.which("7za"),
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None


def _extract_archive(archive_path: Path, dest_dir: Path) -> None:
    ext = archive_path.suffix.lower()

    if ext == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
        return

    seven_zip = _find_7zip()
    if seven_zip:
        cmd = [seven_zip, "x", str(archive_path), f"-o{dest_dir}", "-y"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            return

    if ext == ".7z":
        try:
            import py7zr

            with py7zr.SevenZipFile(archive_path, mode="r") as z:
                z.extractall(path=dest_dir)
            return
        except ImportError:
            pass

    raise PatchFormatError(
        f"Не удалось распаковать архив '{archive_path.name}'.\n"
        f"Пожалуйста, распакуйте архив в папку и используйте кнопку 'Выбрать папку...'."
    )


class ModPatcher:
    """Интеллектуальный установщик переводов (например, Persona 3 Portable от Котонэ)."""

    @staticmethod
    def inspect_mod(mod_path: Union[str, Path]) -> list[str]:
        p = Path(mod_path)
        if not p.exists():
            raise FileNotFoundError(f"Источник мода не найден: {p}")

        found_files: list[str] = []
        if p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    found_files.append(f.relative_to(p).as_posix())
        elif p.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(p, "r") as zf:
                    for name in zf.namelist():
                        if not name.endswith("/"):
                            found_files.append(name)
            except Exception:
                pass
        else:
            found_files.append(f"Архив {p.suffix.upper()} (будет автоматически распакован)")

        return found_files

    @staticmethod
    def apply_mod_package(
        source_iso: Union[str, Path],
        mod_source: Union[str, Path],
        output_iso: Union[str, Path],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> int:
        iso_file = Path(source_iso)
        mod_p = Path(mod_source)
        out_file = Path(output_iso)

        temp_dir: Optional[Path] = None

        try:
            if mod_p.is_file():
                temp_dir = Path(tempfile.mkdtemp(prefix="umd_mod_"))
                _extract_archive(mod_p, temp_dir)
                working_folder = temp_dir
            elif mod_p.is_dir():
                working_folder = mod_p
            else:
                raise PatchFormatError(f"Источник мода должен быть папкой или архивом: {mod_p}")

            mod_files: dict[str, Path] = {}
            xdelta_patches: list[Path] = []

            for item in working_folder.rglob("*"):
                if item.is_file():
                    if item.suffix.lower() == ".xdelta":
                        xdelta_patches.append(item)
                    rel_path = item.relative_to(working_folder).as_posix()
                    mod_files[rel_path.lower()] = item

            replaced_count = 0
            with ISOReader(iso_file) as reader:
                iso_files: list[ISOFile] = []

                def _collect_files(node) -> None:
                    for ch in node.children:
                        if isinstance(ch, ISOFile):
                            iso_files.append(ch)
                        else:
                            _collect_files(ch)

                if reader.root:
                    _collect_files(reader.root)

                # 1. Прямое сопоставление файлов (data.cpk, видео и т.д.)
                for f in iso_files:
                    f_path_clean = f.path.strip("/").lower()
                    f_name = f.name.lower()
                    match_path: Optional[Path] = None

                    if f_path_clean in mod_files:
                        match_path = mod_files[f_path_clean]
                    elif f_path_clean.startswith("psp_game/") and f_path_clean[9:] in mod_files:
                        match_path = mod_files[f_path_clean[9:]]
                    else:
                        for m_rel, m_abs in mod_files.items():
                            if Path(m_rel).name.lower() == f_name:
                                match_path = m_abs
                                break

                    if match_path and not match_path.suffix.lower() == ".xdelta":
                        f.replacement_path = match_path
                        replaced_count += 1

                # 2. Интеллектуальная обработка xdelta-патчей (пробуем и BOOT.BIN, и EBOOT.BIN)
                for xd_patch in xdelta_patches:
                    candidates_to_try = [
                        reader.find_entry("PSP_GAME/SYSDIR/BOOT.BIN"),
                        reader.find_entry("PSP_GAME/SYSDIR/EBOOT.BIN"),
                    ]
                    eboot_entry = reader.find_entry("PSP_GAME/SYSDIR/EBOOT.BIN")

                    for target_entry in candidates_to_try:
                        if isinstance(target_entry, ISOFile):
                            temp_orig = working_folder / f"_orig_{target_entry.name}"
                            temp_patched = working_folder / f"_patched_{target_entry.name}"
                            reader.extract_file(target_entry, temp_orig)

                            try:
                                XDeltaPatcher.apply_file_patch(
                                    source_file=temp_orig,
                                    patch_file=xd_patch,
                                    output_file=temp_patched,
                                )
                                target_entry.replacement_path = temp_patched
                                if target_entry.name == "BOOT.BIN" and isinstance(eboot_entry, ISOFile):
                                    eboot_entry.replacement_path = temp_patched
                                replaced_count += 1
                                break
                            except Exception:
                                continue

                if replaced_count == 0:
                    raise PatchFormatError(
                        "Ни один файл из мода не подошел к содержимому этого ISO-образа.\n\n"
                        "Подсказка: если в моде лежат текстуры для PPSSPP (Aemulus),\n"
                        "их нужно копировать в папку эмулятора PSP/TEXTURES/."
                    )

                ISORebuilder.rebuild(
                    reader=reader,
                    output_iso_path=out_file,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )

            return replaced_count

        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)