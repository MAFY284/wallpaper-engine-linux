"""Importador de carpetas locales (Wallhaven y carpetas personalizadas).

Escanea imágenes, vídeos y GIF directamente, en modo de solo lectura.
"""

from __future__ import annotations

import hashlib
import logging
import os

from app.library.models import (
    GIF_EXTS,
    IMAGE_EXTS,
    SOURCE_CUSTOM,
    SOURCE_WALLHAVEN,
    TYPE_GIF,
    TYPE_IMAGE,
    TYPE_VIDEO,
    VIDEO_EXTS,
    Wallpaper,
)

log = logging.getLogger("wel.importers.folders")

# carpetas predeterminadas del usuario (se detectan ambas variantes)
DEFAULT_FOLDERS = [
    os.path.expanduser("~/Imágenes/Wallpapers"),
    os.path.expanduser("~/Imágenes/wallpapers"),
    os.path.expanduser("~/Pictures/Wallpapers"),
    os.path.expanduser("~/Pictures/wallpapers"),
]

ALL_EXTS = VIDEO_EXTS | GIF_EXTS | IMAGE_EXTS


def _kind_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTS:
        return TYPE_VIDEO
    if ext in GIF_EXTS:
        return TYPE_GIF
    return TYPE_IMAGE


def _stable_id(path: str) -> str:
    digest = hashlib.sha1(os.path.realpath(path).encode("utf-8")).hexdigest()[:16]
    return f"file:{digest}"


def scan_folder(folder: str, source: str = SOURCE_CUSTOM,
                recursive: bool = False) -> list[Wallpaper]:
    """Escanea una carpeta en busca de archivos compatibles."""
    folder = os.path.expanduser(folder)
    items: list[Wallpaper] = []
    if not os.path.isdir(folder):
        log.warning("carpeta inexistente: %s", folder)
        return items

    if recursive:
        entries = []
        for root, _dirs, files in os.walk(folder):
            for name in files:
                entries.append(os.path.join(root, name))
    else:
        entries = [os.path.join(folder, n) for n in sorted(os.listdir(folder))]

    for path in entries:
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in ALL_EXTS:
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        items.append(Wallpaper(
            id=_stable_id(path),
            title=os.path.splitext(os.path.basename(path))[0],
            path=path,
            source=source,
            kind=_kind_for(path),
            format=ext.lstrip("."),
            compatible=True,
            mtime=st.st_mtime,
            size=st.st_size,
        ))
    log.info("carpeta %s: %d archivos compatibles", folder, len(items))
    return items
