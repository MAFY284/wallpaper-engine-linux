"""Diálogo de configuración de la aplicación."""

from __future__ import annotations

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from app.config import manager as config_manager
from app.importers import steam


class SettingsDialog(QDialog):
    find_we_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.resize(600, 480)
        self.settings = config_manager.load()
        self._we_path = self.settings.get("we_workshop_path", "") or ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # -------------------------------------------------- Wallpaper Engine
        layout.addWidget(QLabel("<b>Carpeta de Wallpaper Engine (Steam)</b>"))
        we_row = QHBoxLayout()
        current = self._we_path or steam.find_we_workshop()
        self.we_label = QLabel(current if current else
                               "No encontrada (usa el buscador o elige la carpeta)")
        self.we_label.setObjectName("meta")
        self.we_label.setWordWrap(True)
        we_row.addWidget(self.we_label, 1)
        layout.addLayout(we_row)
        we_btns = QHBoxLayout()
        search_btn = QPushButton("Buscar automáticamente…")
        search_btn.clicked.connect(self.find_we_requested.emit)
        manual_btn = QPushButton("Elegir manualmente…")
        manual_btn.clicked.connect(self._choose_we_folder)
        we_btns.addWidget(search_btn)
        we_btns.addWidget(manual_btn)
        we_btns.addStretch(1)
        layout.addLayout(we_btns)

        # -------------------------------------------------- carpetas extra
        layout.addWidget(QLabel("<b>Carpetas de fondos adicionales</b>"))
        self.folders_list = QListWidget()
        self.folders_list.addItems(self.settings.get("custom_folders", []))
        layout.addWidget(self.folders_list)

        folder_btns = QHBoxLayout()
        add_btn = QPushButton("Añadir carpeta…")
        add_btn.clicked.connect(self._add_folder)
        remove_btn = QPushButton("Quitar seleccionada")
        remove_btn.clicked.connect(self._remove_folder)
        folder_btns.addWidget(add_btn)
        folder_btns.addWidget(remove_btn)
        folder_btns.addStretch(1)
        layout.addLayout(folder_btns)

        # modo de ajuste por defecto
        fit_row = QHBoxLayout()
        fit_row.addWidget(QLabel("Ajuste por defecto:"))
        self.fit_combo = QComboBox()
        self.fit_combo.addItem("Rellenar (crop)", "crop")
        self.fit_combo.addItem("Ajustar (fit)", "fit")
        self.fit_combo.addItem("Estirar (stretch)", "stretch")
        current_fit = self.settings.get("fit_mode", "crop")
        for i in range(self.fit_combo.count()):
            if self.fit_combo.itemData(i) == current_fit:
                self.fit_combo.setCurrentIndex(i)
        fit_row.addWidget(self.fit_combo)
        fit_row.addStretch(1)
        layout.addLayout(fit_row)

        # nota de rendimiento
        note = QLabel(
            "La reproducción usa la aceleración por hardware del sistema. "
            "Los vídeos se reproducen a su velocidad nativa; el audio está "
            "desactivado por defecto.")
        note.setWordWrap(True)
        note.setObjectName("meta")
        layout.addWidget(note)

        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Añadir carpeta de fondos",
                                                os.path.expanduser("~"))
        if path and not self._contains(path):
            self.folders_list.addItem(path)

    def _choose_we_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta de Wallpaper Engine",
            self._we_path or os.path.expanduser("~"))
        if path:
            self._we_path = path
            self.we_label.setText(path)

    def _remove_folder(self) -> None:
        row = self.folders_list.currentRow()
        if row >= 0:
            self.folders_list.takeItem(row)

    def _contains(self, path: str) -> bool:
        for i in range(self.folders_list.count()):
            if self.folders_list.item(i).text() == path:
                return True
        return False

    def _on_accept(self) -> None:
        folders = [self.folders_list.item(i).text()
                   for i in range(self.folders_list.count())]
        self.settings["custom_folders"] = folders
        self.settings["fit_mode"] = self.fit_combo.currentData()
        if self._we_path:
            self.settings["we_workshop_path"] = self._we_path
        config_manager.save(self.settings)
        self.accept()
