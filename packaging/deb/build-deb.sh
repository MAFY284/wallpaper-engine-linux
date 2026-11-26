#!/usr/bin/env bash
# Construye el paquete .deb de Wallpaper Engine Linux (para Ubuntu/Debian).
# Requiere: dpkg-deb (paquete dpkg), make, gcc, wayland-scanner, libmpv-dev.
#
# Uso: ./packaging/deb/build-deb.sh [directorio_salida]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/dist}"
VERSION="$(grep -m1 '^VERSION = ' "$ROOT/app/main.py" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
APP="wallpaper-engine-linux"
STAGE="$(mktemp -d /tmp/wel-deb.XXXXXX)"

echo "== Construyendo $APP $VERSION (deb) =="
mkdir -p "$OUT"

# ---------------------------------------------------------------- compilar daemon
echo "[1/4] Compilando el daemon nativo…"
make -C "$ROOT/core" >/dev/null

# ---------------------------------------------------------------- copiar archivos
echo "[2/4] Preparando el árbol del paquete…"
P="$STAGE/usr/share/$APP"
mkdir -p "$P" "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/lib/$APP"

cp -r "$ROOT/app" "$P/app"
cp -r "$ROOT/core" "$P/core"
cp -r "$ROOT/desktop" "$P/desktop"
cp -r "$ROOT/tools" "$P/tools"
cp -r "$ROOT/docs" "$P/docs"
cp "$ROOT/README.md" "$ROOT/TASKS.md" "$P/" 2>/dev/null || true

install -Dm755 "$ROOT/bin/wel" "$P/bin/wel"
install -Dm755 "$ROOT/bin/wel-wallpaperd" "$STAGE/usr/lib/$APP/wel-wallpaperd"
ln -sf "../share/$APP/bin/wel" "$STAGE/usr/bin/wel"

# plugin de Plasma
W="$STAGE/usr/share/plasma/wallpapers/wel.video"
mkdir -p "$W/contents/ui" "$W/contents/config"
cp "$ROOT/desktop/plasma-plugin/metadata.json" "$W/"
cp "$ROOT/desktop/plasma-plugin/contents/ui/main.qml" "$W/contents/ui/"
cp "$ROOT/desktop/plasma-plugin/contents/config/main.xml" "$W/contents/config/"

# acceso directo e icono
mkdir -p "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/scalable/apps"
cp "$ROOT/desktop/$APP.desktop" "$STAGE/usr/share/applications/$APP.desktop"
cp "$ROOT/desktop/$APP.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/$APP.svg"

# ---------------------------------------------------------------- control
echo "[3/4] Generando metadatos DEBIAN/control…"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $APP
Version: $VERSION
Section: graphics
Priority: optional
Architecture: amd64
Maintainer: MAFY284 <mafy284@users.noreply.github.com>
Depends: python3 (>= 3.10), python3-pyside6, python3-pyside6.qtsvg, python3-pyside6.qtmultimedia, python3-pyside6.qtmultimediawidgets, python3-pyside6.qtwebenginewidgets, python3-pyside6.qtdbus, libmpv2, ffmpeg
Description: Administrador de fondos de pantalla estáticos y animados
 Clon local de Wallpaper Engine para Linux: gestiona y reproduce fondos de
 pantalla estáticos y animados usando las bibliotecas existentes de
 Wallpaper Engine (Steam Workshop) y Wallhaven, sin servicios permanentes y
 con restauración automática del fondo original al cerrar. Compatible con
 KDE Plasma (Wayland/X11) y GNOME (fondos estáticos).
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

# ---------------------------------------------------------------- empaquetar
echo "[4/4] Empaquetando…"
DEB="$OUT/${APP}_${VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB" >/dev/null
rm -rf "$STAGE"

echo "✔ Paquete creado: $DEB"
du -h "$DEB"
