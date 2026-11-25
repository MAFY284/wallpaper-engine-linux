/*
 * wel-wallpaperd — Motor de fondo de escritorio para Wallpaper Engine Linux.
 *
 * Cliente Wayland que crea una superficie zwlr_layer_shell_v1 (capa "background")
 * por monitor y renderiza en ella con libmpv empotrado (imágenes, vídeos, GIF).
 * Se controla mediante un socket Unix con un protocolo de líneas de texto.
 *
 * Diseño de referencia: mpvpaper (GhostNaN), reimplementado con:
 *   - una instancia de mpv independiente por monitor (fondo distinto por monitor),
 *   - control completo por IPC (carga, pausa, volumen, ajuste, FPS, parada),
 *   - watchdog: se autodestruye si la GUI deja de enviar "ping" (3 s),
 *     con lo que el compositor elimina la capa y reaparece el fondo original.
 *
 * Compilación: make  (ver Makefile)
 */

#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <wayland-client.h>
#include <wayland-egl.h>

#include <mpv/client.h>
#include <mpv/render_gl.h>

#include "generated/wlr-layer-shell-unstable-v1-client-protocol.h"
#include "generated/xdg-output-unstable-v1-client-protocol.h"

/* ------------------------------------------------------------------ */
/* Estado global                                                       */
/* ------------------------------------------------------------------ */

static struct wl_display *display;
static struct wl_registry *registry;
static struct wl_compositor *compositor;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct zxdg_output_manager_v1 *xdg_output_manager;

static EGLDisplay egl_display;
static EGLConfig egl_config;
static EGLContext egl_context;

static void (*wel_glViewport)(int, int, int, int);
static void (*wel_glDrawBuffer)(unsigned int);

static struct wl_list outputs; /* struct wel_output */

static int wakeup_pipe[2] = {-1, -1}; /* avisos del update-callback de mpv */
static volatile sig_atomic_t running = 1;

/* IPC */
static char *sock_path;
static int listen_fd = -1;
#define MAX_CLIENTS 8
#define CLIENT_BUF_SZ 4096
static struct {
    int fd;
    char buf[CLIENT_BUF_SZ];
    size_t len;
} clients[MAX_CLIENTS];

static time_t last_ping; /* watchdog */

/* ------------------------------------------------------------------ */
/* Log                                                                 */
/* ------------------------------------------------------------------ */

static void log_msg(const char *fmt, ...)
{
    char ts[32];
    struct timespec now;
    clock_gettime(CLOCK_REALTIME, &now);
    struct tm tm;
    localtime_r(&now.tv_sec, &tm);
    strftime(ts, sizeof(ts), "%H:%M:%S", &tm);
    fprintf(stderr, "[wel-wallpaperd %s] ", ts);
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fprintf(stderr, "\n");
}

/* ------------------------------------------------------------------ */
/* Estructura por monitor                                              */
/* ------------------------------------------------------------------ */

struct wel_output {
    struct wl_list link;
    int index;

    struct wl_output *wl_output;
    struct zxdg_output_v1 *xdg_output;
    char *name; /* p. ej. "DP-2" */

    int32_t width, height; /* coordenadas de superficie (lógicas * escala) */
    int32_t scale;

    struct wl_surface *surface;
    struct zwlr_layer_surface_v1 *layer_surface;
    struct wl_egl_window *egl_window;
    EGLSurface egl_surface;
    struct wl_callback *frame_cb;
    bool configured;

    /* mpv */
    mpv_handle *mpv;
    mpv_render_context *mpv_gl;
    bool needs_render; /* señalizado por el update-callback (atómico) */

    /* petición pendiente de la GUI */
    bool want_mpv;
    char *pending_path;
    char *pending_fit;  /* contain | fill | stretch */
    double pending_volume;
    int pending_fps;

    char *cur_path;
};

static bool output_matches(struct wel_output *o, const char *sel)
{
    if (!sel || !*sel || strcmp(sel, "any") == 0)
        return o == wl_container_of(outputs.next, o, link);
    if (strcmp(sel, "all") == 0 || strcmp(sel, "*") == 0)
        return true;
    if (o->name && strncmp(o->name, sel, strlen(sel)) == 0)
        return true;
    return false;
}

/* ------------------------------------------------------------------ */
/* Render                                                              */
/* ------------------------------------------------------------------ */

static void on_mpv_update(void *ctx)
{
    struct wel_output *o = ctx;
    int idx = o->index;
    if (write(wakeup_pipe[1], &idx, sizeof(idx)) < 0) {
        /* tubería llena o cerrada: no es crítico */
    }
}

/* mpv llamaría a glFenceSync y podría quedarse bloqueado en Wayland;
 * le devolvemos un puntero que siempre devuelve NULL (mismo workaround
 * que usa mpvpaper). */
static void *wrap_glFenceSync(unsigned int condition, unsigned int flags)
{
    (void)condition;
    (void)flags;
    return NULL;
}

static void *get_proc_address(void *ctx, const char *name)
{
    (void)ctx;
    if (strcmp(name, "glFenceSync") == 0)
        return (void *)wrap_glFenceSync;
    return (void *)eglGetProcAddress(name);
}

static void frame_handle_done(void *data, struct wl_callback *cb, uint32_t t)
{
    (void)t;
    struct wel_output *o = data;
    wl_callback_destroy(cb);
    o->frame_cb = NULL;
    if (__atomic_load_n(&o->needs_render, __ATOMIC_ACQUIRE))
        return; /* el bucle principal volverá a renderizar */
}

static const struct wl_callback_listener frame_listener = {
    .done = frame_handle_done,
};

static void render_output(struct wel_output *o)
{
    if (!o->configured || !o->egl_surface || !o->mpv_gl)
        return;

    if (!eglMakeCurrent(egl_display, o->egl_surface, o->egl_surface, egl_context)) {
        log_msg("eglMakeCurrent falló en %s: 0x%x", o->name ? o->name : "?", eglGetError());
        return;
    }

    int32_t pw = o->width * o->scale;
    int32_t ph = o->height * o->scale;
    if (pw <= 0 || ph <= 0)
        return;

    wel_glViewport(0, 0, pw, ph);

    mpv_opengl_fbo fbo = {.fbo = 0, .w = pw, .h = ph};
    int flip_y = 1;
    int block = 0;
    mpv_render_param params[] = {
        {MPV_RENDER_PARAM_OPENGL_FBO, &fbo},
        {MPV_RENDER_PARAM_FLIP_Y, &flip_y},
        {MPV_RENDER_PARAM_BLOCK_FOR_TARGET_TIME, &block},
        {MPV_RENDER_PARAM_INVALID, NULL},
    };

    int err = mpv_render_context_render(o->mpv_gl, params);
    if (err < 0)
        log_msg("render en %s: %s", o->name ? o->name : "?", mpv_error_string(err));

    o->frame_cb = wl_surface_frame(o->surface);
    wl_callback_add_listener(o->frame_cb, &frame_listener, o);
    __atomic_store_n(&o->needs_render, false, __ATOMIC_RELEASE);

    if (!eglSwapBuffers(egl_display, o->egl_surface)) {
        log_msg("eglSwapBuffers falló en %s: 0x%x", o->name ? o->name : "?", eglGetError());
        wl_callback_destroy(o->frame_cb);
        o->frame_cb = NULL;
    } else {
        mpv_render_context_report_swap(o->mpv_gl);
    }
}

/* ------------------------------------------------------------------ */
/* Wayland                                                             */
/* ------------------------------------------------------------------ */

static void layer_surface_configure(void *data, struct zwlr_layer_surface_v1 *ls,
                                    uint32_t serial, uint32_t w, uint32_t h);

static void layer_surface_closed(void *data, struct zwlr_layer_surface_v1 *ls)
{
    (void)ls;
    log_msg("el compositor cerró la superficie de %p", (void *)data);
}

static const struct zwlr_layer_surface_v1_listener layer_listener = {
    .configure = layer_surface_configure,
    .closed = layer_surface_closed,
};

/* --- creación / destrucción del motor por monitor --- */

static void output_teardown_visual(struct wel_output *o)
{
    if (o->mpv_gl) {
        mpv_render_context_free(o->mpv_gl);
        o->mpv_gl = NULL;
    }
    if (o->mpv) {
        mpv_terminate_destroy(o->mpv);
        o->mpv = NULL;
    }
    if (o->egl_surface) {
        if (eglGetCurrentSurface(EGL_DRAW) == o->egl_surface ||
            eglGetCurrentSurface(EGL_READ) == o->egl_surface)
            eglMakeCurrent(egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, egl_context);
        eglDestroySurface(egl_display, o->egl_surface);
        o->egl_surface = EGL_NO_SURFACE;
    }
    if (o->egl_window) {
        wl_egl_window_destroy(o->egl_window);
        o->egl_window = NULL;
    }
    if (o->layer_surface) {
        zwlr_layer_surface_v1_destroy(o->layer_surface);
        o->layer_surface = NULL;
    }
    if (o->surface) {
        wl_surface_destroy(o->surface);
        o->surface = NULL;
    }
    if (o->frame_cb) {
        wl_callback_destroy(o->frame_cb);
        o->frame_cb = NULL;
    }
    o->configured = false;
    o->want_mpv = false;
    free(o->pending_path);
    o->pending_path = NULL;
    free(o->cur_path);
    o->cur_path = NULL;
}

