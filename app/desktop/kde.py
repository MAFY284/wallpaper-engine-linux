"""Integración con KDE Plasma (Wayland y X11).

Estrategia: en KDE los iconos y el fondo de Plasma viven en la misma ventana
del escritorio, por lo que una capa layer-shell externa taparía los iconos.
En su lugar se usa el plugin de fondo de Plasma `wel.video` (instalado en
~/.local/share/plasma/wallpapers/), que reproduce el vídeo DENTRO del
escritorio, detrás de los iconos, igual que Wallpaper Engine.

- snapshot(): guarda plugin y configuración actuales de cada escritorio
  (leyendo el archivo de configuración de Plasma).
- apply():    cambia el plugin a wel.video con el archivo y modo de ajuste.
- restore():  devuelve el plugin y configuración originales.

Notas:
- En este Plasma (6.6) `evaluateScript` ejecuta los scripts pero no devuelve
  su valor, así que las LECTURAS se hacen del archivo de configuración y las
  ESCRITURAS mediante el script (que sí tiene efecto visual inmediato).
- La configuración se restaura al cerrar la aplicación; si esta muere sin
  restaurar, el estado pendiente se guarda en un archivo y se restaura en el
  siguiente arranque.
"""

from __future__ import annotations

import configparser
import json
import logging
import os
import re
import time

import dbus

log = logging.getLogger("wel.desktop.kde")

PLASMASHELL_SERVICE = "org.kde.plasmashell"
PLASMASHELL_PATH = "/PlasmaShell"
PLASMASHELL_IFACE = "org.kde.PlasmaShell"

RC_FILE = os.path.expanduser("~/.config/plasma-org.kde.plasma.desktop-appletsrc")
STATE_FILE = os.path.expanduser("~/.config/wallpaper-engine-linux/plasma-state.json")

VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov", ".avi", ".ogv", ".m4v", ".gif")
PLUGIN_EXTS = VIDEO_EXTS + (".html", ".htm")


def _evaluate(script: str) -> str:
    obj = dbus.SessionBus().get_object(PLASMASHELL_SERVICE, PLASMASHELL_PATH)
    iface = dbus.Interface(obj, PLASMASHELL_IFACE)
    return str(iface.evaluateScript(script))


def _desktop_containment_ids() -> list[str]:
    """IDs de las contenciones de escritorio (una por monitor)."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(RC_FILE)
    except configparser.Error:
        return []
    ids = []
    for section in cp.sections():
        # configparser trunca el nombre en el primer ']': "[Containments][1]" → "Containments][1"
        m = re.fullmatch(r"Containments\]\[(\d+)$", section)
        if not m:
            continue
        plugin = cp.get(section, "plugin", fallback="")
        formfactor = cp.get(section, "formfactor", fallback="")
        if plugin == "org.kde.plasma.folder" or formfactor == "0":
            ids.append(m.group(1))
    return ids


def snapshot() -> dict[str, dict]:
    """Estado actual por contención de escritorio.

    Devuelve {id_contencion: {"plugin": "...", "keys": {"Image": "...", ...}}}
    """
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(RC_FILE)
    except configparser.Error as e:
        log.warning("no se pudo leer la configuración de Plasma: %s", e)
        return {}

    result: dict[str, dict] = {}
    for n in _desktop_containment_ids():
        section = f"Containments][{n}"
        plugin = cp.get(section, "wallpaperplugin", fallback="org.kde.image")
        keys: dict[str, str] = {}
        for sec in cp.sections():
            m = re.fullmatch(
                rf"Containments\]\[{n}\]\[Wallpaper\]\[(.+)\]\[General$", sec)
            if m and m.group(1) == plugin:
                for k, v in cp.items(sec):
                    keys[k] = v
        result[n] = {"plugin": plugin, "keys": keys}
    log.info("estado de Plasma: %s", result)
    return result


def apply(path: str, fit: str = "crop", screen: int | None = None) -> bool:
    """Establece un archivo (vídeo/GIF/imagen) como fondo.

    screen: None = todas las pantallas; 0, 1, … = una pantalla concreta.
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    url = "file://" + path
    ext = os.path.splitext(path)[1].lower()
    screen_filter = "true" if screen is None else f"i === {int(screen)}"
    target_plugin = "wel.video" if ext in PLUGIN_EXTS else "org.kde.image"

    # En Plasma 6.6 la recarga del MISMO plugin con nueva configuración es
    # intermitente. Si el escritorio ya usa el plugin destino, se hace un
    # "rebote" a un plugin neutro y se vuelve, forzando una recarga visual
    # segura (un parpadeo breve de color).
    if _uses_plugin(target_plugin):
        try:
            _evaluate("""
            var ds = desktops();
            for (var i = 0; i < ds.length; i++) {
                ds[i].wallpaperPlugin = "org.kde.color";
            }
            """)
            time.sleep(0.15)
        except dbus.DBusException as e:
            log.warning("rebote de plugin falló: %s", e)

    if target_plugin == "wel.video":
        script = """
        var ds = desktops();
        for (var i = 0; i < ds.length; i++) {
            if (!(%s)) continue;
            var d = ds[i];
            d.wallpaperPlugin = "wel.video";
            d.currentConfigGroup = ["Wallpaper", "wel.video", "General"];
            d.writeConfig("source", %s);
            d.writeConfig("fill", %s);
        }
        """ % (screen_filter, json.dumps(url), json.dumps(fit))
    else:
        script = """
        var ds = desktops();
        for (var i = 0; i < ds.length; i++) {
            if (!(%s)) continue;
            var d = ds[i];
            d.wallpaperPlugin = "org.kde.image";
            d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
            d.writeConfig("Image", %s);
        }
        """ % (screen_filter, json.dumps(url))

    try:
        _evaluate(script)
        log.info("fondo aplicado (pantalla %s): %s", screen, path)
        return True
    except dbus.DBusException as e:
        log.error("no se pudo aplicar el fondo: %s", e)
        return False


def _uses_plugin(plugin: str) -> bool:
    """True si algún escritorio usa actualmente el plugin indicado."""
    try:
        return any(entry.get("plugin") == plugin for entry in snapshot().values())
    except Exception:  # noqa: BLE001
        return False


def restore(state: dict[str, dict] | None = None) -> None:
    """Restaura el fondo original en cada escritorio."""
    if state is None:
        state = _load_pending_state()

    # cfg: {id_contencion: [plugin, [k1, v1, k2, v2, ...]]}
    cfg: dict[str, list] = {}
    for cid, entry in state.items():
        plugin = entry.get("plugin", "org.kde.image")
        keys = dict(entry.get("keys") or {})
        # Si el estado original no tenía claves (fondo por defecto del tema),
        # escribir Image="" fuerza al plugin nativo a volver a la imagen
        # por defecto y provoca la recarga visual.
        if plugin == "org.kde.image" and "Image" not in keys:
            keys["Image"] = ""
        pairs: list[str] = []
        for k, v in keys.items():
            pairs += [k, v]
        cfg[str(cid)] = [plugin, pairs]

    script = """
    var cfg = %s;
    var ds = desktops();
    for (var i = 0; i < ds.length; i++) {
        var d = ds[i];
        var c = cfg[String(d.id)];
        if (c === undefined) {
            c = ["org.kde.image", []];
        }
        d.wallpaperPlugin = c[0];
        d.currentConfigGroup = ["Wallpaper", c[0], "General"];
        for (var k = 0; k < c[1].length; k += 2)
            d.writeConfig(c[1][k], c[1][k + 1]);
    }
    """ % json.dumps(cfg)

    try:
        _evaluate(script)
        log.info("fondo original restaurado")
    except dbus.DBusException as e:
        log.error("no se pudo restaurar el fondo: %s", e)
    _clear_pending_state()


def save_pending_state(state: dict[str, dict]) -> None:
    """Guarda el estado para restaurarlo más tarde (o tras un cierre abrupto)."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"state": state, "pending": True}, f, ensure_ascii=False)
    except OSError as e:
        log.warning("no se pudo guardar el estado pendiente: %s", e)


def restore_pending_if_any() -> bool:
    """Restaura el fondo si quedó un estado pendiente de una ejecución anterior."""
    if not os.path.exists(STATE_FILE):
        return False
    log.warning("se detectó un estado pendiente de una ejecución anterior; restaurando")
    try:
        restore(None)
    except Exception as e:  # noqa: BLE001
        log.error("no se pudo restaurar el estado pendiente: %s", e)
    return True


def _load_pending_state() -> dict[str, dict]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("state") or {}
    except (OSError, ValueError):
        return {}


def _clear_pending_state() -> None:
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass
