"""Потоковый компрессор и декомпрессор формата CSO (CISO v1) для PSP."""

from __future__ import annotations

import array
from dataclasses import dataclass
from pathlib import Path
import struct
from typing import BinaryIO, Callable, Optional, Union
import zlib

from core.exceptions import CSOFormatError

CSO_MAGIC = b"CISO"
CSO_HEADER_SIZE = 24
DEFAULT_BLOCK_SIZE = 2048


@dataclass
class CSOHeader:
    """Заголовок CISO (24 байта)."""

    magic: bytes
    header_size: int
    total_bytes: int
    block_size: int
    version: int
    align: int

    @classmethod
    def unpack(cls, raw: bytes) -> CSOHeader:
        if len(raw) < CSO_HEADER_SIZE:
            raise CSOFormatError(f"Заголовок CSO повреждён: получено {len(raw)} байт, ожидалось 24")
        magic, header_size, total_bytes, block_size, ver, align = struct.unpack_from(
            "<4sIQIBB", raw, 0
        )
        if magic != CSO_MAGIC:
            raise CSOFormatError(f"Неверная сигнатура CSO: ожидалось {CSO_MAGIC!r}, получено {magic!r}")
        if block_size != DEFAULT_BLOCK_SIZE:
            raise CSOFormatError(f"Неподдерживаемый размер блока CSO: {block_size} (поддерживается только 2048)")
        return cls(
            magic=magic,
            header_size=header_size,
            total_bytes=total_bytes,
            block_size=block_size,
            version=ver,
            align=align,
        )

    def pack(self) -> bytes:
        return struct.pack(
            "<4sIQIBBH",
            self.magic,
            self.header_size,
            self.total_bytes,
            self.block_size,
            self.version,
            self.align,
            0,  # reserved
        )


