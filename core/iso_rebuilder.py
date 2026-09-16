"""Двухпроходный потоковый сборщик образов ISO 9660 для PSP."""

from __future__ import annotations

from pathlib import Path
import struct
from typing import BinaryIO, Callable, Optional, Union

from formats.iso import (
    ISODirectory,
    ISOFile,
    ISOItem,
    ISOReader,
    SECTOR_SIZE,
)


def _pack_both_endian_32(val: int) -> bytes:
    """Упаковка 32-битного числа в формате Both-Endian (LE + BE)."""
    return struct.pack("<I", val) + struct.pack(">I", val)


def _pack_both_endian_16(val: int) -> bytes:
    """Упаковка 16-битного числа в формате Both-Endian (LE + BE)."""
    return struct.pack("<H", val) + struct.pack(">H", val)


def _build_directory_record(
    name: str,
    lba: int,
    size: int,
    is_dir: bool,
    date_bytes: bytes = b"\x7C\x01\x01\x00\x00\x00\x00",
) -> bytes:
    """Формирование одной бинарной записи Directory Record."""
    if name == ".":
        name_bytes = b"\x00"
    elif name == "..":
        name_bytes = b"\x01"
    else:
        clean_name = name.upper()
        if not is_dir and ";" not in clean_name:
            clean_name += ";1"
        name_bytes = clean_name.encode("latin-1", errors="replace")

    name_len = len(name_bytes)
    rec_len = 33 + name_len
    if rec_len % 2 != 0:
        rec_len += 1

    buf = bytearray(rec_len)
    buf[0] = rec_len
    buf[1] = 0  # Extended attribute length
    buf[2:10] = _pack_both_endian_32(lba)
    buf[10:18] = _pack_both_endian_32(size)
    buf[18:25] = date_bytes
    buf[25] = 2 if is_dir else 0  # Flags
    buf[26] = 0  # Unit size
    buf[27] = 0  # Interleave gap
    buf[28:32] = _pack_both_endian_16(1)  # Volume sequence number
    buf[32] = name_len
    buf[33 : 33 + name_len] = name_bytes
    return bytes(buf)


def _pack_records_to_sectors(records: list[bytes]) -> bytes:
    """Упаковка записей каталога по секторам 2048 байт без пересечения границ."""
    out = bytearray()
    current_sector = bytearray()

    for rec in records:
        if len(current_sector) + len(rec) > SECTOR_SIZE:
            # Заполняем остаток сектора нулями
            current_sector.extend(b"\x00" * (SECTOR_SIZE - len(current_sector)))
            out.extend(current_sector)
            current_sector = bytearray()
        current_sector.extend(rec)

    if current_sector:
        current_sector.extend(b"\x00" * (SECTOR_SIZE - len(current_sector)))
        out.extend(current_sector)

    return bytes(out)


