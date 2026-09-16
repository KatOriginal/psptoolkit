"""Визуальный редактор параметров PARAM.SFO."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.exceptions import SFOFormatError
from formats.sfo import SFO, SFODataType


class AddEntryDialog(QDialog):
    """Диалог добавления нового параметра в SFO."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добавить параметр")
        self.resize(360, 160)

        layout = QFormLayout(self)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("например, TITLE, DISC_ID, CATEGORY")
        layout.addRow("Ключ:", self.key_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Строка UTF-8", SFODataType.UTF8)
        self.type_combo.addItem("Число (uint32)", SFODataType.INT32)
        layout.addRow("Тип:", self.type_combo)

        self.value_edit = QLineEdit()
        layout.addRow("Значение:", self.value_edit)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def validate_and_accept(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "Ошибка", "Ключ не может быть пустым.")
            return

        data_type = self.type_combo.currentData()
        value_str = self.value_edit.text().strip()

        if data_type == SFODataType.INT32:
            try:
                val = int(value_str, 0)
                if not (0 <= val <= 0xFFFFFFFF):
                    raise ValueError
            except ValueError:
                QMessageBox.warning(
                    self, "Ошибка", "Значение должно быть целым 32-битным числом (0..4294967295)."
                )
                return

        self.accept()

    def get_data(self) -> tuple[str, SFODataType, str]:
        return (
            self.key_edit.text().strip(),
            self.type_combo.currentData(),
            self.value_edit.text().strip(),
        )


class SFOEditorWidget(QWidget):
    """Виджет просмотра и редактирования SFO."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_sfo: Optional[SFO] = None
        self.current_path: Optional[Path] = None

        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_open = QPushButton("Открыть SFO")
        self.btn_open.clicked.connect(self.open_file_dialog)
        toolbar.addWidget(self.btn_open)

        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self.save_file)
        self.btn_save.setEnabled(False)
        toolbar.addWidget(self.btn_save)

        self.btn_save_as = QPushButton("Сохранить как...")
        self.btn_save_as.clicked.connect(self.save_as_file_dialog)
        self.btn_save_as.setEnabled(False)
        toolbar.addWidget(self.btn_save_as)

        toolbar.addSpacing(20)

        self.btn_add = QPushButton("Добавить ключ")
        self.btn_add.clicked.connect(self.add_entry)
        self.btn_add.setEnabled(False)
        toolbar.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Удалить ключ")
        self.btn_delete.clicked.connect(self.delete_entry)
        self.btn_delete.setEnabled(False)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()

        self.lbl_path = QLabel("Файл не загружен (перетащите .SFO сюда)")
        self.lbl_path.setStyleSheet("color: #9295a8;")
        toolbar.addWidget(self.lbl_path)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Ключ (Key)", "Тип данных", "Значение (Value)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(".sfo"):
                event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.load_sfo_file(Path(file_path))

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть PARAM.SFO", "", "SFO Files (*.SFO *.sfo);;All Files (*.*)"
        )
        if path:
            self.load_sfo_file(Path(path))

    def load_sfo_file(self, path: Path) -> None:
        try:
            self.current_sfo = SFO.from_file(str(path))
            self.current_path = path
            self.lbl_path.setText(f"Файл: {path.name}")
            self.lbl_path.setStyleSheet("color: #4caf50; font-weight: bold;")

            self._populate_table()

            self.btn_save.setEnabled(True)
            self.btn_save_as.setEnabled(True)
            self.btn_add.setEnabled(True)
            self.btn_delete.setEnabled(True)
        except SFOFormatError as exc:
            QMessageBox.critical(self, "Ошибка разбора SFO", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка чтения", f"Не удалось прочитать файл: {exc}")

    def _populate_table(self) -> None:
        if not self.current_sfo:
            return

        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for row, (key, entry) in enumerate(self.current_sfo.entries.items()):
            self.table.insertRow(row)

            item_key = QTableWidgetItem(key)
            item_key.setFlags(item_key.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item_key)

            type_str = "Число (uint32)" if entry.data_type == SFODataType.INT32 else "Строка UTF-8"
            item_type = QTableWidgetItem(type_str)
            item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, item_type)

            val_str = (
                f"0x{entry.value:08X} ({entry.value})"
                if entry.data_type == SFODataType.INT32
                else str(entry.value)
            )
            item_val = QTableWidgetItem(val_str)
            self.table.setItem(row, 2, item_val)

        self.table.blockSignals(False)

    def _on_cell_changed(self, row: int, column: int) -> None:
        if column != 2 or not self.current_sfo:
            return

        key = self.table.item(row, 0).text()
        new_val_str = self.table.item(row, 2).text().strip()
        entry = self.current_sfo.entries.get(key)
        if not entry:
            return

        if entry.data_type == SFODataType.INT32:
            try:
                if "(" in new_val_str and new_val_str.endswith(")"):
                    raw_num = new_val_str.split("(")[-1][:-1]
                    val = int(raw_num, 0)
                else:
                    val = int(new_val_str, 0)

                self.current_sfo.set_int(key, val)
            except ValueError:
                QMessageBox.warning(self, "Ошибка", f"Некорректное числовое значение: '{new_val_str}'")
                self._populate_table()
        else:
            self.current_sfo.set_string(key, new_val_str)

    def add_entry(self) -> None:
        if not self.current_sfo:
            return

        dlg = AddEntryDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            key, data_type, value_str = dlg.get_data()

            if data_type == SFODataType.INT32:
                self.current_sfo.set_int(key, int(value_str, 0))
            else:
                self.current_sfo.set_string(key, value_str)

            self._populate_table()

    def delete_entry(self) -> None:
        if not self.current_sfo:
            return

        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Информация", "Выберите запись для удаления.")
            return

        key = self.table.item(current_row, 0).text()
        confirm = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить параметр '{key}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.current_sfo.delete(key)
            self._populate_table()

    def save_file(self) -> None:
        if not self.current_sfo or not self.current_path:
            return
        try:
            self.current_sfo.write_to_file(str(self.current_path))
            QMessageBox.information(self, "Успех", f"Файл сохранён:\n{self.current_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    def save_as_file_dialog(self) -> None:
        if not self.current_sfo:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить PARAM.SFO как", "PARAM.SFO", "SFO Files (*.SFO *.sfo);;All Files (*.*)"
        )
        if path:
            try:
                self.current_sfo.write_to_file(path)
                self.current_path = Path(path)
                self.lbl_path.setText(f"Файл: {self.current_path.name}")
                QMessageBox.information(self, "Успех", f"Файл сохранён:\n{self.current_path}")
            except Exception as exc:
                QMessageBox.critical(self, "Ошибка сохранения", str(exc))


class SFODialog(QDialog):
    """Отдельное диалоговое окно для редактирования PARAM.SFO."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Редактор PARAM.SFO — UMD Studio")
        self.resize(750, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.editor = SFOEditorWidget(self)
        layout.addWidget(self.editor)