"""Модуль для чтения, валидации и сборки файлов формата PARAM.SFO."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct
from typing import BinaryIO, Union

from core.exceptions import SFOFormatError

SFO_MAGIC = b"\x00PSF"
SFO_HEADER_SIZE = 20
SFO_ENTRY_SIZE = 16
DEFAULT_VERSION = 0x00000101  # v1.1


class SFODataType(IntEnum):
    """Типы данных, используемые в записях SFO."""

    UTF8_NOT_TERMINATED = 0x0004
    UTF8 = 0x0204
    INT32 = 0x0404


@dataclass
class SFOEntry:
    """Представление отдельной записи в PARAM.SFO."""

    key: str
    data_type: SFODataType
    value: Union[str, int]
    max_length: int = 0

    def __post_init__(self) -> None:
        if self.data_type == SFODataType.INT32:
            if not isinstance(self.value, int):
                raise SFOFormatError(
                    f"Значение для целочисленного ключа '{self.key}' должно быть int, "
                    f"получено: {type(self.value).__name__}"
                )
            if self.max_length == 0:
                self.max_length = 4
        else:
            if not isinstance(self.value, str):
                raise SFOFormatError(
                    f"Значение для строкового ключа '{self.key}' должно быть str, "
                    f"получено: {type(self.value).__name__}"
                )
            val_len = len(self.value.encode("utf-8")) + (
                1 if self.data_type == SFODataType.UTF8 else 0
            )
            if self.max_length < val_len:
                # Выравнивание по границе 4 байт для устойчивости структуры
                self.max_length = (val_len + 3) & ~3


class SFO:
    """Парсер и построитель структуры PARAM.SFO."""

    def __init__(self) -> None:
        self.version: int = DEFAULT_VERSION
        self.entries: dict[str, SFOEntry] = {}

    def get(self, key: str, default: Union[str, int, None] = None) -> Union[str, int, None]:
        """Получить значение параметра по ключу."""
        entry = self.entries.get(key)
        return entry.value if entry else default

    def set_string(
        self,
        key: str,
        value: str,
        max_length: int = 0,
        null_terminated: bool = True,
    ) -> None:
        """Установить строковое значение."""
        data_type = SFODataType.UTF8 if null_terminated else SFODataType.UTF8_NOT_TERMINATED
        self.entries[key] = SFOEntry(
            key=key,
            data_type=data_type,
            value=value,
            max_length=max_length,
        )

    def set_int(self, key: str, value: int) -> None:
        """Установить целочисленное значение (32-bit unsigned/signed)."""
        if not (0 <= value <= 0xFFFFFFFF):
            raise SFOFormatError(
                f"Значение {value} выходит за пределы 32-битного диапазона (0..4294967295)"
            )
        self.entries[key] = SFOEntry(
            key=key,
            data_type=SFODataType.INT32,
            value=value,
            max_length=4,
        )

    def delete(self, key: str) -> None:
        """Удалить параметр по ключу."""
        if key in self.entries:
            del self.entries[key]

    @classmethod
    def from_bytes(cls, raw_data: bytes) -> SFO:
        """Создать экземпляр SFO из байтов."""
        if len(raw_data) < SFO_HEADER_SIZE:
            raise SFOFormatError(
                f"Размер данных ({len(raw_data)} байт) меньше заголовка SFO ({SFO_HEADER_SIZE} байт)"
            )

        magic, version, key_table_offset, data_table_offset, count = struct.unpack_from(
            "<4sIIII", raw_data, 0
        )

        if magic != SFO_MAGIC:
            raise SFOFormatError(
                f"Неверная сигнатура SFO: ожидалось {SFO_MAGIC!r}, получено {magic!r}"
            )

        expected_entries_end = SFO_HEADER_SIZE + count * SFO_ENTRY_SIZE
        if expected_entries_end > len(raw_data):
            raise SFOFormatError(
                "Таблица записей выходит за пределы файла. Файл повреждён."
            )

        sfo = cls()
        sfo.version = version

        entries_meta: list[tuple[int, int, int, int, int]] = []
        for i in range(count):
            entry_offset = SFO_HEADER_SIZE + (i * SFO_ENTRY_SIZE)
            key_offset, data_type_raw, used_len, max_len, data_offset = struct.unpack_from(
                "<HHIII", raw_data, entry_offset
            )
            entries_meta.append((key_offset, data_type_raw, used_len, max_len, data_offset))

        for key_offset, data_type_raw, used_len, max_len, data_offset in entries_meta:
            abs_key_offset = key_table_offset + key_offset
            if abs_key_offset >= len(raw_data):
                raise SFOFormatError(f"Смещение ключа {abs_key_offset} за пределами файла")

            key_end = raw_data.find(b"\x00", abs_key_offset)
            if key_end == -1 or key_end > data_table_offset:
                raise SFOFormatError("Ключ не завершён нуль-терминатором или выходит за границы")

            try:
                key = raw_data[abs_key_offset:key_end].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SFOFormatError(f"Ключ содержит некорректный UTF-8: {exc}") from exc

            abs_data_offset = data_table_offset + data_offset
            if abs_data_offset + used_len > len(raw_data):
                raise SFOFormatError(
                    f"Данные для ключа '{key}' выходят за границы файла"
                )

            data_raw = raw_data[abs_data_offset : abs_data_offset + used_len]

            try:
                data_type = SFODataType(data_type_raw)
            except ValueError:
                # Если встретился нестандартный тип данных, обрабатываем как UTF8_NOT_TERMINATED
                data_type = SFODataType.UTF8_NOT_TERMINATED

            if data_type == SFODataType.INT32:
                if len(data_raw) < 4:
                    raise SFOFormatError(
                        f"Недостаточно байт для числа в ключе '{key}': ожидалось 4, получено {len(data_raw)}"
                    )
                (int_val,) = struct.unpack_from("<I", data_raw, 0)
                parsed_value: Union[str, int] = int_val
            else:
                # Удаляем завершающий 0x00, если строка формата UTF-8 Null-terminated
                if data_type == SFODataType.UTF8 and data_raw.endswith(b"\x00"):
                    parsed_value = data_raw[:-1].decode("utf-8", errors="replace")
                else:
                    parsed_value = data_raw.decode("utf-8", errors="replace")

            sfo.entries[key] = SFOEntry(
                key=key,
                data_type=data_type,
                value=parsed_value,
                max_length=max_len,
            )

        return sfo

    @classmethod
    def from_file(cls, path: str) -> SFO:
        """Считать SFO из файла."""
        with open(path, "rb") as file_handle:
            return cls.from_bytes(file_handle.read())

    def to_bytes(self) -> bytes:
        """Сериализовать объект SFO в бинарное представление."""
        # Сортировка записей по имени ключа (стандарт PSP/PS3/PS4 требует алфавитный порядок)
        sorted_keys = sorted(self.entries.keys())
        count = len(sorted_keys)

        key_table = bytearray()
        data_table = bytearray()
        entries_table = bytearray()

        # Предварительно рассчитываем смещения
        key_offsets: list[int] = []
        for key in sorted_keys:
            key_offsets.append(len(key_table))
            key_table.extend(key.encode("utf-8") + b"\x00")

        # Выравнивание таблицы ключей до границы 4 байт
        key_padding = (4 - (len(key_table) % 4)) % 4
        key_table.extend(b"\x00" * key_padding)

        header_and_entries_size = SFO_HEADER_SIZE + (count * SFO_ENTRY_SIZE)
        key_table_offset = header_and_entries_size
        data_table_offset = key_table_offset + len(key_table)

        for key, key_offset in zip(sorted_keys, key_offsets):
            entry = self.entries[key]
            data_offset = len(data_table)

            if entry.data_type == SFODataType.INT32:
                assert isinstance(entry.value, int)
                data_bytes = struct.pack("<I", entry.value)
                used_len = 4
                max_len = 4
            elif entry.data_type == SFODataType.UTF8:
                assert isinstance(entry.value, str)
                data_bytes = entry.value.encode("utf-8") + b"\x00"
                used_len = len(data_bytes)
                max_len = max(entry.max_length, used_len)
                # Выравнивание до max_len нулями
                data_bytes += b"\x00" * (max_len - used_len)
            else:  # UTF8_NOT_TERMINATED
                assert isinstance(entry.value, str)
                data_bytes = entry.value.encode("utf-8")
                used_len = len(data_bytes)
                max_len = max(entry.max_length, used_len)
                data_bytes += b"\x00" * (max_len - used_len)

            # Выравнивание каждой записи данных до границы 4 байт
            align_padding = (4 - (len(data_bytes) % 4)) % 4
            if align_padding > 0:
                data_bytes += b"\x00" * align_padding
                max_len += align_padding

            data_table.extend(data_bytes)

            entries_table.extend(
                struct.pack(
                    "<HHIII",
                    key_offset,
                    entry.data_type,
                    used_len,
                    max_len,
                    data_offset,
                )
            )

        header = struct.pack(
            "<4sIIII",
            SFO_MAGIC,
            self.version,
            key_table_offset,
            data_table_offset,
            count,
        )

        return bytes(header + entries_table + key_table + data_table)

    def write_to_file(self, path: str) -> None:
        """Безопасно записать SFO в файл."""
        data = self.to_bytes()
        with open(path, "wb") as file_handle:
            file_handle.write(data)