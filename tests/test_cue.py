"""Тестирование разбора CUE и поиска Game ID."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402
from formats.cue import CUESheet, PS1DiscScanner  # noqa: E402


def test_cue_parser() -> None:
    """Проверка парсинга дорожек и имени файла BIN."""
    cue_text = """
    FILE "Crash Bandicoot (USA).bin" BINARY
      TRACK 01 MODE2/2352
        INDEX 01 00:00:00
      TRACK 02 AUDIO
        INDEX 01 12:34:56
    """
    cue = CUESheet.parse_string(cue_text)
    assert cue.bin_filename == "Crash Bandicoot (USA).bin"
    assert len(cue.tracks) == 2
    assert cue.tracks[0].track_type == "MODE2/2352"
    assert cue.tracks[1].track_type == "AUDIO"
    assert cue.has_audio_tracks is True


def test_ps1_game_id_detection(tmp_path: Path) -> None:
    """Проверка обнаружения Game ID диска в сыром потоке образа."""
    dummy_bin = tmp_path / "game.bin"

    # Эмулируем структуру диска с SYSTEM.CNF внутри
    system_cnf_content = b"BOOT = cdrom:\\SLUS_008.60;1\r\nTCB = 4\r\nEVENT = 16\r\n"
    padding = b"\x00" * 32768  # Смещение до системной области
    dummy_bin.write_bytes(padding + system_cnf_content + padding)

    detected_id = PS1DiscScanner.detect_game_id(dummy_bin)
    assert detected_id == "SLUS-00860"


def test_normalize_game_id() -> None:
    """Проверка форматирования различных вариантов написания Game ID."""
    assert PS1DiscScanner.normalize_game_id("SLUS_008.60") == "SLUS-00860"
    assert PS1DiscScanner.normalize_game_id("SCES-01234") == "SCES-01234"
    assert PS1DiscScanner.normalize_game_id("slpm00001") == "SLPM-00001"


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))