"""Modelo de datos de la biblioteca de fondos."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

# Tipos de contenido
TYPE_VIDEO = "video"
TYPE_GIF = "gif"
TYPE_IMAGE = "image"
TYPE_WEB = "web"
TYPE_SCENE = "scene"  # escena propietaria de Wallpaper Engine (no reproducible)

# Orígenes
SOURCE_WE = "wallpaper_engine"
SOURCE_WALLHAVEN = "wallhaven"
SOURCE_CUSTOM = "custom"

VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".ogv", ".m4v"}
GIF_EXTS = {".gif"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp", ".tif", ".tiff"}

ANIMATED_TYPES = {TYPE_VIDEO, TYPE_GIF, TYPE_WEB, TYPE_SCENE}


@dataclass
class Wallpaper:
    """Un fondo de pantalla de la biblioteca."""

    id: str                       # identificador único ("we:1088889817" o hash de ruta)
    title: str
    path: str                     # archivo principal (reproducción)
    source: str                   # wallpaper_engine | wallhaven | custom
    kind: str                     # video | gif | image | web | scene
    thumbnail: Optional[str] = None      # miniatura en caché
    preview: Optional[str] = None        # vista previa original del proyecto WE
    resolution: str = ""          # "2560x1440"
    width: int = 0
    height: int = 0
    description: str = ""
    tags: list[str] = field(default_factory=list)
    format: str = ""              # mp4, png, ...
    workshop_id: Optional[str] = None
    compatible: bool = True       # False para escenas propietarias
    mtime: float = 0.0
    size: int = 0

    @property
    def animated(self) -> bool:
        return self.kind in ANIMATED_TYPES

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Wallpaper":
        known = {f for f in Wallpaper.__dataclass_fields__}
        return Wallpaper(**{k: v for k, v in data.items() if k in known})

    @property
    def type_label(self) -> str:
        return {
            TYPE_VIDEO: "Vídeo",
            TYPE_GIF: "GIF",
            TYPE_IMAGE: "Imagen",
            TYPE_WEB: "Web",
            TYPE_SCENE: "Escena",
        }.get(self.kind, self.kind)

    @property
    def source_label(self) -> str:
        return {
            SOURCE_WE: "Wallpaper Engine",
            SOURCE_WALLHAVEN: "Wallhaven",
            SOURCE_CUSTOM: "Personalizado",
        }.get(self.source, self.source)
