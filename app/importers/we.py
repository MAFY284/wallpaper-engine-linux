"""Importador de proyectos de Wallpaper Engine (Steam Workshop).

Solo lectura: no modifica, mueve ni elimina los archivos originales.

Estructura real de un proyecto (verificada en el equipo del usuario):
  <workshop_id>/
  ├── project.json   → title, type (scene|video|web|application), preview,
  │                    description, tags, workshopid
  ├── preview.gif|jpg
  └── scene.pkg      (type=scene, propietario)  |  *.mp4 (type=video)  |  *.html (type=web)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from app.library.models import (
    GIF_EXTS,
    SOURCE_WE,
    TYPE_GIF,
    TYPE_SCENE,
    TYPE_VIDEO,
    TYPE_WEB,
    VIDEO_EXTS,
    Wallpaper,
)

log = logging.getLogger("wel.importers.we")


def read_project_json(folder: str) -> Optional[dict]:
    path = os.path.join(folder, "project.json")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        log.warning("project.json ilegible en %s: %s", folder, e)
        return None


def _find_main_file(folder: str, kind: str) -> Optional[str]:
    """Busca el archivo principal reproducible del proyecto."""
    wanted = {
        TYPE_VIDEO: VIDEO_EXTS,
        TYPE_WEB: {".html", ".htm"},
    }.get(kind, set())
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return None
    for name in entries:
        ext = os.path.splitext(name)[1].lower()
        if ext not in wanted:
            continue
        path = os.path.join(folder, name)
        try:
            if os.path.getsize(path) <= 0:  # descarga incompleta
                continue
        except OSError:
            continue
        return path
    return None


def _find_preview(folder: str) -> Optional[str]:
    for name in ("preview.gif", "preview.jpg", "preview.png", "preview.webp"):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return None


def scan_workshop(workshop_root: str) -> list[Wallpaper]:
    """Escanea todos los proyectos del Workshop de Wallpaper Engine."""
    items: list[Wallpaper] = []
    try:
        entries = sorted(os.listdir(workshop_root))
    except OSError as e:
        log.error("no se puede listar el Workshop: %s", e)
        return items

    for name in entries:
        folder = os.path.join(workshop_root, name)
        if not os.path.isdir(folder):
            continue
        meta = read_project_json(folder)
        if not meta:
            continue

        we_type = str(meta.get("type", "")).lower()
        preview = _find_preview(folder)
        # El nombre de la carpeta es el ID de Workshop autoritativo de Steam.
        # (El campo "workshopid" del project.json puede contener el ID del
        # proyecto original en re-subidas y causar colisiones de IDs.)
        workshop_id = name

        if we_type in ("video", "animation"):
            main = _find_main_file(folder, TYPE_VIDEO)
            kind = TYPE_VIDEO
            compatible = main is not None
        elif we_type == "web":
            main = _find_main_file(folder, TYPE_WEB)
            kind = TYPE_WEB
            compatible = main is not None
        elif we_type in ("scene", "application"):
            main = preview  # degradado: la vista previa como contenido visible
            kind = TYPE_SCENE
            compatible = False
        else:
            # tipo desconocido: si hay preview, mostrarla como escena
            main = preview
            kind = TYPE_SCENE
            compatible = False

        if not main and not preview:
            continue

        ext = os.path.splitext(main or "")[1].lower()
        if kind == TYPE_VIDEO and ext in GIF_EXTS:
            kind = TYPE_GIF

        items.append(Wallpaper(
            id=f"we:{workshop_id}",
            title=str(meta.get("title") or name),
            path=main or "",
            source=SOURCE_WE,
            kind=kind,
            preview=preview,
            description=str(meta.get("description") or ""),
            tags=[str(t) for t in (meta.get("tags") or [])],
            format=ext.lstrip("."),
            workshop_id=workshop_id,
            compatible=compatible,
            mtime=os.path.getmtime(folder),
            size=_folder_size(folder),
        ))
    log.info("Workshop escaneado: %d proyectos", len(items))
    return items


def _folder_size(folder: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total
