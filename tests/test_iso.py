"""Тестирование парсера файловой системы ISO 9660."""

from pathlib import Path
import struct
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402
from core.exceptions import ISOFormatError  # noqa: E402
from formats.iso import ISOFile, ISOReader, SECTOR_SIZE  # noqa: E402


def create_minimal_synthetic_iso(tmp_path: Path) -> Path:
    """Генерация валидного минимального ISO 9660 на лету для юнит-тестов."""
    iso_file = tmp_path / "test_synthetic.iso"

    total_sectors = 20
    iso_bytes = bytearray(total_sectors * SECTOR_SIZE)

    # 1. PVD на 16-м секторе (смещение 16 * 2048)
    pvd_offset = 16 * SECTOR_SIZE
    iso_bytes[pvd_offset] = 1  # Type: Primary Volume Descriptor
    iso_bytes[pvd_offset + 1 : pvd_offset + 6] = b"CD001"
    iso_bytes[pvd_offset + 6] = 1  # Version 1

    # Volume ID (32 байта)
    vol_id = b"PSP_TEST_DISC".ljust(32, b" ")
    iso_bytes[pvd_offset + 40 : pvd_offset + 72] = vol_id

    # Root Directory Record внутри PVD (смещение 156)
    root_lba = 17
    root_size = SECTOR_SIZE
    root_rec = bytearray(34)
    root_rec[0] = 34  # Длина записи
    struct.pack_into("<I", root_rec, 2, root_lba)
    struct.pack_into(">I", root_rec, 6, root_lba)
    struct.pack_into("<I", root_rec, 10, root_size)
    struct.pack_into(">I", root_rec, 14, root_size)
    root_rec[25] = 2  # Флаг каталога
    root_rec[32] = 1  # Длина имени
    root_rec[33] = 0  # Корень (\x00)
    iso_bytes[pvd_offset + 156 : pvd_offset + 190] = root_rec

    # 2. Корневой каталог на 17-м секторе
    root_offset = root_lba * SECTOR_SIZE
    file_lba = 18
    payload = b"TEST DATA FOR PSP TOOLKIT"
    file_size = len(payload)

    # Запись для файла "HELLO.TXT;1"
    name_bytes = b"HELLO.TXT;1"
    rec_len = 33 + len(name_bytes)
    if rec_len % 2 != 0:
        rec_len += 1

    file_rec = bytearray(rec_len)
    file_rec[0] = rec_len
    struct.pack_into("<I", file_rec, 2, file_lba)
    struct.pack_into("<I", file_rec, 10, file_size)
    file_rec[25] = 0  # Файл
    file_rec[32] = len(name_bytes)
    file_rec[33 : 33 + len(name_bytes)] = name_bytes

    iso_bytes[root_offset : root_offset + rec_len] = file_rec

    # 3. Данные файла на 18-м секторе
    file_offset = file_lba * SECTOR_SIZE
    iso_bytes[file_offset : file_offset + file_size] = payload

    iso_file.write_bytes(iso_bytes)
    return iso_file


def test_iso_parse_and_read(tmp_path: Path) -> None:
    """Проверка считывания виртуального ISO, разбора PVD и чтения байтов файла."""
    iso_path = create_minimal_synthetic_iso(tmp_path)

    with ISOReader(iso_path) as reader:
        assert reader.volume_id == "PSP_TEST_DISC"
        entry = reader.find_entry("HELLO.TXT")
        assert entry is not None
        assert isinstance(entry, ISOFile)
        assert entry.size == len(b"TEST DATA FOR PSP TOOLKIT")

        data = reader.read_file_bytes(entry)
        assert data == b"TEST DATA FOR PSP TOOLKIT"


def test_iso_invalid_magic(tmp_path: Path) -> None:
    """Файл с неверной сигнатурой должен вызывать ISOFormatError."""
    bad_iso = tmp_path / "bad.iso"
    bad_iso.write_bytes(b"\x00" * (20 * SECTOR_SIZE))  # Нет CD001

    with pytest.raises(ISOFormatError, match="Неверная сигнатура ISO 9660"):
        with ISOReader(bad_iso) as reader:
            pass


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
    """Тестирование парсера файловой системы ISO 9660."""

