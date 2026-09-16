"""Интерфейс модуля UMD Convertor (ISO ↔ CSO сжатие и распаковка)."""

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
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from formats.cso import CSOConverter


class CSOConversionWorker(QThread):
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
    """Вкладка UMD Convertor с двухколоночным интерфейсом со сплиттером."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.worker: Optional[CSOConversionWorker] = None
        self.input_file: Optional[Path] = None
        self.output_file: Optional[Path] = None

        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ЛЕВАЯ КОЛОНКА (Управление и параметры)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Режим конвертации
        mode_box = QGroupBox("1. Режим работы")
        mode_layout = QVBoxLayout(mode_box)

        self.radio_compress = QRadioButton("Сжатие: ISO → CSO (Экономия места на флешке)")
        self.radio_compress.setChecked(True)
        self.radio_decompress = QRadioButton("Распаковка: CSO → ISO (Восстановление оригинала)")

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_compress)
        self.mode_group.addButton(self.radio_decompress)
        self.mode_group.buttonToggled.connect(self._on_mode_changed)

        mode_layout.addWidget(self.radio_compress)
        mode_layout.addWidget(self.radio_decompress)
        left_layout.addWidget(mode_box)

        # 2. Выбор файлов
        files_box = QGroupBox("2. Выбор файлов")
        files_layout = QVBoxLayout(files_box)

        files_layout.addWidget(QLabel("Входной образ (ISO или CSO):"))
        in_row = QHBoxLayout()
        self.edit_input = QLineEdit()
        self.edit_input.setReadOnly(True)
        self.edit_input.setPlaceholderText("Выберите или перетащите файл сюда...")
        self.btn_browse_in = QPushButton("Обзор...")
        self.btn_browse_in.clicked.connect(self._browse_input)
        in_row.addWidget(self.edit_input)
        in_row.addWidget(self.btn_browse_in)
        files_layout.addLayout(in_row)

        files_layout.addWidget(QLabel("Куда сохранить готовый файл:"))
        out_row = QHBoxLayout()
        self.edit_output = QLineEdit()
        self.edit_output.setReadOnly(True)
        self.edit_output.setPlaceholderText("Путь к новому файлу сформируется автоматически...")
        self.btn_browse_out = QPushButton("Изменить...")
        self.btn_browse_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.edit_output)
        out_row.addWidget(self.btn_browse_out)
        files_layout.addLayout(out_row)

        left_layout.addWidget(files_box)

        # 3. Степень сжатия
        self.comp_box = QGroupBox("3. Степень компрессии zlib")
        comp_layout = QVBoxLayout(self.comp_box)

        slider_row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 9)
        self.slider.setValue(9)
        self.slider.setTickInterval(1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.lbl_level = QLabel("<b>Уровень: 9 (Макс.)</b>")
        slider_row.addWidget(self.slider)
        slider_row.addWidget(self.lbl_level)
        comp_layout.addLayout(slider_row)
        left_layout.addWidget(self.comp_box)

        # 4. Блок запуска и прогресса
        control_box = QGroupBox("4. Процесс конвертации")
        ctrl_layout = QVBoxLayout(control_box)

        self.lbl_status = QLabel("Ожидание выбора файла...")
        self.lbl_status.setStyleSheet("color: #9295a8;")
        ctrl_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        ctrl_layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Начать конвертацию")
        self.btn_start.setFixedHeight(38)
        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet("font-weight: bold;")
        self.btn_start.clicked.connect(self._start_conversion)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_conversion)

        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_cancel)
        ctrl_layout.addLayout(btn_row)

        left_layout.addWidget(control_box)
        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # ПРАВАЯ КОЛОНКА (Инфопанель и статистика)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.info_box = QGroupBox("Информация и статистика")
        info_layout = QVBoxLayout(self.info_box)

        self.txt_info = QTextEdit()
        self.txt_info.setReadOnly(True)
        self.txt_info.setPlaceholderText(
            "Здесь отобразится информация:\n"
            " • Исходный и итоговый размер файла\n"
            " • Процент сэкономленного места на карте памяти\n"
            " • Текущий статус обработки блоков"
        )
        info_layout.addWidget(self.txt_info)

        right_layout.addWidget(self.info_box)
        splitter.addWidget(right_widget)

        splitter.setSizes([520, 560])
        main_layout.addWidget(splitter)

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
        self.edit_input.setText(f"{path.name} ({sz_mb:.1f} МБ)")
        self._auto_set_output_path()
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("Готов к запуску")
        self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")

        mode_str = "Сжатие в CSO (экономия памяти)" if self.radio_compress.isChecked() else "Распаковка в ISO"
        self.txt_info.setPlainText(
            f"=== ВХОДНОЙ ФАЙЛ ===\n"
            f"Файл: {path.name}\n"
            f"Размер: {sz_mb:.1f} МБ ({path.stat().st_size:,} байт)\n"
            f"Режим: {mode_str}\n\n"
            f"Нажмите 'Начать конвертацию', чтобы запустить процесс."
        )

    def _auto_set_output_path(self) -> None:
        if not self.input_file:
            return
        is_compress = self.radio_compress.isChecked()
        ext = ".cso" if is_compress else ".iso"
        self.output_file = self.input_file.with_suffix(ext)
        self.edit_output.setText(self.output_file.name)

    def _browse_output(self) -> None:
        if not self.input_file:
            return
        is_compress = self.radio_compress.isChecked()
        filter_str = "CSO Images (*.cso);;All Files (*.*)" if is_compress else "ISO Images (*.iso);;All Files (*.*)"
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как", str(self.output_file), filter_str)
        if path:
            self.output_file = Path(path)
            self.edit_output.setText(self.output_file.name)

    def _start_conversion(self) -> None:
        if not self.input_file or not self.output_file:
            return

        if self.output_file.resolve() == self.input_file.resolve():
            QMessageBox.warning(self, "Предупреждение", "Нельзя перезаписывать исходный файл. Укажите другое имя.")
            return

        is_compress = self.radio_compress.isChecked()
        level = self.slider.value()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Конвертация началась...")
        self.lbl_status.setStyleSheet("color: #0070D1; font-weight: bold;")

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
            self.lbl_status.setStyleSheet("color: #e53935;")
            self.btn_cancel.setEnabled(False)

    def _on_progress(self, curr: int, total: int) -> None:
        if total > 0:
            pct = int((curr / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_status.setText(f"Обработка блоков: {curr} / {total} ({pct}%)")

    def _on_finished(self, msg: str) -> None:
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Операция успешно завершена!")
        self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)

        # Выводим финальную статистику в правое окно
        if self.input_file and self.output_file and self.output_file.exists():
            orig_sz = self.input_file.stat().st_size
            new_sz = self.output_file.stat().st_size
            saved = (orig_sz - new_sz) / (1024 * 1024)
            ratio = (1 - (new_sz / orig_sz)) * 100 if orig_sz > 0 else 0
            self.txt_info.setPlainText(
                f"=== РЕЗУЛЬТАТ КОНВЕРТАЦИИ ===\n\n"
                f"Файл: {self.output_file.name}\n"
                f"Исходный размер: {orig_sz / (1024*1024):.1f} МБ\n"
                f"Итоговый размер: {new_sz / (1024*1024):.1f} МБ\n"
                f"Сэкономлено: {saved:.1f} МБ ({ratio:.1f}%)\n\n"
                f"Статус: Готов к записи на Memory Stick!"
            )

        QMessageBox.information(self, "Готово", msg)

    def _on_error(self, err: str) -> None:
        self.lbl_status.setText("Ошибка при конвертации.")
        self.lbl_status.setStyleSheet("color: #e53935; font-weight: bold;")
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QMessageBox.critical(self, "Ошибка", f"Произошла ошибка:\n{err}")