static void output_destroy(struct wel_output *o)
{
    output_teardown_visual(o);
    if (o->xdg_output)
        zxdg_output_v1_destroy(o->xdg_output);
    if (o->wl_output)
        wl_output_destroy(o->wl_output);
    wl_list_remove(&o->link);
    free(o->name);
    free(o);
}

static void create_layer_surface(struct wel_output *o)
{
    o->surface = wl_compositor_create_surface(compositor);

    /* región de entrada vacía: la capa no captura clics ni foco */
    struct wl_region *region = wl_compositor_create_region(compositor);
    wl_surface_set_input_region(o->surface, region);
    wl_region_destroy(region);

    o->layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        layer_shell, o->surface, o->wl_output,
        ZWLR_LAYER_SHELL_V1_LAYER_BACKGROUND, "wel");

    zwlr_layer_surface_v1_set_size(o->layer_surface, 0, 0);
    zwlr_layer_surface_v1_set_anchor(o->layer_surface,
        ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT);
    zwlr_layer_surface_v1_set_exclusive_zone(o->layer_surface, -1);
    zwlr_layer_surface_v1_add_listener(o->layer_surface, &layer_listener, o);
    wl_surface_commit(o->surface);
}

static void layer_surface_configure(void *data, struct zwlr_layer_surface_v1 *ls,
                                    uint32_t serial, uint32_t w, uint32_t h)
{
    struct wel_output *o = data;
    o->width = (int32_t)w;
    o->height = (int32_t)h;
    zwlr_layer_surface_v1_ack_configure(ls, serial);
    wl_surface_set_buffer_scale(o->surface, o->scale);

    if (w == 0 || h == 0)
        return;

    if (!o->egl_window) {
        o->egl_window = wl_egl_window_create(o->surface, w * o->scale, h * o->scale);
        o->egl_surface = eglCreatePlatformWindowSurface(egl_display, egl_config, o->egl_window, NULL);
        if (!o->egl_surface) {
            log_msg("no se pudo crear la superficie EGL de %s: 0x%x",
                    o->name ? o->name : "?", eglGetError());
            return;
        }
        if (!eglMakeCurrent(egl_display, o->egl_surface, o->egl_surface, egl_context))
            log_msg("eglMakeCurrent inicial falló: 0x%x", eglGetError());
        eglSwapInterval(egl_display, 0);
        wel_glDrawBuffer(0x0405 /* GL_BACK */);
        o->configured = true;
        log_msg("salida %s lista: %ux%u (escala %d)",
                o->name ? o->name : "?", w, h, o->scale);
    } else {
        wl_egl_window_resize(o->egl_window, w * o->scale, h * o->scale, 0, 0);
    }
}

static void output_geometry(void *d, struct wl_output *o, int32_t x, int32_t y,
                            int32_t pw, int32_t ph, int32_t sub, const char *make,
                            const char *model, int32_t transform)
{
    (void)d; (void)o; (void)x; (void)y; (void)pw; (void)ph;
    (void)sub; (void)make; (void)model; (void)transform;
}

static void output_mode(void *d, struct wl_output *o, uint32_t flags,
                        int32_t w, int32_t h, int32_t refresh)
{
    (void)d; (void)o; (void)flags; (void)w; (void)h; (void)refresh;
}

static void output_done(void *d, struct wl_output *o)
{
    (void)d; (void)o;
}

static void output_scale(void *d, struct wl_output *o, int32_t scale)
{
    struct wel_output *out = d;
    (void)o;
    out->scale = scale;
}

static const struct wl_output_listener output_listener = {
    .geometry = output_geometry,
    .mode = output_mode,
    .done = output_done,
    .scale = output_scale,
};

static void xdg_output_name(void *d, struct zxdg_output_v1 *xo, const char *name)
{
    struct wel_output *o = d;
    (void)xo;
    free(o->name);
    o->name = strdup(name);
    log_msg("salida detectada: %s", name);
    if (!o->layer_surface && layer_shell)
        create_layer_surface(o);
}

static void xdg_output_noop_pos(void *d, struct zxdg_output_v1 *xo, int32_t x, int32_t y)
{ (void)d; (void)xo; (void)x; (void)y; }

static void xdg_output_noop_size(void *d, struct zxdg_output_v1 *xo, int32_t w, int32_t h)
{ (void)d; (void)xo; (void)w; (void)h; }

