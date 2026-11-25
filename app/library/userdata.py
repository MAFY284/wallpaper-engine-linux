"""Datos del usuario: favoritos, recientes y preferencias (persistentes)."""

from __future__ import annotations

import json
import os
import time

CONFIG_DIR = os.path.expanduser("~/.config/wallpaper-engine-linux")
DATA_FILE = os.path.join(CONFIG_DIR, "userdata.json")

_DEFAULTS = {
    "favorites": {},          # id -> timestamp
    "recents": [],            # [id, ...] más reciente primero
    "settings": {},           # preferencias (fase 5)
}


class UserData:
    def __init__(self, path: str = DATA_FILE) -> None:
        self.path = path
        self._data = _load(path)

    # ---------------------------------------------------------- favoritos
    def is_favorite(self, item_id: str) -> bool:
        return item_id in self._data["favorites"]

    def toggle_favorite(self, item_id: str) -> bool:
        if item_id in self._data["favorites"]:
            del self._data["favorites"][item_id]
            self._save()
            return False
        self._data["favorites"][item_id] = time.time()
        self._save()
        return True

    def favorites(self) -> list[str]:
        return list(self._data["favorites"].keys())

    # ---------------------------------------------------------- recientes
    def mark_used(self, item_id: str) -> None:
        recents = self._data["recents"]
        if item_id in recents:
            recents.remove(item_id)
        recents.insert(0, item_id)
        del recents[20:]  # máximo 20 recientes
        self._save()

    def recents(self) -> list[str]:
        return list(self._data["recents"])

    # ---------------------------------------------------------- ajustes
    def get_setting(self, key: str, default=None):
        return self._data["settings"].get(key, default)

    def set_setting(self, key: str, value) -> None:
        self._data["settings"][key] = value
        self._save()

    # ---------------------------------------------------------- persistencia
    def _save(self) -> None:
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=1)
        except OSError:
            pass


def _load(path: str) -> dict:
    data = json.loads(json.dumps(_DEFAULTS))  # copia profunda
    try:
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        for key in _DEFAULTS:
            if key in stored:
                data[key] = stored[key]
    except (OSError, ValueError):
        pass
    return data
