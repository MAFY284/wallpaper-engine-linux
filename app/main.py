"""Wallpaper Engine Linux — interfaz gráfica.

Fase 3: biblioteca visual (Wallpaper Engine de Steam + Wallhaven + carpetas),
con búsqueda, miniaturas, tipos y aplicación/restauración de fondos.
"""

from __future__ import annotations

import logging
import os
import sys

# asegurar que el directorio raíz del proyecto está en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.desktop import environment, gnome, kde
from app.library.models import TYPE_SCENE, Wallpaper
from app.library.userdata import UserData
from app.monitors import outputs
from app.ui.detail_panel import DetailPanel
from app.ui.library_view import LibraryView
from app.ui.settings_dialog import SettingsDialog

log = logging.getLogger("wel")

APP_NAME = "Wallpaper Engine Linux"
VERSION = "1.0.0"


class LogHandler(logging.Handler):
    """Envía los mensajes de log al widget de texto."""

    def __init__(self, widget: QPlainTextEdit) -> None:
        super().__init__()
        self.widget = widget

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:  # noqa: BLE001
            msg = str(record.getMessage())
        self.widget.appendPlainText(msg)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.env = environment.detect()
        self.userdata = UserData()
        self.original_state: dict = {}
        self.current: Wallpaper | None = None
        self._build_ui()
        self._capture_original_state()
        self._update_status()

    # ---------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME}")
        self.resize(1240, 760)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # cabecera
        header = QHBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        self.restore_btn = QPushButton("Restaurar fondo original")
        self.restore_btn.clicked.connect(self._restore)
        self.add_file_btn = QPushButton("Abrir archivo…")
        self.add_file_btn.clicked.connect(self._open_file)
        self.add_folder_btn = QPushButton("Añadir carpeta…")
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.refresh_btn = QPushButton("Actualizar biblioteca")
        self.refresh_btn.clicked.connect(self.library_refresh)
        self.settings_btn = QPushButton("Configuración")
        self.settings_btn.clicked.connect(self._open_settings)
        header.addWidget(self.restore_btn)
        header.addWidget(self.add_file_btn)
        header.addWidget(self.add_folder_btn)
        header.addWidget(self.refresh_btn)
        header.addWidget(self.settings_btn)
        layout.addLayout(header)

        # contenido: biblioteca + panel de detalles
        content = QHBoxLayout()
        content.setSpacing(10)
        self.library = LibraryView(self.userdata)
        self.library.apply_requested.connect(self._on_apply_requested)
        self.library.preview_requested.connect(self._on_preview_requested)
        self.library.selected.connect(self._on_selected)
        self.library.favorite_toggled.connect(self._on_favorite_toggled)
        content.addWidget(self.library, 1)

        self.details = DetailPanel()
        self.details.set_screens(outputs.list_outputs())
        self.details.apply_requested.connect(self._on_detail_apply)
        self.details.favorite_toggled.connect(self._on_favorite_toggled)
        content.addWidget(self.details)
        layout.addLayout(content, 1)

        # registro
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(300)
        self.log_view.setFixedHeight(110)
        layout.addWidget(self.log_view)

    # ---------------------------------------------------------- estado
    def _capture_original_state(self) -> None:
        if self.env["desktop"] == "kde":
            self.original_state = kde.snapshot()
        elif self.env["desktop"] == "gnome":
            self.original_state = gnome.snapshot()
        else:
            log.warning("escritorio no reconocido; la restauración puede no funcionar")

    def _update_status(self) -> None:
        anim, via = environment.supports_animated(self.env)
        current = f" · fondo activo: {self.current.title}" if self.current else ""
        self.statusBar().showMessage(
            f"{self.env['desktop_name']} ({self.env['session_type']}) · "
            f"animados: {'sí' if anim else 'no'}{current}", 0)

    # ---------------------------------------------------------- acciones
    def _on_selected(self, item: Wallpaper) -> None:
        self.details.set_item(item, self.userdata.is_favorite(item.id))

    def _on_favorite_toggled(self, item: Wallpaper) -> None:
        is_fav = self.userdata.toggle_favorite(item.id)
        self.details.set_favorite(is_fav)
        self.library.update_favorites()
        self.statusBar().showMessage(
            f"{item.title}: añadido a favoritos" if is_fav
            else f"{item.title}: quitado de favoritos", 3000)

    def _on_detail_apply(self, item: Wallpaper, screen, fit: str) -> None:
        self._on_apply_requested(item, screen=screen, fit=fit)

    def _on_apply_requested(self, item: Wallpaper, screen=None, fit: str = None) -> None:
        if not item.compatible:
            self._on_preview_requested(item)
            return
        fit = fit or "crop"
        try:
            if self.env["desktop"] == "kde":
                kde.save_pending_state(self.original_state)
                ok = kde.apply(item.path, fit, screen=screen)
            elif self.env["desktop"] == "gnome":
                if item.animated:
                    self._notify_no_animated_gnome()
                    return
                ok = gnome.apply(item.path)
            else:
                self._notify_unsupported_desktop()
                return
        except FileNotFoundError:
            self.statusBar().showMessage("El archivo no existe", 4000)
            return
        if ok:
            self.current = item
            self.userdata.mark_used(item.id)
            self.library.update_favorites()
            self._update_status()
            self.statusBar().showMessage(
                f"Fondo aplicado: {item.title} — cierra la aplicación para restaurar "
                "el original", 6000)
        else:
            self.statusBar().showMessage("Error al aplicar (ver registro)", 5000)

    def _on_preview_requested(self, item: Wallpaper) -> None:
        if item.kind == TYPE_SCENE and item.preview:
            box = QMessageBox(self)
            box.setWindowTitle("Formato no compatible")
            box.setText(
                f"«{item.title}» es una escena de Wallpaper Engine (formato "
                "propietario) y no puede reproducirse.\n\n"
                "Puedes usar su vista previa animada/imagen como fondo degradado.")
            box.setIcon(QMessageBox.Warning)
            preview_btn = box.addButton("Usar vista previa", QMessageBox.AcceptRole)
            box.addButton("Cancelar", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is preview_btn:
                item2 = Wallpaper.from_dict(item.to_dict())
                item2.path = item.preview
                self._on_apply_requested(item2)
        else:
            self.statusBar().showMessage(
                f"«{item.title}» no es compatible con este entorno", 6000)

    def _restore(self) -> None:
        if self.env["desktop"] == "kde":
            kde.restore(self.original_state)
        elif self.env["desktop"] == "gnome":
            gnome.restore(self.original_state)
        self.current = None
        self._update_status()
        self.statusBar().showMessage("Fondo original restaurado", 5000)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir fondo",
            os.path.expanduser("~"),
            "Fondos compatibles (*.mp4 *.webm *.mkv *.mov *.gif *.jpg *.jpeg *.png *.webp *.avif);;Todos los archivos (*)")
        if path:
            ext = os.path.splitext(path)[1].lower()
            kind = "gif" if ext == ".gif" else ("video" if ext in kde.VIDEO_EXTS else "image")
            item = Wallpaper(id=f"adhoc:{os.path.basename(path)}", title=os.path.basename(path),
                             path=path, source="custom", kind=kind, compatible=True)
            self.details.set_item(item)
            self._on_apply_requested(item)

    def _add_folder(self) -> None:
        """Añade una carpeta de fondos a la biblioteca."""
        path = QFileDialog.getExistingDirectory(
            self, "Añadir carpeta de fondos", os.path.expanduser("~"))
        if not path:
            return
        from app.config import manager as config_manager
        config_manager.add_custom_folder(path)
        self.statusBar().showMessage(
            f"Carpeta añadida: {path} — actualizando biblioteca…", 4000)
        self.library.refresh()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.statusBar().showMessage(
                "Configuración guardada; actualizando biblioteca…", 3000)
            self.library.refresh()
            self.details.set_screens(outputs.list_outputs())

    def library_refresh(self) -> None:
        self.library.refresh()

    # ---------------------------------------------------------- avisos
    def _notify_no_animated_gnome(self) -> None:
        QMessageBox.information(
            self, "Limitación de GNOME Wayland",
            "GNOME Wayland no permite fondos animados de aplicaciones externas.\n"
            "Se soportan fondos estáticos (imágenes) mediante gsettings.\n\n"
            "Esta limitación está documentada en docs/01-informe-tecnico.md.")

    def _notify_unsupported_desktop(self) -> None:
        QMessageBox.information(
            self, "Escritorio no soportado",
            "Este escritorio aún no está soportado para aplicar fondos.")

    # ---------------------------------------------------------- cierre
    def closeEvent(self, event) -> None:  # noqa: N802
        log.info("cerrando: restaurando el fondo original…")
        self._restore()
        event.accept()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(STYLE)

    # recuperación de un cierre abrupto anterior
    env = environment.detect()
    if env["desktop"] == "kde":
        kde.restore_pending_if_any()

    window = MainWindow()
    logging.getLogger().addHandler(LogHandler(window.log_view))
    window.show()
    window.library.start_scan()

    return app.exec()


