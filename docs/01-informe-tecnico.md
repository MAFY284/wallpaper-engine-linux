# Wallpaper Engine Linux — Informe técnico y arquitectura propuesta

**Fase 1 — Investigación y viabilidad**
**Fecha:** 2026-11-24
**Equipo objetivo:** Ubuntu 26.04 LTS con KDE Plasma 6.6 (Wayland) y GNOME 50 (Wayland)

---

## 1. Resumen ejecutivo

Es **viable** construir un clon local de Wallpaper Engine para el equipo del usuario:

- **KDE Plasma Wayland (entorno actual):** KWin 6.6.7 soporta el protocolo
  `zwlr_layer_shell_v1`, lo que permite dibujar superficies en la *capa de fondo*
  del escritorio (detrás de iconos y ventanas, encima del fondo de Plasma). Es la
  vía principal para fondos animados. **No se modifica ninguna configuración de
  Plasma**: la capa simplemente cubre el fondo nativo y, al cerrar la aplicación,
  este reaparece intacto.
- **GNOME Wayland (Ubuntu normal):** Mutter **no** soporta `zwlr_layer_shell_v1`
  ni permite que aplicaciones externas dibujen detrás del escritorio. En GNOME se
  usarán **fondos estáticos reales** mediante `gsettings` (guardando y restaurando
  la configuración original). Los fondos animados en GNOME Wayland son una
  limitación documentada (sin una extensión de GNOME Shell no hay vía soportada).
- **Biblioteca de Wallpaper Engine:** 55 proyectos localizados. De ellos:
  - 23 proyectos `video` (MP4) → **compatibles** directamente.
  - 1 proyecto `web` (HTML5) → compatible con matices (fase avanzada).
  - 31 proyectos `scene` (`scene.pkg`) → formato propietario compilado de
    Wallpaper Engine; **no reproducibles** (se documenta y se muestra su vista
    previa animada como alternativa de baja fidelidad opcional).
- **Wallhaven:** la carpeta real del usuario es `~/Imágenes/Wallpapers/` (la ruta
  `~/Imágenes/wallpapers/` no existe; se soportan ambas por detección).

La arquitectura separa la **GUI de administración** (Python + PySide6) del
**motor de reproducción** (daemon nativo en C con libmpv empotrado, inspirado en
el diseño probado de *mpvpaper*). Esto cumple los requisitos de rendimiento,
ausencia de procesos huérfanos y restauración automática del escritorio.

---

## 2. Investigación del entorno (datos reales)

### 2.1 Sesión y escritorio

| Dato | Valor |
|---|---|
| Distro | Ubuntu 26.04.1 LTS (Resolute Raccoon) |
| Sesión actual | `XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=KDE` |
| Compositor | KWin 6.6.7 (`kwin_wayland`) |
| Shell alternativo instalado | GNOME Shell 50.1 |
| Monitores | 1× DP-2, 2560×1440 @ 180 Hz, escala 1 (consultable con `kscreen-doctor`) |
| GPU | AMD Radeon RX 9070 (RDNA4) + iGPU Phoenix |
| Protocolo de superficies de fondo | **`zwlr_layer_shell_v1` disponible en KWin** (verificado en `libkwin`: símbolos `QtWaylandServer::zwlr_layer_shell_v1`) |

### 2.2 Bibliotecas de contenido

**Steam:** biblioteca principal en `~/.local/share/Steam` (única en
`libraryfolders.vdf`). Wallpaper Engine = AppID `431960`.

```
~/.local/share/Steam/steamapps/workshop/content/431960/   →  55 proyectos, 2,4 GB
```

**Distribución real de tipos** (leído de cada `project.json`):

| Tipo | Cantidad | Compatibilidad |
|---|---|---|
| `scene` / `Scene` | 31 | ❌ Formato propietario (`scene.pkg`) |
| `video` / `Video` | 23 | ✅ MP4 (reproducibles con mpv) |
| `Web` | 1 | ⚠️ HTML5 (fase avanzada) |

