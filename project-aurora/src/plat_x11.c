/* plat_x11.c -- X11 + GLX backend.
 *
 * This is the development and verification backend: it is what lets the game
 * be launched headless under Xvfb so worldgen, physics and rendering can be
 * exercised automatically. The shipping Windows build uses plat_win32.c.
 */
#include "ff_platform.h"

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <X11/XKBlib.h>
/* GLX pulls in the system GL headers; this file deliberately does not
 * include ff_gl.h so the two sets of declarations never collide. */
#include <GL/glx.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>

ff_platform_state ff_plat;

typedef GLXContext (*PFNGLXCREATECONTEXTATTRIBSARB)(Display *, GLXFBConfig, GLXContext, Bool, const int *);

#define GLX_CONTEXT_MAJOR_VERSION_ARB 0x2091
#define GLX_CONTEXT_MINOR_VERSION_ARB 0x2092
#define GLX_CONTEXT_PROFILE_MASK_ARB  0x9126
#define GLX_CONTEXT_CORE_PROFILE_BIT  0x00000001

static Display   *g_dpy;
static Window     g_win;
static GLXContext g_ctx;
static Atom       g_wm_delete;
static Cursor     g_blank_cursor;
static int        g_warp_x, g_warp_y, g_ignore_warp;
static double     g_time_base;
static char       g_save_dir[1024];

static int ff_key_from_keysym(KeySym ks)
{
    if (ks >= XK_a && ks <= XK_z) return FF_KEY_A + (int)(ks - XK_a);
    if (ks >= XK_A && ks <= XK_Z) return FF_KEY_A + (int)(ks - XK_A);
    if (ks >= XK_1 && ks <= XK_9) return FF_KEY_1 + (int)(ks - XK_1);
    switch (ks) {
        case XK_0:          return FF_KEY_0;
        case XK_space:      return FF_KEY_SPACE;
        case XK_Escape:     return FF_KEY_ESCAPE;
        case XK_Shift_L: case XK_Shift_R:     return FF_KEY_LSHIFT;
        case XK_Control_L: case XK_Control_R: return FF_KEY_LCTRL;
        case XK_Tab:        return FF_KEY_TAB;
        case XK_Return: case XK_KP_Enter:     return FF_KEY_ENTER;
        case XK_BackSpace:  return FF_KEY_BACKSPACE;
        case XK_Left:       return FF_KEY_LEFT;
        case XK_Right:      return FF_KEY_RIGHT;
        case XK_Up:         return FF_KEY_UP;
        case XK_Down:       return FF_KEY_DOWN;
        case XK_F1:         return FF_KEY_F1;
        case XK_F2:         return FF_KEY_F2;
        case XK_F3:         return FF_KEY_F3;
        case XK_F4:         return FF_KEY_F4;
        case XK_F5:         return FF_KEY_F5;
        case XK_F11:        return FF_KEY_F11;
        default:            return FF_KEY_UNKNOWN;
    }
}

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

