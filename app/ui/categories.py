"""Barra de categorías (chips) para filtrar la biblioteca."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from app.library.models import SOURCE_WE, SOURCE_WALLHAVEN, TYPE_SCENE, Wallpaper

CATEGORIES = [
    ("all", "Todos"),
    ("we", "Wallpaper Engine"),
    ("wallhaven", "Wallhaven"),
    ("static", "Estáticos"),
    ("animated", "Animados"),
    ("favorites", "Favoritos"),
    ("recents", "Recientes"),
]


class CategoryBar(QWidget):
    changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for key, label in CATEGORIES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("chip", True)
            btn.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            self.group.addButton(btn)
            self.buttons[key] = btn
            layout.addWidget(btn)
        layout.addStretch(1)
        self.buttons["all"].setChecked(True)

    def current(self) -> str:
        return self.group.checkedButton() and next(
            (k for k, b in self.buttons.items() if b is self.group.checkedButton()), "all") or "all"

    def set_category(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)


def matches_category(item: Wallpaper, category: str,
                     favorites: set[str], recents: list[str]) -> bool:
    if category == "all":
        return True
    if category == "we":
        return item.source == SOURCE_WE
    if category == "wallhaven":
        return item.source == SOURCE_WALLHAVEN
    if category == "static":
        return not item.animated and item.kind != TYPE_SCENE
    if category == "animated":
        return item.animated
    if category == "favorites":
        return item.id in favorites
    if category == "recents":
        return item.id in recents
    return True
