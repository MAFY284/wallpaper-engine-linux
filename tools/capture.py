#!/usr/bin/env python3
"""Herramienta de captura de pantalla para verificación (KDE Wayland).

Usa la API nativa de KWin org.kde.KWin.ScreenShot2, autorizada mediante
el archivo .desktop wel-capture.desktop (X-KDE-DBUS-Restricted-Interfaces).

Uso: capture.py <archivo_salida.png>
"""
import os
import sys

import dbus
from PySide6.QtGui import QGuiApplication, QImage

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/wel-capture.png"

bus = dbus.SessionBus()
obj = bus.get_object("org.kde.KWin.ScreenShot2", "/org/kde/KWin/ScreenShot2")
iface = dbus.Interface(obj, "org.kde.KWin.ScreenShot2")

rfd, wfd = os.pipe()
try:
    result = dict(iface.CaptureActiveScreen(
        {"include-cursor": dbus.Boolean(False, variant_level=1),
         "native-resolution": dbus.Boolean(True, variant_level=1)},
        dbus.types.UnixFd(wfd)))
except Exception as e:
    print("error de captura:", e, file=sys.stderr)
    sys.exit(1)
finally:
    os.close(wfd)

data = b""
while True:
    chunk = os.read(rfd, 1 << 20)
    if not chunk:
        break
    data += chunk
os.close(rfd)

w = int(result.get("width", 0))
h = int(result.get("height", 0))
stride = int(result.get("stride", 0))
fmt = int(result.get("format", 0))

if not data or w <= 0 or h <= 0:
    print("captura vacía:", result, file=sys.stderr)
    sys.exit(1)

app = QGuiApplication(sys.argv)
img = QImage(bytes(data), w, h, stride, QImage.Format(fmt)).copy()
if not img.save(out):
    print("no se pudo guardar", out, file=sys.stderr)
    sys.exit(1)
print(out)
