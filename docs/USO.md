# Uso

## Primer arranque

Abre **Wallpaper Engine Linux** desde el menú de aplicaciones. La aplicación:

1. Detecta tu escritorio y guarda el fondo actual (para restaurarlo al salir).
2. Escanea automáticamente:
   - **Wallpaper Engine (Steam Workshop)** — en todas las bibliotecas de Steam.
   - **Wallhaven** — `~/Imágenes/Wallpapers/` (y variantes de mayúsculas).
   - **Carpetas personalizadas** — las que añadas en Configuración.

La biblioteca muestra todos los fondos con miniaturas, nombre, tipo, resolución
y origen. Solo lectura: **nunca se modifican, mueven ni eliminan los archivos
originales**.

## Establecer un fondo

- **Doble clic** en una tarjeta → aplica el fondo a todas las pantallas.
- Clic simple → previsualización en el panel derecho (vídeos en movimiento).
- En el panel derecho: elegir **pantalla** destino, **modo de ajuste**
  (rellenar / ajustar / estirar) y pulsar «Establecer como fondo».
- **☆** marca favoritos; la barra superior filtra por categorías
  (Wallpaper Engine, Wallhaven, estáticos, animados, favoritos, recientes).

## Mientras la aplicación está abierta

- Puedes cambiar de fondo libremente; el cambio es inmediato.
- «Restaurar fondo original» devuelve el fondo de antes de abrir la app.
- La ventana es de administración: no se queda sobre el escritorio.

## Al cerrar

Al cerrar la ventana (o con Ctrl+Q), la aplicación:

1. Detiene la reproducción.
2. Restaura automáticamente el fondo original de tu escritorio.

Si la aplicación se cerrara de forma inesperada (crash, SIGKILL), el fondo
queda registrado como «pendiente de restaurar» y **se restaura solo en el
siguiente arranque** de la aplicación.

> En KDE, cerrar la aplicación restaura el plugin de fondo original; el vídeo
> deja de reproducirse y Plasma recupera su fondo habitual al instante.

## Tipos de contenido

| Contenido | Estado |
|---|---|
| Vídeos MP4/WebM/MKV/MOV | ✅ Reproducción en bucle, audio silenciado, hw-accel |
| GIF | ✅ Animación en bucle |
| Imágenes (JPG/PNG/WebP/AVIF) | ✅ Fondo real de Plasma (plugin nativo) |
| Páginas web (HTML5) | ✅ Renderizadas con WebEngine (sin interacción de ratón) |
| Escenas de Wallpaper Engine (`scene.pkg`) | ❌ Formato propietario, no reproducible. Se ofrece usar su vista previa como fondo degradado |

## Configuración

El botón «Configuración» permite:

- Añadir/quitar **carpetas de fondos** adicionales.
- Elegir el **modo de ajuste** por defecto.

La configuración se guarda en `~/.config/wallpaper-engine-linux/`.

## Límites conocidos

- **GNOME Wayland** no permite fondos animados externos (limitación de Mutter);
  la aplicación usa fondos estáticos reales (gsettings) y lo indica al usuario.
- **Escenas** de Wallpaper Engine: formato propietario (ver tabla).
- Los fondos web no reciben interacción del ratón.
- X11 y compositores wlroots (Hyprland/Sway) usan el daemon `wel-wallpaperd`
  (capa layer-shell); en KDE se usa el plugin de Plasma, que es la vía nativa.

Ver también: `docs/01-informe-tecnico.md` (arquitectura y decisiones).
