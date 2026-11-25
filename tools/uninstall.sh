#!/usr/bin/env bash
# Desinstalador de Wallpaper Engine Linux (nivel de usuario).
#
#  - Restaura el fondo original si la aplicación lo dejó pendiente
#  - Elimina el acceso directo, el icono y el plugin de Plasma
#  - Conserva la configuración y caché salvo que se pase --purge
#
# Uso: ./tools/uninstall.sh [--purge]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="wallpaper-engine-linux"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

echo "== Wallpaper Engine Linux: desinstalación =="

# 1. Restaurar el fondo si quedó pendiente
echo "[1/4] Comprobando fondo pendiente…"
if python3 -c "import sys; sys.path.insert(0, '$ROOT'); from app.desktop import kde; exit(0 if kde.restore_pending_if_any() else 0)" 2>/dev/null; then
    :
fi

# 2. Acceso directo e icono
echo "[2/4] Eliminando acceso directo e icono…"
rm -f "$HOME/.local/share/applications/$APP_NAME.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_NAME.svg"
if command -v kbuildsycoca6 >/dev/null; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi

# 3. Plugin de Plasma
echo "[3/4] Eliminando el plugin de Plasma…"
rm -rf "$HOME/.local/share/plasma/wallpapers/wel.video"

# 4. Datos (opcional)
if [ "$PURGE" = "1" ]; then
    echo "[4/4] Eliminando configuración y caché…"
    rm -rf "$HOME/.config/wallpaper-engine-linux"
    rm -rf "$HOME/.cache/wallpaper-engine-linux"
    rm -rf "$HOME/.local/share/wallpaper-engine-linux"
else
    echo "[4/4] Conservando configuración y caché (usa --purge para borrarlas)"
fi

echo "✔ Desinstalación completada. El código en $ROOT no se elimina;"
echo "  bórralo manualmente si no lo quieres:  rm -rf $ROOT"