static void xdg_output_noop_done(void *d, struct zxdg_output_v1 *xo)
{ (void)d; (void)xo; }

static void xdg_output_noop_desc(void *d, struct zxdg_output_v1 *xo, const char *s)
{ (void)d; (void)xo; (void)s; }

static const struct zxdg_output_v1_listener xdg_output_listener = {
    .logical_position = xdg_output_noop_pos,
    .logical_size = xdg_output_noop_size,
    .done = xdg_output_noop_done,
    .name = xdg_output_name,
    .description = xdg_output_noop_desc,
};

static void registry_global(void *data, struct wl_registry *reg, uint32_t id,
                            const char *interface, uint32_t version)
{
    (void)data;
    (void)version;
    if (strcmp(interface, wl_compositor_interface.name) == 0) {
        compositor = wl_registry_bind(reg, id, &wl_compositor_interface, 4);
    } else if (strcmp(interface, zwlr_layer_shell_v1_interface.name) == 0) {
        layer_shell = wl_registry_bind(reg, id, &zwlr_layer_shell_v1_interface, 1);
    } else if (strcmp(interface, zxdg_output_manager_v1_interface.name) == 0) {
        xdg_output_manager = wl_registry_bind(reg, id, &zxdg_output_manager_v1_interface, 3);
    } else if (strcmp(interface, wl_output_interface.name) == 0) {
        struct wel_output *o = calloc(1, sizeof(*o));
        o->index = 0;
        o->scale = 1;
        o->wl_output = wl_registry_bind(reg, id, &wl_output_interface, 3);
        wl_output_add_listener(o->wl_output, &output_listener, o);
        if (xdg_output_manager)
            o->xdg_output = zxdg_output_manager_v1_get_xdg_output(xdg_output_manager, o->wl_output);
        if (o->xdg_output)
            zxdg_output_v1_add_listener(o->xdg_output, &xdg_output_listener, o);
        /* índice para la tubería de wakeup */
        struct wel_output *it;
        int n = 0;
        wl_list_for_each(it, &outputs, link) n++;
        o->index = n;
        wl_list_insert(outputs.prev, &o->link);
        log_msg("output wayland global %u vinculado", id);
    }
}

static void registry_global_remove(void *data, struct wl_registry *reg, uint32_t id)
{
    (void)data; (void)reg;
    struct wel_output *o, *tmp;
    wl_list_for_each_safe(o, tmp, &outputs, link) {
        /* el proxy guarda el id del global */
        if (wl_proxy_get_id((struct wl_proxy *)o->wl_output) == id) {
            log_msg("salida %s desconectada", o->name ? o->name : "?");
            output_destroy(o);
        }
    }
}

static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_global_remove,
};

/* ------------------------------------------------------------------ */
/* mpv por monitor                                                     */
/* ------------------------------------------------------------------ */

static void output_ensure_mpv(struct wel_output *o)
{
    if (o->mpv || !o->configured || !o->egl_surface)
        return;

    o->mpv = mpv_create();
    if (!o->mpv) {
        log_msg("mpv_create falló");
        return;
    }

    const char *opts[] = {
        "vo", "libmpv",
        "hwdec", "auto-safe",
        "loop-file", "inf",
        "mute", "yes",
        "keepaspect", "yes",
        "idle", "yes",
        "terminal", "no",
        "msg-level", "all=warn",
        "osc", "no",
        "osd-level", "0",
        "input-default-bindings", "no",
        "audio", "auto",
        NULL
    };
    for (int i = 0; opts[i]; i += 2)
        mpv_set_option_string(o->mpv, opts[i], opts[i + 1]);
    if (o->pending_fps > 0) {
        char v[16];
        snprintf(v, sizeof(v), "%d", o->pending_fps);
        mpv_set_option_string(o->mpv, "fps", v);
    }
    if (mpv_initialize(o->mpv) < 0) {
        log_msg("mpv_initialize falló en %s", o->name ? o->name : "?");
        mpv_destroy(o->mpv);
        o->mpv = NULL;
        return;
    }

    if (!eglMakeCurrent(egl_display, o->egl_surface, o->egl_surface, egl_context)) {
        log_msg("eglMakeCurrent (mpv init) falló");
        return;
    }

    mpv_opengl_init_params gl_params = {
        .get_proc_address = get_proc_address,
        .get_proc_address_ctx = NULL,
    };
    int advanced = 1;
    mpv_render_param params[] = {
        {MPV_RENDER_PARAM_API_TYPE, (void *)MPV_RENDER_API_TYPE_OPENGL},
        {MPV_RENDER_PARAM_OPENGL_INIT_PARAMS, &gl_params},
        {MPV_RENDER_PARAM_ADVANCED_CONTROL, &advanced},
        {MPV_RENDER_PARAM_WL_DISPLAY, display},
        {MPV_RENDER_PARAM_INVALID, NULL},
    };
    if (mpv_render_context_create(&o->mpv_gl, o->mpv, params) < 0) {
        log_msg("mpv_render_context_create falló en %s", o->name ? o->name : "?");
        mpv_terminate_destroy(o->mpv);
        o->mpv = NULL;
        return;
    }
    mpv_render_context_set_update_callback(o->mpv_gl, on_mpv_update, o);
}

