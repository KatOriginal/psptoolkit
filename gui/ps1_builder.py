"""Интерфейс для конвертации дисков PS1 в EBOOT.PBP."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.ps1_builder import PS1EBOOTBuilder
from formats.cue import CUESheet, PS1DiscScanner
from gui.widgets.xmb_preview import XMBDisplayFrame


class PS1BuildWorker(QThread):
    """Фоновый поток для сжатия и сборки EBOOT.PBP."""

    progress = Signal(int, int)
    finished_success = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        bin_path: Path,
        output_pbp_path: Path,
        title: str,
        game_id: str,
        data_psp: bytes,
        icon0_png: bytes,
        pic1_png: bytes,
        compression_level: int,
    ) -> None:
        super().__init__()
        self.bin_path = bin_path
        self.output_pbp_path = output_pbp_path
        self.title = title
        self.game_id = game_id
        self.data_psp = data_psp
        self.icon0_png = icon0_png
        self.pic1_png = pic1_png
        self.compression_level = compression_level
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            PS1EBOOTBuilder.build_eboot(
                bin_path=self.bin_path,
                output_pbp_path=self.output_pbp_path,
                title=self.title,
                game_id=self.game_id,
                data_psp=self.data_psp,
                icon0_png=self.icon0_png,
                pic1_png=self.pic1_png,
                compression_level=self.compression_level,
                progress_callback=self.progress.emit,
                cancel_check=lambda: self._cancelled,
            )
            if not self._cancelled:
                sz_mb = self.output_pbp_path.stat().st_size / (1024 * 1024)
                msg = (
                    f"EBOOT.PBP успешно создан!\n\n"
                    f"Игра: {self.title} [{self.game_id}]\n"
                    f"Размер: {sz_mb:.1f} МБ\n"
                    f"Путь: {self.output_pbp_path}\n\n"
                    f"Скопируйте папку с файлом на PSP в: PSP/GAME/{self.game_id}/"
                )
                self.finished_success.emit(msg)
        except Exception as exc:
            self.error.emit(str(exc))


class PS1BuilderWidget(QWidget):
    """Вкладка PS1 to PSP EBOOT Builder."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.input_bin: Optional[Path] = None
        self.output_pbp: Optional[Path] = None
        self.icon0_bytes: bytes = b""
        self.pic1_bytes: bytes = b""
        self.data_psp_bytes: bytes = b""

        self.worker: Optional[PS1BuildWorker] = None

        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая колонка: параметры и ввод
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        disc_box = QGroupBox("Образ диска PS1 (.cue / .bin / .img)")
        disc_layout = QVBoxLayout(disc_box)

        file_pick_layout = QHBoxLayout()
        self.lbl_disc = QLabel("<b>Файл:</b> (перетащите .cue или .bin сюда)")
        self.btn_browse_disc = QPushButton("Обзор...")
        self.btn_browse_disc.clicked.connect(self._browse_disc)
        file_pick_layout.addWidget(self.lbl_disc)
        file_pick_layout.addStretch()
        file_pick_layout.addWidget(self.btn_browse_disc)
        disc_layout.addLayout(file_pick_layout)
        left_layout.addWidget(disc_box)

        meta_box = QGroupBox("Метаданные игры")
        meta_layout = QVBoxLayout(meta_box)

        meta_layout.addWidget(QLabel("Название игры:"))
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText("например, Crash Bandicoot")
        self.edit_title.textChanged.connect(self._update_preview)
        meta_layout.addWidget(self.edit_title)

        meta_layout.addWidget(QLabel("Game ID (Код диска):"))
        self.edit_game_id = QLineEdit()
        self.edit_game_id.setPlaceholderText("например, SCUS-94900")
        self.edit_game_id.textChanged.connect(self._update_preview)
        meta_layout.addWidget(self.edit_game_id)
        left_layout.addWidget(meta_box)

        opts_box = QGroupBox("Параметры сборки")
        opts_layout = QVBoxLayout(opts_box)

        comp_h_layout = QHBoxLayout()
        comp_h_layout.addWidget(QLabel("Компрессия:"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 9)
        self.slider.setValue(9)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.lbl_level = QLabel("Уровень: 9 (Макс.)")
        self.slider.valueChanged.connect(self._on_slider_changed)
        comp_h_layout.addWidget(self.slider)
        comp_h_layout.addWidget(self.lbl_level)
        opts_layout.addLayout(comp_h_layout)

        base_layout = QHBoxLayout()
        self.lbl_base = QLabel("BASE.PBP: [Встроенный эмулятор]")
        self.btn_select_base = QPushButton("Выбрать свой BASE.PBP...")
        self.btn_select_base.clicked.connect(self._browse_base_pbp)
        base_layout.addWidget(self.lbl_base)
        base_layout.addStretch()
        base_layout.addWidget(self.btn_select_base)
        opts_layout.addLayout(base_layout)

        left_layout.addWidget(opts_box)
        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # Правая колонка: XMB Preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_box = QGroupBox("Предпросмотр PSP (XMB)")
        preview_layout = QVBoxLayout(preview_box)

        self.xmb_frame = XMBDisplayFrame()
        preview_layout.addWidget(self.xmb_frame)

        art_btns = QHBoxLayout()
        self.btn_load_icon = QPushButton("Выбрать ICON0.PNG...")
        self.btn_load_icon.clicked.connect(self._browse_icon)
        self.btn_load_pic = QPushButton("Выбрать PIC1.PNG...")
        self.btn_load_pic.clicked.connect(self._browse_pic)
        self.btn_clear_art = QPushButton("Очистить")
        self.btn_clear_art.clicked.connect(self._clear_art)

        art_btns.addWidget(self.btn_load_icon)
        art_btns.addWidget(self.btn_load_pic)
        art_btns.addWidget(self.btn_clear_art)
        preview_layout.addLayout(art_btns)

        right_layout.addWidget(preview_box)
        right_layout.addStretch()
        splitter.addWidget(right_widget)

        splitter.setSizes([550, 500])
        main_layout.addWidget(splitter)

        # Нижняя панель действий и прогресс
        main_layout.addSpacing(10)
        self.lbl_status = QLabel("Выберите файл образа диска...")
        main_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        ctrl_btns = QHBoxLayout()
        self.btn_build = QPushButton("Собрать EBOOT.PBP")
        self.btn_build.setFixedHeight(36)
        self.btn_build.setEnabled(False)
        self.btn_build.clicked.connect(self._start_build)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_build)

        ctrl_btns.addWidget(self.btn_build)
        ctrl_btns.addWidget(self.btn_cancel)
        main_layout.addLayout(ctrl_btns)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                ext = urls[0].toLocalFile().lower()
                if ext.endswith((".cue", ".bin", ".img", ".iso")):
                    event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            self.load_disc_image(path)

    def _browse_disc(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите образ PS1",
            "",
            "PS1 Images (*.cue *.bin *.img *.iso);;All Files (*.*)",
        )
        if path:
            self.load_disc_image(Path(path))

    def load_disc_image(self, path: Path) -> None:
        target_bin = path
        if path.suffix.lower() == ".cue":
            try:
                cue = CUESheet.parse_file(path)
                candidate = path.parent / cue.bin_filename
                if candidate.exists():
                    target_bin = candidate
            except Exception:
                pass

        self.input_bin = target_bin
        sz_mb = target_bin.stat().st_size / (1024 * 1024)
        self.lbl_disc.setText(f"<b>Файл:</b> {target_bin.name} ({sz_mb:.1f} МБ)")

        detected_id = PS1DiscScanner.detect_game_id(target_bin)
        game_id = detected_id or "SLUS-00000"
        title = target_bin.stem.replace("_", " ").title()

        self.edit_game_id.setText(game_id)
        self.edit_title.setText(title)

        self._auto_detect_local_artwork(target_bin.parent)
        self._update_preview()

        self.btn_build.setEnabled(True)
        self.lbl_status.setText("Готов к сборке EBOOT.PBP")

    def _auto_detect_local_artwork(self, folder: Path) -> None:
        icon_candidate = folder / "ICON0.PNG"
        if not icon_candidate.exists():
            icon_candidate = folder / "icon0.png"
        if icon_candidate.exists():
            self.icon0_bytes = icon_candidate.read_bytes()

        pic_candidate = folder / "PIC1.PNG"
        if not pic_candidate.exists():
            pic_candidate = folder / "pic1.png"
        if pic_candidate.exists():
            self.pic1_bytes = pic_candidate.read_bytes()

    def _update_preview(self) -> None:
        title = self.edit_title.text().strip()
        gid = self.edit_game_id.text().strip()
        self.xmb_frame.set_assets(
            icon0_bytes=self.icon0_bytes if self.icon0_bytes else None,
            pic1_bytes=self.pic1_bytes if self.pic1_bytes else None,
            title=title,
            game_id=gid,
        )

    def _browse_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать иконку", "", "PNG Images (*.png)")
        if path:
            self.icon0_bytes = Path(path).read_bytes()
            self._update_preview()

    def _browse_pic(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать фоновый арт", "", "PNG Images (*.png)")
        if path:
            self.pic1_bytes = Path(path).read_bytes()
            self._update_preview()

    def _clear_art(self) -> None:
        self.icon0_bytes = b""
        self.pic1_bytes = b""
        self._update_preview()

    def _browse_base_pbp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать BASE.PBP", "", "PBP Files (*.PBP *.pbp)")
        if path:
            try:
                from formats.pbp import PBPReader

                reader = PBPReader(path)
                data_psp = reader.read_section("data_psp")
                if data_psp:
                    self.data_psp_bytes = data_psp
                    self.lbl_base.setText(f"BASE.PBP: {Path(path).name} (OK)")
                else:
                    QMessageBox.warning(self, "Внимание", "В выбранном файле нет секции DATA.PSP.")
            except Exception as exc:
                QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать BASE.PBP:\n{exc}")

    def _on_slider_changed(self, val: int) -> None:
        if val == 0:
            descr = "0 (Без сжатия)"
        elif val == 9:
            descr = "9 (Макс. сжатие)"
        else:
            descr = str(val)
        self.lbl_level.setText(f"Уровень: {descr}")

    def _start_build(self) -> None:
        if not self.input_bin:
            return

        title = self.edit_title.text().strip() or "PS1 Game"
        game_id = self.edit_game_id.text().strip() or "SLUS-00000"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить EBOOT.PBP как",
            str(self.input_bin.parent / "EBOOT.PBP"),
            "PSP EBOOT (*.PBP);;All Files (*.*)",
        )
        if not save_path:
            return

        self.btn_build.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Сборка PS1 EBOOT.PBP началась...")

        self.worker = PS1BuildWorker(
            bin_path=self.input_bin,
            output_pbp_path=Path(save_path),
            title=title,
            game_id=game_id,
            data_psp=self.data_psp_bytes,
            icon0_png=self.icon0_bytes,
            pic1_png=self.pic1_bytes,
            compression_level=self.slider.value(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _cancel_build(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText("Отмена сборки...")
            self.btn_cancel.setEnabled(False)

    def _on_progress(self, curr: int, total: int) -> None:
        if total > 0:
            pct = int((curr / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_status.setText(f"Сжатие блоков PSISOIMG: {curr} / {total} ({pct}%)")

    def _on_finished(self, msg: str) -> None:
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Сборка успешно завершена!")
        self.btn_build.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QMessageBox.information(self, "Готово", msg)

    def _on_error(self, err: str) -> None:
        self.lbl_status.setText("Ошибка при сборке.")
        self.btn_build.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QMessageBox.critical(self, "Ошибка сборки", f"Произошла ошибка:\n{err}")