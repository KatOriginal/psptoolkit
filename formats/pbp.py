"""Универсальный ридер и сборщик контейнера Sony PBP (EBOOT.PBP)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import struct
from typing import BinaryIO, Callable, Optional, Union

from core.exceptions import PBPFormatError

PBP_MAGIC = b"\x00PBP"
PBP_HEADER_SIZE = 40
PBP_VERSION = 0x00010000

# 8 стандартных секций контейнера PBP в строгом порядке спецификации
PBP_ENTRIES = (
    "param_sfo",
    "icon0_png",
    "icon1_pmf",
    "pic0_png",
    "pic1_png",
    "snd0_at3",
    "data_psp",
    "data_psar",
)


@dataclass
class PBPSource:
    """Представление данных для сборки контейнера PBP."""

    param_sfo: bytes = b""
    icon0_png: bytes = b""
    icon1_pmf: bytes = b""
    pic0_png: bytes = b""
    pic1_png: bytes = b""
    snd0_at3: bytes = b""
    data_psp: bytes = b""
    data_psar: bytes = b""


class PBPReader:
    """Парсер и распаковщик контейнера PBP."""

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.path = Path(file_path)
        self.offsets: list[int] = []
        self.sizes: dict[str, int] = {}
        self.total_size: int = 0

    def read_header(self) -> dict[str, int]:
        """Чтение заголовка PBP и смещений секций."""
        if not self.path.exists():
            raise FileNotFoundError(f"Файл PBP не найден: {self.path}")

        self.total_size = self.path.stat().st_size
        if self.total_size < PBP_HEADER_SIZE:
            raise PBPFormatError(f"Файл слишком мал для PBP: {self.total_size} байт")

        with open(self.path, "rb") as fp:
            header_data = fp.read(PBP_HEADER_SIZE)

        magic, version = struct.unpack_from("<4sI", header_data, 0)
        if magic != PBP_MAGIC:
            raise PBPFormatError(f"Неверная сигнатура PBP: ожидалось {PBP_MAGIC!r}, получено {magic!r}")

        raw_offsets = struct.unpack_from("<8I", header_data, 8)
        self.offsets = list(raw_offsets)

        # Вычисляем размеры каждой из 8 секций
        self.sizes = {}
        for i, name in enumerate(PBP_ENTRIES):
            start = self.offsets[i]
            end = self.offsets[i + 1] if i < 7 else self.total_size
            self.sizes[name] = max(0, end - start)

        return self.sizes

    def read_section(self, section_name: str) -> bytes:
        """Потоковое чтение конкретной секции из PBP."""
        if not self.sizes:
            self.read_header()

        if section_name not in PBP_ENTRIES:
            raise KeyError(f"Неизвестная секция PBP: {section_name}")

        idx = PBP_ENTRIES.index(section_name)
        offset = self.offsets[idx]
        size = self.sizes[section_name]

        if size == 0:
            return b""

        with open(self.path, "rb") as fp:
            fp.seek(offset)
            return fp.read(size)

    def unpack_all(self, dest_folder: Union[str, Path]) -> None:
        """Распаковка всех существующих секций PBP в папку."""
        dest = Path(dest_folder)
        dest.mkdir(parents=True, exist_ok=True)

        if not self.sizes:
            self.read_header()

        with open(self.path, "rb") as fp:
            for i, name in enumerate(PBP_ENTRIES):
                size = self.sizes[name]
                if size == 0:
                    continue

                out_filename = name.upper().replace("_", ".")
                out_path = dest / out_filename
                fp.seek(self.offsets[i])

                # Читаем чанками
                with open(out_path, "wb") as out_fp:
                    remaining = size
                    while remaining > 0:
                        chunk = fp.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        out_fp.write(chunk)
                        remaining -= len(chunk)


class PBPWriter:
    """Сборщик контейнера PBP."""

    @staticmethod
    def write_pbp(
        output_path: Union[str, Path],
        source: PBPSource,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Сборка нового файла PBP из байтов секций."""
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        sections = [
            source.param_sfo,
            source.icon0_png,
            source.icon1_pmf,
            source.pic0_png,
            source.pic1_png,
            source.snd0_at3,
            source.data_psp,
            source.data_psar,
        ]

        # Расчёт смещений секций
        offsets: list[int] = []
        curr_offset = PBP_HEADER_SIZE

        for sec in sections:
            offsets.append(curr_offset)
            curr_offset += len(sec)

        # Упаковка заголовка (40 байт)
        header = struct.pack(
            "<4sI8I",
            PBP_MAGIC,
            PBP_VERSION,
            *offsets,
        )

        total_bytes = curr_offset
        written_bytes = 0

        with open(dest, "wb") as fp:
            fp.write(header)
            written_bytes += len(header)

            for sec in sections:
                if sec:
                    fp.write(sec)
                    written_bytes += len(sec)
                if progress_callback:
                    progress_callback(written_bytes, total_bytes)