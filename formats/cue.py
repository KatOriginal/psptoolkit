"""Парсер разметки CUE Sheet и сканер идентификаторов дисков PS1."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Optional, Union

from core.exceptions import CUEFormatError

# Регулярное выражение для поиска стандартного Game ID PS1 (например, SLUS_008.60 или SCES_012.34)
PS1_GAME_ID_REGEX = re.compile(
    rb"(S[LC][UEI][SABDEJ]_\d{3}\.\d{2})|"
    rb"((?:SLUS|SLES|SCUS|SCES|SLPS|SLPM|SLED|SCED)[-_]?\d{5})",
    re.IGNORECASE,
)


@dataclass
class CUETrack:
    """Информация об отдельной дорожке диска."""

    number: int
    track_type: str  # MODE2/2352, MODE1/2352, AUDIO
    index01: str = "00:00:00"


@dataclass
class CUESheet:
    """Представление структуры CUE Sheet."""

    cue_path: Optional[Path]
    bin_filename: str
    tracks: list[CUETrack] = field(default_factory=list)

    @property
    def has_audio_tracks(self) -> bool:
        """Есть ли на диске аудиотреки (CDDA)."""
        return any("AUDIO" in track.track_type.upper() for track in self.tracks)

    @classmethod
    def parse_file(cls, cue_path: Union[str, Path]) -> CUESheet:
        """Парсинг файла .CUE."""
        path = Path(cue_path)
        if not path.exists():
            raise FileNotFoundError(f"Файл CUE не найден: {path}")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            raise CUEFormatError(f"Ошибка чтения CUE: {exc}") from exc

        return cls.parse_string(content, cue_path=path)

    @classmethod
    def parse_string(cls, content: str, cue_path: Optional[Path] = None) -> CUESheet:
        """Разбор содержимого CUE из строки."""
        bin_filename = ""
        tracks: list[CUETrack] = []
        current_track: Optional[CUETrack] = None

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("REM"):
                continue

            parts = line.split()
            cmd = parts[0].upper()

            if cmd == "FILE":
                # FILE "game.bin" BINARY
                match = re.search(r'FILE\s+"([^"]+)"', line, re.IGNORECASE)
                if match:
                    bin_filename = match.group(1)
                elif len(parts) >= 2:
                    bin_filename = parts[1]

            elif cmd == "TRACK":
                # TRACK 01 MODE2/2352
                if len(parts) >= 3:
                    try:
                        track_num = int(parts[1])
                    except ValueError:
                        track_num = len(tracks) + 1
                    track_type = parts[2].upper()
                    current_track = CUETrack(number=track_num, track_type=track_type)
                    tracks.append(current_track)

            elif cmd == "INDEX":
                # INDEX 01 00:00:00
                if len(parts) >= 3 and current_track and parts[1] == "01":
                    current_track.index01 = parts[2]

        if not bin_filename and cue_path:
            # Если имя BIN не указано, предполагаем одноимённый файл рядом
            candidate = cue_path.with_suffix(".bin")
            if candidate.exists():
                bin_filename = candidate.name

        return cls(cue_path=cue_path, bin_filename=bin_filename, tracks=tracks)


class PS1DiscScanner:
    """Утилита анализа и извлечения метаданных из дисков PS1."""

    @staticmethod
    def detect_game_id(bin_path: Union[str, Path], scan_bytes: int = 10 * 1024 * 1024) -> Optional[str]:
        """Потоковый поиск Game ID диска в первых мегабайтах (SYSTEM.CNF / ISO Primary Descriptor)."""
        path = Path(bin_path)
        if not path.exists():
            return None

        # Читаем до 10 МБ от начала диска чанками
        chunk_size = 1024 * 1024
        to_read = min(path.stat().st_size, scan_bytes)
        buffer = bytearray()

        with open(path, "rb") as fp:
            while len(buffer) < to_read:
                chunk = fp.read(min(chunk_size, to_read - len(buffer)))
                if not chunk:
                    break
                buffer.extend(chunk)

                # Ищем паттерн Game ID
                match = PS1_GAME_ID_REGEX.search(buffer)
                if match:
                    raw_id = match.group(0).decode("ascii", errors="ignore").upper()
                    return PS1DiscScanner.normalize_game_id(raw_id)

        return None

    @staticmethod
    def normalize_game_id(raw_id: str) -> str:
        """Нормализация строки ID (например, 'SLUS_008.60' -> 'SLUS-00860')."""
        # Убираем подчёркивания, точки и дефисы
        clean = re.sub(r"[^A-Za-z0-9]", "", raw_id).upper()
        if len(clean) >= 9:
            # Первые 4 буквы (префикс региона/издателя) + 5 цифр
            prefix = clean[:4]
            digits = clean[4:9]
            return f"{prefix}-{digits}"
        return clean