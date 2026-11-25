#!/usr/bin/env python3
"""Genera las capturas de pantalla de la aplicación para la documentación.

Captura la ventana de la propia aplicación con Qt (grab), sin necesidad de
permisos del compositor. No modifica el fondo del escritorio.

Uso: make_screenshots.py [directorio_salida]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.main import MainWindow, STYLE, APP_NAME

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "screenshots")

app = QApplication(sys.argv)
app.setApplicationName(APP_NAME)
app.setStyleSheet(STYLE)

window = MainWindow()
window.show()


def grab(name: str) -> None:
    pixmap = window.grab()
    path = os.path.join(OUT_DIR, name)
    os.makedirs(OUT_DIR, exist_ok=True)
    if pixmap.save(path):
        print("capturado:", path)
    else:
        print("fallo al guardar:", path)


def step_settings() -> None:
    from app.ui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(window)
    dialog.show()
    QTimer.singleShot(800, lambda: _grab_dialog(dialog, "03-configuracion.png"))


def _grab_dialog(dialog, name: str) -> None:
    pixmap = dialog.grab()
    path = os.path.join(OUT_DIR, name)
    if pixmap.save(path):
        print("capturado:", path)
    dialog.close()
    app.quit()


def step_details() -> None:
    # seleccionar un vídeo compatible para mostrar la previsualización
    item = None
    for w in window.library.items:
        if w.kind == "video" and w.compatible:
            item = w
            break
    if item is None:
        print("sin vídeos en la biblioteca; usando el primero")
        item = window.library.items[0] if window.library.items else None
    if item:
        window.details.set_item(item, False)
    QTimer.singleShot(1500, lambda: (grab("02-detalles.png"), step_settings()))


def step_library() -> None:
    grab("01-biblioteca.png")
    step_details()


def check_scan() -> None:
    if window.library.items:
        QTimer.singleShot(800, step_library)
    else:
        QTimer.singleShot(500, check_scan)


window.library.start_scan()
QTimer.singleShot(1000, check_scan)

# salir sin pasar por closeEvent (no tocar el fondo del escritorio)
sys.exit(app.exec())
