"""Vista de la biblioteca: rejilla de tarjetas con búsqueda y categorías.

El escaneo se ejecuta en un PROCESO INDEPENDIENTE (app/library/scanner_main.py)
para que un fallo nativo durante el escaneo (archivos a medio descargar de
Steam, formatos extraños) jamás tumbe la interfaz. La biblioteca se
actualiza automáticamente cada AUTO_REFRESH_MS.
"""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QProcess, QTimer, Signal
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

_SCANNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "library", "scanner_main.py")
AUTO_REFRESH_MS = 30_000   # refresco automático para detectar nuevas descargas
SCAN_TIMEOUT_MS = 120_000  # si un escaneo tarda más, se mata el proceso


class LibraryView(QWidget):
    """Biblioteca visual de fondos."""

    apply_requested = Signal(object)      # Wallpaper compatible → aplicar
    preview_requested = Signal(object)    # Wallpaper no compatible → aviso
    selected = Signal(object)             # clic en una tarjeta
    favorite_toggled = Signal(object)     # estrella pulsada
    scan_output = Signal(str)             # salida del escáner (para el registro)

    def __init__(self, userdata: UserData | None = None, parent=None) -> None:
        super().__init__(parent)
        self.userdata = userdata or UserData()
        self.items: list[Wallpaper] = []
        self.cards: dict[str, WallpaperCard] = {}
        self._category = "all"
        self._proc: QProcess | None = None
        self._build_ui()

        # refresco automático: detecta nuevos fondos sin intervención
        self._timer = QTimer(self)
        self._timer.setInterval(AUTO_REFRESH_MS)
        self._timer.timeout.connect(self.start_scan)
        self._timer.start()

        # si un escaneo se cuelga, se mata el proceso
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.setInterval(SCAN_TIMEOUT_MS)
        self._watchdog.timeout.connect(self._kill_scan)

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
        if self._proc is not None:
            return  # ya hay un escaneo en curso
        self.status_label.setText("Escaneando bibliotecas…")
        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setArguments([_SCANNER])
        self._proc.finished.connect(self._on_scan_finished)
        self._proc.errorOccurred.connect(self._on_scan_error)
        self._proc.readyReadStandardOutput.connect(self._on_scan_stdout)
        self._proc.readyReadStandardError.connect(self._on_scan_stderr)
        self._watchdog.start()
        self._proc.start()

    def _kill_scan(self) -> None:
        if self._proc is not None:
            log.warning("escaneo demasiado lento; terminando el proceso")
            self._proc.kill()

    def _on_scan_stdout(self) -> None:
        if self._proc:
            self.scan_output.emit(
                bytes(self._proc.readAllStandardOutput()).decode(errors="replace").strip())

    def _on_scan_stderr(self) -> None:
        if self._proc:
            text = bytes(self._proc.readAllStandardError()).decode(errors="replace").strip()
            if text:
                self.scan_output.emit(text)

    def _on_scan_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            log.error("no se pudo iniciar el escáner")
            self.status_label.setText("No se pudo iniciar el escáner (reintentando…)")
            self._cleanup_scan()

    def _on_scan_finished(self, exit_code: int, exit_status) -> None:
        self._watchdog.stop()
        crashed = exit_status != QProcess.NormalExit or exit_code != 0
        if crashed:
            log.warning("el escáner terminó con error (código %s, estado %s)",
                        exit_code, exit_status)
            self.status_label.setText(
                "El escaneo falló; se conserva la biblioteca anterior y se "
                "reintentará automáticamente")
            self._cleanup_scan()
            return

        # leer el índice guardado por el escáner
        try:
            items = list(indexer.load_index().values())
        except Exception as e:  # noqa: BLE001
            log.warning("no se pudo leer el índice: %s", e)
            items = []
        self._cleanup_scan()

        if items:
            self.items = items
            self._rebuild()
            compatible = sum(1 for i in items if i.compatible)
            self.status_label.setText(
                f"{len(items)} fondos · {compatible} compatibles")
            log.info("biblioteca lista: %d fondos", len(items))
        else:
            self.status_label.setText("Escaneo sin resultados (se conserva la biblioteca)")

    def _cleanup_scan(self) -> None:
        if self._proc is not None:
            self._proc.deleteLater()
            self._proc = None

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
        """Fuerza un reescaneo inmediato."""
        if self._proc is None:
            self.start_scan()

    def update_favorites(self) -> None:
        """Actualiza las estrellas y el filtro de favoritos."""
        favorites = set(self.userdata.favorites())
        for item_id, card in self.cards.items():
            card.set_favorite(item_id in favorites)
        if self._category in ("favorites",):
            self._rebuild()