int ff_platform_init(const char *title, int width, int height)
{
    memset(&ff_plat, 0, sizeof ff_plat);
    ff_plat.width = width;
    ff_plat.height = height;
    ff_plat.focused = 1;

    g_dpy = XOpenDisplay(NULL);
    if (!g_dpy) {
        fprintf(stderr, "[x11] cannot open display (is DISPLAY set?)\n");
        return 0;
    }

    static int fb_attribs[] = {
        GLX_X_RENDERABLE,  True,
        GLX_DRAWABLE_TYPE, GLX_WINDOW_BIT,
        GLX_RENDER_TYPE,   GLX_RGBA_BIT,
        GLX_RED_SIZE,      8,
        GLX_GREEN_SIZE,    8,
        GLX_BLUE_SIZE,     8,
        GLX_ALPHA_SIZE,    8,
        GLX_DEPTH_SIZE,    24,
        GLX_DOUBLEBUFFER,  True,
        None
    };
    int fb_count = 0;
    GLXFBConfig *fbc = glXChooseFBConfig(g_dpy, DefaultScreen(g_dpy), fb_attribs, &fb_count);
    if (!fbc || fb_count == 0) {
        fprintf(stderr, "[x11] no suitable framebuffer config\n");
        return 0;
    }
    GLXFBConfig cfg = fbc[0];
    XFree(fbc);

    XVisualInfo *vi = glXGetVisualFromFBConfig(g_dpy, cfg);
    if (!vi) { fprintf(stderr, "[x11] no visual\n"); return 0; }

    XSetWindowAttributes swa;
    memset(&swa, 0, sizeof swa);
    swa.colormap = XCreateColormap(g_dpy, RootWindow(g_dpy, vi->screen), vi->visual, AllocNone);
    swa.event_mask = ExposureMask | KeyPressMask | KeyReleaseMask | ButtonPressMask |
                     ButtonReleaseMask | PointerMotionMask | StructureNotifyMask |
                     FocusChangeMask;

    g_win = XCreateWindow(g_dpy, RootWindow(g_dpy, vi->screen), 0, 0,
                          (unsigned)width, (unsigned)height, 0, vi->depth,
                          InputOutput, vi->visual, CWColormap | CWEventMask, &swa);
    if (!g_win) { fprintf(stderr, "[x11] cannot create window\n"); return 0; }

    XStoreName(g_dpy, g_win, title);
    g_wm_delete = XInternAtom(g_dpy, "WM_DELETE_WINDOW", False);
    XSetWMProtocols(g_dpy, g_win, &g_wm_delete, 1);
    XMapWindow(g_dpy, g_win);

    PFNGLXCREATECONTEXTATTRIBSARB create_ctx =
        (PFNGLXCREATECONTEXTATTRIBSARB)glXGetProcAddressARB((const GLubyte *)"glXCreateContextAttribsARB");
    if (create_ctx) {
        int ctx_attribs[] = {
            GLX_CONTEXT_MAJOR_VERSION_ARB, 3,
            GLX_CONTEXT_MINOR_VERSION_ARB, 3,
            GLX_CONTEXT_PROFILE_MASK_ARB,  GLX_CONTEXT_CORE_PROFILE_BIT,
            None
        };
        g_ctx = create_ctx(g_dpy, cfg, 0, True, ctx_attribs);
    }
    if (!g_ctx) g_ctx = glXCreateNewContext(g_dpy, cfg, GLX_RGBA_TYPE, 0, True);
    XFree(vi);
    if (!g_ctx) { fprintf(stderr, "[x11] cannot create GL 3.3 context\n"); return 0; }

    glXMakeCurrent(g_dpy, g_win, g_ctx);
    XkbSetDetectableAutoRepeat(g_dpy, True, NULL);

    /* 1x1 transparent pixmap doubles as a hidden cursor for mouse-look. */
    {
        XColor black; char data[8] = {0};
        Pixmap pm = XCreateBitmapFromData(g_dpy, g_win, data, 8, 8);
        memset(&black, 0, sizeof black);
        g_blank_cursor = XCreatePixmapCursor(g_dpy, pm, pm, &black, &black, 0, 0);
        XFreePixmap(g_dpy, pm);
    }

    g_time_base = now_seconds();
    return 1;
}

void ff_platform_shutdown(void)
{
    if (g_dpy) {
        if (g_ctx) { glXMakeCurrent(g_dpy, None, NULL); glXDestroyContext(g_dpy, g_ctx); }
        if (g_win) XDestroyWindow(g_dpy, g_win);
        XCloseDisplay(g_dpy);
    }
    g_dpy = NULL; g_win = 0; g_ctx = NULL;
}

void ff_platform_capture_mouse(int capture)
{
    if (!g_dpy) return;
    if (capture == ff_plat.mouse_captured) return;
    ff_plat.mouse_captured = capture;
    if (capture) {
        XDefineCursor(g_dpy, g_win, g_blank_cursor);
        XGrabPointer(g_dpy, g_win, True, ButtonPressMask | ButtonReleaseMask | PointerMotionMask,
                     GrabModeAsync, GrabModeAsync, g_win, g_blank_cursor, CurrentTime);
        g_warp_x = ff_plat.width / 2;
        g_warp_y = ff_plat.height / 2;
        XWarpPointer(g_dpy, None, g_win, 0, 0, 0, 0, g_warp_x, g_warp_y);
        g_ignore_warp = 1;
    } else {
        XUngrabPointer(g_dpy, CurrentTime);
        XUndefineCursor(g_dpy, g_win);
    }
    XFlush(g_dpy);
}

