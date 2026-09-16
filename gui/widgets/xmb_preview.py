"""Визуальный компонент экрана PSP XMB (CrossMediaBar)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class XMBDisplayFrame(QFrame):
    """Отрисовка экрана PSP с сохранением классических пропорций 480x272."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 272)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)

        self.pic1: Optional[QPixmap] = None  # 480x272 Background
        self.icon0: Optional[QPixmap] = None  # 144x80 Icon
        self.title_text: str = ""
        self.game_id_text: str = ""

    def set_assets(
        self,
        icon0_bytes: Optional[bytes] = None,
        pic1_bytes: Optional[bytes] = None,
        title: str = "",
        game_id: str = "",
    ) -> None:
        """Обновление ресурсов отображения XMB."""
        self.title_text = title
        self.game_id_text = game_id

        if icon0_bytes:
            pix = QPixmap()
            pix.loadFromData(icon0_bytes)
            self.icon0 = pix
        else:
            self.icon0 = None

        if pic1_bytes:
            pix = QPixmap()
            pix.loadFromData(pic1_bytes)
            self.pic1 = pix
        else:
            self.pic1 = None

        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Отрисовка фона (PIC1 или стилизованный градиент волн PSP)
        if self.pic1 and not self.pic1.isNull():
            scaled_bg = self.pic1.scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            # Центрируем картинку
            x_offset = (scaled_bg.width() - w) // 2
            y_offset = (scaled_bg.height() - h) // 2
            painter.drawPixmap(0, 0, scaled_bg, x_offset, y_offset, w, h)
        else:
            gradient = QLinearGradient(0, 0, w, h)
            gradient.setColorAt(0.0, QColor(25, 30, 45))
            gradient.setColorAt(1.0, QColor(10, 12, 18))
            painter.fillRect(0, 0, w, h, gradient)

        # Тёмная подложка для читаемости текста и иконки
        overlay = QLinearGradient(0, 0, 0, h)
        overlay.setColorAt(0.0, QColor(0, 0, 0, 50))
        overlay.setColorAt(0.7, QColor(0, 0, 0, 80))
        overlay.setColorAt(1.0, QColor(0, 0, 0, 180))
        painter.fillRect(0, 0, w, h, overlay)

        # 2. Отрисовка иконки (ICON0)
        icon_x = 40
        icon_y = h - 130
        icon_w = 144
        icon_h = 80

        if self.icon0 and not self.icon0.isNull():
            scaled_icon = self.icon0.scaled(
                icon_w, icon_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            # Рамка вокруг иконки
            painter.setPen(QColor(255, 255, 255, 120))
            painter.drawRect(icon_x - 2, icon_y - 2, scaled_icon.width() + 3, scaled_icon.height() + 3)
            painter.drawPixmap(icon_x, icon_y, scaled_icon)
        else:
            # Плейсхолдер при отсутствии иконки
            painter.setPen(QColor(255, 255, 255, 80))
            painter.setBrush(QColor(40, 40, 40, 150))
            painter.drawRect(icon_x, icon_y, icon_w, icon_h)
            painter.setPen(QColor(200, 200, 200, 180))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(
                QRect(icon_x, icon_y, icon_w, icon_h),
                Qt.AlignmentFlag.AlignCenter,
                "НЕТ ИКОНКИ",
            )

        # 3. Отрисовка названия игры и ID
        if self.title_text:
            text_x = icon_x + icon_w + 25
            text_y = icon_y + 25

            # Тень текста
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.setPen(QColor(0, 0, 0, 220))
            painter.drawText(text_x + 1, text_y + 1, self.title_text)

            # Белый основной текст
            painter.setPen(QColor(255, 255, 255, 240))
            painter.drawText(text_x, text_y, self.title_text)

            if self.game_id_text:
                painter.setFont(QFont("Segoe UI", 10))
                painter.setPen(QColor(180, 200, 220, 200))
                painter.drawText(text_x, text_y + 28, f"[{self.game_id_text}]")


class XMBPreviewWidget(QWidget):
    """Виджет предварительного просмотра с кнопками быстрого экспорта графики."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.raw_icon0: Optional[bytes] = None
        self.raw_pic1: Optional[bytes] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.display = XMBDisplayFrame()
        layout.addWidget(self.display)

        # Кнопки экспорта ресурсов
        btn_bar = QHBoxLayout()
        self.btn_export_icon = QPushButton("Сохранить ICON0.PNG...")
        self.btn_export_icon.setEnabled(False)
        self.btn_export_icon.clicked.connect(self._export_icon)
        btn_bar.addWidget(self.btn_export_icon)

        self.btn_export_pic = QPushButton("Сохранить PIC1.PNG...")
        self.btn_export_pic.setEnabled(False)
        self.btn_export_pic.clicked.connect(self._export_pic)
        btn_bar.addWidget(self.btn_export_pic)

        layout.addLayout(btn_bar)

    def update_data(
        self,
        icon0_bytes: Optional[bytes],
        pic1_bytes: Optional[bytes],
        title: str,
        game_id: str,
    ) -> None:
        """Передать сырые байты картинок и метаданные."""
        self.raw_icon0 = icon0_bytes
        self.raw_pic1 = pic1_bytes

        self.display.set_assets(icon0_bytes, pic1_bytes, title, game_id)
        self.btn_export_icon.setEnabled(icon0_bytes is not None)
        self.btn_export_pic.setEnabled(pic1_bytes is not None)

    def _export_icon(self) -> None:
        if not self.raw_icon0:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить иконку", "ICON0.PNG", "PNG Images (*.png)")
        if path:
            Path(path).write_bytes(self.raw_icon0)
            QMessageBox.information(self, "Успех", f"Иконка сохранена:\n{path}")

    def _export_pic(self) -> None:
        if not self.raw_pic1:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить фон", "PIC1.PNG", "PNG Images (*.png)")
        if path:
            Path(path).write_bytes(self.raw_pic1)
            QMessageBox.information(self, "Успех", f"Фон сохранён:\n{path}")