class ISORebuilder:
    """Потоковый пересборщик образов ISO 9660 с сохранением UMD-структуры."""

    @staticmethod
    def rebuild(
        reader: ISOReader,
        output_iso_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        """Пересборка ISO с заменой файлов и пересчётом LBA."""
        out_path = Path(output_iso_path)
        temp_path = out_path.with_suffix(".tmp_iso")

        if not reader.root or not reader._fp:
            raise ValueError("ISOReader должен быть открыт")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Собираем список всех каталогов и файлов
        all_dirs: list[tuple[ISODirectory, Optional[ISODirectory]]] = []
        all_files: list[ISOFile] = []

        def collect(node: ISODirectory, parent: Optional[ISODirectory]) -> None:
            all_dirs.append((node, parent))
            for ch in node.children:
                if isinstance(ch, ISODirectory):
                    collect(ch, node)
                elif isinstance(ch, ISOFile):
                    all_files.append(ch)

        collect(reader.root, None)

        # -------------------------------------------------------------
        # ПРОХОД 1: Определение размеров каталогов и назначение LBA
        # -------------------------------------------------------------
        # Размер записи каталога зависит ТОЛЬКО от имени файла, но не от его размера!
        # Поэтому мы можем заранее узнать точные размеры каталогов в секторах.
        dir_sector_counts: dict[str, int] = {}
        dir_lba_map: dict[str, int] = {}
        file_lba_map: dict[str, int] = {}

        for dir_node, parent_node in all_dirs:
            # Для каждого каталога генерируем фиктивные записи, чтобы узнать длину
            dummy_records = [
                _build_directory_record(".", 0, 0, True),
                _build_directory_record("..", 0, 0, True),
            ]
            for child in dir_node.children:
                dummy_records.append(
                    _build_directory_record(child.name, 0, child.effective_size if isinstance(child, ISOFile) else 0, child.is_directory)
                )
            packed = _pack_records_to_sectors(dummy_records)
            dir_sector_counts[dir_node.path] = len(packed) // SECTOR_SIZE

        # Назначаем LBA:
        # Секторы 0..15: System area (16 секторов)
        # Сектор 16: PVD (1 сектор)
        # Сектор 17: Terminator (1 сектор)
        # Начиная с 18 сектора: каталоги, затем данные файлов
        next_lba = 18

        for dir_node, _ in all_dirs:
            dir_lba_map[dir_node.path] = next_lba
            next_lba += dir_sector_counts[dir_node.path]

        for f in all_files:
            file_lba_map[f.path] = next_lba
            needed_sectors = (f.effective_size + SECTOR_SIZE - 1) // SECTOR_SIZE
            next_lba += needed_sectors

        total_volume_sectors = next_lba

        # Теперь, когда все LBA известны, формируем реальные бинарные секторы каталогов
        final_dir_bytes: dict[str, bytes] = {}
        for dir_node, parent_node in all_dirs:
            my_lba = dir_lba_map[dir_node.path]
            my_size = dir_sector_counts[dir_node.path] * SECTOR_SIZE
            parent_lba = dir_lba_map[parent_node.path] if parent_node else my_lba
            parent_size = dir_sector_counts[parent_node.path] * SECTOR_SIZE if parent_node else my_size

            records = [
                _build_directory_record(".", my_lba, my_size, True),
                _build_directory_record("..", parent_lba, parent_size, True),
            ]
            for child in dir_node.children:
                if isinstance(child, ISODirectory):
                    c_lba = dir_lba_map[child.path]
                    c_size = dir_sector_counts[child.path] * SECTOR_SIZE
                else:
                    c_lba = file_lba_map[child.path]
                    c_size = child.effective_size
                records.append(_build_directory_record(child.name, c_lba, c_size, child.is_directory))

            final_dir_bytes[dir_node.path] = _pack_records_to_sectors(records)

        # -------------------------------------------------------------
        # ПРОХОД 2: Потоковая сборка и запись образа
        # -------------------------------------------------------------
        total_uncompressed_bytes = sum(f.effective_size for f in all_files)
        written_file_bytes = 0

        try:
            with open(temp_path, "wb") as out_fp:
                # 1. Секторы 0..15 (System Area)
                reader._fp.seek(0)
                sys_area = reader._fp.read(16 * SECTOR_SIZE)
                if len(sys_area) < 16 * SECTOR_SIZE:
                    sys_area = sys_area.ljust(16 * SECTOR_SIZE, b"\x00")
                out_fp.write(sys_area)

                # 2. Сектор 16 (PVD)
                pvd_buf = bytearray(SECTOR_SIZE)
                pvd_buf[0] = 1  # Primary Volume Descriptor
                pvd_buf[1:6] = b"CD001"
                pvd_buf[6] = 1  # Version

                sys_id = reader.system_id.encode("ascii", errors="replace")[:32].ljust(32, b" ")
                vol_id = (reader.volume_id or "PSP_GAME").encode("ascii", errors="replace")[:32].ljust(32, b" ")
                pvd_buf[8:40] = sys_id
                pvd_buf[40:72] = vol_id

                # Общий размер тома в секторах
                pvd_buf[80:88] = _pack_both_endian_32(total_volume_sectors)
                # Volume Set Size (1) и Sequence (1)
                pvd_buf[120:124] = _pack_both_endian_16(1)
                pvd_buf[124:128] = _pack_both_endian_16(1)
                # Logical block size (2048)
                pvd_buf[128:132] = _pack_both_endian_16(SECTOR_SIZE)

                # Запись корневого каталога (Root Directory Record) в PVD
                root_lba = dir_lba_map[""]
                root_size = dir_sector_counts[""] * SECTOR_SIZE
                pvd_buf[156:190] = _build_directory_record(".", root_lba, root_size, True)
                pvd_buf[881] = 1  # File structure version

                out_fp.write(pvd_buf)

                # 3. Сектор 17 (Volume Descriptor Set Terminator)
                term_buf = bytearray(SECTOR_SIZE)
                term_buf[0] = 255  # Terminator
                term_buf[1:6] = b"CD001"
                term_buf[6] = 1
                out_fp.write(term_buf)

                # 4. Запись секторов всех каталогов
                for dir_node, _ in all_dirs:
                    out_fp.write(final_dir_bytes[dir_node.path])

                # 5. Потоковая запись данных файлов
                for f in all_files:
                    if cancel_check and cancel_check():
                        out_fp.close()
                        temp_path.unlink(missing_ok=True)
                        return

                    f_size = f.effective_size
                    if f.replacement_path and f.replacement_path.exists():
                        in_stream = open(f.replacement_path, "rb")
                    else:
                        reader._fp.seek(f.lba * SECTOR_SIZE)
                        in_stream = reader._fp

                    rem = f_size
                    while rem > 0:
                        chunk = in_stream.read(min(chunk_size, rem))
                        if not chunk:
                            break
                        out_fp.write(chunk)
                        rem -= len(chunk)
                        written_file_bytes += len(chunk)
                        if progress_callback:
                            progress_callback(written_file_bytes, total_uncompressed_bytes, f.path)

                    if f.replacement_path and f.replacement_path.exists():
                        in_stream.close()

                    # Выравнивание до сектора 2048 байт
                    pad = (SECTOR_SIZE - (f_size % SECTOR_SIZE)) % SECTOR_SIZE
                    if pad > 0:
                        out_fp.write(b"\x00" * pad)

            # Атомарное переименование
            if out_path.exists():
                out_path.unlink()
            temp_path.rename(out_path)

        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise