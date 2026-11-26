"""Gestión de configuración de la aplicación (JSON persistente)."""

from __future__ import annotations

import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/wallpaper-engine-linux")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "custom_folders": [],
    "fit_mode": "crop",       # crop | fit | stretch
    "default_screen": None,   # None = todas las pantallas
    "quality": "auto",        # auto | low | high
    "max_fps": 0,             # 0 = sin límite (QtMultimedia no expone límite)
    "mute": True,
    "we_workshop_path": "",   # carpeta Workshop de WE encontrada por el buscador
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)
        for key in DEFAULTS:
            if key in stored:
                data[key] = stored[key]
    except (OSError, ValueError):
        pass
    return data


def save(settings: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def get(key: str, default=None):
    return load().get(key, default)


def set_value(key: str, value) -> None:
    settings = load()
    settings[key] = value
    save(settings)


def custom_folders() -> list[str]:
    return [str(p) for p in load().get("custom_folders", [])]


def we_workshop_path() -> str:
    """Carpeta Workshop de Wallpaper Engine guardada por el buscador ("" si no hay)."""
    return str(load().get("we_workshop_path", "") or "")


def add_custom_folder(path: str) -> None:
    folders = custom_folders()
    path = os.path.expanduser(path)
    if path not in folders:
        folders.append(path)
        set_value("custom_folders", folders)


def remove_custom_folder(path: str) -> None:
    folders = [p for p in custom_folders() if p != path]
    set_value("custom_folders", folders)
