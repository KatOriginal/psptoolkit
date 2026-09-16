"""Потоковый парсер и применитель патчей PPF (PlayStation Patch Format v1/v2/v3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import BinaryIO, Callable, Optional, Union

from core.exceptions import PatchFormatError

PPF_MAGIC_1 = b"PPF10"
PPF_MAGIC_2 = b"PPF20"
PPF_MAGIC_3 = b"PPF30"


@dataclass
class PPFInfo:
    """Метаданные патча PPF."""

    version: int  # 1, 2 или 3
    description: str
    has_blockcheck: bool
    has_undo: bool


class PPFPatcher:
    """Утилита потокового применения патчей PPF к образам ISO."""

    @staticmethod
    def read_info(ppf_path: Union[str, Path]) -> PPFInfo:
        """Чтение заголовка и описания из файла PPF."""
        path = Path(ppf_path)
        if not path.exists():
            raise FileNotFoundError(f"Файл патча не найден: {path}")

        with open(path, "rb") as fp:
            magic = fp.read(5)
            if magic == PPF_MAGIC_3:
                # PPF 3.0: 60 байт заголовок
                fp.seek(0)
                hdr = fp.read(60)
                if len(hdr) < 60:
                    raise PatchFormatError("Заголовок PPF30 повреждён")
                desc = hdr[6:56].decode("ascii", errors="replace").strip()
                blockcheck = bool(hdr[57])
                undo = bool(hdr[58])
                return PPFInfo(version=3, description=desc, has_blockcheck=blockcheck, has_undo=undo)

            elif magic == PPF_MAGIC_2:
                # PPF 2.0: 5+50+4+4 = 63 байта
                fp.seek(5)
                desc = fp.read(50).decode("ascii", errors="replace").strip()
                return PPFInfo(version=2, description=desc, has_blockcheck=True, has_undo=False)

            elif magic == PPF_MAGIC_1:
                # PPF 1.0: 5+50 = 55 байт
                fp.seek(5)
                desc = fp.read(50).decode("ascii", errors="replace").strip()
                return PPFInfo(version=1, description=desc, has_blockcheck=False, has_undo=False)
            else:
                raise PatchFormatError(f"Неизвестный формат патча: {magic!r}")

    @staticmethod
    def apply_patch(
        source_iso: Union[str, Path],
        ppf_path: Union[str, Path],
        output_iso: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        chunk_size: int = 2 * 1024 * 1024,
    ) -> None:
        """Потоковое создание нового пропатченного ISO без изменения оригинала."""
        src = Path(source_iso)
        ppf = Path(ppf_path)
        out = Path(output_iso)

        if not src.exists():
            raise FileNotFoundError(f"Исходный ISO не найден: {src}")

        info = PPFPatcher.read_info(ppf)
        total_src_size = src.stat().st_size
        out.parent.mkdir(parents=True, exist_ok=True)

        # 1. Потоково копируем исходный ISO в новый файл
        with open(src, "rb") as s_fp, open(out, "wb") as d_fp:
            rem = total_src_size
            while rem > 0:
                if cancel_check and cancel_check():
                    d_fp.close()
                    out.unlink(missing_ok=True)
                    return
                c = s_fp.read(min(chunk_size, rem))
                if not c:
                    break
                d_fp.write(c)
                rem -= len(c)

        # 2. Применяем бинарные куски патча к новому файлу
        with open(ppf, "rb") as p_fp, open(out, "r+b") as target_fp:
            ppf_size = ppf.stat().st_size

            if info.version == 3:
                # Смещение после заголовка (60 байт)
                offset_start = 60
                if info.has_blockcheck:
                    offset_start += 1024  # пропускаем валидационный блок
                p_fp.seek(offset_start)

                while p_fp.tell() < ppf_size:
                    if cancel_check and cancel_check():
                        target_fp.close()
                        out.unlink(missing_ok=True)
                        return

                    header_chunk = p_fp.read(9)  # 8 байт offset + 1 байт length
                    if len(header_chunk) < 9:
                        break

                    target_offset, patch_len = struct.unpack("<QB", header_chunk)
                    data_to_write = p_fp.read(patch_len)
                    if len(data_to_write) < patch_len:
                        break

                    # Если есть undo-данные, пропускаем их
                    if info.has_undo:
                        p_fp.seek(patch_len, 1)

                    target_fp.seek(target_offset)
                    target_fp.write(data_to_write)

                    if progress_callback and (p_fp.tell() % 65536 == 0):
                        progress_callback(p_fp.tell(), ppf_size)

            else:
                # PPF 1.0 / 2.0 (4-байтные смещения)
                offset_start = 55 if info.version == 1 else 63 + (1024 if info.has_blockcheck else 0)
                p_fp.seek(offset_start)

                while p_fp.tell() < ppf_size:
                    if cancel_check and cancel_check():
                        target_fp.close()
                        out.unlink(missing_ok=True)
                        return

                    header_chunk = p_fp.read(5)
                    if len(header_chunk) < 5:
                        break

                    target_offset, patch_len = struct.unpack("<IB", header_chunk)
                    data_to_write = p_fp.read(patch_len)

                    target_fp.seek(target_offset)
                    target_fp.write(data_to_write)

                    if progress_callback and (p_fp.tell() % 65536 == 0):
                        progress_callback(p_fp.tell(), ppf_size)

        if progress_callback:
            progress_callback(1, 1)