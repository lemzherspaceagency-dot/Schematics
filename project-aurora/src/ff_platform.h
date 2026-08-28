/* ff_platform.h -- window, input, timing and paths.
 *
 * Two backends implement this: plat_win32.c (WGL, the shipping build) and
 * plat_x11.c (GLX, used for development and automated verification). The game
 * layer never touches an OS header.
 */
#ifndef FF_PLATFORM_H
#define FF_PLATFORM_H

enum {
    FF_KEY_UNKNOWN = 0,
    FF_KEY_A, FF_KEY_B, FF_KEY_C, FF_KEY_D, FF_KEY_E, FF_KEY_F, FF_KEY_G,
    FF_KEY_H, FF_KEY_I, FF_KEY_J, FF_KEY_K, FF_KEY_L, FF_KEY_M, FF_KEY_N,
    FF_KEY_O, FF_KEY_P, FF_KEY_Q, FF_KEY_R, FF_KEY_S, FF_KEY_T, FF_KEY_U,
    FF_KEY_V, FF_KEY_W, FF_KEY_X, FF_KEY_Y, FF_KEY_Z,
    FF_KEY_1, FF_KEY_2, FF_KEY_3, FF_KEY_4, FF_KEY_5,
    FF_KEY_6, FF_KEY_7, FF_KEY_8, FF_KEY_9, FF_KEY_0,
    FF_KEY_SPACE, FF_KEY_ESCAPE, FF_KEY_LSHIFT, FF_KEY_LCTRL, FF_KEY_TAB,
    FF_KEY_ENTER, FF_KEY_BACKSPACE,
    FF_KEY_LEFT, FF_KEY_RIGHT, FF_KEY_UP, FF_KEY_DOWN,
    FF_KEY_F1, FF_KEY_F2, FF_KEY_F3, FF_KEY_F4, FF_KEY_F5, FF_KEY_F11,
    FF_KEY_COUNT
};

enum { FF_MOUSE_LEFT = 0, FF_MOUSE_RIGHT = 1, FF_MOUSE_MIDDLE = 2, FF_MOUSE_COUNT };

typedef struct {
    int   width, height;          /* framebuffer size in pixels          */
    int   should_close;
    int   focused;
    int   mouse_captured;

    unsigned char key_down[FF_KEY_COUNT];
    unsigned char key_pressed[FF_KEY_COUNT];   /* edge, cleared each poll */
    unsigned char mouse_down[FF_MOUSE_COUNT];
    unsigned char mouse_pressed[FF_MOUSE_COUNT];
    float mouse_dx, mouse_dy;     /* relative motion since last poll     */
    float scroll;                 /* wheel notches since last poll       */
} ff_platform_state;

extern ff_platform_state ff_plat;

int    ff_platform_init(const char *title, int width, int height);
void   ff_platform_shutdown(void);
void   ff_platform_poll(void);        /* pump events, refresh ff_plat    */
void   ff_platform_swap(void);        /* present the back buffer         */
void   ff_platform_capture_mouse(int capture);
void   ff_platform_sleep_ms(int ms);
double ff_platform_time(void);        /* seconds, monotonic              */
void  *ff_platform_gl_proc(const char *name);
/* Per-user writable directory for saves; created if absent. */
const char *ff_platform_save_dir(void);
/* Best-effort message box / stderr notice for fatal startup failures. */
void   ff_platform_error_box(const char *title, const char *message);

#endif /* FF_PLATFORM_H */
