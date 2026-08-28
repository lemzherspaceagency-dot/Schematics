/* main.c -- entry point, frame loop, and the headless self-test.
 *
 * PROJECT AURORA: THE LAST CHILD -- Room One
 * A vertical slice, per the project's own build rule: one room, one
 * mechanic, one prototype, only then continue.
 */
#include "ff_platform.h"
#include "ff_gl.h"
#include "au_render.h"
#include "au_game.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define AU_VERSION "prototype 0.1"

static int run_selftest(const char *shot_dir, int width, int height);
static int str_eq(const char *a, const char *b) { return strcmp(a, b) == 0; }

static void translate_input(void)
{
    au_in.forward = ff_plat.key_down[FF_KEY_W];
    au_in.back    = ff_plat.key_down[FF_KEY_S];
    au_in.left    = ff_plat.key_down[FF_KEY_A];
    au_in.right   = ff_plat.key_down[FF_KEY_D];
    au_in.interact_pressed = ff_plat.key_pressed[FF_KEY_E];
    au_in.trace_held = ff_plat.mouse_down[FF_MOUSE_RIGHT];
    au_in.mouse_dx = ff_plat.mouse_dx;
    au_in.mouse_dy = ff_plat.mouse_dy;
}

static int au_main(int argc, char **argv)
{
    int width = 1280, height = 720, want_selftest = 0;
    const char *shot_dir = ".";

    for (int i = 1; i < argc; i++) {
        if (str_eq(argv[i], "--width") && i + 1 < argc)       width = atoi(argv[++i]);
        else if (str_eq(argv[i], "--height") && i + 1 < argc) height = atoi(argv[++i]);
        else if (str_eq(argv[i], "--selftest"))               want_selftest = 1;
        else if (str_eq(argv[i], "--shots") && i + 1 < argc)  shot_dir = argv[++i];
        else if (str_eq(argv[i], "--help")) {
            printf("Project Aurora -- Room One (%s)\n"
                   "  --width N --height N   window size\n"
                   "  --selftest [--shots D] run the automated check and exit\n", AU_VERSION);
            return 0;
        }
    }
    if (width < 320) width = 320;
    if (height < 240) height = 240;

    if (!ff_platform_init("Project Aurora - The Last Child (Room One)", width, height)) return 1;

    if (ff_gl_load(ff_platform_gl_proc) > 0) {
        ff_platform_error_box("Project Aurora",
            "This computer's graphics driver is missing OpenGL 3.3 functions this\n"
            "prototype needs. Updating the graphics driver usually fixes this.");
        ff_platform_shutdown();
        return 1;
    }
    if (!au_render_init() || !au_ui_init()) {
        ff_platform_error_box("Project Aurora", "The renderer failed to start up.");
        ff_platform_shutdown();
        return 1;
    }
    au_render_resize(ff_plat.width, ff_plat.height);
    au_game_init();

    if (want_selftest) {
        int rc = run_selftest(shot_dir, width, height);
        ff_platform_shutdown();
        return rc;
    }

    double prev = ff_platform_time();
    double fps_accum = 0.0; int fps_frames = 0;
    int last_w = ff_plat.width, last_h = ff_plat.height;

    while (!ff_plat.should_close) {
        ff_platform_poll();
        double now = ff_platform_time();
        float dt = (float)(now - prev);
        prev = now;
        if (dt > 0.25f) dt = 0.25f;

        fps_accum += dt;
        if (++fps_frames, fps_accum >= 0.4) { au_g.fps = (float)(fps_frames / fps_accum); fps_accum = 0; fps_frames = 0; }

        if (ff_plat.width != last_w || ff_plat.height != last_h) {
            last_w = ff_plat.width; last_h = ff_plat.height;
            au_render_resize(last_w, last_h);
        }
        if (!ff_plat.focused && au_g.state == GS_PLAYING) {
            au_g.state = GS_PAUSED;
            ff_platform_capture_mouse(0);
        }

        translate_input();
        au_game_update(dt);
        au_game_render(ff_plat.width, ff_plat.height);
        ff_platform_swap();
    }

    ff_platform_shutdown();
    return 0;
}

/* ===================================================================== *
 *  Self-test
 * ===================================================================== */

