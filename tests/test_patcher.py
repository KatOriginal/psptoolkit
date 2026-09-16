"""Тестирование применения бинарных патчей PPF и пакетов модификаций."""

from pathlib import Path
import struct
import sys
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402
from core.mod_patcher import ModPatcher  # noqa: E402
from formats.iso import ISOFile, ISOReader  # noqa: E402
from formats.ppf import PPFPatcher  # noqa: E402
from tests.test_iso import create_minimal_synthetic_iso  # noqa: E402


def test_ppf3_patch_application(tmp_path: Path) -> None:
    """Проверка применения синтетического патча PPF 3.0."""
    source_bin = tmp_path / "game.iso"
    output_bin = tmp_path / "patched.iso"
    ppf_file = tmp_path / "patch.ppf"

    source_bin.write_bytes(b"ORIGINAL_DATA_BLOCK_12345" * 10)

    # Формируем заголовок PPF 3.0 (60 байт)
    hdr = bytearray(60)
    hdr[0:5] = b"PPF30"
    hdr[5] = 2  # PPF 3.0
    hdr[6:40] = b"Persona 3 Portable Rus Patch".ljust(34, b" ")
    hdr[56] = 0  # Imagetype: BIN
    hdr[57] = 0  # Blockcheck disabled
    hdr[58] = 0  # Undo disabled

    # Чанк патча: по смещению 10 заменяем 5 байт на b"HELLO"
    target_offset = 10
    patch_bytes = b"HELLO"
    chunk = struct.pack("<QB", target_offset, len(patch_bytes)) + patch_bytes

    ppf_file.write_bytes(bytes(hdr) + chunk)

    # Применяем патч
    PPFPatcher.apply_patch(source_bin, ppf_file, output_bin)

    assert output_bin.exists()
    patched_data = output_bin.read_bytes()
    assert patched_data[10:15] == b"HELLO"
    # Исходный файл не изменился
    assert source_bin.read_bytes()[10:15] != b"HELLO"


def test_mod_package_zip_application(tmp_path: Path) -> None:
    """Проверка применения мода из ZIP-архива (замена файлов в ISO)."""
    # Создаём исходный виртуальный ISO с файлом HELLO.TXT
    iso_file = create_minimal_synthetic_iso(tmp_path)
    output_iso = tmp_path / "p3p_russian.iso"

    # Создаём ZIP архив с русификатором (новый HELLO.TXT)
    zip_path = tmp_path / "P3P_Kotone_Translation.zip"
    new_txt = b"RUSSIAN TRANSLATION BY KOTONE TRANSLATION BUREAU"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("HELLO.TXT", new_txt)

    # Применяем мод
    replaced = ModPatcher.apply_mod_package(iso_file, zip_path, output_iso)
    assert replaced == 1
    assert output_iso.exists()

    # Проверяем, что в новом ISO лежит русский текст
    with ISOReader(output_iso) as reader:
        entry = reader.find_entry("HELLO.TXT")
        assert isinstance(entry, ISOFile)
        assert entry.size == len(new_txt)
        assert reader.read_file_bytes(entry) == new_txt


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))