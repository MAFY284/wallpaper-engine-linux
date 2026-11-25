# Registro de tareas, decisiones y errores

Registro vivo del proyecto. Actualizar en cada fase.

## Estado general

| Fase | Estado | Notas |
|---|---|---|
| F1 Investigación y viabilidad | ✅ Completada | Ver `docs/01-informe-tecnico.md` |
| F2 Prototipo funcional | ✅ Completada | Plugin Plasma `wel.video` (vídeo detrás de iconos) + daemon layer-shell C + GUI básica + restauración verificada |
| F3 Bibliotecas | ✅ Completada | 58 fondos indexados (55 WE + 3 Wallhaven), miniaturas cacheadas, biblioteca visual |
| F4 Motor de reproducción | ✅ Completada | Vídeos/GIF/HTML5 vía plugin (QtMultimedia+WebEngine), hw-accel (1,3 % CPU en 1080p), daemon IPC verificado |
| F5 Interfaz completa | ✅ Completada | Categorías, búsqueda, favoritos, panel de detalles con previsualización, configuración, selector de pantalla |
| F6 Integración Ubuntu | ✅ Completada | `.desktop` + icono SVG + `tools/install.sh`/`uninstall.sh`; verificado desde el menú de aplicaciones |
| F7 Pruebas y optimización | ✅ Completada | Recuperación de crashes verificada; sin procesos huérfanos; 1,3 % CPU en vídeo 1080p; 3/3 vídeos secuenciales; publicado en GitHub v1.0.0 |

## Decisiones técnicas

| # | Fecha | Decisión | Motivo |
|---|---|---|---|
| D1 | 2026-11-24 | Daemon nativo en C + libmpv empotrado como motor | Un motor para imagen/vídeo/GIF; sin procesos hijos (no hay huérfanos); hw-accel; control IPC completo |
| D2 | 2026-11-24 | KDE Wayland: capa `zwlr_layer_shell_v1` (background) | KWin 6.6.7 lo soporta; no toca la configuración de Plasma; restauración automática al desconectar |
| D3 | 2026-11-24 | GNOME Wayland: gsettings para estáticos, animados = limitación documentada | Mutter no soporta layer-shell ni superficies de fondo externas |
| D4 | 2026-11-24 | GUI en Python + PySide6 desde apt (6.10.2) | Qt maduro, WebEngine disponible, sin virtualenv, iteración rápida |
| D5 | 2026-11-24 | Escenas `scene.pkg` de WE: no reproducibles; mostrar vista previa + etiqueta | Formato propietario; documentado en informe §6 |
| D6 | 2026-11-24 | Watchdog heartbeat GUI↔daemon (3 s) | Si la GUI muere, el daemon se autodestruye y el compositor restaura el fondo |
| D7 | 2026-11-24 | Ruta Wallhaven: detectar `~/Imágenes/Wallpapers/` (real) y `~/Imágenes/wallpapers/` (documentada) | La del usuario real difiere del enunciado; ambas son configurables |
| D8 | 2026-11-24 | **KDE: plugin de fondo de Plasma `wel.video` (QML + QtMultimedia) en lugar de layer-shell** | Los iconos y el fondo de Plasma viven en la misma ventana; layer-shell los taparía (KWin 6.6 coloca layer background en DesktopLayer y KWin eleva el escritorio al hacer clic). El plugin renderiza el vídeo DENTRO del escritorio, detrás de los iconos, igual que Wallpaper Engine |
| D9 | 2026-11-24 | El daemon layer-shell C se mantiene como backend portátil (Hyprland/Sway/X11) | Funciona y está verificado; documentado como alternativa para otros compositores |
| D10 | 2026-11-24 | Control de Plasma vía `evaluateScript` (escribe config) + lectura de estado vía análisis del archivo de configuración | En Plasma 6.6 evaluateScript ejecuta pero no devuelve valores |
| D11 | 2026-11-24 | Restaurar con `Image=""` cuando el estado original no tenía claves | Fuerza al plugin nativo a volver al fondo por defecto y provoca la recarga visual (bug verificado: sin escritura no hay recarga) |