static int g_checks, g_failures;
static void check(const char *what, int ok)
{
    g_checks++;
    if (!ok) g_failures++;
    printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what);
    fflush(stdout);
}
static void pump(int frames, float dt)
{
    for (int i = 0; i < frames; i++) {
        ff_platform_poll();
        translate_input();
        au_game_update(dt);
        au_game_render(ff_plat.width, ff_plat.height);
        ff_platform_swap();
    }
}
/* For a single directly-poked edge (a key_pressed or au_in field set by hand):
 * skips poll()/translate_input() so that poke is what au_game_update sees,
 * rather than being cleared or re-derived from ff_plat first. */
static void step(float dt)
{
    au_game_update(dt);
    au_game_render(ff_plat.width, ff_plat.height);
    ff_platform_swap();
}
static void shot(const char *dir, const char *name, int w, int h)
{
    char path[1024];
    snprintf(path, sizeof path, "%s/%s.tga", dir, name);
    if (ff_render_screenshot(path, w, h)) printf("  [shot] %s\n", path);
}
static float dist3(vec3 a, vec3 b) { return v3len(v3sub(a, b)); }

static int run_selftest(const char *shot_dir, int width, int height)
{
    printf("Project Aurora -- Room One self-test\n");
    printf("GL_VERSION  : %s\n", (const char *)glGetString(GL_VERSION));
    printf("GL_RENDERER : %s\n", (const char *)glGetString(GL_RENDERER));

    /* ---- title screen ---- */
    check("starts on the title screen", au_g.state == GS_TITLE);
    step(1.0f / 60.0f);   /* draw at least one frame before reading it back */
    shot(shot_dir, "01-title", width, height);

    ff_plat.key_pressed[FF_KEY_ENTER] = 1;
    step(1.0f / 60.0f);
    ff_plat.key_pressed[FF_KEY_ENTER] = 0;
    check("Enter on the title screen starts play", au_g.state == GS_PLAYING);
    check("the player spawns in an unobstructed cell", !au_collides(au_g.player.pos.x, au_g.player.pos.z));

    /* ---- Aurora's scripted approach ---- */
    pump(1, 1.0f / 60.0f);
    check("Aurora begins idle", au_g.auroraState == AU_IDLE);
    pump(90, 1.0f / 60.0f);   /* past idle(1.1s) + well into approach */
    check("Aurora approaches after the idle beat", au_g.auroraState == AU_APPROACH || au_g.auroraState == AU_SCAN);

    /* idle(1.1)+approach(2.6)+scan(1.3)+speak1(2.6)=7.6s to enter speak2, which
     * runs 7.6..10.4s and is when the slogan line is on screen; 90 frames
     * (1.5s) already elapsed above. */
    pump(400, 1.0f / 60.0f);   /* cumulative ~8.2s: inside the speak2 window */
    check("the welcome line uses the project's slogan",
          strstr(au_g.subOrpheon, "Let our song guide you here") != NULL);

    pump(250, 1.0f / 60.0f);   /* cumulative ~12.3s: comfortably past 10.4s */
    check("Aurora reaches the await-look beat", au_g.auroraState == AU_AWAIT_LOOK);
    shot(shot_dir, "02-aurora-scan", width, height);

    /* ---- looking away makes her vanish ---- */
    {
        int hunt = 0;
        au_g.player.yaw = au_g.player.yaw + FF_PI;   /* turn around, away from her */
        while (au_g.auroraState != AU_GONE && hunt < 180) { pump(1, 1.0f / 60.0f); hunt++; }
        check("Aurora vanishes once the player looks away", au_g.auroraState == AU_GONE);
        check("she relocates to the hidden anchor point", dist3(au_g.auroraPos, au_aurora_hidden_pos()) < 0.01f);
        check("looking away resolved well within the 20s fallback", hunt < 150);
    }
    shot(shot_dir, "03-aurora-gone", width, height);

    /* ---- D.I.V.A. pickup ---- */
    {
        au_g.player.pos.x = -4.0f; au_g.player.pos.z = -3.9f;
        check("not carrying D.I.V.A. yet", !au_g.hasDiva);
        au_in.interact_pressed = 1;
        step(1.0f / 60.0f);
        au_in.interact_pressed = 0;
        check("E at the desk picks up D.I.V.A.", au_g.hasDiva);
    }

    /* ---- the door starts locked ---- */
    check("the inner door starts locked", au_collides(0.0f, -7.9f));

    /* ---- tracing exposes the conduit and the pulse can be aimed at ---- */
    {
        ff_plat.mouse_down[FF_MOUSE_RIGHT] = 1;
        pump(1, 1.0f / 60.0f);
        check("holding trace with D.I.V.A. equipped enables tracing", au_g.tracing);

        /* Aim the pilot at wherever the pulse currently sits along its path. */
        vec3 eye = v3(au_g.player.pos.x, 1.7f, au_g.player.pos.z);
        vec3 target = { -4.0f, 3.15f, -4.0f };   /* conduit's first waypoint, t=0 */
        vec3 d = v3norm(v3sub(target, eye));
        au_g.player.yaw = atan2f(d.z, d.x);
        au_g.player.pitch = asinf(ff_clampf(d.y, -1.0f, 1.0f));
        au_g.pulseT = 0.0f;   /* park the pulse exactly where we're aiming */
        pump(1, 1.0f / 60.0f);

        au_in.interact_pressed = 1;
        step(1.0f / 60.0f);
        au_in.interact_pressed = 0;
        check("tapping the aimed signal arms the redirect", au_g.redirectArmed);
        shot(shot_dir, "04-conduit-armed", width, height);

        au_in.interact_pressed = 1;
        step(1.0f / 60.0f);
        au_in.interact_pressed = 0;
        check("a second tap commits the redirect", au_g.redirected);
        check("committing the redirect unlocks the door", !au_g.doorLocked);
        ff_plat.mouse_down[FF_MOUSE_RIGHT] = 0;
    }

    /* ---- the door animates open and stops blocking the doorway ---- */
    pump(90, 1.0f / 60.0f);
    check("the door finishes its open animation", au_g.doorAnimT >= 1.0f);
    check("the doorway no longer collides once unlocked", !au_collides(0.0f, -7.9f));
    shot(shot_dir, "05-door-open", width, height);

    /* ---- walking through ends the prototype ---- */
    {
        au_g.player.pos = v3(0.0f, 1.7f, -7.0f);
        ff_plat.key_down[FF_KEY_W] = 1;
        au_g.player.yaw = -FF_PI * 0.5f;   /* face -Z, matches ff_dir_from_angles' convention */
        int hunt = 0;
        while (au_g.state != GS_ENDED && hunt < 240) { pump(1, 1.0f / 60.0f); hunt++; }
        ff_plat.key_down[FF_KEY_W] = 0;
        check("walking through the open doorway ends the prototype", au_g.state == GS_ENDED);
    }
    shot(shot_dir, "06-end", width, height);

    /* ---- restart from the end screen ---- */
    ff_plat.key_pressed[FF_KEY_ENTER] = 1;
    step(1.0f / 60.0f);
    ff_plat.key_pressed[FF_KEY_ENTER] = 0;
    check("Enter on the end screen restarts the room", au_g.state == GS_TITLE);
    check("restarting resets the objective state", !au_g.hasDiva && au_g.doorLocked && !au_g.redirected);

    /* ---- stability ---- */
    {
        ff_plat.key_pressed[FF_KEY_ENTER] = 1; step(1.0f/60.0f); ff_plat.key_pressed[FF_KEY_ENTER] = 0;
        double t0 = ff_platform_time();
        pump(120, 1.0f / 60.0f);
        double el = ff_platform_time() - t0;
        printf("  [time] 120 frames in %.2fs (%.1f fps on a software rasteriser)\n",
               el, 120.0 / (el > 0.0 ? el : 1.0));
        check("no GL errors during the run", glGetError() == GL_NO_ERROR);
    }

    printf("\n%d checks, %d failures\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 2;
}

int main(int argc, char **argv) { return au_main(argc, argv); }

#ifdef _WIN32
#include <windows.h>
int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmdline, int show)
{
    (void)inst; (void)prev; (void)cmdline; (void)show;
    return au_main(__argc, __argv);
}
#endif
