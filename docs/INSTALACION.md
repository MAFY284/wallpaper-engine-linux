# Instalación

Wallpaper Engine Linux se instala a **nivel de usuario** (sin root ni sudo en
la instalación), no crea servicios ni entradas de inicio automático.

## Requisitos

- Ubuntu 24.04 o posterior (probado en **Ubuntu 26.04 LTS** con KDE Plasma 6.6
  en Wayland; compatible con GNOME para fondos estáticos).
- Dependencias del sistema (instalación única, con sudo):

```bash
sudo apt install python3-pyside6 python3-pyside6.qtsvg \
                 python3-pyside6.qtmultimedia python3-pyside6.qtmultimediawidgets \
                 python3-pyside6.qtwebenginewidgets python3-pyside6.qtdbus \
                 mpv libmpv2 ffmpeg
```

Solo si quieres el motor nativo para otros compositores (Hyprland/Sway/X11;
en KDE no es necesario):

```bash
sudo apt install libmpv-dev libwayland-dev libegl1-mesa-dev \
                 build-essential pkg-config
```

## Instalación

```bash
cd /ruta/a/wallpaper-engine-linux
./tools/install.sh
```

El instalador:

1. Compila el daemon nativo `bin/wel-wallpaperd` (si hay dependencias).
2. Instala el plugin de fondo de Plasma `wel.video` en
   `~/.local/share/plasma/wallpapers/`.
3. Instala el acceso directo y el icono en `~/.local/share/`.
4. Actualiza la caché de KDE.

Después, busca **«Wallpaper Engine Linux»** en el menú de aplicaciones.

> **Nota sobre plasmashell:** si actualizas el plugin QML manualmente, Plasma
> cachea el código: reinicia el shell con
> `systemctl --user restart plasma-plasmashell.service`.

## Desinstalación

```bash
./tools/uninstall.sh            # conserva configuración y caché
./tools/uninstall.sh --purge    # elimina también configuración y caché
```

La desinstalación restaura el fondo original si quedó pendiente y elimina el
acceso directo, el icono y el plugin de Plasma. El código fuente se elimina
manualmente (`rm -rf wallpaper-engine-linux`).

## Actualización

```bash
cd /ruta/a/wallpaper-engine-linux
git pull                       # si usas git
./tools/install.sh             # reinstala plugin, .desktop e icono
```
