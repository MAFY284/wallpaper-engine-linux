"""Integración con GNOME (Wayland/X11).

En GNOME los fondos estáticos se establecen con gsettings
(org.gnome.desktop.background), que es un fondo REAL del sistema. Los fondos
animados no son posibles en GNOME Wayland (Mutter no permite superficies de
fondo externas); se documenta como limitación.

Se guarda la configuración original (picture-uri y picture-uri-dark) y se
restaura al cerrar la aplicación.
"""

from __future__ import annotations

import logging
import os
import subprocess

log = logging.getLogger("wel.desktop.gnome")

SCHEMA = "org.gnome.desktop.background"
STATE_FILE = os.path.expanduser("~/.config/wallpaper-engine-linux/gnome-state.json")


def _gsettings_get(key: str) -> str:
    out = subprocess.run(
        ["gsettings", "get", SCHEMA, key], capture_output=True, text=True, check=False)
    return out.stdout.strip().strip("'\"") if out.returncode == 0 else ""


def _gsettings_set(key: str, value: str) -> bool:
    if value:
        result = subprocess.run(
            ["gsettings", "set", SCHEMA, key, value], capture_output=True, check=False)
    else:
        result = subprocess.run(
            ["gsettings", "reset", SCHEMA, key], capture_output=True, check=False)
    return result.returncode == 0


def snapshot() -> dict:
    return {
        "picture-uri": _gsettings_get("picture-uri"),
        "picture-uri-dark": _gsettings_get("picture-uri-dark"),
    }


def apply(path: str, fit: str = "zoom") -> bool:
    """Aplica una imagen estática como fondo real de GNOME."""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    uri = "file://" + path
    ok1 = _gsettings_set("picture-uri", uri)
    ok2 = _gsettings_set("picture-uri-dark", uri)
    if ok1 and ok2:
        log.info("fondo GNOME aplicado: %s", path)
    return ok1 and ok2


def restore(state: dict | None = None) -> None:
    state = state if state is not None else {"picture-uri": "", "picture-uri-dark": ""}
    _gsettings_set("picture-uri", state.get("picture-uri", ""))
    _gsettings_set("picture-uri-dark", state.get("picture-uri-dark", ""))
    log.info("fondo GNOME restaurado")