static void output_apply_fit(struct wel_output *o)
{
    const char *fit = o->pending_fit ? o->pending_fit : "contain";

    if (strcmp(fit, "stretch") == 0) {
        mpv_set_property_string(o->mpv, "keepaspect", "no");
        double z = 0.0;
        mpv_set_property(o->mpv, "video-zoom", MPV_FORMAT_DOUBLE, &z);
        return;
    }

    mpv_set_property_string(o->mpv, "keepaspect", "yes");
    if (strcmp(fit, "fill") == 0) {
        /* zoom = máx(ancho/pancho_vídeo, alto/palto_vídeo) relativo a "contain" */
        int64_t vw = 0, vh = 0;
        for (int i = 0; i < 100 && (!vw || !vh); i++) {
            usleep(10000);
            mpv_get_property(o->mpv, "video-params/w", MPV_FORMAT_INT64, &vw);
            mpv_get_property(o->mpv, "video-params/h", MPV_FORMAT_INT64, &vh);
        }
        double tw = (double)o->width * o->scale;
        double th = (double)o->height * o->scale;
        if (vw > 0 && vh > 0) {
            double contain_scale = fmin(tw / vw, th / vh);
            double cover_scale = fmax(tw / vw, th / vh);
            double zoom = contain_scale > 0 ? cover_scale / contain_scale : 0.0;
            mpv_set_property(o->mpv, "video-zoom", MPV_FORMAT_DOUBLE, &zoom);
        }
    } else {
        double z = 0.0;
        mpv_set_property(o->mpv, "video-zoom", MPV_FORMAT_DOUBLE, &z);
    }
}

static void output_apply_pending(struct wel_output *o)
{
    if (!o->mpv || !o->pending_path)
        return;

    double vol = o->pending_volume;
    mpv_set_property(o->mpv, "volume", MPV_FORMAT_DOUBLE, &vol);
    mpv_set_property_string(o->mpv, "pause", "no");

    const char *cmd[] = {"loadfile", o->pending_path, "replace", NULL};
    int err = mpv_command(o->mpv, cmd);
    if (err < 0)
        log_msg("loadfile %s: %s", o->pending_path, mpv_error_string(err));

    output_apply_fit(o);

    free(o->cur_path);
    o->cur_path = o->pending_path;
    o->pending_path = NULL;

    __atomic_store_n(&o->needs_render, true, __ATOMIC_RELEASE);
}

/* ------------------------------------------------------------------ */
/* IPC                                                                 */
/* ------------------------------------------------------------------ */

static void client_close(int i)
{
    close(clients[i].fd);
    clients[i].fd = -1;
    clients[i].len = 0;
}

static void client_respond(int i, const char *fmt, ...)
{
    if (clients[i].fd < 0)
        return;
    char buf[1024];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n > 0)
        (void)!write(clients[i].fd, buf, (size_t)n);
}

