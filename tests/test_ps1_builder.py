"""Тестирование сборки PS1 EBOOT.PBP и структуры PSISOIMG."""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402
from core.ps1_builder import PS1_BLOCK_SIZE, PS1EBOOTBuilder, PSISOIMG_MAGIC
from formats.pbp import PBPReader
from formats.sfo import SFO


def test_build_ps1_eboot_roundtrip(tmp_path: Path) -> None:
    """Проверка сборки PS1 EBOOT из синтетического BIN и проверка его секций."""
    dummy_bin = tmp_path / "game.bin"
    output_pbp = tmp_path / "EBOOT.PBP"

    # Создаём образ PS1 размером в 2 блока (75 264 байт)
    dummy_bin.write_bytes(os.urandom(PS1_BLOCK_SIZE * 2))

    PS1EBOOTBuilder.build_eboot(
        bin_path=dummy_bin,
        output_pbp_path=output_pbp,
        title="Silent Hill",
        game_id="SLUS-00001",
        compression_level=1,
    )

    assert output_pbp.exists()
    assert output_pbp.stat().st_size > 0x100000  # Должен включать заголовок PSISOIMG

    # Проверяем получившийся PBP
    reader = PBPReader(output_pbp)
    reader.read_header()

    # 1. Проверяем PARAM.SFO внутри собранного PBP
    raw_sfo = reader.read_section("param_sfo")
    assert len(raw_sfo) > 0
    sfo = SFO.from_bytes(raw_sfo)
    assert sfo.get("TITLE") == "Silent Hill"
    assert sfo.get("DISC_ID") == "SLUS00001"
    assert sfo.get("CATEGORY") == "ME"

    # 2. Проверяем сигнатуру PSISOIMG0000 внутри DATA.PSAR
    raw_psar = reader.read_section("data_psar")
    assert raw_psar.startswith(PSISOIMG_MAGIC)


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))