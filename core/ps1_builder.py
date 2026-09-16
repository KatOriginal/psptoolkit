"""Движок сборки образов PS1 (BIN/CUE) в формат EBOOT.PBP для PSP POPS."""

from __future__ import annotations

import os
from pathlib import Path
import struct
from typing import Callable, Optional, Union
import zlib

from core.exceptions import BinaryFormatError
from formats.cue import CUESheet, PS1DiscScanner
from formats.pbp import PBPSource, PBPWriter
from formats.sfo import SFO

PSISOIMG_MAGIC = b"PSISOIMG0000"
PSISOIMG_HEADER_SIZE = 0x100000  # 1 MB заголовок
PS1_BLOCK_SIZE = 37632  # 16 секторов * 2352 байта (0x9300)
TOC_ENTRIES_OFFSET = 0x800
BLOCK_TABLE_OFFSET = 0x4000
BLOCK_ENTRY_SIZE = 32


class PSISOIMGBuilder:
    """Генератор контейнера PSISOIMG внутри DATA.PSAR."""

    @staticmethod
    def build_psar(
        bin_path: Union[str, Path],
        output_psar_path: Union[str, Path],
        cue_sheet: Optional[CUESheet] = None,
        compression_level: int = 9,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Потоковая упаковка BIN-образа в блок DATA.PSAR со структурой PSISOIMG."""
        bin_file = Path(bin_path)
        psar_file = Path(output_psar_path)

        if not bin_file.exists():
            raise FileNotFoundError(f"Файл диска не найден: {bin_file}")

        total_bin_size = bin_file.stat().st_size
        num_blocks = (total_bin_size + PS1_BLOCK_SIZE - 1) // PS1_BLOCK_SIZE

        psar_file.parent.mkdir(parents=True, exist_ok=True)

        # 1. Формируем 1-мегабайтный заголовок PSISOIMG0000
        header_buf = bytearray(PSISOIMG_HEADER_SIZE)
        header_buf[0:12] = PSISOIMG_MAGIC

        # Смещение данных ISO: 0x100000
        struct.pack_into("<I", header_buf, 0xBFC, PSISOIMG_HEADER_SIZE)

        # Заполнение TOC (Table of Contents)
        total_sectors = total_bin_size // 2352
        leadout_m = total_sectors // (60 * 75)
        rem = total_sectors % (60 * 75)
        leadout_s = rem // 75
        leadout_f = rem % 75

        # Point 0xA0 (первый трек: 1)
        header_buf[TOC_ENTRIES_OFFSET + 0 : TOC_ENTRIES_OFFSET + 10] = bytes(
            [0x41, 0x00, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00]
        )
        # Point 0xA1 (последний трек: 1)
        header_buf[TOC_ENTRIES_OFFSET + 10 : TOC_ENTRIES_OFFSET + 20] = bytes(
            [0x41, 0x00, 0xA1, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00]
        )
        # Point 0xA2 (Lead-out адрес)
        header_buf[TOC_ENTRIES_OFFSET + 20 : TOC_ENTRIES_OFFSET + 30] = bytes(
            [0x41, 0x00, 0xA2, 0x00, 0x00, 0x00, 0x00, leadout_m, leadout_s, leadout_f]
        )
        # Трек 1 (Данные Mode 2)
        header_buf[TOC_ENTRIES_OFFSET + 30 : TOC_ENTRIES_OFFSET + 40] = bytes(
            [0x41, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00]
        )

        with open(bin_file, "rb") as in_fp, open(psar_file, "wb") as out_fp:
            # Записываем заготовку заголовка
            out_fp.write(header_buf)

            block_entries: list[bytes] = []
            curr_data_offset = 0

            # 2. Потоковое сжатие блоков по 37 632 байта
            for block_idx in range(num_blocks):
                if cancel_check and cancel_check():
                    out_fp.close()
                    psar_file.unlink(missing_ok=True)
                    return

                raw_chunk = in_fp.read(PS1_BLOCK_SIZE)
                if not raw_chunk:
                    break

                if compression_level > 0:
                    compressed = zlib.compress(raw_chunk, compression_level)
                    if len(compressed) < len(raw_chunk):
                        to_write = compressed
                        size = len(compressed)
                        flag = 0  # сжатый
                    else:
                        to_write = raw_chunk
                        size = len(raw_chunk)
                        flag = 1  # несжатый
                else:
                    to_write = raw_chunk
                    size = len(raw_chunk)
                    flag = 1

                # 32-байтовая запись таблицы блоков: offset (u32), size (u16), flag (u16), padding (24 bytes)
                entry = struct.pack("<IHH24x", curr_data_offset, size, flag)
                block_entries.append(entry)

                out_fp.write(to_write)
                curr_data_offset += len(to_write)

                if progress_callback and (block_idx % 100 == 0 or block_idx == num_blocks - 1):
                    progress_callback(block_idx + 1, num_blocks)

            # 3. Записываем готовую таблицу блоков в заголовок
            out_fp.seek(BLOCK_TABLE_OFFSET)
            for entry in block_entries:
                out_fp.write(entry)


class PS1EBOOTBuilder:
    """Сборщик итогового EBOOT.PBP для запуска PS1 на PSP."""

    @staticmethod
    def build_eboot(
        bin_path: Union[str, Path],
        output_pbp_path: Union[str, Path],
        title: str,
        game_id: str,
        data_psp: bytes = b"",
        icon0_png: bytes = b"",
        pic1_png: bytes = b"",
        compression_level: int = 9,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Полный цикл создания EBOOT.PBP."""
        pbp_file = Path(output_pbp_path)
        temp_psar_file = pbp_file.with_suffix(".psar.tmp")

        # 1. Генерируем PARAM.SFO для PS1
        clean_id = game_id.replace("-", "").replace("_", "")
        sfo = SFO()
        sfo.set_string("TITLE", title, max_length=128)
        sfo.set_string("DISC_ID", clean_id, max_length=16)
        sfo.set_string("CATEGORY", "ME", max_length=4)
        sfo.set_string("PSP_SYSTEM_VER", "3.00", max_length=8)
        sfo.set_string("DISC_VERSION", "1.00", max_length=8)
        sfo.set_int("BOOTABLE", 1)
        sfo.set_int("PARENTAL_LEVEL", 5)
        raw_sfo = sfo.to_bytes()

        # 2. Создаем DATA.PSAR (PSISOIMG)
        try:
            PSISOIMGBuilder.build_psar(
                bin_path=bin_path,
                output_psar_path=temp_psar_file,
                compression_level=compression_level,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )

            if cancel_check and cancel_check():
                temp_psar_file.unlink(missing_ok=True)
                return

            # Читаем собранный PSAR потоково и пакуем в PBP
            with open(temp_psar_file, "rb") as psar_fp:
                psar_data = psar_fp.read()

            source = PBPSource(
                param_sfo=raw_sfo,
                icon0_png=icon0_png,
                pic1_png=pic1_png,
                data_psp=data_psp,
                data_psar=psar_data,
            )

            PBPWriter.write_pbp(pbp_file, source)
        finally:
            temp_psar_file.unlink(missing_ok=True)