from pathlib import Path
import struct
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402
from core.exceptions import ISOFormatError  # noqa: E402
from formats.iso import ISODirectory, ISOFile, ISOReader, SECTOR_SIZE  # noqa: E402


def create_minimal_synthetic_iso(tmp_path: Path) -> Path:
    """Генерация валидного минимального ISO 9660 на лету для юнит-тестов."""
    iso_file = tmp_path / "test_synthetic.iso"

    total_sectors = 20
    iso_bytes = bytearray(total_sectors * SECTOR_SIZE)

    pvd_offset = 16 * SECTOR_SIZE
    iso_bytes[pvd_offset] = 1
    iso_bytes[pvd_offset + 1 : pvd_offset + 6] = b"CD001"
    iso_bytes[pvd_offset + 6] = 1

    vol_id = b"PSP_TEST_DISC".ljust(32, b" ")
    iso_bytes[pvd_offset + 40 : pvd_offset + 72] = vol_id

    root_lba = 17
    root_size = SECTOR_SIZE
    root_rec = bytearray(34)
    root_rec[0] = 34
    struct.pack_into("<I", root_rec, 2, root_lba)
    struct.pack_into("<I", root_rec, 10, root_size)
    root_rec[25] = 2
    root_rec[32] = 1
    root_rec[33] = 0
    iso_bytes[pvd_offset + 156 : pvd_offset + 190] = root_rec

    root_offset = root_lba * SECTOR_SIZE
    file_lba = 18
    payload = b"TEST DATA FOR PSP TOOLKIT"
    file_size = len(payload)

    name_bytes = b"HELLO.TXT;1"
    rec_len = 33 + len(name_bytes)
    if rec_len % 2 != 0:
        rec_len += 1

    file_rec = bytearray(rec_len)
    file_rec[0] = rec_len
    struct.pack_into("<I", file_rec, 2, file_lba)
    struct.pack_into("<I", file_rec, 10, file_size)
    file_rec[25] = 0
    file_rec[32] = len(name_bytes)
    file_rec[33 : 33 + len(name_bytes)] = name_bytes

    iso_bytes[root_offset : root_offset + rec_len] = file_rec

    file_offset = file_lba * SECTOR_SIZE
    iso_bytes[file_offset : file_offset + file_size] = payload

    iso_file.write_bytes(iso_bytes)
    return iso_file


def test_iso_parse_and_read(tmp_path: Path) -> None:
    """Проверка считывания виртуального ISO, разбора PVD и чтения байтов файла."""
    iso_path = create_minimal_synthetic_iso(tmp_path)

    with ISOReader(iso_path) as reader:
        assert reader.volume_id == "PSP_TEST_DISC"
        entry = reader.find_entry("HELLO.TXT")
        assert entry is not None
        assert isinstance(entry, ISOFile)
        assert entry.size == len(b"TEST DATA FOR PSP TOOLKIT")

        data = reader.read_file_bytes(entry)
        assert data == b"TEST DATA FOR PSP TOOLKIT"


def test_iso_extract_directory(tmp_path: Path) -> None:
    """Проверка рекурсивного извлечения директории на диск."""
    iso_path = create_minimal_synthetic_iso(tmp_path)
    output_dir = tmp_path / "extracted"

    with ISOReader(iso_path) as reader:
        assert reader.root is not None
        reader.extract_directory(reader.root, output_dir)

    extracted_file = output_dir / "HELLO.TXT"
    assert extracted_file.exists()
    assert extracted_file.read_bytes() == b"TEST DATA FOR PSP TOOLKIT"


def test_iso_invalid_magic(tmp_path: Path) -> None:
    """Файл с неверной сигнатурой должен вызывать ISOFormatError."""
    bad_iso = tmp_path / "bad.iso"
    bad_iso.write_bytes(b"\x00" * (20 * SECTOR_SIZE))

    with pytest.raises(ISOFormatError, match="Неверная сигнатура ISO 9660"):
        with ISOReader(bad_iso) as reader:
            pass


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))