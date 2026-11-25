#!/usr/bin/env python3
"""Renderiza una página web con QtWebEngine fuera de pantalla y la guarda como PNG.

Herramienta de desarrollo para verificar fondos web sin necesidad de ver el
escritorio. Uso: render_page.py <url|ruta.html> <salida.png> [tiempo_s]
"""
import os
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

url = sys.argv[1] if len(sys.argv) > 1 else ""
out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/opencode/page.png"
wait = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0

if not url:
    print("uso: render_page.py <url> <salida.png> [segundos]")
    sys.exit(2)

app = QApplication(sys.argv)
view = QWebEngineView()
view.resize(1280, 720)
target = QUrl.fromLocalFile(os.path.abspath(url)) if not url.startswith("http") else QUrl(url)
view.load(target)
view.show()  # necesario para el render en algunos backends


def shot():
    pixmap = view.grab()
    if pixmap.save(out):
        print("guardado en", out)
        app.quit()
    else:
        print("no se pudo guardar")
        app.exit(1)


QTimer.singleShot(int(wait * 1000), shot)
sys.exit(app.exec())
