"""Тестирование компрессора и декомпрессора CSO."""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402
from core.exceptions import CSOFormatError  # noqa: E402
from formats.cso import CSOConverter, DEFAULT_BLOCK_SIZE  # noqa: E402


def test_cso_compression_and_decompression_roundtrip(tmp_path: Path) -> None:
    """Проверка полного цикла: ISO -> CSO -> ISO байт-в-байт."""
    # Генерируем тестовый ISO (несколько секторов: сжимаемые данные + нули)
    original_iso = tmp_path / "test.iso"
    cso_file = tmp_path / "test.cso"
    restored_iso = tmp_path / "restored.iso"

    # Создаём 10 секторов тестовых данных (20 КБ)
    block_1 = b"ABCDEFGH" * (DEFAULT_BLOCK_SIZE // 8)  # отлично сжимается
    block_2 = b"\x00" * DEFAULT_BLOCK_SIZE              # нули
    block_3 = os.urandom(DEFAULT_BLOCK_SIZE)            # несжимаемые случайные байты (бит 31)

    payload = (block_1 + block_2 + block_3) * 3
    original_iso.write_bytes(payload)

    # 1. Сжимаем в CSO
    CSOConverter.compress_iso_to_cso(original_iso, cso_file, compression_level=9)
    assert cso_file.exists()
    assert cso_file.stat().st_size < original_iso.stat().st_size

    # 2. Распаковываем обратно в ISO
    CSOConverter.decompress_cso_to_iso(cso_file, restored_iso)
    assert restored_iso.exists()

    # 3. Сверяем байт-в-байт
    assert restored_iso.read_bytes() == original_iso.read_bytes()


def test_cso_corrupted_header(tmp_path: Path) -> None:
    """Повреждённый заголовок CSO вызывает CSOFormatError."""
    bad_cso = tmp_path / "bad.cso"
    bad_cso.write_bytes(b"WRONG_MAGIC_DATA_12345678")

    with pytest.raises(CSOFormatError, match="Неверная сигнатура CSO"):
        CSOConverter.decompress_cso_to_iso(bad_cso, tmp_path / "out.iso")


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))