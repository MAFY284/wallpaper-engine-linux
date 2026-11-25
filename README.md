# Wallpaper Engine Linux

Aplicación local para Ubuntu (KDE Plasma / GNOME) que gestiona y reproduce
fondos de pantalla estáticos y animados usando tus bibliotecas existentes de
Wallpaper Engine (Steam Workshop) y Wallhaven, sin servicios permanentes y con
restauración automática del fondo original al cerrar.

## Estado

- ✅ Fase 1: Investigación y arquitectura — `docs/01-informe-tecnico.md`
- ✅ Fase 2: Prototipo funcional (plugin de Plasma + daemon C)
- ✅ Fase 3: Bibliotecas (Steam/WE + Wallhaven, índice, miniaturas)
- ✅ Fase 4: Motor de reproducción (vídeos, GIF, HTML5, hw-accel)
- ✅ Fase 5: Interfaz completa (categorías, favoritos, detalles, ajustes)
- ✅ Fase 6: Integración Ubuntu (.desktop, icono, instalador)
- 🔄 Fase 7: Pruebas y optimización

## Instalación rápida

```bash
./tools/install.sh
```

Ver `docs/INSTALACION.md` (requisitos, instalación, desinstalación) y
`docs/USO.md` (guía de uso y límites conocidos).

## Estructura

```
app/      GUI Python (PySide6) — interfaz, biblioteca, importadores, integración
core/     Daemon nativo C — capa de fondo (Wayland layer-shell) + libmpv
desktop/  Plugin de Plasma (wel.video), archivo .desktop, icono SVG
bin/      Lanzadores y binarios
tools/    Instalador, desinstalador y herramientas de desarrollo
docs/     Documentación
```

## Documentación

- Informe técnico y arquitectura: `docs/01-informe-tecnico.md`
- Instalación: `docs/INSTALACION.md`
- Uso: `docs/USO.md`
- Registro de tareas y decisiones: `TASKS.md`
