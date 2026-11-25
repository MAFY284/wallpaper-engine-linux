"""Panel de detalles: previsualización, metadatos y controles del fondo."""

from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.library.models import TYPE_GIF, TYPE_IMAGE, TYPE_SCENE, TYPE_VIDEO, Wallpaper


def _ffprobe_ok(path: str) -> bool:
    """True si ffprobe puede leer el vídeo (descarta archivos corruptos/incompletos)."""
    if not path or not os.path.isfile(path):
        return False
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
            capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip()


class DetailPanel(QFrame):
    """Panel lateral con la información y controles del fondo seleccionado."""

    apply_requested = Signal(object, object, str)   # (item, screen, fit)
    favorite_toggled = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("detailPanel")
        self.setFixedWidth(320)
        self.item: Wallpaper | None = None
        self._movie: QMovie | None = None
        self._player: QMediaPlayer | None = None
        self._build_ui()
        self._show_empty()

    # ---------------------------------------------------------- UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # previsualización (etiqueta y vídeo superpuestos en un contenedor)
        self.preview_container = QFrame()
        self.preview_container.setObjectName("previewBox")
        self.preview_container.setFixedHeight(170)
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.video_widget = QVideoWidget()
        self.video_widget.setVisible(False)
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.video_widget)
        layout.addWidget(self.preview_container)

        # título
        self.title_label = QLabel("Selecciona un fondo")
        self.title_label.setObjectName("detailTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # descripción
        self.desc = QTextEdit()
        self.desc.setReadOnly(True)
        self.desc.setFixedHeight(90)
        self.desc.setObjectName("detailDesc")
        layout.addWidget(self.desc)

        # metadatos
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("meta")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        layout.addStretch(1)

        # pantalla destino
        self.screen_combo = QComboBox()
        self.screen_combo.addItem("Todas las pantallas", None)
        layout.addWidget(QLabel("Pantalla:"))
        layout.addWidget(self.screen_combo)

        # modo de ajuste
        self.fit_combo = QComboBox()
        self.fit_combo.addItem("Rellenar (crop)", "crop")
        self.fit_combo.addItem("Ajustar (fit)", "fit")
        self.fit_combo.addItem("Estirar (stretch)", "stretch")
        layout.addWidget(QLabel("Ajuste:"))
        layout.addWidget(self.fit_combo)

        # botones
        buttons = QHBoxLayout()
        self.fav_btn = QPushButton("☆ Favorito")
        self.fav_btn.setCheckable(True)
        self.fav_btn.clicked.connect(self._on_fav_clicked)
        self.apply_btn = QPushButton("Establecer como fondo")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        buttons.addWidget(self.fav_btn)
        buttons.addWidget(self.apply_btn, 1)
        layout.addLayout(buttons)

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("meta")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

    # ---------------------------------------------------------- estado
    def set_screens(self, outputs: list[dict]) -> None:
        """Actualiza el selector de pantallas."""
        current = self.screen_combo.currentData()
        self.screen_combo.clear()
        self.screen_combo.addItem("Todas las pantallas", None)
        for out in outputs:
            label = out["name"] + (f" · {out['size']}" if out.get("size") else "")
            self.screen_combo.addItem(label, out["index"])
        # restaurar selección si era válida
        for i in range(self.screen_combo.count()):
            if self.screen_combo.itemData(i) == current:
                self.screen_combo.setCurrentIndex(i)
                break

    def set_favorite(self, is_fav: bool) -> None:
        self.fav_btn.setChecked(is_fav)
        self.fav_btn.setText("★ Favorito" if is_fav else "☆ Favorito")

    def set_item(self, item: Wallpaper | None, is_favorite: bool = False) -> None:
        self._stop_preview()
        self.item = item
        if item is None:
            self._show_empty()
            return

        self.title_label.setText(item.title)
        self.set_favorite(is_favorite)
        meta_parts = [
            f"Tipo: {item.type_label}",
            f"Formato: {item.format.upper()}" if item.format else "",
            f"Resolución: {item.resolution}" if item.resolution else "",
            f"Origen: {item.source_label}",
            f"Ruta: {item.path}" if item.path else "",
        ]
        self.meta_label.setText(" · ".join(p for p in meta_parts if p))
        self.desc.setPlainText(item.description or "(sin descripción)")

        if not item.compatible:
            self.hint_label.setText(
                "⚠ Este fondo usa el formato propietario de Wallpaper Engine "
                "(escena) y no puede reproducirse. Puedes usar su vista previa.")
            self.apply_btn.setEnabled(bool(item.preview))
            self.apply_btn.setText("Usar vista previa" if item.preview
                                   else "No disponible")
        else:
            self.hint_label.setText("")
            self.apply_btn.setEnabled(True)
            self.apply_btn.setText("Establecer como fondo")

        self._start_preview(item)

    def _show_empty(self) -> None:
        self.preview_label.setText("")
        self.preview_label.setPixmap(QPixmap())
        self.title_label.setText("Selecciona un fondo")
        self.desc.setPlainText("Haz clic en un fondo de la biblioteca para ver "
                               "su previsualización y detalles.")
        self.meta_label.setText("")
        self.hint_label.setText("")
        self.apply_btn.setEnabled(False)
        self.fav_btn.setChecked(False)

    # ---------------------------------------------------------- previsualización
    def _start_preview(self, item: Wallpaper) -> None:
        path = item.path or item.preview or ""
        if not path or not os.path.isfile(path):
            return
        if item.kind in (TYPE_VIDEO,) and item.compatible:
            self._start_video(path)
        elif item.kind == TYPE_GIF or (item.kind == TYPE_SCENE and
                                       path.lower().endswith(".gif")):
            self._start_movie(path)
        else:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.preview_label.setPixmap(pixmap.scaled(
                    self.preview_label.width(), self.preview_label.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _start_video(self, path: str) -> None:
        # comprobar que el archivo es un vídeo íntegro antes de dárselo a
        # QtMultimedia (un archivo a medio descargar puede tumbar el proceso)
        if not _ffprobe_ok(path):
            self._video_fallback()
            return
        self._player = QMediaPlayer(self)
        self._player.setVideoOutput(self.video_widget)
        self._player.setAudioOutput(QAudioOutput(self))
        self._player.audioOutput().setMuted(True)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.setLoops(QMediaPlayer.Infinite)
        self._player.errorOccurred.connect(
            lambda *_: self._video_fallback())
        self.video_widget.setVisible(True)
        self.preview_label.clear()
        self.preview_label.setPixmap(QPixmap())
        self._player.play()

    def _video_fallback(self) -> None:
        """Si el vídeo no puede reproducirse, muestra la miniatura."""
        if not self.item:
            return
        for path in (self.item.thumbnail, self.item.preview, self.item.path):
            if path and os.path.isfile(path):
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    self.video_widget.setVisible(False)
                    self.preview_label.setPixmap(pixmap.scaled(
                        self.preview_label.width(), self.preview_label.height(),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    return

    def _start_movie(self, path: str) -> None:
        self._movie = QMovie(path)
        self.preview_label.setMovie(self._movie)
        self._movie.start()

    def _stop_preview(self) -> None:
        if self._player:
            self._player.stop()
            self._player.deleteLater()
            self._player = None
        if self._movie:
            self._movie.stop()
            self._movie = None
        self.video_widget.setVisible(False)
        self.preview_label.setMovie(None)
        self.preview_label.setPixmap(QPixmap())

    # ---------------------------------------------------------- eventos
    def _on_apply_clicked(self) -> None:
        if not self.item:
            return
        screen = self.screen_combo.currentData()
        fit = self.fit_combo.currentData()
        self.apply_requested.emit(self.item, screen, fit)

    def _on_fav_clicked(self) -> None:
        if not self.item:
            return
        self.favorite_toggled.emit(self.item)
