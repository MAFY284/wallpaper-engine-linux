"""Tarjetas de fondo y rejilla fluida para la biblioteca visual."""

from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.library.models import TYPE_SCENE, Wallpaper

TYPE_COLORS = {
    "video": "#1f6feb",
    "gif": "#2ea08f",
    "image": "#2f9e44",
    "web": "#9d4edd",
    "scene": "#e8590c",
}
SOURCE_COLORS = {
    "wallpaper_engine": "#ff6b35",
    "wallhaven": "#4da3ff",
    "custom": "#8b949e",
}


class FlowLayout(QLayout):
    """Rejilla fluida: dispone las tarjetas en filas según el ancho."""

    def __init__(self, parent=None, margin: int = 8, spacing: int = 12) -> None:
        super().__init__(parent)
        self._items: list = []
        self._margin = margin
        self._spacing = spacing

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size + QSize(2 * self._margin, 2 * self._margin)

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x, y = rect.x() + self._margin, rect.y() + self._margin
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > rect.right() - self._margin and line_height > 0:
                x = rect.x() + self._margin
                y += line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + self._margin


class WallpaperCard(QFrame):
    """Tarjeta de un fondo en la biblioteca."""

    apply_requested = Signal(object)
    preview_requested = Signal(object)
    selected = Signal(object)
    favorite_toggled = Signal(object)

    CARD_WIDTH = 232

    def __init__(self, item: Wallpaper, is_favorite: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self._favorite = is_favorite
        self.setFixedWidth(self.CARD_WIDTH)
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # miniatura
        self.thumb = QLabel()
        self.thumb.setObjectName("thumb")
        self.thumb.setFixedHeight(130)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setText("…")
        pixmap = self._load_pixmap()
        if pixmap:
            self.thumb.setPixmap(pixmap)
        layout.addWidget(self.thumb)

        # título
        self.title_label = QLabel(item.title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setToolTip(self._tooltip())
        self.title_label.setFixedHeight(20)
        layout.addWidget(self.title_label)

        # insignias
        badges = QHBoxLayout()
        badges.setSpacing(4)
        badges.addWidget(self._badge(item.type_label, TYPE_COLORS.get(item.kind, "#888")))
        if item.kind == TYPE_SCENE:
            badges.addWidget(self._badge("No compatible", "#5c6670"))
        badges.addStretch(1)
        if item.resolution:
            res = QLabel(item.resolution)
            res.setObjectName("meta")
            badges.addWidget(res)
        layout.addLayout(badges)

        # pie: origen + favorito + aplicar
        footer = QHBoxLayout()
        footer.setSpacing(4)
        src = QLabel(item.source_label)
        src.setObjectName("meta")
        src.setStyleSheet(f"color: {SOURCE_COLORS.get(item.source, '#8b949e')};")
        footer.addWidget(src)
        footer.addStretch(1)
        self.star = QLabel("★" if self._favorite else "☆")
        self.star.setObjectName("star")
        self.star.setToolTip("Favorito")
        apply_btn = QLabel("▶")
        apply_btn.setObjectName("applyIcon")
        apply_btn.setToolTip("Establecer como fondo")
        footer.addWidget(self.star)
        footer.addWidget(apply_btn)
        layout.addLayout(footer)

        self._star_rect_hint = self.star

    def set_favorite(self, is_fav: bool) -> None:
        self._favorite = is_fav
        self.star.setText("★" if is_fav else "☆")

    # ---------------------------------------------------------- helpers
    def _load_pixmap(self) -> QPixmap | None:
        for path in (self.item.thumbnail, self.item.preview):
            if path and os.path.isfile(path):
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    return pixmap.scaled(
                        self.CARD_WIDTH - 16, 130,
                        Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        return None

    def _badge(self, text: str, color: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("badge")
        label.setStyleSheet(
            f"background-color: {color}22; color: {color};"
            "border: 1px solid transparent; border-radius: 4px;"
            "padding: 1px 6px; font-size: 10px; font-weight: bold;")
        return label

    def _tooltip(self) -> str:
        parts = [self.item.title]
        if self.item.description:
            parts.append(self.item.description[:400])
        parts.append(f"{self.item.type_label} · {self.item.resolution or '?'} · "
                     f"{self.item.source_label}")
        return "\n".join(parts)

    # ---------------------------------------------------------- eventos
    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self.item.compatible:
            self.apply_requested.emit(self.item)
        else:
            self.preview_requested.emit(self.item)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            pos = event.position()
            # botón ▶ (esquina inferior derecha)
            if pos.x() > self.width() - 36 and pos.y() > self.height() - 28:
                if self.item.compatible:
                    self.apply_requested.emit(self.item)
                else:
                    self.preview_requested.emit(self.item)
                return
            # estrella de favorito
            star_global = self.star.mapTo(self, self.star.rect().topLeft())
            if star_global.x() <= pos.x() <= star_global.x() + self.star.width() and \
               star_global.y() <= pos.y() <= star_global.y() + self.star.height():
                self.favorite_toggled.emit(self.item)
                return
            self.selected.emit(self.item)
            return
        super().mousePressEvent(event)
