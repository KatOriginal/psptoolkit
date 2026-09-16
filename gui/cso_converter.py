"""Интерфейс для конвертации ISO ↔ CSO с прогрессом и отменой."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from formats.cso import CSOConverter


class CSOConversionWorker(QThread):
    """Фоновый рабочий поток конвертации."""

    progress = Signal(int, int)
    finished_success = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        is_compression: bool,
        input_path: Path,
        output_path: Path,
        compression_level: int = 9,
    ) -> None:
        super().__init__()
        self.is_compression = is_compression
        self.input_path = input_path
        self.output_path = output_path
        self.compression_level = compression_level
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            if self.is_compression:
                CSOConverter.compress_iso_to_cso(
                    iso_path=self.input_path,
                    cso_path=self.output_path,
                    compression_level=self.compression_level,
                    progress_callback=self.progress.emit,
                    cancel_check=lambda: self._cancelled,
                )
                if not self._cancelled:
                    orig_sz = self.input_path.stat().st_size
                    new_sz = self.output_path.stat().st_size
                    saved = (orig_sz - new_sz) / (1024 * 1024)
                    ratio = (1 - (new_sz / orig_sz)) * 100 if orig_sz > 0 else 0
                    msg = (
                        f"Сжатие успешно завершено!\n\n"
                        f"Исходный размер: {orig_sz / (1024*1024):.1f} МБ\n"
                        f"Итоговый размер: {new_sz / (1024*1024):.1f} МБ\n"
                        f"Сэкономлено: {saved:.1f} МБ ({ratio:.1f}%)"
                    )
                    self.finished_success.emit(msg)
            else:
                CSOConverter.decompress_cso_to_iso(
                    cso_path=self.input_path,
                    iso_path=self.output_path,
                    progress_callback=self.progress.emit,
                    cancel_check=lambda: self._cancelled,
                )
                if not self._cancelled:
                    new_sz = self.output_path.stat().st_size
                    self.finished_success.emit(
                        f"Распаковка успешно завершена!\n\n"
                        f"Размер полученного ISO: {new_sz / (1024*1024):.1f} МБ"
                    )
        except Exception as exc:
            self.error.emit(str(exc))


class CSOConverterWidget(QWidget):
    """Вкладка конвертера ISO ↔ CSO."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.worker: Optional[CSOConversionWorker] = None
        self.input_file: Optional[Path] = None
        self.output_file: Optional[Path] = None

        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # Выбор режима
        mode_box = QGroupBox("Режим конвертации")
        mode_layout = QHBoxLayout(mode_box)

        self.radio_compress = QRadioButton("Сжатие: ISO → CSO")
        self.radio_compress.setChecked(True)
        self.radio_decompress = QRadioButton("Распаковка: CSO → ISO")

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_compress)
        self.mode_group.addButton(self.radio_decompress)
        self.mode_group.buttonToggled.connect(self._on_mode_changed)

        mode_layout.addWidget(self.radio_compress)
        mode_layout.addWidget(self.radio_decompress)
        mode_layout.addStretch()
        main_layout.addWidget(mode_box)

        # Выбор файлов
        files_box = QGroupBox("Файлы")
        files_layout = QVBoxLayout(files_box)

        in_layout = QHBoxLayout()
        self.lbl_input = QLabel("<b>Входной файл:</b> (перетащите файл сюда)")
        self.btn_browse_in = QPushButton("Обзор...")
        self.btn_browse_in.clicked.connect(self._browse_input)
        in_layout.addWidget(self.lbl_input)
        in_layout.addStretch()
        in_layout.addWidget(self.btn_browse_in)
        files_layout.addLayout(in_layout)

        out_layout = QHBoxLayout()
        self.lbl_output = QLabel("<b>Выходной файл:</b> -")
        self.btn_browse_out = QPushButton("Изменить путь...")
        self.btn_browse_out.clicked.connect(self._browse_output)
        out_layout.addWidget(self.lbl_output)
        out_layout.addStretch()
        out_layout.addWidget(self.btn_browse_out)
        files_layout.addLayout(out_layout)

        main_layout.addWidget(files_box)

        # Степень сжатия
        self.comp_box = QGroupBox("Степень компрессии zlib (1 - быстро, 9 - максимально сжато)")
        comp_layout = QHBoxLayout(self.comp_box)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 9)
        self.slider.setValue(9)
        self.slider.setTickInterval(1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.lbl_level = QLabel("<b>Уровень: 9</b> (Рекомендуется)")
        comp_layout.addWidget(self.slider)
        comp_layout.addWidget(self.lbl_level)
        main_layout.addWidget(self.comp_box)

        # Прогресс и управление
        main_layout.addSpacing(10)
        self.lbl_status = QLabel("Ожидание выбора файла...")
        main_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Начать конвертацию")
        self.btn_start.setFixedHeight(36)
        self.btn_start.clicked.connect(self._start_conversion)
        self.btn_start.setEnabled(False)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.clicked.connect(self._cancel_conversion)
        self.btn_cancel.setEnabled(False)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)
        main_layout.addStretch()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                ext = urls[0].toLocalFile().lower()
                if ext.endswith(".iso") or ext.endswith(".cso"):
                    event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            self._set_input_path(path)

    def _on_mode_changed(self) -> None:
        is_compress = self.radio_compress.isChecked()
        self.comp_box.setVisible(is_compress)
        if self.input_file:
            self._auto_set_output_path()

    def _on_slider_changed(self, val: int) -> None:
        descr = " (Рекомендуется)" if val == 9 else " (Быстро)" if val <= 3 else ""
        self.lbl_level.setText(f"<b>Уровень: {val}</b>{descr}")

    def _browse_input(self) -> None:
        is_compress = self.radio_compress.isChecked()
        filter_str = "ISO Images (*.iso *.ISO);;All Files (*.*)" if is_compress else "CSO Images (*.cso *.CSO);;All Files (*.*)"
        title = "Выберите файл ISO для сжатия" if is_compress else "Выберите файл CSO для распаковки"
        path, _ = QFileDialog.getOpenFileName(self, title, "", filter_str)
        if path:
            self._set_input_path(Path(path))

    def _set_input_path(self, path: Path) -> None:
        self.input_file = path
        if path.suffix.lower() == ".cso":
            self.radio_decompress.setChecked(True)
        elif path.suffix.lower() == ".iso":
            self.radio_compress.setChecked(True)

        sz_mb = path.stat().st_size / (1024 * 1024)
        self.lbl_input.setText(f"<b>Входной:</b> {path.name} ({sz_mb:.1f} МБ)")
        self._auto_set_output_path()
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("Готов к запуску")

    def _auto_set_output_path(self) -> None:
        if not self.input_file:
            return
        is_compress = self.radio_compress.isChecked()
        ext = ".cso" if is_compress else ".iso"
        self.output_file = self.input_file.with_suffix(ext)
        self.lbl_output.setText(f"<b>Выходной:</b> {self.output_file.name} ({self.output_file.parent})")

    def _browse_output(self) -> None:
        if not self.input_file:
            return
        is_compress = self.radio_compress.isChecked()
        filter_str = "CSO Images (*.cso);;All Files (*.*)" if is_compress else "ISO Images (*.iso);;All Files (*.*)"
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как", str(self.output_file), filter_str)
        if path:
            self.output_file = Path(path)
            self.lbl_output.setText(f"<b>Выходной:</b> {self.output_file.name} ({self.output_file.parent})")

    def _start_conversion(self) -> None:
        if not self.input_file or not self.output_file:
            return

        is_compress = self.radio_compress.isChecked()
        level = self.slider.value()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Конвертация началась...")

        self.worker = CSOConversionWorker(
            is_compression=is_compress,
            input_path=self.input_file,
            output_path=self.output_file,
            compression_level=level,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _cancel_conversion(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText("Отмена операции...")
            self.btn_cancel.setEnabled(False)

    def _on_progress(self, curr: int, total: int) -> None:
        if total > 0:
            pct = int((curr / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_status.setText(f"Обработка блоков: {curr} / {total} ({pct}%)")

    def _on_finished(self, msg: str) -> None:
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Операция успешно завершена!")
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QMessageBox.information(self, "Готово", msg)

    def _on_error(self, err: str) -> None:
        self.lbl_status.setText("Ошибка при конвертации.")
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QMessageBox.critical(self, "Ошибка", f"Произошла ошибка:\n{err}")