static void handle_command(int i, char *line)
{
    /* recortar fin de línea */
    size_t n = strlen(line);
    while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r'))
        line[--n] = '\0';

    char *cmd = strtok(line, " \t");
    if (!cmd)
        return;

    if (strcmp(cmd, "ping") == 0) {
        last_ping = time(NULL);
        client_respond(i, "OK pong\n");
        return;
    }

    if (strcmp(cmd, "quit") == 0) {
        client_respond(i, "OK quit\n");
        running = 0;
        return;
    }

    if (strcmp(cmd, "info") == 0) {
        struct wel_output *o;
        char buf[1024];
        wl_list_for_each(o, &outputs, link) {
            snprintf(buf, sizeof(buf), "output %s %dx%d scale=%d file=%s\n",
                     o->name ? o->name : "?",
                     o->width, o->height, o->scale,
                     o->cur_path ? o->cur_path : "-");
            client_respond(i, buf);
        }
        client_respond(i, "END\n");
        return;
    }

    if (strcmp(cmd, "load") == 0) {
        char *sel = strtok(NULL, " \t");
        char *fit = strtok(NULL, " \t");
        char *vols = strtok(NULL, " \t");
        char *path = strtok(NULL, "");
        if (!sel || !path || !*path) {
            client_respond(i, "ERR load: uso: load <output|any|all> <contain|fill|stretch> <volumen> <ruta>\n");
            return;
        }
        double volume = vols ? atof(vols) : 0.0;
        const char *fitname = (fit && *fit) ? fit : "contain";
        if (strcmp(fitname, "fill") != 0 && strcmp(fitname, "stretch") != 0)
            fitname = "contain";

        struct wel_output *o;
        int applied = 0;
        wl_list_for_each(o, &outputs, link) {
            if (!output_matches(o, sel))
                continue;
            free(o->pending_path);
            o->pending_path = strdup(path);
            free(o->pending_fit);
            o->pending_fit = strdup(fitname);
            o->pending_volume = volume;
            o->want_mpv = true;
            if (!o->layer_surface)
                create_layer_surface(o);
            if (o->configured) {
                output_ensure_mpv(o);
                output_apply_pending(o);
                if (o->mpv_gl)
                    __atomic_store_n(&o->needs_render, true, __ATOMIC_RELEASE);
            }
            applied++;
        }
        if (applied == 0)
            client_respond(i, "ERR load: salida no encontrada\n");
        else
            client_respond(i, "OK load\n");
        return;
    }

    if (strcmp(cmd, "stop") == 0) {
        char *sel = strtok(NULL, " \t");
        if (!sel) {
            client_respond(i, "ERR stop: uso: stop <output|any|all>\n");
            return;
        }
        struct wel_output *o;
        wl_list_for_each(o, &outputs, link) {
            if (output_matches(o, sel))
                output_teardown_visual(o);
        }
        client_respond(i, "OK stop\n");
        return;
    }

    if (strcmp(cmd, "pause") == 0 || strcmp(cmd, "mute") == 0) {
        char *sel = strtok(NULL, " \t");
        char *vals = strtok(NULL, " \t");
        if (!sel || !vals) {
            client_respond(i, "ERR %s: uso: %s <output|any|all> <0|1>\n", cmd, cmd);
            return;
        }
        const char *prop = strcmp(cmd, "pause") == 0 ? "pause" : "mute";
        int v = atoi(vals) ? 1 : 0;
        struct wel_output *o;
        wl_list_for_each(o, &outputs, link) {
            if (output_matches(o, sel) && o->mpv)
                mpv_set_property_string(o->mpv, prop, v ? "yes" : "no");
        }
        client_respond(i, "OK %s\n", cmd);
        return;
    }

    if (strcmp(cmd, "volume") == 0) {
        char *sel = strtok(NULL, " \t");
        char *vals = strtok(NULL, " \t");
        if (!sel || !vals) {
            client_respond(i, "ERR volume: uso: volume <output|any|all> <0-100>\n");
            return;
        }
        double v = atof(vals);
        struct wel_output *o;
        wl_list_for_each(o, &outputs, link) {
            if (output_matches(o, sel) && o->mpv)
                mpv_set_property(o->mpv, "volume", MPV_FORMAT_DOUBLE, &v);
        }
        client_respond(i, "OK volume\n");
        return;
    }

    if (strcmp(cmd, "fps") == 0) {
        char *sel = strtok(NULL, " \t");
        char *vals = strtok(NULL, " \t");
        if (!sel || !vals) {
            client_respond(i, "ERR fps: uso: fps <output|any|all> <fps>\n");
            return;
        }
        struct wel_output *o;
        wl_list_for_each(o, &outputs, link) {
            if (output_matches(o, sel)) {
                o->pending_fps = atoi(vals);
                if (o->mpv) {
                    char v[16];
                    snprintf(v, sizeof(v), "%d", o->pending_fps);
                    mpv_set_option_string(o->mpv, "fps", v);
                }
            }
        }
        client_respond(i, "OK fps\n");
        return;
    }

    client_respond(i, "ERR comando desconocido\n");
}

static void handle_client_data(int i)
{
    ssize_t r = read(clients[i].fd, clients[i].buf + clients[i].len,
                     CLIENT_BUF_SZ - clients[i].len - 1);
    if (r <= 0) {
        client_close(i);
        return;
    }
    clients[i].len += (size_t)r;
    clients[i].buf[clients[i].len] = '\0';

    char *start = clients[i].buf;
    while (1) {
        char *nl = memchr(start, '\n', clients[i].buf + clients[i].len - start);
        if (!nl)
            break;
        *nl = '\0';
        handle_command(i, start);
        start = nl + 1;
    }
    size_t consumed = (size_t)(start - clients[i].buf);
    memmove(clients[i].buf, start, clients[i].len - consumed);
    clients[i].len -= consumed;
    clients[i].buf[clients[i].len] = '\0';
}

