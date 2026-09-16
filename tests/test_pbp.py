"""Тестирование сборки и распаковки контейнера PBP."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402
from core.exceptions import PBPFormatError  # noqa: E402
from formats.pbp import PBPSource, PBPReader, PBPWriter  # noqa: E402


def test_pbp_roundtrip(tmp_path: Path) -> None:
    """Проверка упаковки секций в PBP и обратного чтения байт-в-байт."""
    output_pbp = tmp_path / "EBOOT.PBP"

    source = PBPSource(
        param_sfo=b"DUMMY_SFO_DATA_12345",
        icon0_png=b"FAKE_PNG_ICON_DATA",
        pic1_png=b"FAKE_PNG_BACKGROUND_PIC1",
        data_psp=b"FAKE_EXECUTABLE_PAYLOAD",
    )

    # 1. Запись PBP
    PBPWriter.write_pbp(output_pbp, source)
    assert output_pbp.exists()
    assert output_pbp.stat().st_size > 40

    # 2. Чтение PBP
    reader = PBPReader(output_pbp)
    sizes = reader.read_header()

    assert sizes["param_sfo"] == len(b"DUMMY_SFO_DATA_12345")
    assert sizes["icon0_png"] == len(b"FAKE_PNG_ICON_DATA")
    assert sizes["icon1_pmf"] == 0  # пустая секция
    assert sizes["pic1_png"] == len(b"FAKE_PNG_BACKGROUND_PIC1")
    assert sizes["data_psp"] == len(b"FAKE_EXECUTABLE_PAYLOAD")
    assert sizes["data_psar"] == 0

    assert reader.read_section("param_sfo") == b"DUMMY_SFO_DATA_12345"
    assert reader.read_section("icon0_png") == b"FAKE_PNG_ICON_DATA"
    assert reader.read_section("pic1_png") == b"FAKE_PNG_BACKGROUND_PIC1"


def test_pbp_corrupted_header(tmp_path: Path) -> None:
    """Повреждённая сигнатура PBP должна вызывать PBPFormatError."""
    bad_pbp = tmp_path / "bad.pbp"
    bad_pbp.write_bytes(b"BAD_MAGIC_PBP_HEADER_PADDING_BYTES_1234567890")

    reader = PBPReader(bad_pbp)
    with pytest.raises(PBPFormatError, match="Неверная сигнатура PBP"):
        reader.read_header()


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))