**Estructura típica de un proyecto** (verificada):

```
<workshop_id>/
├── project.json      # metadatos: title, type, preview, tags, description, workshopid
├── preview.gif       # o preview.jpg (vista previa, siempre presente)
└── scene.pkg         # tipo scene  (propietario)
   └──  o bien: *.mp4  # tipo video
   └──  o bien: *.html + assets  # tipo web
```

- Las escenas son paquetes binarios con efectos/shaders compilados del motor
  propietario de Wallpaper Engine. Reproducirlas requeriría reimplementar un
  intérprete propietario; **fuera de alcance** (documentado en §8).
- Las vistas previas (`preview.gif`/`preview.jpg`) siempre existen: sirven para
  miniaturas y como degradado elegante para escenas incompatibles.

**Wallhaven:** el usuario tiene `~/Imágenes/Wallpapers/` (3 PNG, 2560×1440).
`~/Imágenes/` contiene además muchos archivos sueltos que **no** se indexarán por
defecto (solo carpetas de fondos configuradas).

### 2.3 Herramientas disponibles

| Herramienta | Estado | Uso |
|---|---|---|
| Python 3.14.4 + pip + venv | ✅ | GUI |
| PySide6 6.10.2 (Qt 6.10) | ✅ en apt (widgets, SVG, Multimedia, WebEngine) | GUI |
| mpv 0.41.0 + `libmpv2` | ✅ instalado | Motor de reproducción |
| `libmpv-dev` 0.41.0 | ⚠️ instalable desde apt | Daemon C |
| ffmpeg 8.0.1 | ✅ | Generación de miniaturas |
| gcc, g++, cmake, ninja, pkg-config, wayland-scanner | ✅ | Daemon C |
| `libwayland-dev` 1.24, `libegl1-mesa-dev` | ✅ | Cliente Wayland |
| `kscreen-doctor`, `qdbus6`, `kreadconfig6` | ✅ | Monitores / estado KDE |
| `plasma-apply-wallpaperimage` | ✅ | Restauración KDE (si fuese necesaria) |
| `gsettings` + esquema `org.gnome.desktop.background` | ✅ | Fondos estáticos GNOME |
| mpvpaper | ❌ no empaquetado en Ubuntu | — (implementación propia) |

---

## 3. Evaluación y justificación de tecnologías

### 3.1 Motor de reproducción sobre el escritorio

| Alternativa | KDE Wayland | GNOME Wayland | X11 | Rendimiento | Verdicto |
|---|---|---|---|---|---|
| **mpv empotrado + capa layer-shell propia (C)** | ✅ | ❌ (Mutter) | ✅ (ventana desktop) | ✅ hw-accel VAAPI/Vulkan | **Elegida** |
| mpvpaper como subproceso | ✅ | ❌ | ✅ | ✅ | Rechazada: sin IPC de control fino (pausa/volumen/por-monitor), no empaquetada |
| Qt Multimedia | ❌ (sin layer-shell) | ❌ | ✅ | ⚠️ formatos limitados | Rechazada |
| Qt WebEngine (HTML5) | ⚠️ solo con LayerShellQt | ❌ | ✅ | ⚠️ pesado | Solo para fondos web (fase avanzada) |
| Plugin QML de Plasma | ✅ | ❌ | ✅ | ✅ | Rechazada: altera configuración persistente de Plasma |
| xwinwrap / herramientas X11 | — | — | ⚠️ hacky | ⚠️ | Rechazada: solo X11 |

**Decisión:** daemon nativo en **C** (`wel-wallpaperd`) con **libmpv empotrado**
(render API). Razones:

1. **Un solo motor para todo:** mpv reproduce MP4/WebM/GIF e imágenes estáticas
   (JPG/PNG/WebP/AVIF) con loop, mute, pausa y límite de FPS por opciones.
   No hay bifurcación imagen/vídeo.
