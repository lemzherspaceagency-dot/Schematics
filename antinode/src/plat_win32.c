/* plat_win32.c -- Win32 + WGL backend (the shipping build).
 *
 * Creates a real GL 3.3 core context through the usual two-step WGL dance:
 * a throwaway window supplies wglChoosePixelFormatARB/wglCreateContextAttribsARB,
 * which the real window then uses. No external libraries are involved, so the
 * shipped executable depends only on the system DLLs every Windows install has.
 */
#include "ff_platform.h"
#include "ff_gl.h"

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

ff_platform_state ff_plat;

#define WGL_DRAW_TO_WINDOW_ARB            0x2001
#define WGL_ACCELERATION_ARB              0x2003
#define WGL_SUPPORT_OPENGL_ARB            0x2010
#define WGL_DOUBLE_BUFFER_ARB             0x2011
#define WGL_PIXEL_TYPE_ARB                0x2013
#define WGL_COLOR_BITS_ARB                0x2014
#define WGL_DEPTH_BITS_ARB                0x2022
#define WGL_STENCIL_BITS_ARB              0x2023
#define WGL_FULL_ACCELERATION_ARB         0x2027
#define WGL_TYPE_RGBA_ARB                 0x202B
#define WGL_CONTEXT_MAJOR_VERSION_ARB     0x2091
#define WGL_CONTEXT_MINOR_VERSION_ARB     0x2092
#define WGL_CONTEXT_FLAGS_ARB             0x2094
#define WGL_CONTEXT_PROFILE_MASK_ARB      0x9126
#define WGL_CONTEXT_CORE_PROFILE_BIT_ARB  0x00000001

typedef BOOL  (WINAPI *PFNWGLCHOOSEPIXELFORMATARB)(HDC, const int *, const FLOAT *, UINT, int *, UINT *);
typedef HGLRC (WINAPI *PFNWGLCREATECONTEXTATTRIBSARB)(HDC, HGLRC, const int *);
typedef BOOL  (WINAPI *PFNWGLSWAPINTERVALEXT)(int);

static HINSTANCE g_inst;
static HWND      g_hwnd;
static HDC       g_hdc;
static HGLRC     g_hglrc;
static HMODULE   g_opengl32;
static LARGE_INTEGER g_freq, g_start;
static char      g_save_dir[MAX_PATH];
static int       g_want_close;

static int ff_key_from_vk(WPARAM vk)
{
    if (vk >= 'A' && vk <= 'Z') return FF_KEY_A + (int)(vk - 'A');
    if (vk >= '1' && vk <= '9') return FF_KEY_1 + (int)(vk - '1');
    switch (vk) {
        case '0':          return FF_KEY_0;
        case VK_SPACE:     return FF_KEY_SPACE;
        case VK_ESCAPE:    return FF_KEY_ESCAPE;
        case VK_SHIFT: case VK_LSHIFT: case VK_RSHIFT:    return FF_KEY_LSHIFT;
        case VK_CONTROL: case VK_LCONTROL: case VK_RCONTROL: return FF_KEY_LCTRL;
        case VK_TAB:       return FF_KEY_TAB;
        case VK_RETURN:    return FF_KEY_ENTER;
        case VK_BACK:      return FF_KEY_BACKSPACE;
        case VK_LEFT:      return FF_KEY_LEFT;
        case VK_RIGHT:     return FF_KEY_RIGHT;
        case VK_UP:        return FF_KEY_UP;
        case VK_DOWN:      return FF_KEY_DOWN;
        case VK_F1:        return FF_KEY_F1;
        case VK_F2:        return FF_KEY_F2;
        case VK_F3:        return FF_KEY_F3;
        case VK_F4:        return FF_KEY_F4;
        case VK_F5:        return FF_KEY_F5;
        case VK_F11:       return FF_KEY_F11;
        default:           return FF_KEY_UNKNOWN;
    }
}