## Errores y hallazgos

| # | Fecha | Hallazgo | Resolución |
|---|---|---|---|
| H1 | 2026-11-24 | `~/Imágenes/wallpapers/` no existe; la real es `~/Imágenes/Wallpapers/` | D7 |
| H2 | 2026-11-24 | `mpvpaper` no está empaquetado en Ubuntu 26.04 | Implementación propia del daemon |
| H3 | 2026-11-24 | 31/55 fondos WE son escenas propietarias | Limitación documentada + degradado a preview |
| H4 | 2026-11-24 | PySide6 no instalado, pero disponible en apt (6.10.2) | Instalar por apt en F2 |
| H5 | 2026-11-24 | KWin 6.6: layer-shell background cae en DesktopLayer; el clic en el escritorio ELEVA la ventana del escritorio sobre la capa | En KDE usar el plugin de Plasma (D8); layer-shell solo como fallback |
| H6 | 2026-11-24 | Plasma 6.6: `evaluateScript` ejecuta scripts pero NO devuelve su valor (toda llamada devuelve '') | Lecturas por análisis del archivo de configuración (D10) |
| H7 | 2026-11-24 | Bug de restauración: si el estado original no tenía claves, el script no escribía nada y Plasma no recargaba visualmente el fondo | D11: escribir Image="" fuerza la recarga al fondo por defecto |
| H8 | 2026-11-24 | KWin ScreenShot2 requiere autorización por .desktop (X-KDE-DBUS-Restricted-Interfaces); el portal de capturas de KDE se cuelga en esta sesión | Verificación visual con el usuario; herramienta `tools/capture.py` preparada |
| H9 | 2026-11-24 | La caché sycoca de KDE guarda nombres en UTF-16BE (`strings` normal no los encuentra) | Usar `strings -eb`; y `kbuildsycoca6` para refrescar |
| H10 | 2026-11-24 | plasmashell cachea el QML compilado de los plugins de fondo; los cambios en main.qml no aplican sin reiniciar el shell | `systemctl --user restart plasma-plasmashell.service` tras cada cambio de QML (documentado también por TuxPapers) |
| H11 | 2026-11-24 | Fondos web: WebEngineView SÍ funciona en el plugin (verificado con página simple y con la tabla periódica); el "negro" inicial era el QML viejo cacheado | Herramienta `tools/render_page.py` para verificar páginas sin mirar el escritorio |
| H12 | 2026-11-24 | **Pantalla negra intermitente**: sin `contents/config/main.xml` (esquema KConfig XT), el mapa de configuración del plugin llega VACÍO al arrancar plasmashell (solo funciona al reaplicar) | Añadir `config/main.xml` declarando source/fill; con él el plugin carga el vídeo desde el arranque |
| H13 | 2026-11-24 | La recarga del MISMO plugin con nueva configuración es intermitente en Plasma 6.6 (a veces no recarga visualmente) | Rebote de plugin (`org.kde.color` → destino) en cada apply para recarga determinista |

## Tareas pendientes / próximas

- [x] F2.1 Instalar dependencias apt (libmpv-dev, PySide6)
- [x] F2.2 Daemon C mínimo: capa layer-shell + libmpv (imagen y vídeo)
- [x] F2.3 GUI con arranque/parada y aplicación de fondos
- [x] F2.4 Verificación en KDE Wayland real + restauración del fondo
- [ ] Opcional: backend X11 del daemon (otros WMs)
- [ ] Opcional: pausa en vivo del vídeo (IPC al plugin de Plasma)
- [ ] Opcional: soporte HDR y audio del fondo
- [ ] Opcional: degradado "usar preview" para escenas WE ya implementado; mejorar con preview animada en el escritorio (GIF de escena)