static void handle_new_client(void)
{
    int fd = accept(listen_fd, NULL, NULL);
    if (fd < 0)
        return;
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].fd < 0) {
            clients[i].fd = fd;
            clients[i].len = 0;
            return;
        }
    }
    close(fd); /* demasiados clientes */
}

static int setup_socket(void)
{
    const char *path = getenv("WEL_SOCKET");
    char fallback[512];
    if (!path || !*path) {
        const char *xdg = getenv("XDG_RUNTIME_DIR");
        if (!xdg)
            xdg = "/tmp";
        snprintf(fallback, sizeof(fallback), "%s/wel/wel-wallpaperd.sock", xdg);
        char dir[512];
        snprintf(dir, sizeof(dir), "%s/wel", xdg);
        mkdir(dir, 0700);
        path = fallback;
    }
    sock_path = strdup(path);
    unlink(sock_path);

    listen_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (listen_fd < 0)
        return -1;

    struct sockaddr_un addr = {0};
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, sock_path, sizeof(addr.sun_path) - 1);
    if (bind(listen_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        log_msg("bind %s: %s", sock_path, strerror(errno));
        return -1;
    }
    if (listen(listen_fd, 4) < 0)
        return -1;
    fcntl(listen_fd, F_SETFL, fcntl(listen_fd, F_GETFL, 0) | O_NONBLOCK);
    chmod(sock_path, 0600);
    return 0;
}

/* ------------------------------------------------------------------ */
/* Señales y limpieza                                                  */
/* ------------------------------------------------------------------ */

static void on_signal(int sig)
{
    (void)sig;
    running = 0;
}