static LRESULT CALLBACK ff_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_CLOSE:
    case WM_DESTROY:
        g_want_close = 1;
        return 0;
    case WM_SIZE:
        ff_plat.width  = LOWORD(lp);
        ff_plat.height = HIWORD(lp);
        if (ff_plat.width  < 1) ff_plat.width  = 1;
        if (ff_plat.height < 1) ff_plat.height = 1;
        return 0;
    case WM_SETFOCUS:  ff_plat.focused = 1; return 0;
    case WM_KILLFOCUS:
        ff_plat.focused = 0;
        memset(ff_plat.key_down, 0, sizeof ff_plat.key_down);
        memset(ff_plat.mouse_down, 0, sizeof ff_plat.mouse_down);
        return 0;
    case WM_SYSKEYDOWN:
    case WM_KEYDOWN: {
        int k = ff_key_from_vk(wp);
        if (k) { if (!ff_plat.key_down[k]) ff_plat.key_pressed[k] = 1; ff_plat.key_down[k] = 1; }
        if (wp == VK_F10 || (wp == VK_MENU)) return 0;   /* don't open the system menu */
        break;
    }
    case WM_SYSKEYUP:
    case WM_KEYUP: {
        int k = ff_key_from_vk(wp);
        if (k) ff_plat.key_down[k] = 0;
        break;
    }
    case WM_LBUTTONDOWN: if (!ff_plat.mouse_down[0]) ff_plat.mouse_pressed[0] = 1; ff_plat.mouse_down[0] = 1; SetCapture(hwnd); return 0;
    case WM_LBUTTONUP:   ff_plat.mouse_down[0] = 0; ReleaseCapture(); return 0;
    case WM_RBUTTONDOWN: if (!ff_plat.mouse_down[1]) ff_plat.mouse_pressed[1] = 1; ff_plat.mouse_down[1] = 1; return 0;
    case WM_RBUTTONUP:   ff_plat.mouse_down[1] = 0; return 0;
    case WM_MBUTTONDOWN: if (!ff_plat.mouse_down[2]) ff_plat.mouse_pressed[2] = 1; ff_plat.mouse_down[2] = 1; return 0;
    case WM_MBUTTONUP:   ff_plat.mouse_down[2] = 0; return 0;
    case WM_MOUSEWHEEL:
        ff_plat.scroll += (float)GET_WHEEL_DELTA_WPARAM(wp) / (float)WHEEL_DELTA;
        return 0;
    case WM_ERASEBKGND:
        return 1;   /* GL owns the client area; skip the flicker */
    default: break;
    }
    return DefWindowProcA(hwnd, msg, wp, lp);
}

/* The throwaway context that hands us the modern WGL entry points. */
static int ff_bootstrap_wgl(PFNWGLCHOOSEPIXELFORMATARB *out_choose,
                            PFNWGLCREATECONTEXTATTRIBSARB *out_create)
{
    WNDCLASSA wc;
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc   = DefWindowProcA;
    wc.hInstance     = g_inst;
    wc.lpszClassName = "ANTINODEBootstrap";
    if (!RegisterClassA(&wc)) return 0;

    HWND dummy = CreateWindowExA(0, wc.lpszClassName, "", 0, 0, 0, 1, 1,
                                 NULL, NULL, g_inst, NULL);
    if (!dummy) return 0;
    HDC dc = GetDC(dummy);

    PIXELFORMATDESCRIPTOR pfd;
    memset(&pfd, 0, sizeof pfd);
    pfd.nSize      = sizeof pfd;
    pfd.nVersion   = 1;
    pfd.dwFlags    = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER;
    pfd.iPixelType = PFD_TYPE_RGBA;
    pfd.cColorBits = 32;
    pfd.cDepthBits = 24;
    int pf = ChoosePixelFormat(dc, &pfd);
    SetPixelFormat(dc, pf, &pfd);

    HGLRC rc = wglCreateContext(dc);
    wglMakeCurrent(dc, rc);

    *out_choose = (PFNWGLCHOOSEPIXELFORMATARB)wglGetProcAddress("wglChoosePixelFormatARB");
    *out_create = (PFNWGLCREATECONTEXTATTRIBSARB)wglGetProcAddress("wglCreateContextAttribsARB");

    wglMakeCurrent(NULL, NULL);
    wglDeleteContext(rc);
    ReleaseDC(dummy, dc);
    DestroyWindow(dummy);
    UnregisterClassA(wc.lpszClassName, g_inst);
    return (*out_choose && *out_create);
}

