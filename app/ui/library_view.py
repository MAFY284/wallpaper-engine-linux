"""Vista de la biblioteca: rejilla de tarjetas con búsqueda y categorías."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.library import indexer
from app.library.models import Wallpaper
from app.library.userdata import UserData
from app.ui.cards import FlowLayout, WallpaperCard
from app.ui.categories import CategoryBar, matches_category

log = logging.getLogger("wel.ui.library")


class _ScanWorker(QRunnable):
    """Escaneo de bibliotecas en segundo plano (no bloquea la interfaz)."""

    def __init__(self, signals: "LibrarySignals") -> None:
        super().__init__()
        self.signals = signals

    def run(self) -> None:
        try:
            previous = indexer.load_index()
            items = indexer.build_index(previous)
            indexer.save_index(items)
            self.signals.scan_done.emit(items)
        except Exception as e:  # noqa: BLE001
            log.exception("error durante el escaneo")
            self.signals.scan_failed.emit(str(e))


class LibrarySignals(QObject):
    scan_done = Signal(list)
    scan_failed = Signal(str)


class LibraryView(QWidget):
    """Biblioteca visual de fondos."""

    apply_requested = Signal(object)      # Wallpaper compatible → aplicar
    preview_requested = Signal(object)    # Wallpaper no compatible → aviso
    selected = Signal(object)             # clic en una tarjeta
    favorite_toggled = Signal(object)     # estrella pulsada

    def __init__(self, userdata: UserData | None = None, parent=None) -> None:
        super().__init__(parent)
        self.userdata = userdata or UserData()
        self.items: list[Wallpaper] = []
        self.cards: dict[str, WallpaperCard] = {}
        self._category = "all"
        self._pool = QThreadPool.globalInstance()
        self.signals = LibrarySignals()
        self.signals.scan_done.connect(self._on_scan_done)
        self.signals.scan_failed.connect(self._on_scan_failed)
        self._build_ui()

    # ---------------------------------------------------------- UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # categorías
        self.categories = CategoryBar()
        self.categories.changed.connect(self._on_category_changed)
        layout.addWidget(self.categories)

        # búsqueda + contador
        top = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar fondos por nombre…")
        self.search_edit.textChanged.connect(self._apply_filter)
        top.addWidget(self.search_edit, 1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("meta")
        top.addWidget(self.count_label)
        layout.addLayout(top)

        # área de tarjetas
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.grid_host = QWidget()
        self.grid = FlowLayout(self.grid_host, margin=4, spacing=12)
        self.scroll.setWidget(self.grid_host)
        layout.addWidget(self.scroll, 1)

        self.status_label = QLabel("Escaneando bibliotecas…")
        self.status_label.setObjectName("meta")
        layout.addWidget(self.status_label)

    # ---------------------------------------------------------- escaneo
    def start_scan(self) -> None:
        self.status_label.setText("Escaneando bibliotecas…")
        self._pool.start(_ScanWorker(self.signals))

    @Slot(list)
    def _on_scan_done(self, items: list) -> None:
        self.items = items
        self._rebuild()
        compatible = sum(1 for i in items if i.compatible)
        self.status_label.setText(
            f"{len(items)} fondos · {compatible} compatibles")
        log.info("biblioteca lista: %d fondos", len(items))

    @Slot(str)
    def _on_scan_failed(self, error: str) -> None:
        self.status_label.setText(f"Error al escanear: {error}")

    # ---------------------------------------------------------- filtrado
    def _on_category_changed(self, category: str) -> None:
        self._category = category
        self._rebuild()

    def _apply_filter(self) -> None:
        if not self.items:
            return
        self._rebuild()

    def _rebuild(self) -> None:
        self.cards.clear()
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        query = self.search_edit.text().strip().lower()
        favorites = set(self.userdata.favorites())
        recents = self.userdata.recents()

        for wallpaper in self.items:
            if query and query not in wallpaper.title.lower():
                continue
            if not matches_category(wallpaper, self._category, favorites, recents):
                continue
            card = WallpaperCard(wallpaper, is_favorite=wallpaper.id in favorites)
            card.apply_requested.connect(self.apply_requested)
            card.preview_requested.connect(self.preview_requested)
            card.selected.connect(self.selected)
            card.favorite_toggled.connect(self.favorite_toggled)
            self.cards[wallpaper.id] = card
            self.grid.addWidget(card)
        self.grid_host.updateGeometry()
        self._update_count()

    def _update_count(self) -> None:
        total = len(self.items)
        shown = len(self.cards)
        self.count_label.setText(f"{shown} de {total}")

    # ---------------------------------------------------------- API
    def refresh(self) -> None:
        """Reescanea (por ejemplo, tras añadir archivos nuevos)."""
        self.start_scan()

    def update_favorites(self) -> None:
        """Actualiza las estrellas y el filtro de favoritos."""
        favorites = set(self.userdata.favorites())
        for item_id, card in self.cards.items():
            card.set_favorite(item_id in favorites)
        if self._category in ("favorites",):
            self._rebuild()
