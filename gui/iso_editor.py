"""Визуальный интерфейс UMD Editor для просмотра, извлечения и замены ресурсов в ISO."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.exceptions import ISOFormatError
from core.iso_rebuilder import ISORebuilder
from formats.iso import ISODirectory, ISOFile, ISOItem, ISOReader
from formats.sfo import SFO
from gui.widgets.xmb_preview import XMBPreviewWidget


class BatchExtractionWorker(QThread):
    progress = Signal(int, int, str)
    finished_success = Signal(str)
    error = Signal(str)

    def __init__(self, reader: ISOReader, item: ISOItem, dest_path: Path) -> None:
        super().__init__()
        self.reader = reader
        self.item = item
        self.dest_path = dest_path

    def run(self) -> None:
        try:
            if isinstance(self.item, ISOFile):
                self.reader.extract_file(
                    self.item,
                    self.dest_path,
                    progress_callback=lambda done, total: self.progress.emit(done, total, self.item.name),
                )
            elif isinstance(self.item, ISODirectory):
                self.reader.extract_directory(
                    self.item,
                    self.dest_path,
                    progress_callback=lambda done, total, name: self.progress.emit(done, total, name),
                )
            self.finished_success.emit(f"Успешно извлечено в:\n{self.dest_path}")
        except Exception as exc:
            self.error.emit(str(exc))


class ISORebuildWorker(QThread):
    progress = Signal(int, int, str)
    finished_success = Signal(str)
    error = Signal(str)

    def __init__(self, reader: ISOReader, dest_iso_path: Path) -> None:
        super().__init__()
        self.reader = reader
        self.dest_iso_path = dest_iso_path
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            ISORebuilder.rebuild(
                reader=self.reader,
                output_iso_path=self.dest_iso_path,
                progress_callback=lambda done, total, path: self.progress.emit(done, total, path),
                cancel_check=lambda: self._cancelled,
            )
            if not self._cancelled:
                self.finished_success.emit(f"Изменённый образ успешно сохранён:\n{self.dest_iso_path}")
        except Exception as exc:
            self.error.emit(str(exc))


class ISOEditorWidget(QWidget):
    """Виджет UMD Editor: браузер, извлечение и замена графики/файлов диска."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.reader: Optional[ISOReader] = None
        self.worker: Optional[Union[BatchExtractionWorker, ISORebuildWorker]] = None
        self.has_modifications = False

        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_open = QPushButton("Открыть ISO")
        self.btn_open.clicked.connect(self.open_file_dialog)
        toolbar.addWidget(self.btn_open)

        self.btn_extract_selected = QPushButton("Извлечь выбранное...")
        self.btn_extract_selected.clicked.connect(self.extract_selected)
        self.btn_extract_selected.setEnabled(False)
        toolbar.addWidget(self.btn_extract_selected)

        self.btn_extract_all = QPushButton("Распаковать весь ISO...")
        self.btn_extract_all.clicked.connect(self.extract_all)
        self.btn_extract_all.setEnabled(False)
        toolbar.addWidget(self.btn_extract_all)

        toolbar.addSpacing(15)

        self.btn_save_iso = QPushButton("Сохранить изменённый ISO...")
        self.btn_save_iso.clicked.connect(self.save_rebuilt_iso)
        self.btn_save_iso.setEnabled(False)
        toolbar.addWidget(self.btn_save_iso)

        toolbar.addStretch()
        main_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая колонка: дерево файлов
        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Имя", "Размер", "LBA (Сектор)", "Тип", "Статус"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        tree_layout.addWidget(self.tree)
        splitter.addWidget(tree_container)

        # Правая колонка: XMB Preview и технические параметры
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_box = QGroupBox("Предпросмотр PSP (XMB)")
        preview_layout = QVBoxLayout(self.preview_box)
        self.xmb_widget = XMBPreviewWidget()
        self.xmb_widget.replace_icon_requested.connect(self._replace_xmb_icon)
        self.xmb_widget.replace_pic_requested.connect(self._replace_xmb_pic)
        preview_layout.addWidget(self.xmb_widget)
        right_layout.addWidget(self.preview_box)

        self.info_box = QGroupBox("Параметры диска")
        info_layout = QVBoxLayout(self.info_box)
        self.lbl_volume = QLabel("<b>Том:</b> -")
        self.lbl_size = QLabel("<b>Размер ISO:</b> -")
        self.lbl_uncompressed = QLabel("<b>Размер файлов:</b> -")
        info_layout.addWidget(self.lbl_volume)
        info_layout.addWidget(self.lbl_size)
        info_layout.addWidget(self.lbl_uncompressed)
        right_layout.addWidget(self.info_box)
        right_layout.addStretch()

        splitter.addWidget(right_container)
        splitter.setSizes([620, 480])
        main_layout.addWidget(splitter)

        self.lbl_status = QLabel("")
        main_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(".iso"):
                event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.load_iso(Path(file_path))

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть образ PSP", "", "PSP ISO Images (*.iso *.ISO);;All Files (*.*)"
        )
        if path:
            self.load_iso(Path(path))

    def load_iso(self, path: Path) -> None:
        if self.reader:
            self.reader.close()

        try:
            self.reader = ISOReader(path)
            self.reader.open()
            self.has_modifications = False

            size_mb = path.stat().st_size / (1024 * 1024)
            uncompressed_mb = self.reader.get_total_uncompressed_size() / (1024 * 1024)

            self.lbl_volume.setText(f"<b>Том:</b> {self.reader.volume_id or 'Без метки'}")
            self.lbl_size.setText(f"<b>Размер ISO:</b> {size_mb:.2f} МБ")
            self.lbl_uncompressed.setText(f"<b>Размер файлов:</b> {uncompressed_mb:.2f} МБ")

            self._load_game_presentation()
            self._populate_tree()

            self.btn_extract_selected.setEnabled(True)
            self.btn_extract_all.setEnabled(True)
            self.btn_save_iso.setEnabled(False)
        except ISOFormatError as exc:
            QMessageBox.critical(self, "Ошибка ISO", f"Файл не является корректным образом ISO 9660:\n{exc}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка чтения", f"Не удалось открыть образ:\n{exc}")

    def _load_game_presentation(self) -> None:
        assert self.reader is not None
        title = "Неизвестная игра"
        game_id = ""

        sfo_entry = self.reader.find_entry("PSP_GAME/PARAM.SFO")
        if isinstance(sfo_entry, ISOFile):
            try:
                raw_sfo = self.reader.read_file_bytes(sfo_entry)
                sfo = SFO.from_bytes(raw_sfo)
                title = str(sfo.get("TITLE", title))
                game_id = str(sfo.get("DISC_ID", ""))
            except Exception:
                pass

        icon0_bytes = None
        icon0_entry = self.reader.find_entry("PSP_GAME/ICON0.PNG")
        if isinstance(icon0_entry, ISOFile):
            icon0_bytes = self.reader.read_file_bytes(icon0_entry)

        pic1_bytes = None
        pic1_entry = self.reader.find_entry("PSP_GAME/PIC1.PNG")
        if isinstance(pic1_entry, ISOFile):
            pic1_bytes = self.reader.read_file_bytes(pic1_entry)

        self.xmb_widget.update_data(icon0_bytes, pic1_bytes, title, game_id, can_replace=True)

    def _replace_xmb_icon(self) -> None:
        if not self.reader:
            return
        icon_entry = self.reader.find_entry("PSP_GAME/ICON0.PNG")
        if not isinstance(icon_entry, ISOFile):
            QMessageBox.warning(self, "Внимание", "В образе нет файла PSP_GAME/ICON0.PNG")
            return
        self._replace_file_dialog(icon_entry)

    def _replace_xmb_pic(self) -> None:
        if not self.reader:
            return
        pic_entry = self.reader.find_entry("PSP_GAME/PIC1.PNG")
        if not isinstance(pic_entry, ISOFile):
            QMessageBox.warning(self, "Внимание", "В образе нет файла PSP_GAME/PIC1.PNG")
            return
        self._replace_file_dialog(pic_entry)

    def _populate_tree(self) -> None:
        self.tree.clear()
        if not self.reader or not self.reader.root:
            return

        def add_node(item: Union[ISODirectory, ISOFile], parent_widget: Union[QTreeWidget, QTreeWidgetItem]) -> None:
            size_str = self._format_size(item.effective_size if isinstance(item, ISOFile) else item.size) if not item.is_directory else ""
            type_str = "Папка" if item.is_directory else "Файл"
            status_str = "[ИЗМЕНЁН]" if isinstance(item, ISOFile) and item.is_modified else ""

            node = QTreeWidgetItem([item.name, size_str, str(item.lba), type_str, status_str])
            node.setData(0, Qt.ItemDataRole.UserRole, item)

            if isinstance(item, ISOFile) and item.is_modified:
                node.setForeground(4, QColor("#ff9800"))
                font = node.font(0)
                font.setBold(True)
                node.setFont(0, font)

            if isinstance(parent_widget, QTreeWidget):
                parent_widget.addTopLevelItem(node)
            else:
                parent_widget.addChild(node)

            if isinstance(item, ISODirectory):
                for child in item.children:
                    add_node(child, node)

        for top_item in self.reader.root.children:
            add_node(top_item, self.tree)

        self.tree.expandToDepth(0)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} КБ"
        return f"{size_bytes / (1024 * 1024):.2f} МБ"

    def _on_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        self.btn_extract_selected.setEnabled(len(items) > 0)

    def _show_context_menu(self, position) -> None:
        item = self.tree.itemAt(position)
        if not item:
            return

        iso_item: ISOItem = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        action_text = "Извлечь папку..." if iso_item.is_directory else "Извлечь файл..."
        action_extract = menu.addAction(action_text)
        action_extract.triggered.connect(self.extract_selected)

        if isinstance(iso_item, ISOFile):
            menu.addSeparator()
            action_replace = menu.addAction("Заменить файл...")
            action_replace.triggered.connect(lambda: self._replace_file_dialog(iso_item))

            if iso_item.is_modified:
                action_revert = menu.addAction("Сбросить замену")
                action_revert.triggered.connect(lambda: self._revert_replacement(iso_item))

        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _replace_file_dialog(self, iso_file: ISOFile) -> None:
        filter_str = "PNG Images (*.png);;All Files (*.*)" if iso_file.name.lower().endswith(".png") else "All Files (*.*)"
        path, _ = QFileDialog.getOpenFileName(
            self, f"Выберите новый файл для замены '{iso_file.name}'", "", filter_str
        )
        if path:
            iso_file.replacement_path = Path(path)
            iso_file.replacement_bytes = None
            self.has_modifications = True
            self.btn_save_iso.setEnabled(True)

            if iso_file.path.upper().endswith("PARAM.SFO") or iso_file.path.upper().endswith(".PNG"):
                self._load_game_presentation()

            self._populate_tree()
            QMessageBox.information(
                self,
                "Файл заменён",
                f"Файл '{iso_file.name}' помечен для замены.\n"
                f"Новый источник:\n{path}\n\n"
                f"Чтобы применить изменения, нажмите 'Сохранить изменённый ISO...'.",
            )

    def _revert_replacement(self, iso_file: ISOFile) -> None:
        iso_file.replacement_path = None
        iso_file.replacement_bytes = None
        self._populate_tree()
        self._load_game_presentation()

    def extract_selected(self) -> None:
        selected = self.tree.selectedItems()
        if not selected or not self.reader:
            return

        iso_item: ISOItem = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if iso_item.is_directory:
            dest_dir = QFileDialog.getExistingDirectory(self, "Выберите папку для извлечения")
            if not dest_dir:
                return
            target_path = Path(dest_dir) / iso_item.name
            self._start_extraction(iso_item, target_path)
        else:
            dest_path, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", iso_item.name)
            if not dest_path:
                return
            self._start_extraction(iso_item, Path(dest_path))

    def extract_all(self) -> None:
        if not self.reader or not self.reader.root:
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "Выберите папку для распаковки всего ISO")
        if not dest_dir:
            return
        self._start_extraction(self.reader.root, Path(dest_dir))

    def _start_extraction(self, item: ISOItem, target: Path) -> None:
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_extract_selected.setEnabled(False)
        self.btn_extract_all.setEnabled(False)

        self.worker = BatchExtractionWorker(self.reader, item, target)
        self.worker.progress.connect(self._on_extract_progress)
        self.worker.finished_success.connect(self._on_action_success)
        self.worker.error.connect(self._on_action_error)
        self.worker.start()

    def save_rebuilt_iso(self) -> None:
        if not self.reader:
            return

        suggested = self.reader.path.stem + "_modified.iso"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить изменённый ISO как",
            str(self.reader.path.parent / suggested),
            "PSP ISO Images (*.iso *.ISO);;All Files (*.*)",
        )
        if not save_path:
            return

        if Path(save_path).resolve() == self.reader.path.resolve():
            QMessageBox.warning(
                self,
                "Предупреждение",
                "Нельзя перезаписывать исходный открытый ISO-образ напрямую во избежание сбоя.\n"
                "Пожалуйста, укажите другое имя файла.",
            )
            return

        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_save_iso.setEnabled(False)
        self.btn_extract_selected.setEnabled(False)
        self.btn_extract_all.setEnabled(False)

        worker = ISORebuildWorker(self.reader, Path(save_path))
        self.worker = worker
        worker.progress.connect(self._on_rebuild_progress)
        worker.finished_success.connect(self._on_rebuild_success)
        worker.error.connect(self._on_action_error)
        worker.start()

    def _on_extract_progress(self, done: int, total: int, current_file: str) -> None:
        if total > 0:
            pct = int((done / total) * 100)
            self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Извлечение: {current_file} ({done / (1024 * 1024):.1f} / {total / (1024 * 1024):.1f} МБ)")

    def _on_rebuild_progress(self, done: int, total: int, current_file: str) -> None:
        if total > 0:
            pct = int((done / total) * 100)
            self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Сборка ISO: {current_file} ({done / (1024 * 1024):.1f} / {total / (1024 * 1024):.1f} МБ)")

    def _on_rebuild_success(self, msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("Сборка успешно завершена!")
        self.btn_save_iso.setEnabled(True)
        self.btn_extract_selected.setEnabled(True)
        self.btn_extract_all.setEnabled(True)
        QMessageBox.information(self, "Успех", msg)

    def _on_action_success(self, msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("")
        self.btn_extract_selected.setEnabled(True)
        self.btn_extract_all.setEnabled(True)
        QMessageBox.information(self, "Готово", msg)

    def _on_action_error(self, err_msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("")
        self.btn_save_iso.setEnabled(True)
        self.btn_extract_selected.setEnabled(True)
        self.btn_extract_all.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", f"Произошла ошибка:\n{err_msg}")