STYLE = """
QWidget {
    background-color: #0d1117;
    color: #e8eaed;
    font-size: 13px;
}
QMainWindow, QPlainTextEdit, QLineEdit {
    background-color: #10161d;
}
QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #4da3ff;
}
QLabel#meta {
    color: #8b949e;
    font-size: 11px;
}
QLabel#cardTitle {
    font-weight: bold;
    color: #e8eaed;
}
QLabel#thumb {
    background-color: #161c24;
    border-radius: 8px;
    color: #55606c;
}
QFrame#card {
    background-color: #161c24;
    border: 1px solid #232d38;
    border-radius: 10px;
}
QFrame#card:hover {
    border-color: #4da3ff;
}
QLabel#applyIcon {
    color: #4da3ff;
    font-size: 14px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 4px;
}
QLabel#applyIcon:hover {
    background-color: #1f6feb;
    color: white;
}
QLineEdit {
    border: 1px solid #2a323c;
    border-radius: 6px;
    padding: 6px;
}
QLineEdit:focus {
    border-color: #4da3ff;
}
QPushButton {
    background-color: #232b34;
    border: 1px solid #2f3a46;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover {
    background-color: #2c3641;
}
QPushButton#primary {
    background-color: #1f6feb;
    border-color: #1f6feb;
    color: white;
    font-weight: bold;
}
QScrollArea {
    border: none;
}
QPushButton[chip="true"] {
    background-color: #1a212b;
    border: 1px solid #2a323c;
    border-radius: 14px;
    padding: 5px 12px;
    font-size: 12px;
}
QPushButton[chip="true"]:checked {
    background-color: #1f6feb;
    border-color: #1f6feb;
    color: white;
    font-weight: bold;
}
QFrame#detailPanel {
    background-color: #12171e;
    border: 1px solid #232d38;
    border-radius: 10px;
}
QFrame#previewBox {
    background-color: #0a0e13;
    border-radius: 8px;
    color: #55606c;
}
QLabel#detailTitle {
    font-size: 16px;
    font-weight: bold;
}
QTextEdit#detailDesc {
    background-color: #161c24;
    border: 1px solid #232d38;
    border-radius: 6px;
    color: #9aa4ae;
}
QLabel#star {
    font-size: 16px;
    color: #e3b341;
}
QLabel#star:hover {
    font-size: 18px;
}
QStatusBar {
    background-color: #0d1117;
    color: #9aa4ae;
}
"""


if __name__ == "__main__":
    sys.exit(main())
