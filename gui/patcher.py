"""Интерфейс модуля UMD Patcher (PPF, XDelta, моды из архивов и папок)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.mod_patcher import ModPatcher
from formats.ppf import PPFPatcher
from formats.xdelta import XDeltaPatcher


class PatcherWorker(QThread):
    progress = Signal(int, int, str)
    finished_success = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        is_binary_patch: bool,
        iso_path: Path,
        patch_path: Path,
        out_iso_path: Path,
        force_checksum: bool = True,
    ) -> None:
        super().__init__()
        self.is_binary_patch = is_binary_patch
        self.iso_path = iso_path
        self.patch_path = patch_path
        self.out_iso_path = out_iso_path
        self.force_checksum = force_checksum
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            if self.is_binary_patch:
                ext = self.patch_path.suffix.lower()
                if ext == ".xdelta":
                    XDeltaPatcher.apply_to_iso(
                        source_iso=self.iso_path,
                        patch_path=self.patch_path,
                        output_iso=self.out_iso_path,
                        force_checksum=self.force_checksum,
                        progress_callback=lambda curr, total, msg: self.progress.emit(curr, total, msg),
                        cancel_check=lambda: self._cancelled,
                    )
                else:
                    PPFPatcher.apply_patch(
                        source_iso=self.iso_path,
                        ppf_path=self.patch_path,
                        output_iso=self.out_iso_path,
                        progress_callback=lambda curr, total: self.progress.emit(curr, total, "Применение PPF патча..."),
                        cancel_check=lambda: self._cancelled,
                    )
                if not self._cancelled:
                    self.finished_success.emit(f"Патч успешно применён!\n\nГотовый образ:\n{self.out_iso_path}")
            else:
                replaced = ModPatcher.apply_mod_package(
                    source_iso=self.iso_path,
                    mod_source=self.patch_path,
                    output_iso=self.out_iso_path,
                    progress_callback=lambda curr, total, name: self.progress.emit(curr, total, f"Интеграция: {name}"),
                    cancel_check=lambda: self._cancelled,
                )
                if not self._cancelled:
                    self.finished_success.emit(
                        f"Мод/Русификатор успешно установлен!\n\n"
                        f"Заменено/пропатчено файлов: {replaced}\n"
                        f"Готовый образ:\n{self.out_iso_path}"
                    )
        except Exception as exc:
            self.error.emit(str(exc))


class PatcherWidget(QWidget):
    """Вкладка UMD Patcher с двухколоночным интерфейсом."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.input_iso: Optional[Path] = None
        self.patch_source: Optional[Path] = None
        self.output_iso: Optional[Path] = None

        self.worker: Optional[PatcherWorker] = None

        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ЛЕВАЯ КОЛОНКА
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Тип патча
        type_box = QGroupBox("1. Тип патча или модификации")
        type_layout = QVBoxLayout(type_box)

        self.radio_binary = QRadioButton("Бинарный патч (.xdelta / .ppf)")
        self.radio_mod = QRadioButton("Мод / Русификатор (Архив .7z/.zip/.rar или папка)")
        self.radio_binary.setChecked(True)

        self.type_group = QButtonGroup(self)
        self.type_group.addButton(self.radio_binary)
        self.type_group.addButton(self.radio_mod)
        self.type_group.buttonToggled.connect(self._on_type_changed)

        type_layout.addWidget(self.radio_binary)
        type_layout.addWidget(self.radio_mod)

        # Чекбокс совместимости контрольной суммы
        self.chk_force_checksum = QCheckBox("Игнорировать проверку контрольной суммы (-n)")
        self.chk_force_checksum.setChecked(True)
        self.chk_force_checksum.setToolTip("Позволяет применить патч, даже если версия дампа игры незначительно отличается")
        type_layout.addWidget(self.chk_force_checksum)

        left_layout.addWidget(type_box)

        # 2. Файлы
        files_box = QGroupBox("2. Выбор файлов")
        files_layout = QVBoxLayout(files_box)

        files_layout.addWidget(QLabel("Исходный чистый ISO-образ:"))
        iso_row = QHBoxLayout()
        self.edit_iso = QLineEdit()
        self.edit_iso.setReadOnly(True)
        self.edit_iso.setPlaceholderText("Выберите или перетащите файл .iso сюда...")
        self.btn_browse_iso = QPushButton("Обзор...")
        self.btn_browse_iso.clicked.connect(self._browse_iso)
        iso_row.addWidget(self.edit_iso)
        iso_row.addWidget(self.btn_browse_iso)
        files_layout.addLayout(iso_row)

        self.lbl_patch_title = QLabel("Файл патча (.xdelta или .ppf):")
        files_layout.addWidget(self.lbl_patch_title)
        patch_row = QHBoxLayout()
        self.edit_patch = QLineEdit()
        self.edit_patch.setReadOnly(True)
        self.edit_patch.setPlaceholderText("Выберите файл патча или архив мода...")
        self.btn_browse_patch = QPushButton("Выбрать патч...")
        self.btn_browse_patch.clicked.connect(self._browse_patch)
        self.btn_browse_folder = QPushButton("Папка...")
        self.btn_browse_folder.clicked.connect(self._browse_patch_folder)
        self.btn_browse_folder.setVisible(False)

        patch_row.addWidget(self.edit_patch)
        patch_row.addWidget(self.btn_browse_patch)
        patch_row.addWidget(self.btn_browse_folder)
        files_layout.addLayout(patch_row)

        files_layout.addWidget(QLabel("Готовый пропатченный ISO:"))
        out_row = QHBoxLayout()
        self.edit_out = QLineEdit()
        self.edit_out.setReadOnly(True)
        self.edit_out.setPlaceholderText("Путь к новому образу сформируется автоматически...")
        self.btn_browse_out = QPushButton("Изменить...")
        self.btn_browse_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.edit_out)
        out_row.addWidget(self.btn_browse_out)
        files_layout.addLayout(out_row)

        left_layout.addWidget(files_box)

        # 3. Управление
        control_box = QGroupBox("3. Применение патча")
        ctrl_layout = QVBoxLayout(control_box)

        self.lbl_status = QLabel("Ожидание выбора файлов...")
        self.lbl_status.setStyleSheet("color: #9295a8;")
        ctrl_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        ctrl_layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.btn_apply = QPushButton("Применить патч")
        self.btn_apply.setFixedHeight(38)
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet("font-weight: bold;")
        self.btn_apply.clicked.connect(self._start_patching)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_patching)

        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_cancel)
        ctrl_layout.addLayout(btn_row)

        left_layout.addWidget(control_box)
        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # ПРАВАЯ КОЛОНКА
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.info_box = QGroupBox("Информация о патче и список файлов")
        info_layout = QVBoxLayout(self.info_box)

        self.txt_info = QTextEdit()
        self.txt_info.setReadOnly(True)
        self.txt_info.setPlaceholderText("Здесь появится описание патча...")
        info_layout.addWidget(self.txt_info)

        right_layout.addWidget(self.info_box)
        splitter.addWidget(right_widget)

        splitter.setSizes([520, 560])
        main_layout.addWidget(splitter)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) >= 1:
                event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        for u in urls:
            path = Path(u.toLocalFile())
            if path.suffix.lower() == ".iso":
                self._set_iso_path(path)
            elif path.suffix.lower() in (".xdelta", ".ppf", ".zip", ".7z", ".rar") or path.is_dir():
                self._set_patch_path(path)

    def _on_type_changed(self) -> None:
        is_binary = self.radio_binary.isChecked()
        self.btn_browse_folder.setVisible(not is_binary)
        self.chk_force_checksum.setVisible(is_binary)
        if is_binary:
            self.lbl_patch_title.setText("Файл патча (.xdelta или .ppf):")
            self.btn_browse_patch.setText("Выбрать патч...")
        else:
            self.lbl_patch_title.setText("Файлы мода / русификатора (архив или папка):")
            self.btn_browse_patch.setText("Выбрать архив...")

    def _browse_iso(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите чистый ISO-образ", "", "PSP ISO Images (*.iso *.ISO);;All Files (*.*)"
        )
        if path:
            self._set_iso_path(Path(path))

    def _set_iso_path(self, path: Path) -> None:
        self.input_iso = path
        sz_mb = path.stat().st_size / (1024 * 1024)
        self.edit_iso.setText(f"{path.name} ({sz_mb:.1f} МБ)")
        self._auto_set_output_path()
        self._check_ready()

    def _browse_patch(self) -> None:
        if self.radio_binary.isChecked():
            filter_str = "Binary Patches (*.xdelta *.ppf);;xdelta (*.xdelta);;PPF (*.ppf);;All Files (*.*)"
            title = "Выберите файл патча (.xdelta или .ppf)"
        else:
            filter_str = "Archives (*.7z *.zip *.rar);;7-Zip (*.7z);;ZIP (*.zip);;RAR (*.rar);;All Files (*.*)"
            title = "Выберите архив с модом"

        path, _ = QFileDialog.getOpenFileName(self, title, "", filter_str)
        if path:
            self._set_patch_path(Path(path))

    def _browse_patch_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с файлами русификатора/мода")
        if folder:
            self._set_patch_path(Path(folder))

    def _set_patch_path(self, path: Path) -> None:
        self.patch_source = path
        ext = path.suffix.lower()
        self.edit_patch.setText(path.name)

        if ext == ".xdelta":
            self.radio_binary.setChecked(True)
            self.txt_info.setPlainText(
                f"=== БИНАРНЫЙ ПАТЧ XDELTA3 ===\n"
                f"Файл: {path.name}\n"
                f"Размер: {path.stat().st_size / (1024*1024):.1f} МБ\n\n"
                f"Патч готов к применению. Включен режим совместимости контрольной суммы (-n)."
            )
        elif ext == ".ppf":
            self.radio_binary.setChecked(True)
            try:
                info = PPFPatcher.read_info(path)
                self.txt_info.setPlainText(
                    f"=== БИНАРНЫЙ ПАТЧ PPF v{info.version}.0 ===\n"
                    f"Файл: {path.name}\n"
                    f"Описание от авторов: {info.description or 'Без описания'}\n"
                    f"Проверка блоков (Blockcheck): {'Включена' if info.has_blockcheck else 'Отключена'}"
                )
            except Exception as exc:
                self.txt_info.setPlainText(f"Ошибка чтения PPF: {exc}")
        else:
            self.radio_mod.setChecked(True)
            try:
                files = ModPatcher.inspect_mod(path)
                file_list_str = "\n".join(f"  • {f}" for f in files[:40])
                if len(files) > 40:
                    file_list_str += f"\n  ... и ещё {len(files) - 40} файлов."
                self.txt_info.setPlainText(
                    f"=== ПАКЕТ МОДИФИКАЦИИ / ПЕРЕВОДА ===\n"
                    f"Источник: {path.name}\n"
                    f"Найдено элементов: {len(files)}\n\n"
                    f"Список файлов:\n{file_list_str}"
                )
            except Exception as exc:
                self.txt_info.setPlainText(f"Ошибка анализа архива/папки: {exc}")

        self._auto_set_output_path()
        self._check_ready()

    def _auto_set_output_path(self) -> None:
        if not self.input_iso:
            return
        suffix = "_patched.iso"
        self.output_iso = self.input_iso.with_name(self.input_iso.stem + suffix)
        self.edit_out.setText(self.output_iso.name)

    def _browse_output(self) -> None:
        if not self.output_iso:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить пропатченный ISO как", str(self.output_iso), "ISO Images (*.iso);;All Files (*.*)"
        )
        if path:
            self.output_iso = Path(path)
            self.edit_out.setText(self.output_iso.name)

    def _check_ready(self) -> None:
        ready = self.input_iso is not None and self.patch_source is not None and self.output_iso is not None
        self.btn_apply.setEnabled(ready)
        if ready:
            self.lbl_status.setText("Готов к применению патча")
            self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")

    def _start_patching(self) -> None:
        if not self.input_iso or not self.patch_source or not self.output_iso:
            return

        if self.output_iso.resolve() == self.input_iso.resolve():
            QMessageBox.warning(self, "Предупреждение", "Нельзя перезаписывать исходный файл. Укажите другое имя.")
            return

        self.btn_apply.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Применение патча...")
        self.lbl_status.setStyleSheet("color: #0070D1; font-weight: bold;")

        is_binary = self.radio_binary.isChecked()
        force_chk = self.chk_force_checksum.isChecked()

        self.worker = PatcherWorker(
            is_binary_patch=is_binary,
            iso_path=self.input_iso,
            patch_path=self.patch_source,
            out_iso_path=self.output_iso,
            force_checksum=force_chk,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _cancel_patching(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText("Отмена операции...")
            self.lbl_status.setStyleSheet("color: #e53935;")
            self.btn_cancel.setEnabled(False)

    def _on_progress(self, curr: int, total: int, msg: str) -> None:
        if total > 0:
            pct = int((curr / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_status.setText(f"{msg} ({pct}%)")

    def _on_finished(self, msg: str) -> None:
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Успешно завершено!")
        self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")
        self.btn_apply.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QMessageBox.information(self, "Успех", msg)

    def _on_error(self, err: str) -> None:
        self.lbl_status.setText("Ошибка при установке патча.")
        self.lbl_status.setStyleSheet("color: #e53935; font-weight: bold;")
        self.btn_apply.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QMessageBox.critical(self, "Ошибка патчера", f"Произошла ошибка:\n{err}")