2. **Sin procesos hijos:** libmpv va dentro del daemon → **imposible dejar
   procesos huérfanos** (requisito §5).
3. **Wayland nativo:** el daemon es un cliente `zwlr_layer_shell_v1` con salida
   EGL; KWin destruye la superficie automáticamente si el daemon muere (incluso
   con SIGKILL), restaurando el fondo de Plasma al instante. *Mecanismo de
   recuperación casi gratuito.*
4. **X11:** mismo daemon con backend de ventana `_NET_WM_WINDOW_TYPE_DESKTOP`
   (detrás de iconos en KDE/GNOME X11 y otros WMs).
5. **Portable:** `zwlr_layer_shell_v1` también lo soportan Hyprland/Sway
   (wlroots), con lo que la arquitectura ya cubre otros compositores.
6. **Hardware:** libplacebo `gpu-next` + VAAPI/Vulkan en la RX 9070 → consumo
   mínimo de CPU y GPU.
7. Referencia de diseño: *mpvpaper* (código abierto, mismo patrón), pero con
   control IPC completo que mpvpaper no ofrece.

### 3.2 GUI

| Alternativa | Valoración |
|---|---|
| **Python + PySide6 (Qt 6.10, paquete de Ubuntu)** | ✅ **Elegida.** Qt Widgets maduro, estilo moderno con QSS, WebEngine disponible para vistas previas HTML, instalación limpia vía apt sin virtualenv, iteración rápida |
| Python + GTK4 | ✅ viable, pero Qt casa mejor con QML futuro y con WebEngine |
| C++ + Qt | ⚠️ más rápido, mucho más coste de mantenimiento; el rendimiento crítico ya vive en el daemon C |
| Rust + GTK/Qt | ⚠️ ecosistema GUI menos maduro para esta interfaz; mismo argumento que C++ |

La GUI solo administra: la librería, las vistas previas, la configuración y el
control del daemon por IPC. El trabajo pesado (decodificación/render) ocurre en
el daemon nativo, por lo que Python no es un cuello de botella.

### 3.3 Fondos web/HTML5

Solo hay 1 fondo web en la biblioteca del usuario. Plan:

- **Fase avanzada:** renderizar la página en QtWebEngine (offscreen) y transmitir
  frames RGB al daemon por memoria compartida (modo "fuente de frames externa").
- Se documenta que la interactividad (clics) no estará disponible en la capa de
  fondo; solo animación.
- Si la complejidad no lo justifica, se degrada a vista previa estática.

---

## 4. Arquitectura propuesta

### 4.1 Diagrama de componentes

```
┌────────────────────────────────────────────────────────────────┐
│                      GUI (Python + PySide6)                    │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ ui/      │ │ library/ │ │importers/│ │ engine/ (cliente  │  │
│  │ ventanas │ │ índice,  │ │ steam/we │ │ IPC del daemon)   │  │
│  │ estilos  │ │ caché,   │ │ wallhaven│ └───────────────────┘  │
│  └──────────┘ │ favoritos│ └──────────┘           │            │
│  ┌──────────┐ └──────────┘                        │            │
│  │desktop/  │ ← detección KDE/GNOME/X11/          │  socket    │
│  │monitors/ │   guardado/restauración fondo        │  Unix JSON │
│  │config/   │                                      ▼            │
└──┴──────────┴───────────────────────────────────────────────────┘
                                                    │
                        ┌───────────────────────────▼───────────┐
                        │        wel-wallpaperd (daemon C)      │
                        │                                       │
                        │  backend wayland: capa layer-shell    │
                        │    (zwlr_layer_shell_v1, background)  │
                        │  backend x11: ventana tipo DESKTOP     │
                        │                                       │
                        │  por monitor: surface + EGL +         │
                        │  libmpv render API (mpv empotrado)    │
                        │                                       │
                        │  IPC: {"cmd":"load","output":"DP-2",  │
                        │        "path":"...","fit":"fill",...} │
                        └───────────────────────────────────────┘
```

