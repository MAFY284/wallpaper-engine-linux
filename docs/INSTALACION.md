# Instalación

Wallpaper Engine Linux funciona en **cualquier distribución** con Python 3.10+
y PySide6 (Qt 6). No crea servicios ni entradas de inicio automático; la
instalación es por usuario o por sistema según el método elegido.

## Ubuntu / Debian / derivadas

### Opción A: paquete .deb (recomendada)

Descarga `wallpaper-engine-linux_<versión>_amd64.deb` de la página de
[Releases](https://github.com/MAFY284/wallpaper-engine-linux/releases) y:

```bash
sudo apt install ./wallpaper-engine-linux_1.1.0_amd64.deb
```

El paquete instala las dependencias automáticamente (PySide6, ffmpeg, libmpv),
el acceso directo del menú, el icono y el plugin de Plasma. Desinstalar:

```bash
sudo apt remove wallpaper-engine-linux
```

### Opción B: desde el código fuente

```bash
sudo apt install python3-pyside6 python3-pyside6.qtsvg \
                 python3-pyside6.qtmultimedia python3-pyside6.qtmultimediawidgets \
                 python3-pyside6.qtwebenginewidgets python3-pyside6.qtdbus \
                 mpv ffmpeg
# opcional (motor nativo para otros compositores):
sudo apt install libmpv-dev libwayland-dev libegl1-mesa-dev build-essential pkg-config

git clone https://github.com/MAFY284/wallpaper-engine-linux.git
cd wallpaper-engine-linux
./tools/install.sh
```

## Arch Linux / Manjaro / EndeavourOS

### Opción A: PKGBUILD (recomendada)

Descarga el `PKGBUILD` de la página de
[Releases](https://github.com/MAFY284/wallpaper-engine-linux/releases)
(o usa `packaging/arch/PKGBUILD` del repositorio) y:

```bash
mkdir wallpaper-engine-linux && cd wallpaper-engine-linux
cp /ruta/al/PKGBUILD .
makepkg -si
```

Dependencias que resuelve pacman: `python`, `pyside6`, `qt6-multimedia`,
`qt6-webengine`, `qt6-svg`, `ffmpeg`, `libmpv`.

### Opción B: desde el código fuente

```bash
sudo pacman -S pyside6 qt6-multimedia qt6-webengine qt6-svg mpv ffmpeg

git clone https://github.com/MAFY284/wallpaper-engine-linux.git
cd wallpaper-engine-linux
./tools/install.sh
```

## Fedora / openSUSE / otras

Instala las dependencias equivalentes (PySide6 completo, ffmpeg, mpv) con el
gestor de tu distribución y después:

```bash
git clone https://github.com/MAFY284/wallpaper-engine-linux.git
cd wallpaper-engine-linux
./tools/install.sh
```

`install.sh` detecta la distribución y te indica los paquetes exactos si falta
algo. Como alternativa universal a los paquetes del sistema, PySide6 también
se puede instalar con pip: `pip install --user PySide6`.

## Desinstalación (instalación por script)

```bash
./tools/uninstall.sh            # conserva configuración y caché
./tools/uninstall.sh --purge    # elimina también configuración y caché
```

La desinstalación restaura el fondo original si quedó pendiente.

## Notas comunes

- **plasmashell cachea el QML de los plugins**: tras actualizar el plugin
  manualmente, reinicia el shell con
  `systemctl --user restart plasma-plasmashell.service`.
- **Buscador automático**: si la aplicación no encuentra tu biblioteca de
  Wallpaper Engine (por ejemplo, Steam instalado en otro disco), al arrancar
  la busca automáticamente y te pide confirmación de la carpeta encontrada.
  También puedes lanzarla desde Configuración → «Buscar automáticamente…».
- Las bibliotecas originales (Steam Workshop y Wallhaven) se usan en **modo
  de solo lectura**: nunca se modifican, mueven ni eliminan sus archivos.
