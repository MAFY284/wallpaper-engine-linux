"""Autobuscador de la carpeta de Wallpaper Engine.

Busca `workshop/content/431960` primero en las ubicaciones habituales de
Steam y, si no aparece, recorre el disco (puede tardar). Al encontrarla
avisa al usuario, que confirma si quiere usar esa carpeta.

La búsqueda corre en un hilo de trabajo (solo código Python, sin Qt) y se
comunica con la interfaz mediante señales.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from app.importers import steam


class WEFolderFinder(QObject):
    """Ejecuta la búsqueda en segundo plano."""

    found = Signal(str)        # ruta encontrada
    not_found = Signal()       # búsqueda terminada sin resultados
    progress = Signal(str)     # directorio que se está explorando

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        try:
            path = steam.search_we_workshop_deeply(
                progress_cb=lambda p: self.progress.emit(p),
                stop_flag=self._stop.is_set)
        except Exception as e:  # noqa: BLE001
            self.not_found.emit()
            return
        if self._stop.is_set():
            self.not_found.emit()
            return
        if path:
            self.found.emit(path)
        else:
            self.not_found.emit()
