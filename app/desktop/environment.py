"""Detección del entorno de escritorio (KDE / GNOME / otros, Wayland / X11)."""

from __future__ import annotations

import logging
import os
import shutil

log = logging.getLogger("wel.desktop.environment")


def detect() -> dict:
    """Devuelve información del entorno.

    {
      "session_type": "wayland" | "x11" | "?",
      "desktop":      "kde" | "gnome" | "other" | "?",
      "desktop_name": valor de XDG_CURRENT_DESKTOP,
      "display_server":"wayland" | "x11" | "?",
      "has_plasmashell": bool,
      "has_gnome_shell": bool,
    }
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "?").lower()
    desktop_name = os.environ.get("XDG_CURRENT_DESKTOP", "?")

    if "KDE" in desktop_name.upper():
        desktop = "kde"
    elif "GNOME" in desktop_name.upper():
        desktop = "gnome"
    else:
        desktop = "other"

    info = {
        "session_type": session_type,
        "desktop": desktop,
        "desktop_name": desktop_name,
        "display_server": session_type if session_type in ("wayland", "x11") else "?",
        "has_plasmashell": shutil.which("plasmashell") is not None,
        "has_gnome_shell": shutil.which("gnome-shell") is not None,
    }
    log.info("entorno detectado: %s", info)
    return info


def supports_animated(info: dict | None = None) -> tuple[bool, str]:
    """Indica si los fondos animados son soportados y por qué vía."""
    info = info or detect()
    if info["desktop"] == "kde":
        return True, "plugin de fondo de Plasma (wel.video)"
    if info["desktop"] == "gnome":
        if info["session_type"] == "wayland":
            return False, "GNOME Wayland no permite fondos animados externos (limitación documentada)"
        return True, "ventana de escritorio X11 (fase posterior)"
    if info["session_type"] == "wayland":
        return True, "capa layer-shell (wlroots)"
    return True, "ventana de escritorio X11 (fase posterior)"
