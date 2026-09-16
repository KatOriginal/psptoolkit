"""Тестирование пересборщика ISO 9660 и замены файлов."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402
from core.iso_rebuilder import ISORebuilder  # noqa: E402
from formats.iso import ISOFile, ISOReader  # noqa: E402
from tests.test_iso import create_minimal_synthetic_iso  # noqa: E402


def test_iso_replace_file_and_rebuild(tmp_path: Path) -> None:
    """Проверка подмены файла в ISO, сборки в новый образ и верификации данных."""
    # 1. Создаём исходный синтетический ISO
    original_iso = create_minimal_synthetic_iso(tmp_path)
    rebuilt_iso = tmp_path / "rebuilt.iso"

    # 2. Создаём файл для подмены с большим объёмом данных
    new_content = b"REPLACED DATA FOR PSP TOOLKIT! " * 50
    replacement_file = tmp_path / "new_hello.txt"
    replacement_file.write_bytes(new_content)

    # 3. Открываем ISO, подменяем HELLO.TXT и запускаем сборку
    with ISOReader(original_iso) as reader:
        item = reader.find_entry("HELLO.TXT")
        assert isinstance(item, ISOFile)
        item.replacement_path = replacement_file

        ISORebuilder.rebuild(reader, rebuilt_iso)

    assert rebuilt_iso.exists()

    # 4. Открываем пересобранный ISO и сверяем данные байт-в-байт
    with ISOReader(rebuilt_iso) as reader:
        rebuilt_item = reader.find_entry("HELLO.TXT")
        assert isinstance(rebuilt_item, ISOFile)
        assert rebuilt_item.size == len(new_content)

        read_back_data = reader.read_file_bytes(rebuilt_item)
        assert read_back_data == new_content


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))