### 4.2 Módulos

| Módulo | Ubicación | Responsabilidad |
|---|---|---|
| 1. Interfaz gráfica | `app/ui/` | Biblioteca en cuadrícula, búsqueda, filtros, panel de detalles, configuración |
| 2. Administrador de bibliotecas | `app/library/` | Índice unificado, miniaturas en caché, favoritos, recientes, tipos |
| 3. Importadores | `app/importers/` | Steam/WE (solo lectura, detección de carpetas) y Wallhaven/carpetas personalizadas |
| 4. Motor de reproducción | `core/` (C) + `app/engine/` (cliente IPC) | Daemon libmpv + protocolo de control |
| 5. Integración de escritorio | `app/desktop/` | Detección de entorno, guardado/restauración del fondo original |
| 6. Administrador de monitores | `app/monitors/` | Detección de salidas (kscreen-doctor / wayland), asignación fondo→monitor |
| 7. Configuración | `app/config/` | JSON persistente en `~/.config/wallpaper-engine-linux/` |
| 8. Gestión de procesos/restauración | `app/engine/lifecycle.py` + daemon | Arranque/apagado seguro, heartbeat, recuperación |

### 4.3 Flujo de vida de la aplicación (requisito §5)

```
Abrir:
 1. detectar_entorno()          → KDE-Wayland / KDE-X11 / GNOME-Wayland / GNOME-X11 / Hyprland
 2. snapshot_fondo_original()   → KDE: nada que tocar (capa cubre) + guardar por si acaso
                                  GNOME: leer picture-uri / picture-uri-dark actuales
 3. lanzar wel-wallpaperd       → socket en $XDG_RUNTIME_DIR/wel/
 4. usuario elige fondo         → cmd "load" → superficie por monitor + libmpv
 5. cambios de fondo            → cmd "load" sobre el mismo contexto (sin reiniciar)

Cerrar (normal o Ctrl+Q):
 1. cmd "shutdown" o SIGTERM al daemon → libera superficies/EGL/libmpv
 2. el compositor elimina la capa → reaparece el fondo nativo de Plasma
 3. GNOME: restaurar picture-uri guardado (gsettings)
 4. verificar que no quedan procesos (QProcess::finished + verificación)

Fallo inesperado:
 - SIGKILL al daemon → KWin/X11 elimina la superficie automáticamente (fondo restaurado)
 - GUI muere sin avisar → el daemon tiene watchdog: sin heartbeat (3 s) se autodestruye
 - reinicio posterior → si quedó estado guardado sin restaurar, se restaura al abrir
```

### 4.4 Protocolo IPC (borrador)

Socket Unix, líneas JSON. Comandos: `hello`, `load`, `pause`, `resume`, `set_volume`,
`set_fit`, `set_fps`, `mute`, `next/prev`, `info`, `shutdown`. Un daemon gestiona
todos los monitores; cada `output` tiene su propia superficie y contexto mpv
(permite fondo distinto por monitor).

### 4.5 Rendimiento (§7)

- Decodificación por hardware (VAAPI/Vulkan) en libmpv.
- Miniaturas generadas con ffmpeg, cacheadas en `~/.cache/wallpaper-engine-linux/`.
- Pausa automática cuando: no hay ventana visible en el monitor / modo ahorro /
  opción del usuario. El daemon puede pausar el `mpv_context` (0 % CPU).
- Límite de FPS configurable (por defecto 30).
- Audio desactivado por defecto; volumen por fondo opcional.
- Sin copias de los originales: se leen directamente de Steam/Wallhaven (solo lectura).

---

## 5. Matriz de compatibilidad por escritorio

