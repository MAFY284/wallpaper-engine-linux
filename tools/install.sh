#!/usr/bin/env bash
# Instalador de Wallpaper Engine Linux (instalación a nivel de usuario, sin root).
#
#  - Compila el daemon nativo (core/)
#  - Instala el plugin de fondo de Plasma (wel.video) en ~/.local/share/plasma/
#  - Instala el acceso directo (.desktop) y el icono
#  - Actualiza la caché de KDE
#
# Uso: ./tools/install.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="wallpaper-engine-linux"

echo "== Wallpaper Engine Linux: instalación =="

# 1. Compilar el daemon nativo (opcional: motor para otros compositores)
echo "[1/4] Compilando el daemon nativo…"
if command -v wayland-scanner >/dev/null && pkg-config --exists mpv egl wayland-client wayland-egl; then
    make -C "$ROOT/core" >/dev/null
    echo "      daemon: $ROOT/bin/wel-wallpaperd"
else
    echo "      (sin dependencias del daemon; se omite — solo afecta a Hyprland/Sway/X11)"
fi

# 2. Plugin de fondo de Plasma
echo "[2/4] Instalando el plugin de Plasma (wel.video)…"
PLUGIN_DIR="$HOME/.local/share/plasma/wallpapers/wel.video"
mkdir -p "$PLUGIN_DIR/contents/ui" "$PLUGIN_DIR/contents/config"
cp "$ROOT/desktop/plasma-plugin/metadata.json" "$PLUGIN_DIR/"
cp "$ROOT/desktop/plasma-plugin/contents/ui/main.qml" "$PLUGIN_DIR/contents/ui/"
cp "$ROOT/desktop/plasma-plugin/contents/config/main.xml" "$PLUGIN_DIR/contents/config/"
echo "      instalado en $PLUGIN_DIR"

# 3. Acceso directo e icono
echo "[3/4] Instalando acceso directo e icono…"
mkdir -p "$HOME/.local/share/applications"
cp "$ROOT/desktop/$APP_NAME.desktop" "$HOME/.local/share/applications/$APP_NAME.desktop"
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
cp "$ROOT/desktop/$APP_NAME.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_NAME.svg"
chmod +x "$ROOT/bin/wel"
echo "      acceso directo: $HOME/.local/share/applications/$APP_NAME.desktop"

# 4. Actualizar caché de KDE
echo "[4/4] Actualizando la caché de aplicaciones…"
if command -v kbuildsycoca6 >/dev/null; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi

echo
echo "✔ Instalación completada."
echo "  Abre «Wallpaper Engine Linux» desde el menú de aplicaciones."
echo "  No se instala ningún servicio ni inicio automático."
