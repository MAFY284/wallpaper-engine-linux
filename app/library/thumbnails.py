"""Generación y caché de miniaturas.

- Imágenes: QImageReader (rápido, sin proceso externo).
- Vídeos/GIF: ffmpeg (extrae un fotograma y lo escala).
- Proyectos de Wallpaper Engine: se usa su `preview.*` cuando existe.

Las miniaturas se guardan en ~/.cache/wallpaper-engine-linux/thumbnails/.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from app.library.models import (
    GIF_EXTS,
    IMAGE_EXTS,
    TYPE_GIF,
    TYPE_IMAGE,
    TYPE_VIDEO,
    VIDEO_EXTS,
    Wallpaper,
)

log = logging.getLogger("wel.library.thumbnails")

CACHE_DIR = os.path.expanduser("~/.cache/wallpaper-engine-linux/thumbnails")
THUMB_WIDTH = 480
THUMB_HEIGHT = 270


def cache_path(item: Wallpaper) -> str:
    key = f"{item.id}-{item.format}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, digest + ".jpg")


def ensure(item: Wallpaper, force: bool = False) -> str:
    """Devuelve la ruta de la miniatura (la genera si no existe)."""
    path = cache_path(item)
    if os.path.isfile(path) and os.path.getsize(path) > 0 and not force:
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        if _generate(item, path):
            return path
    except Exception as e:  # noqa: BLE001
        log.warning("miniatura fallida para %s: %s", item.title, e)
    return ""


def _generate(item: Wallpaper, out: str) -> bool:
    source = item.path or ""
    ext = os.path.splitext(source)[1].lower()

    # 1) preferir la vista previa del proyecto WE si el contenido no es
    #    directamente reproducible o es una escena
    if item.preview and (item.kind not in (TYPE_VIDEO, TYPE_IMAGE) or not item.compatible):
        source = item.preview
        ext = os.path.splitext(source)[1].lower()

    if not source or not os.path.isfile(source):
        return False

    if ext in IMAGE_EXTS:
        return _image_thumb(source, out)
    return _ffmpeg_thumb(source, out)


def _image_thumb(source: str, out: str) -> bool:
    reader = QImageReader(source)
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid():
        return False
    scale = min(THUMB_WIDTH / max(size.width(), 1),
                THUMB_HEIGHT / max(size.height(), 1), 1.0)
    reader.setScaledSize(size * scale)
    image = reader.read()
    if image.isNull():
        return False
    return image.save(out, "JPG", 85)


def _ffmpeg_thumb(source: str, out: str) -> bool:
    tmp = out + ".tmp.jpg"
    try:
        os.remove(tmp)
    except OSError:
        pass
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", "1", "-i", source,
        "-frames:v", "1",
        "-vf", f"scale={THUMB_WIDTH}:{THUMB_HEIGHT}:force_original_aspect_ratio=decrease",
        "-q:v", "4",
        tmp,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("ffmpeg falló para %s: %s", source, e)
        return False
    if result.returncode != 0 or not os.path.isfile(tmp):
        return False
    os.replace(tmp, out)
    return True


def probe_resolution(path: str) -> tuple[int, int]:
    """Anchura y altura de un archivo (imagen o vídeo)."""
    if not path or not os.path.isfile(path):
        return 0, 0
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        reader = QImageReader(path)
        size = reader.size()
        return (size.width(), size.height()) if size.isValid() else (0, 0)
    if ext in VIDEO_EXTS | GIF_EXTS:
        return _ffprobe_resolution(path)
    return 0, 0


def _ffprobe_resolution(path: str) -> tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return 0, 0
    parts = result.stdout.strip().split(",")
    if len(parts) == 2:
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            pass
    return 0, 0