| Entorno | Imágenes | Vídeos/GIF | Web HTML5 | Fondo "detrás de iconos" |
|---|---|---|---|---|
| **KDE Plasma Wayland** (actual) | ✅ layer-shell | ✅ layer-shell | ⚠️ fase avanzada | ✅ |
| KDE Plasma X11 | ✅ ventana desktop | ✅ ventana desktop | ✅ WebEngine | ✅ |
| GNOME Wayland (Ubuntu) | ✅ `gsettings` (fondo real) | ❌ limitación documentada* | ❌ | n/a (GNOME no muestra iconos en escritorio) |
| GNOME X11 (si existe sesión) | ✅ | ✅ ventana desktop | ✅ | ⚠️ sin iconos de escritorio en GNOME |
| Hyprland / Sway (wlroots) | ✅ layer-shell | ✅ layer-shell | ⚠️ fase avanzada | ✅ |

\* En GNOME Wayland, con fondos animados, el plan de degradación es aplicar su
fotograma/vista previa como fondo estático real e informar al usuario. No se
usarán hacks que rompan el escritorio.

---

## 6. Limitaciones documentadas (requisito "no prometer compatibilidad universal")

1. **Escenas de Wallpaper Engine (31 de 55 fondos):** formato `scene.pkg`
   propietario (efectos y shaders compilados). No reproducibles. La aplicación
   las mostrará en la biblioteca con su vista previa animada y una etiqueta
   "No compatible"; opcionalmente, se podrá usar su `preview.gif` como fondo
   degradado (configurable).
2. **GNOME Wayland:** sin soporte para superficies de fondo de aplicaciones
   externas. Solo fondos estáticos reales vía gsettings.
3. **Interactividad de fondos web:** sin entrada de ratón en la capa de fondo.
4. **HDR/10 bits:** se reproducirá en SDR (mapeo correcto de color); el HDR del
   escritorio queda fuera del alcance inicial.
5. **No se usa autostart ni servicios systemd/user permanentes** (requisito explícito).

---

## 7. Dependencias a instalar

Paquetes apt (se instalarán en la Fase 2, con confirmación):

```
libmpv-dev                                    # cabeceras libmpv para el daemon
python3-pyside6                               # Qt Widgets
python3-pyside6.qtsvg python3-pyside6.qtmultimedia python3-pyside6.qtwebenginewidgets
```

Ya presentes: mpv/libmpv2, ffmpeg, gcc/cmake/ninja/pkg-config/wayland-scanner,
libwayland-dev, libegl1-mesa-dev.

---

## 8. Plan de fases y criterios de verificación

| Fase | Entregable | Criterio de éxito |
|---|---|---|
| **F1 Investigación** ✅ | Este informe | — |
| **F2 Prototipo** | Ventana PySide6 básica + daemon C que muestra imagen y vídeo en la capa de fondo de KDE Wayland; guardar/restaurar fondo al cerrar | Vídeo visible detrás del escritorio; al cerrar reaparece el fondo de Plasma; sin procesos residuales |
| **F3 Bibliotecas** | Detección Steam + escaneo WE/Wallhaven, índice JSON, miniaturas, biblioteca visual | Los 55 fondos WE + Wallhaven aparecen con miniaturas y tipos correctos |
| **F4 Motor** | MP4/WebM/GIF, FPS, pausa, volumen, ajuste (fill/fit/stretch), multi-monitor, backend X11 | Cambio de fondo instantáneo, 2 monitores distintos si se conecta uno |
| **F5 Interfaz completa** | Búsqueda, filtros, favoritos, recientes, panel de detalles, ajustes, fondos web (degradado si procede) | Todas las secciones funcionales (sin botones decorativos) |
| **F6 Integración Ubuntu** | `.desktop` + icono, cierre seguro, verificación GNOME (gsettings) y X11 | Abre desde el menú, restaura siempre el fondo original |
| **F7 Pruebas y optimización** | Pruebas de recursos, cierres inesperados, multi-monitor, correcciones | CPU < ~5 % en vídeo 1080p, sin huérfanos tras SIGKILL |

Registro continuo de tareas/decisiones/errores: `TASKS.md`.
