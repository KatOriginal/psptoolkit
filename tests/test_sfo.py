"""Тестирование парсинга, сериализации и обработки ошибок PARAM.SFO."""

import pytest

from core.exceptions import SFOFormatError
from formats.sfo import SFO, SFODataType


def test_sfo_build_and_parse_roundtrip() -> None:
    """Проверка полного цикла создания, сохранения и чтения SFO."""
    sfo = SFO()
    sfo.set_string("TITLE", "Crisis Core: Final Fantasy VII", max_length=128)
    sfo.set_string("DISC_ID", "ULUS10336", max_length=16)
    sfo.set_int("PARENTAL_LEVEL", 5)
    sfo.set_int("CATEGORY", 0x474D)  # 'MG'

    serialized = sfo.to_bytes()
    assert len(serialized) > 0

    parsed = SFO.from_bytes(serialized)
    assert parsed.get("TITLE") == "Crisis Core: Final Fantasy VII"
    assert parsed.get("DISC_ID") == "ULUS10336"
    assert parsed.get("PARENTAL_LEVEL") == 5
    assert parsed.get("CATEGORY") == 0x474D


def test_sfo_sorted_keys() -> None:
    """Ключи в бинарном представлении должны быть отсортированы лексикографически."""
    sfo = SFO()
    sfo.set_string("Z_KEY", "Z")
    sfo.set_string("A_KEY", "A")
    sfo.set_string("M_KEY", "M")

    serialized = sfo.to_bytes()
    parsed = SFO.from_bytes(serialized)

    keys = list(parsed.entries.keys())
    assert keys == ["A_KEY", "M_KEY", "Z_KEY"]


def test_sfo_corrupted_magic() -> None:
    """Повреждённая сигнатура должна вызывать SFOFormatError."""
    invalid_data = b"NOPE\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    with pytest.raises(SFOFormatError, match="Неверная сигнатура SFO"):
        SFO.from_bytes(invalid_data)


def test_sfo_truncated_file() -> None:
    """Усечённый файл должен вызывать ошибку."""
    truncated_data = b"\x00PSF\x01\x01\x00\x00"
    with pytest.raises(SFOFormatError, match="меньше заголовка SFO"):
        SFO.from_bytes(truncated_data)


def test_sfo_int_bounds() -> None:
    """Числовые значения должны укладываться в uint32."""
    sfo = SFO()
    with pytest.raises(SFOFormatError, match="выходит за пределы 32-битного диапазона"):
        sfo.set_int("OVERFLOW", 0x1_0000_0000)