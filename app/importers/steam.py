"""Detección de bibliotecas de Steam y localización de Wallpaper Engine.

Steam guarda la lista de bibliotecas en `libraryfolders.vdf` (formato KeyValues
de Valve: claves entre comillas, valores anidados entre llaves). Este módulo lo
lee con un parser propio (solo lectura, sin dependencias).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger("wel.importers.steam")

WE_APPID = "431960"  # Wallpaper Engine


def default_steam_paths() -> list[str]:
    """Rutas por defecto donde Steam suele instalarse."""
    home = os.path.expanduser("~")
    return [
        os.path.join(home, ".local/share/Steam/steamapps"),
        os.path.join(home, ".steam/steam/steamapps"),
        os.path.join(home, ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"),
    ]


def parse_vdf(text: str) -> dict:
    """Parser mínimo del formato KeyValues de Valve (VDF)."""

    def parse_object(i: int) -> tuple[dict, int]:
        obj: dict = {}
        while i < len(text):
            while i < len(text) and text[i] in " \t\r\n":
                i += 1
            if i >= len(text) or text[i] == "}":
                return obj, i + 1
            if text[i] == '"':
                j = i + 1
                while j < len(text) and text[j] != '"':
                    if text[j] == "\\" and j + 1 < len(text):
                        j += 1
                    j += 1
                key = text[i + 1:j]
                i = j + 1
                while i < len(text) and text[i] in " \t\r\n":
                    i += 1
                if i < len(text) and text[i] == '"':
                    j = i + 1
                    while j < len(text) and text[j] != '"':
                        if text[j] == "\\" and j + 1 < len(text):
                            j += 1
                        j += 1
                    obj[key] = text[i + 1:j]
                    i = j + 1
                elif i < len(text) and text[i] == "{":
                    nested, i = parse_object(i + 1)
                    obj[key] = nested
                else:
                    i += 1
            else:
                i += 1
        return obj, i

    obj, _ = parse_object(0)
    return obj


def find_steam_libraries() -> list[str]:
    """Devuelve las rutas `steamapps` de todas las bibliotecas de Steam."""
    libraries: list[str] = []
    seen: set[str] = set()

    for base in default_steam_paths():
        vdf_path = os.path.join(os.path.dirname(base), "libraryfolders.vdf")
        if not os.path.isfile(vdf_path):
            continue
        try:
            with open(vdf_path, "r", encoding="utf-8", errors="replace") as f:
                data = parse_vdf(f.read())
        except OSError as e:
            log.warning("no se pudo leer %s: %s", vdf_path, e)
            continue

        folders = data.get("libraryfolders", data)
        for _key, entry in folders.items():
            if isinstance(entry, dict):
                path = entry.get("path")
                if path:
                    full = os.path.join(path, "steamapps")
                    real = os.path.realpath(full)
                    if real not in seen:
                        seen.add(real)
                        libraries.append(real)

    # añadir las rutas por defecto si existen aunque no estén en el vdf
    for base in default_steam_paths():
        real = os.path.realpath(base)
        if os.path.isdir(real) and real not in seen:
            seen.add(real)
            libraries.append(real)

    log.info("bibliotecas de Steam detectadas: %s", libraries)
    return libraries


def find_we_workshop(libraries: Optional[list[str]] = None) -> Optional[str]:
    """Localiza la carpeta Workshop de Wallpaper Engine (solo lectura)."""
    for steamapps in (libraries or find_steam_libraries()):
        candidate = os.path.join(steamapps, "workshop", "content", WE_APPID)
        if os.path.isdir(candidate):
            log.info("Workshop de Wallpaper Engine: %s", candidate)
            return candidate
    log.warning("no se encontró el Workshop de Wallpaper Engine")
    return None


# --------------------------------------------------------------------------
# Búsqueda profunda ("autobuscador")
# --------------------------------------------------------------------------

# directorios que se ignoran al recorrer el sistema de archivos
_WALK_EXCLUDE = {
    "proc", "sys", "dev", "run", "tmp", "boot", "etc", "root", "sbin", "bin",
    "lib", "lib64", "usr", "snap", "nix", "lost+found", "node_modules",
    "__pycache__", ".git", ".npm", ".cache", ".wine", ".mozilla", ".cargo",
    ".rustup", ".local/share/Trash",
}
# directorios ocultos que SÍ se recorren (los relevantes para Steam)
_WALK_ALLOW_HIDDEN = {".local", ".steam", ".var", ".config", ".share"}


def _steam_like_dirnames(dirnames: list[str], dirpath: str) -> None:
    """Recorta la lista de subdirectorios a recorrer (poda inteligente)."""
    kept = []
    for d in dirnames:
        if d in _WALK_EXCLUDE:
            continue
        if d.startswith(".") and d not in _WALK_ALLOW_HIDDEN:
            continue
        kept.append(d)
    dirnames[:] = kept


def _extra_mount_roots() -> list[str]:
    """Puntos de montaje candidatos (discos secundarios con bibliotecas)."""
    roots: list[str] = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                mount = parts[1]
                if mount.startswith(("/mnt", "/media", "/run/media", "/games", "/data", "/srv")):
                    roots.append(mount)
    except OSError:
        pass
    return roots


def search_we_workshop_deeply(progress_cb=None, stop_flag=None,
                              roots: Optional[list[str]] = None) -> Optional[str]:
    """Busca la carpeta Workshop de Wallpaper Engine en todo el sistema.

    1. Primero las ubicaciones habituales (libraryfolders.vdf y rutas por
       defecto): es inmediato.
    2. Si no aparece, recorre el disco de forma exhaustiva pero podada
       (puede tardar un poco); la carpeta buscada siempre se llama
       `workshop/content/431960`.

    progress_cb: función opcional a la que se informa del directorio actual.
    stop_flag:   función opcional que devuelve True para cancelar la búsqueda.
    roots:       raíces a explorar (para pruebas; por defecto ~ y los puntos
                 de montaje candidatos).
    """
    # 1) vía rápida: ubicaciones estándar de Steam
    found = find_we_workshop()
    if found:
        return found

    if roots is None:
        roots = [os.path.expanduser("~")] + _extra_mount_roots()
        for extra in ("/opt", "/mnt", "/media", "/games", "/data", "/srv"):
            if extra not in roots:
                roots.append(extra)

    # 2) recorrido profundo con poda
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, _filenames in os.walk(root, onerror=lambda e: None):
            if stop_flag and stop_flag():
                log.info("búsqueda cancelada por el usuario")
                return None
            if progress_cb and len(dirpath) % 97 == 0:  # informar ocasionalmente
                try:
                    progress_cb(dirpath)
                except Exception:  # noqa: BLE001
                    pass
            _steam_like_dirnames(dirnames, dirpath)
            if (os.path.basename(dirpath) == WE_APPID
                    and os.path.basename(os.path.dirname(dirpath)) == "content"
                    and os.path.basename(os.path.dirname(os.path.dirname(dirpath))) == "workshop"):
                log.info("Workshop encontrado (búsqueda profunda): %s", dirpath)
                return dirpath
    return None
