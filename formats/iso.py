"""Потоковый парсер дисковых образов ISO 9660 для PSP."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import struct
from typing import BinaryIO, Callable, Optional, Union

from core.exceptions import ISOFormatError

SECTOR_SIZE = 2048
PVD_SECTOR = 16
ISO_STANDARD_ID = b"CD001"


@dataclass
class ISOItem:
    """Базовый элемент файловой структуры ISO."""

    name: str
    lba: int
    size: int
    path: str
    is_directory: bool = False


@dataclass
class ISOFile(ISOItem):
    """Файл внутри образа ISO с поддержкой замены."""

    is_directory: bool = False
    replacement_path: Optional[Path] = None
    replacement_bytes: Optional[bytes] = None

    @property
    def effective_size(self) -> int:
        """Реальный размер файла с учётом подмены."""
        if self.replacement_bytes is not None:
            return len(self.replacement_bytes)
        if self.replacement_path and self.replacement_path.exists():
            return self.replacement_path.stat().st_size
        return self.size

    @property
    def is_modified(self) -> bool:
        """Был ли файл заменён."""
        return (self.replacement_path is not None) or (self.replacement_bytes is not None)


@dataclass
class ISODirectory(ISOItem):
    """Каталог внутри образа ISO."""

    is_directory: bool = True
    children: list[Union[ISOFile, ISODirectory]] = field(default_factory=list)


class ISOReader:
    """Низкоуровневый потоковый ридер ISO 9660."""

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.path = Path(file_path)
        self._fp: Optional[BinaryIO] = None
        self.volume_id: str = ""
        self.system_id: str = ""
        self.root: Optional[ISODirectory] = None
        self.total_size: int = 0

    def __enter__(self) -> ISOReader:
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def open(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Файл образа не найден: {self.path}")

        self.total_size = self.path.stat().st_size
        if self.total_size < (PVD_SECTOR + 1) * SECTOR_SIZE:
            raise ISOFormatError(
                f"Файл слишком мал для ISO 9660: размер {self.total_size} байт"
            )

        self._fp = open(self.path, "rb")
        self._parse_pvd()

    def close(self) -> None:
        if self._fp and not self._fp.closed:
            self._fp.close()
            self._fp = None

    def _parse_pvd(self) -> None:
        assert self._fp is not None
        self._fp.seek(PVD_SECTOR * SECTOR_SIZE)
        pvd_data = self._fp.read(SECTOR_SIZE)

        vd_type, standard_id, version = struct.unpack_from("<B5sB", pvd_data, 0)
        if standard_id != ISO_STANDARD_ID:
            raise ISOFormatError(
                f"Неверная сигнатура ISO 9660: ожидалось {ISO_STANDARD_ID!r}, получено {standard_id!r}"
            )
        if vd_type != 1:
            raise ISOFormatError(f"Сектор 16 не является Primary Volume Descriptor (тип {vd_type})")

        self.system_id = pvd_data[8:40].decode("ascii", errors="replace").strip()
        self.volume_id = pvd_data[40:72].decode("ascii", errors="replace").strip()

        root_record = pvd_data[156:190]
        root_lba = struct.unpack_from("<I", root_record, 2)[0]
        root_size = struct.unpack_from("<I", root_record, 10)[0]

        self.root = ISODirectory(
            name="/",
            lba=root_lba,
            size=root_size,
            path="",
            is_directory=True,
        )

        self._read_directory(self.root)

    def _read_directory(self, dir_node: ISODirectory) -> None:
        assert self._fp is not None
        self._fp.seek(dir_node.lba * SECTOR_SIZE)
        raw_dir_data = self._fp.read(dir_node.size)

        offset = 0
        total_len = len(raw_dir_data)

        while offset < total_len:
            sector_offset = offset % SECTOR_SIZE
            if sector_offset >= SECTOR_SIZE:
                continue

            rec_len = raw_dir_data[offset]
            if rec_len == 0:
                remaining = SECTOR_SIZE - sector_offset
                offset += remaining
                continue

            if offset + rec_len > total_len:
                break

            record = raw_dir_data[offset : offset + rec_len]
            ext_lba = struct.unpack_from("<I", record, 2)[0]
            data_len = struct.unpack_from("<I", record, 10)[0]
            flags = record[25]
            name_len = record[32]

            name_bytes = record[33 : 33 + name_len]
            offset += rec_len

            if name_bytes in (b"\x00", b"\x01"):
                continue

            name = name_bytes.decode("latin-1", errors="replace")
            if ";" in name:
                name = name.split(";")[0]

            item_path = f"{dir_node.path}/{name}" if dir_node.path else name
            is_dir = bool(flags & 2)

            if is_dir:
                sub_dir = ISODirectory(
                    name=name,
                    lba=ext_lba,
                    size=data_len,
                    path=item_path,
                    is_directory=True,
                )
                dir_node.children.append(sub_dir)
                self._read_directory(sub_dir)
            else:
                file_item = ISOFile(
                    name=name,
                    lba=ext_lba,
                    size=data_len,
                    path=item_path,
                    is_directory=False,
                )
                dir_node.children.append(file_item)

    def find_entry(self, virtual_path: str) -> Optional[Union[ISOFile, ISODirectory]]:
        if not self.root:
            return None

        clean_path = virtual_path.strip("/").replace("\\", "/")
        if not clean_path:
            return self.root

        parts = clean_path.split("/")
        current = self.root

        for part in parts:
            part_lower = part.lower()
            found = None
            if not isinstance(current, ISODirectory):
                return None

            for child in current.children:
                if child.name.lower() == part_lower:
                    found = child
                    break

            if not found:
                return None
            current = found  # type: ignore

        return current

    def read_file_bytes(self, item: ISOFile, max_bytes: Optional[int] = None) -> bytes:
        if item.replacement_bytes is not None:
            return item.replacement_bytes[:max_bytes] if max_bytes else item.replacement_bytes

        if item.replacement_path and item.replacement_path.exists():
            with open(item.replacement_path, "rb") as r_fp:
                return r_fp.read(max_bytes) if max_bytes else r_fp.read()

        assert self._fp is not None
        bytes_to_read = item.size if max_bytes is None else min(item.size, max_bytes)
        self._fp.seek(item.lba * SECTOR_SIZE)
        return self._fp.read(bytes_to_read)

    def extract_file(
        self,
        item: ISOFile,
        destination_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if item.replacement_bytes is not None:
            dest.write_bytes(item.replacement_bytes)
            if progress_callback:
                progress_callback(len(item.replacement_bytes), len(item.replacement_bytes))
            return

        if item.replacement_path and item.replacement_path.exists():
            source_fp = open(item.replacement_path, "rb")
            file_size = item.effective_size
        else:
            assert self._fp is not None
            self._fp.seek(item.lba * SECTOR_SIZE)
            source_fp = self._fp
            file_size = item.size

        remaining = file_size
        written = 0

        with open(dest, "wb") as out_fp:
            while remaining > 0:
                current_chunk = min(chunk_size, remaining)
                buffer = source_fp.read(current_chunk)
                if not buffer:
                    break
                out_fp.write(buffer)
                remaining -= len(buffer)
                written += len(buffer)
                if progress_callback:
                    progress_callback(written, file_size)

        if item.replacement_path and item.replacement_path.exists():
            source_fp.close()

    def get_total_uncompressed_size(self, node: Optional[Union[ISOFile, ISODirectory]] = None) -> int:
        target = node or self.root
        if not target:
            return 0
        if isinstance(target, ISOFile):
            return target.effective_size

        total = 0
        for child in target.children:
            if isinstance(child, ISOFile):
                total += child.effective_size
            else:
                total += self.get_total_uncompressed_size(child)
        return total

    def extract_directory(
        self,
        dir_item: ISODirectory,
        dest_folder: Union[str, Path],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        dest = Path(dest_folder)
        dest.mkdir(parents=True, exist_ok=True)

        total_bytes = self.get_total_uncompressed_size(dir_item)
        extracted_bytes = 0

        def _extract_recursive(current_dir: ISODirectory, current_target_path: Path) -> None:
            nonlocal extracted_bytes
            for child in current_dir.children:
                child_dest = current_target_path / child.name
                if isinstance(child, ISODirectory):
                    child_dest.mkdir(parents=True, exist_ok=True)
                    _extract_recursive(child, child_dest)
                elif isinstance(child, ISOFile):
                    def file_progress(done_in_file: int, file_size: int) -> None:
                        if progress_callback:
                            current_total_done = extracted_bytes + done_in_file
                            progress_callback(current_total_done, total_bytes, child.path)

                    self.extract_file(child, child_dest, progress_callback=file_progress, chunk_size=chunk_size)
                    extracted_bytes += child.effective_size

        _extract_recursive(dir_item, dest)