int ff_platform_init(const char *title, int width, int height)
{
    memset(&ff_plat, 0, sizeof ff_plat);
    ff_plat.width = width;
    ff_plat.height = height;
    ff_plat.focused = 1;

    g_inst = GetModuleHandleA(NULL);

    /* Crisp pixels on scaled displays; harmless if the call is unavailable. */
    {
        HMODULE user32 = LoadLibraryA("user32.dll");
        if (user32) {
            typedef BOOL (WINAPI *PFNSETDPIAWARE)(void);
            PFNSETDPIAWARE set_dpi = (PFNSETDPIAWARE)(void *)GetProcAddress(user32, "SetProcessDPIAware");
            if (set_dpi) set_dpi();
            FreeLibrary(user32);
        }
    }

    PFNWGLCHOOSEPIXELFORMATARB    wgl_choose = NULL;
    PFNWGLCREATECONTEXTATTRIBSARB wgl_create = NULL;
    int have_modern = ff_bootstrap_wgl(&wgl_choose, &wgl_create);

    WNDCLASSA wc;
    memset(&wc, 0, sizeof wc);
    wc.style         = CS_OWNDC;
    wc.lpfnWndProc   = ff_wndproc;
    wc.hInstance     = g_inst;
    wc.hCursor       = LoadCursor(NULL, IDC_ARROW);
    wc.lpszClassName = "ANTINODEWindow";
    wc.hIcon         = LoadIconA(g_inst, "APPICON");
    if (!wc.hIcon) wc.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    if (!RegisterClassA(&wc)) {
        ff_platform_error_box("ANTINODE", "Could not register the window class.");
        return 0;
    }

    RECT r = { 0, 0, width, height };
    AdjustWindowRect(&r, WS_OVERLAPPEDWINDOW, FALSE);
    int win_w = r.right - r.left, win_h = r.bottom - r.top;
    int sx = (GetSystemMetrics(SM_CXSCREEN) - win_w) / 2;
    int sy = (GetSystemMetrics(SM_CYSCREEN) - win_h) / 2;

    g_hwnd = CreateWindowExA(0, wc.lpszClassName, title, WS_OVERLAPPEDWINDOW,
                             sx > 0 ? sx : 0, sy > 0 ? sy : 0, win_w, win_h,
                             NULL, NULL, g_inst, NULL);
    if (!g_hwnd) {
        ff_platform_error_box("ANTINODE", "Could not create the game window.");
        return 0;
    }
    g_hdc = GetDC(g_hwnd);

    if (have_modern) {
        const int pf_attribs[] = {
            WGL_DRAW_TO_WINDOW_ARB, GL_TRUE,
            WGL_SUPPORT_OPENGL_ARB, GL_TRUE,
            WGL_DOUBLE_BUFFER_ARB,  GL_TRUE,
            WGL_ACCELERATION_ARB,   WGL_FULL_ACCELERATION_ARB,
            WGL_PIXEL_TYPE_ARB,     WGL_TYPE_RGBA_ARB,
            WGL_COLOR_BITS_ARB,     32,
            WGL_DEPTH_BITS_ARB,     24,
            WGL_STENCIL_BITS_ARB,   8,
            0
        };
        int pf = 0; UINT num = 0;
        if (wgl_choose(g_hdc, pf_attribs, NULL, 1, &pf, &num) && num > 0) {
            PIXELFORMATDESCRIPTOR pfd;
            memset(&pfd, 0, sizeof pfd);
            pfd.nSize = sizeof pfd; pfd.nVersion = 1;
            DescribePixelFormat(g_hdc, pf, sizeof pfd, &pfd);
            SetPixelFormat(g_hdc, pf, &pfd);

            const int ctx_attribs[] = {
                WGL_CONTEXT_MAJOR_VERSION_ARB, 3,
                WGL_CONTEXT_MINOR_VERSION_ARB, 3,
                WGL_CONTEXT_PROFILE_MASK_ARB,  WGL_CONTEXT_CORE_PROFILE_BIT_ARB,
                0
            };
            g_hglrc = wgl_create(g_hdc, NULL, ctx_attribs);
        }
    }

    if (!g_hglrc) {
        ff_platform_error_box("ANTINODE",
            "This computer's graphics driver does not provide OpenGL 3.3.\n\n"
            "Updating the graphics driver usually fixes this.");
        return 0;
    }

    wglMakeCurrent(g_hdc, g_hglrc);

    /* vsync on when the driver exposes it */
    {
        PFNWGLSWAPINTERVALEXT swap_interval =
            (PFNWGLSWAPINTERVALEXT)wglGetProcAddress("wglSwapIntervalEXT");
        if (swap_interval) swap_interval(1);
    }

    ShowWindow(g_hwnd, SW_SHOW);
    SetForegroundWindow(g_hwnd);
    SetFocus(g_hwnd);

    QueryPerformanceFrequency(&g_freq);
    QueryPerformanceCounter(&g_start);
    return 1;
}