class CSOConverter:
    """Утилита потоковой конвертации ISO -> CSO и CSO -> ISO."""

    @staticmethod
    def compress_iso_to_cso(
        iso_path: Union[str, Path],
        cso_path: Union[str, Path],
        compression_level: int = 9,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Потоковое сжатие ISO в CSO (raw deflate, wbits=-15)."""
        iso_file = Path(iso_path)
        cso_file = Path(cso_path)

        if not iso_file.exists():
            raise FileNotFoundError(f"Файл ISO не найден: {iso_file}")

        total_bytes = iso_file.stat().st_size
        block_size = DEFAULT_BLOCK_SIZE
        num_blocks = (total_bytes + block_size - 1) // block_size

        # Для образов > 2 ГБ используем выравнивание align = 2, иначе стандартный align = 0
        align = 2 if total_bytes >= 0x7FFFFFFF else 0
        align_step = 1 << align

        header = CSOHeader(
            magic=CSO_MAGIC,
            header_size=CSO_HEADER_SIZE,
            total_bytes=total_bytes,
            block_size=block_size,
            version=1,
            align=align,
        )

        index_entries_count = num_blocks + 1
        index_table = array.array("I", [0] * index_entries_count)

        cso_file.parent.mkdir(parents=True, exist_ok=True)

        with open(iso_file, "rb") as in_fp, open(cso_file, "wb") as out_fp:
            # 1. Записываем временный заголовок и пустышку под таблицу индексов
            out_fp.write(header.pack())
            index_table.tofile(out_fp)

            current_out_offset = out_fp.tell()

            # Выравнивание начала первого блока
            if align > 0:
                pad = (align_step - (current_out_offset % align_step)) % align_step
                if pad > 0:
                    out_fp.write(b"\x00" * pad)
                    current_out_offset += pad

            # 2. Потоковое сжатие секторов
            for block_idx in range(num_blocks):
                if cancel_check and cancel_check():
                    out_fp.close()
                    cso_file.unlink(missing_ok=True)
                    return

                raw_block = in_fp.read(block_size)
                if not raw_block:
                    break

                # Сырой DEFLATE (wbits = -15) без zlib-обёртки
                compressor = zlib.compressobj(
                    level=compression_level,
                    method=zlib.DEFLATED,
                    wbits=-15,
                )
                compressed = compressor.compress(raw_block) + compressor.flush()

                # Если сжатый блок меньше оригинала — сохраняем сжатый
                if len(compressed) < len(raw_block):
                    data_to_write = compressed
                    index_val = current_out_offset >> align
                else:
                    # Иначе сохраняем как есть с выставленным битом 31 (несжатый блок)
                    data_to_write = raw_block
                    index_val = (current_out_offset >> align) | 0x80000000

                index_table[block_idx] = index_val
                out_fp.write(data_to_write)
                current_out_offset += len(data_to_write)

                # Выравнивание следующего блока
                if align > 0:
                    pad = (align_step - (current_out_offset % align_step)) % align_step
                    if pad > 0:
                        out_fp.write(b"\x00" * pad)
                        current_out_offset += pad

                # Дросселируем прогресс для плавности GUI
                if progress_callback and (block_idx % 500 == 0 or block_idx == num_blocks - 1):
                    progress_callback(block_idx + 1, num_blocks)

            # Последний индекс указывает на конечный размер файла
            index_table[num_blocks] = current_out_offset >> align

            # 3. Перезаписываем готовую таблицу индексов в начало файла
            out_fp.seek(CSO_HEADER_SIZE)
            index_table.tofile(out_fp)

    @staticmethod
    def decompress_cso_to_iso(
        cso_path: Union[str, Path],
        iso_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Потоковая распаковка CSO обратно в полноценный ISO."""
        cso_file = Path(cso_path)
        iso_file = Path(iso_path)

        if not cso_file.exists():
            raise FileNotFoundError(f"Файл CSO не найден: {cso_file}")

        with open(cso_file, "rb") as in_fp:
            raw_header = in_fp.read(CSO_HEADER_SIZE)
            header = CSOHeader.unpack(raw_header)

            num_blocks = (header.total_bytes + header.block_size - 1) // header.block_size
            align = header.align

            # Чтение таблицы индексов
            index_bytes = in_fp.read((num_blocks + 1) * 4)
            if len(index_bytes) < (num_blocks + 1) * 4:
                raise CSOFormatError("Таблица индексов CSO повреждена или обрезана")

            index_table = array.array("I")
            index_table.frombytes(index_bytes)

            iso_file.parent.mkdir(parents=True, exist_ok=True)

            with open(iso_file, "wb") as out_fp:
                written_total = 0

                for block_idx in range(num_blocks):
                    if cancel_check and cancel_check():
                        out_fp.close()
                        iso_file.unlink(missing_ok=True)
                        return

                    curr_idx = index_table[block_idx]
                    next_idx = index_table[block_idx + 1]

                    is_uncompressed = bool(curr_idx & 0x80000000)
                    offset_curr = (curr_idx & 0x7FFFFFFF) << align
                    offset_next = (next_idx & 0x7FFFFFFF) << align
                    block_len = offset_next - offset_curr

                    expected_uncompressed_len = min(header.block_size, header.total_bytes - written_total)

                    in_fp.seek(offset_curr)
                    block_data = in_fp.read(block_len)

                    if is_uncompressed:
                        uncompressed_data = block_data[:expected_uncompressed_len]
                    else:
                        try:
                            # Распаковка сырого DEFLATE (wbits = -15)
                            uncompressed_data = zlib.decompress(block_data, -15)
                            if len(uncompressed_data) > expected_uncompressed_len:
                                uncompressed_data = uncompressed_data[:expected_uncompressed_len]
                        except zlib.error as exc:
                            raise CSOFormatError(f"Ошибка распаковки блока {block_idx}: {exc}") from exc

                    out_fp.write(uncompressed_data)
                    written_total += len(uncompressed_data)

                    if progress_callback and (block_idx % 500 == 0 or block_idx == num_blocks - 1):
                        progress_callback(block_idx + 1, num_blocks)