static void cleanup(void)
{
    struct wel_output *o, *tmp;
    wl_list_for_each_safe(o, tmp, &outputs, link)
        output_destroy(o);

    for (int i = 0; i < MAX_CLIENTS; i++)
        if (clients[i].fd >= 0)
            close(clients[i].fd);
    if (listen_fd >= 0)
        close(listen_fd);
    if (sock_path) {
        unlink(sock_path);
        free(sock_path);
    }
    if (wakeup_pipe[0] >= 0)
        close(wakeup_pipe[0]);
    if (wakeup_pipe[1] >= 0)
        close(wakeup_pipe[1]);

    if (egl_display != EGL_NO_DISPLAY) {
        eglMakeCurrent(egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        eglTerminate(egl_display);
    }
    if (registry)
        wl_registry_destroy(registry);
    if (compositor)
        wl_compositor_destroy(compositor);
    if (layer_shell)
        zwlr_layer_shell_v1_destroy(layer_shell);
    if (xdg_output_manager)
        zxdg_output_manager_v1_destroy(xdg_output_manager);
    if (display)
        wl_display_disconnect(display);
    log_msg("limpieza completada, salida");
}

/* ------------------------------------------------------------------ */
/* main                                                                */
/* ------------------------------------------------------------------ */

int main(void)
{
    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    signal(SIGHUP, on_signal);
    signal(SIGPIPE, SIG_IGN);

    wl_list_init(&outputs);
    for (int i = 0; i < MAX_CLIENTS; i++)
        clients[i].fd = -1;

    display = wl_display_connect(NULL);
    if (!display) {
        log_msg("no se pudo conectar al compositor Wayland");
        return 1;
    }

    /* EGL */
    egl_display = eglGetPlatformDisplay(EGL_PLATFORM_WAYLAND_KHR, display, NULL);
    if (egl_display == EGL_NO_DISPLAY || !eglInitialize(egl_display, NULL, NULL)) {
        log_msg("no se pudo inicializar EGL");
        return 1;
    }
    eglBindAPI(EGL_OPENGL_API);
    const EGLint cfg_attrib[] = {
        EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT,
        EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 8,
        EGL_NONE};
    EGLint num_cfg = 0;
    if (!eglChooseConfig(egl_display, cfg_attrib, &egl_config, 1, &num_cfg)) {
        log_msg("eglChooseConfig falló");
        return 1;
    }
    static const struct { int maj, min; } gl_vers[] = {
        {4, 6}, {4, 5}, {4, 4}, {4, 3}, {4, 2}, {4, 1}, {4, 0},
        {3, 3}, {3, 2}, {3, 1}, {3, 0}, {0, 0}};
    egl_context = EGL_NO_CONTEXT;
    for (int i = 0; gl_vers[i].maj > 0 && egl_context == EGL_NO_CONTEXT; i++) {
        const EGLint ctx_attrib[] = {
            EGL_CONTEXT_MAJOR_VERSION, gl_vers[i].maj,
            EGL_CONTEXT_MINOR_VERSION, gl_vers[i].min,
            EGL_NONE};
        egl_context = eglCreateContext(egl_display, egl_config, EGL_NO_CONTEXT, ctx_attrib);
    }
    if (egl_context == EGL_NO_CONTEXT) {
        log_msg("no se pudo crear el contexto OpenGL");
        return 1;
    }
    if (!eglMakeCurrent(egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, egl_context)) {
        log_msg("eglMakeCurrent(NO_SURFACE) falló");
        return 1;
    }
    wel_glViewport = (void *)eglGetProcAddress("glViewport");
    wel_glDrawBuffer = (void *)eglGetProcAddress("glDrawBuffer");
    if (!wel_glViewport || !wel_glDrawBuffer) {
        log_msg("no se pudieron cargar glViewport/glDrawBuffer");
        return 1;
    }

    /* tubería de wakeup para el update-callback de mpv */
    if (pipe2(wakeup_pipe, O_NONBLOCK | O_CLOEXEC) < 0) {
        log_msg("pipe2 falló");
        return 1;
    }

    /* Wayland: descubrir compositor y salidas */
    registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);
    if (!compositor || !layer_shell) {
        log_msg("el compositor no ofrece los protocolos necesarios "
                "(wl_compositor / zwlr_layer_shell_v1)");
        return 1;
    }
    wl_display_roundtrip(display); /* nombres y geometría de salidas */

    if (wl_list_empty(&outputs)) {
        log_msg("no se detectó ninguna salida");
        return 1;
    }

    if (setup_socket() < 0) {
        log_msg("no se pudo crear el socket de control");
        return 1;
    }
    last_ping = time(NULL);
    log_msg("listo, socket: %s", sock_path);

    /* bucle principal */
    while (running) {
        struct pollfd fds[1 + 1 + 1 + MAX_CLIENTS];
        int n = 0;
        fds[n].fd = wl_display_get_fd(display);
        fds[n].events = POLLIN;
        n++;
        fds[n].fd = wakeup_pipe[0];
        fds[n].events = POLLIN;
        n++;
        fds[n].fd = listen_fd;
        fds[n].events = POLLIN;
        n++;
        for (int i = 0; i < MAX_CLIENTS; i++) {
            if (clients[i].fd >= 0) {
                fds[n].fd = clients[i].fd;
                fds[n].events = POLLIN;
                n++;
            }
        }

        /* protocolo anti-deadlock de Wayland */
        while (wl_display_prepare_read(display) != 0)
            wl_display_dispatch_pending(display);
        if (wl_display_flush(display) < 0 && errno != EAGAIN) {
            running = 0;
            break;
        }

        int r = poll(fds, (nfds_t)n, 2000);
        if (r < 0) {
            if (errno == EINTR)
                continue;
            log_msg("poll: %s", strerror(errno));
            break;
        }
        if (r == 0) {
            wl_display_cancel_read(display);
            /* watchdog: la GUI debe enviar ping cada 2 s */
            if (time(NULL) - last_ping > 6) {
                log_msg("watchdog: sin heartbeat de la GUI, saliendo");
                running = 0;
            }
            continue;
        }

        if (fds[0].revents & POLLIN) {
            wl_display_read_events(display);
            wl_display_dispatch_pending(display);
        } else {
            wl_display_cancel_read(display);
        }

        if (fds[1].revents & POLLIN) {
            int idx;
            while (read(wakeup_pipe[0], &idx, sizeof(idx)) == sizeof(idx)) {
                struct wel_output *o;
                wl_list_for_each(o, &outputs, link) {
                    if (o->index == idx) {
                        __atomic_store_n(&o->needs_render, true, __ATOMIC_RELEASE);
                        break;
                    }
                }
            }
        }

        if (fds[2].revents & POLLIN)
            handle_new_client();
        for (int i = 0; i < MAX_CLIENTS; i++) {
            if (clients[i].fd >= 0 && fds[3 + i].revents & POLLIN)
                handle_client_data(i);
        }

        /* renderizar salidas pendientes (solo una por callback de frame) */
        struct wel_output *o;
        wl_list_for_each(o, &outputs, link) {
            if (__atomic_load_n(&o->needs_render, __ATOMIC_ACQUIRE) &&
                o->frame_cb == NULL && o->configured && o->mpv_gl)
                render_output(o);
        }
    }

    cleanup();
    return 0;
}