void ff_platform_shutdown(void)
{
    if (g_hglrc) { wglMakeCurrent(NULL, NULL); wglDeleteContext(g_hglrc); g_hglrc = NULL; }
    if (g_hdc)   { ReleaseDC(g_hwnd, g_hdc); g_hdc = NULL; }
    if (g_hwnd)  { DestroyWindow(g_hwnd); g_hwnd = NULL; }
    if (g_opengl32) { FreeLibrary(g_opengl32); g_opengl32 = NULL; }
}

void ff_platform_capture_mouse(int capture)
{
    if (capture == ff_plat.mouse_captured) return;
    ff_plat.mouse_captured = capture;
    ShowCursor(capture ? FALSE : TRUE);
    if (capture) {
        RECT rc; GetClientRect(g_hwnd, &rc);
        POINT c = { (rc.right - rc.left) / 2, (rc.bottom - rc.top) / 2 };
        ClientToScreen(g_hwnd, &c);
        SetCursorPos(c.x, c.y);
    }
}

void ff_platform_poll(void)
{
    memset(ff_plat.key_pressed, 0, sizeof ff_plat.key_pressed);
    memset(ff_plat.mouse_pressed, 0, sizeof ff_plat.mouse_pressed);
    ff_plat.mouse_dx = ff_plat.mouse_dy = 0.0f;
    ff_plat.scroll = 0.0f;

    MSG msg;
    while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }
    if (g_want_close) ff_plat.should_close = 1;

    if (ff_plat.mouse_captured && ff_plat.focused) {
        RECT rc; GetClientRect(g_hwnd, &rc);
        POINT center = { (rc.right - rc.left) / 2, (rc.bottom - rc.top) / 2 };
        POINT screen_center = center;
        ClientToScreen(g_hwnd, &screen_center);

        POINT p;
        GetCursorPos(&p);
        ff_plat.mouse_dx = (float)(p.x - screen_center.x);
        ff_plat.mouse_dy = (float)(p.y - screen_center.y);
        if (ff_plat.mouse_dx != 0.0f || ff_plat.mouse_dy != 0.0f)
            SetCursorPos(screen_center.x, screen_center.y);
    }
}

void ff_platform_swap(void) { SwapBuffers(g_hdc); }

void ff_platform_sleep_ms(int ms) { Sleep((DWORD)ms); }

double ff_platform_time(void)
{
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    return (double)(now.QuadPart - g_start.QuadPart) / (double)g_freq.QuadPart;
}

void *ff_platform_gl_proc(const char *name)
{
    void *p = (void *)wglGetProcAddress(name);
    /* wglGetProcAddress only knows about extensions; the GL 1.1 core still
     * lives in opengl32.dll and has to be looked up directly. */
    if (p == NULL || p == (void *)1 || p == (void *)2 ||
        p == (void *)3 || p == (void *)-1) {
        if (!g_opengl32) g_opengl32 = LoadLibraryA("opengl32.dll");
        p = g_opengl32 ? (void *)GetProcAddress(g_opengl32, name) : NULL;
    }
    return p;
}

const char *ff_platform_save_dir(void)
{
    if (g_save_dir[0]) return g_save_dir;
    const char *appdata = getenv("APPDATA");
    if (appdata && appdata[0]) snprintf(g_save_dir, sizeof g_save_dir, "%s\\Antinode", appdata);
    else                       snprintf(g_save_dir, sizeof g_save_dir, ".\\Antinode");
    CreateDirectoryA(g_save_dir, NULL);
    return g_save_dir;
}

void ff_platform_error_box(const char *title, const char *message)
{
    MessageBoxA(g_hwnd, message, title, MB_OK | MB_ICONERROR);
}