void ff_platform_poll(void)
{
    memset(ff_plat.key_pressed, 0, sizeof ff_plat.key_pressed);
    memset(ff_plat.mouse_pressed, 0, sizeof ff_plat.mouse_pressed);
    ff_plat.mouse_dx = ff_plat.mouse_dy = 0.0f;
    ff_plat.scroll = 0.0f;

    while (XPending(g_dpy)) {
        XEvent ev;
        XNextEvent(g_dpy, &ev);
        switch (ev.type) {
        case ClientMessage:
            if ((Atom)ev.xclient.data.l[0] == g_wm_delete) ff_plat.should_close = 1;
            break;
        case ConfigureNotify:
            ff_plat.width  = ev.xconfigure.width;
            ff_plat.height = ev.xconfigure.height;
            break;
        case FocusIn:  ff_plat.focused = 1; break;
        case FocusOut: ff_plat.focused = 0; break;
        case KeyPress: {
            KeySym ks = XkbKeycodeToKeysym(g_dpy, (KeyCode)ev.xkey.keycode, 0, 0);
            int k = ff_key_from_keysym(ks);
            if (k) { if (!ff_plat.key_down[k]) ff_plat.key_pressed[k] = 1; ff_plat.key_down[k] = 1; }
            break;
        }
        case KeyRelease: {
            KeySym ks = XkbKeycodeToKeysym(g_dpy, (KeyCode)ev.xkey.keycode, 0, 0);
            int k = ff_key_from_keysym(ks);
            if (k) ff_plat.key_down[k] = 0;
            break;
        }
        case ButtonPress:
            if (ev.xbutton.button == Button1) { if (!ff_plat.mouse_down[0]) ff_plat.mouse_pressed[0] = 1; ff_plat.mouse_down[0] = 1; }
            else if (ev.xbutton.button == Button3) { if (!ff_plat.mouse_down[1]) ff_plat.mouse_pressed[1] = 1; ff_plat.mouse_down[1] = 1; }
            else if (ev.xbutton.button == Button2) { if (!ff_plat.mouse_down[2]) ff_plat.mouse_pressed[2] = 1; ff_plat.mouse_down[2] = 1; }
            else if (ev.xbutton.button == Button4) ff_plat.scroll += 1.0f;
            else if (ev.xbutton.button == Button5) ff_plat.scroll -= 1.0f;
            break;
        case ButtonRelease:
            if (ev.xbutton.button == Button1) ff_plat.mouse_down[0] = 0;
            else if (ev.xbutton.button == Button3) ff_plat.mouse_down[1] = 0;
            else if (ev.xbutton.button == Button2) ff_plat.mouse_down[2] = 0;
            break;
        case MotionNotify:
            if (ff_plat.mouse_captured) {
                /* Skip the synthetic motion produced by our own re-centering. */
                if (g_ignore_warp && ev.xmotion.x == g_warp_x && ev.xmotion.y == g_warp_y) {
                    g_ignore_warp = 0;
                    break;
                }
                ff_plat.mouse_dx += (float)(ev.xmotion.x - g_warp_x);
                ff_plat.mouse_dy += (float)(ev.xmotion.y - g_warp_y);
            }
            break;
        default: break;
        }
    }

    if (ff_plat.mouse_captured) {
        g_warp_x = ff_plat.width / 2;
        g_warp_y = ff_plat.height / 2;
        XWarpPointer(g_dpy, None, g_win, 0, 0, 0, 0, g_warp_x, g_warp_y);
        g_ignore_warp = 1;
    }
}

void ff_platform_swap(void) { glXSwapBuffers(g_dpy, g_win); }

void ff_platform_sleep_ms(int ms)
{
    struct timespec ts;
    ts.tv_sec  = ms / 1000;
    ts.tv_nsec = (long)(ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
}

double ff_platform_time(void) { return now_seconds() - g_time_base; }

void *ff_platform_gl_proc(const char *name)
{
    return (void *)glXGetProcAddressARB((const GLubyte *)name);
}

const char *ff_platform_save_dir(void)
{
    if (g_save_dir[0]) return g_save_dir;

    const char *xdg = getenv("XDG_DATA_HOME");
    const char *home = getenv("HOME");
    if (xdg && xdg[0])       snprintf(g_save_dir, sizeof g_save_dir, "%s/antinode", xdg);
    else if (home && home[0]) snprintf(g_save_dir, sizeof g_save_dir, "%s/.local/share/antinode", home);
    else                      snprintf(g_save_dir, sizeof g_save_dir, "./antinode-data");

    /* mkdir -p over the whole path so a fresh machine just works. */
    char tmp[1024];
    snprintf(tmp, sizeof tmp, "%s", g_save_dir);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') { *p = 0; mkdir(tmp, 0755); *p = '/'; }
    }
    mkdir(tmp, 0755);
    return g_save_dir;
}

void ff_platform_error_box(const char *title, const char *message)
{
    fprintf(stderr, "[%s] %s\n", title, message);
}
