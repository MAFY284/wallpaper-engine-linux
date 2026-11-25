"""Indexador de la biblioteca: reúne todas las fuentes en un índice único.

Fuentes:
  1. Workshop de Wallpaper Engine (Steam) — solo lectura.
  2. Carpeta Wallhaven (se detectan variantes de mayúsculas).
  3. Carpetas personalizadas (configurables en fase 5).

El índice se guarda en ~/.local/share/wallpaper-engine-linux/library.json
y se regenera de forma incremental (mtime/tamaño).
"""

from __future__ import annotations

import json
import logging
import os

from app.config import manager as config_manager
from app.importers import folders, steam, we
from app.library.models import SOURCE_WALLHAVEN, Wallpaper
from app.library.thumbnails import ensure, probe_resolution

log = logging.getLogger("wel.library.indexer")

INDEX_DIR = os.path.expanduser("~/.local/share/wallpaper-engine-linux")
INDEX_FILE = os.path.join(INDEX_DIR, "library.json")


def default_wallhaven_folder() -> str | None:
    """Primera carpeta de Wallhaven que exista (variantes de mayúsculas)."""
    for folder in folders.DEFAULT_FOLDERS:
        if os.path.isdir(folder):
            return folder
    return None


def collect_items() -> list[Wallpaper]:
    """Recopila los fondos de todas las fuentes."""
    items: list[Wallpaper] = []

    workshop = steam.find_we_workshop()
    if workshop:
        items.extend(we.scan_workshop(workshop))

    wallhaven = default_wallhaven_folder()
    if wallhaven:
        items.extend(folders.scan_folder(wallhaven, source=SOURCE_WALLHAVEN))
    else:
        log.info("no se encontró ninguna carpeta de Wallhaven")

    # carpetas personalizadas
    for folder in config_manager.custom_folders():
        items.extend(folders.scan_folder(folder))

    return items


def build_index(previous: dict[str, Wallpaper] | None = None) -> list[Wallpaper]:
    """Construye (o actualiza) el índice y devuelve la lista de fondos.

    previous: índice anterior para actualización incremental.
    """
    previous = previous or {}
    items = collect_items()
    seen: set[str] = set()

    result: list[Wallpaper] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)

        old = previous.get(item.id)
        if (old and old.mtime == item.mtime and old.size == item.size
                and old.width and old.height):
            # sin cambios: reutilizar metadatos costosos
            item.width, item.height = old.width, old.height
            item.thumbnail = old.thumbnail
        else:
            item.width, item.height = probe_resolution(item.path)
            item.thumbnail = ensure(item)

        if item.width and item.height:
            item.resolution = f"{item.width}x{item.height}"
        result.append(item)

    result.sort(key=lambda w: (w.source != SOURCE_WALLHAVEN, w.title.lower()))
    return result


def load_index() -> dict[str, Wallpaper]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {entry["id"]: Wallpaper.from_dict(entry)
                for entry in data.get("items", []) if "id" in entry}
    except (OSError, ValueError):
        return {}


def save_index(items: list[Wallpaper]) -> None:
    """Guarda el índice de forma atómica (nunca deja un archivo corrupto)."""
    try:
        os.makedirs(INDEX_DIR, exist_ok=True)
        tmp = INDEX_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "items": [i.to_dict() for i in items]},
                      f, ensure_ascii=False, indent=1)
        os.replace(tmp, INDEX_FILE)
    except OSError as e:
        log.warning("no se pudo guardar el índice: %s", e)
