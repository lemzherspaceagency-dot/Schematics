/* main.c -- entry point, frame loop, and the headless self-test.
 *
 * ANTINODE
 * A lightless vault, a handful of wave emitters, and a crust called the Bloom
 * that can only travel over solid ground. You never place a block: you tune
 * the waves, and where they agree the world becomes solid.
 */
#include "ff_platform.h"
#include "ff_gl.h"
#include "ff_render.h"
#include "ff_game.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FF_VERSION "alpha 0.1"

static int run_selftest(const char *shot_dir, int width, int height);
static int str_eq(const char *a, const char *b) { return strcmp(a, b) == 0; }

static int ff_main(int argc, char **argv)
{
    int width = 1280, height = 720;
    int want_selftest = 0, force_new = 0;
    unsigned int seed = 0;
    const char *shot_dir = ".";

    for (int i = 1; i < argc; i++) {
        if (str_eq(argv[i], "--width") && i + 1 < argc)       width = atoi(argv[++i]);
        else if (str_eq(argv[i], "--height") && i + 1 < argc) height = atoi(argv[++i]);
        else if (str_eq(argv[i], "--seed") && i + 1 < argc)   seed = (unsigned)strtoul(argv[++i], NULL, 10);
        else if (str_eq(argv[i], "--new"))                    force_new = 1;
        else if (str_eq(argv[i], "--selftest"))               want_selftest = 1;
        else if (str_eq(argv[i], "--shots") && i + 1 < argc)  shot_dir = argv[++i];
        else if (str_eq(argv[i], "--help")) {
            printf("ANTINODE %s\n"
                   "  --width N --height N   window size\n"
                   "  --seed N               vault seed for a new run\n"
                   "  --new                  ignore the stored state\n"
                   "  --selftest [--shots D] run the automated check and exit\n", FF_VERSION);
            return 0;
        }
    }
    if (width < 320) width = 320;
    if (height < 240) height = 240;

    if (!ff_platform_init("ANTINODE " FF_VERSION, width, height)) return 1;

    if (ff_gl_load(ff_platform_gl_proc) > 0) {
        ff_platform_error_box("ANTINODE",
            "The graphics driver is missing OpenGL 3.3 functions this game needs.\n\n"
            "Updating the graphics driver usually fixes this.");
        ff_platform_shutdown();
        return 1;
    }
    if (!ff_render_init() || !ff_ui_init()) {
        ff_platform_error_box("ANTINODE", "The renderer failed to start up.");
        ff_platform_shutdown();
        return 1;
    }
    ff_render_resize(ff_plat.width, ff_plat.height);

    if (want_selftest) {
        int rc = run_selftest(shot_dir, width, height);
        ff_render_shutdown();
        ff_platform_shutdown();
        return rc;
    }

    int had_save = 0;
    if (!force_new) had_save = ff_game_load();
    if (!had_save)
        ff_game_new(seed ? seed : (unsigned)(ff_platform_time() * 1000.0) ^ 0x9E37u, 0);

    ff_g.state = GS_TITLE;
    ff_g.menu_index = had_save ? 0 : 1;

    double prev = ff_platform_time();
    double fps_accum = 0.0;
    int fps_frames = 0, last_w = ff_plat.width, last_h = ff_plat.height;

    while (!ff_plat.should_close) {
        ff_platform_poll();
        double now = ff_platform_time();
        float dt = (float)(now - prev);
        prev = now;
        if (dt > 0.25f) dt = 0.25f;

        fps_accum += dt;
        if (++fps_frames, fps_accum >= 0.4) {
            ff_g.fps = (float)(fps_frames / fps_accum);
            fps_accum = 0.0;
            fps_frames = 0;
        }
        if (ff_plat.width != last_w || ff_plat.height != last_h) {
            last_w = ff_plat.width; last_h = ff_plat.height;
            ff_render_resize(last_w, last_h);
        }
        if (!ff_plat.focused && ff_plat.mouse_captured && ff_g.state == GS_PLAYING) {
            ff_g.state = GS_PAUSED;
            ff_g.menu_index = 0;
            ff_platform_capture_mouse(0);
        }

        ff_game_update(dt);
        ff_game_render(ff_plat.width, ff_plat.height);
        ff_platform_swap();
    }

    if (ff_g.state != GS_TITLE) ff_game_save();
    ff_render_shutdown();
    ff_platform_shutdown();
    return 0;
}

/* ===================================================================== *
 *  Self-test -- drives the real loop and asserts on the systems that are
 *  easy to break and hard to eyeball.
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
        ff_game_update(dt);
        ff_game_render(ff_plat.width, ff_plat.height);
        ff_platform_swap();
    }
}

static void shot(const char *dir, const char *name, int w, int h)
{
    char path[1024];
    snprintf(path, sizeof path, "%s/%s.tga", dir, name);
    if (ff_render_screenshot(path, w, h)) printf("  [shot] %s\n", path);
}

static void clear_input(void)
{
    memset(ff_plat.key_down, 0, sizeof ff_plat.key_down);
    memset(ff_plat.key_pressed, 0, sizeof ff_plat.key_pressed);
    memset(ff_plat.mouse_down, 0, sizeof ff_plat.mouse_down);
    memset(ff_plat.mouse_pressed, 0, sizeof ff_plat.mouse_pressed);
}

static int count_mat(uint8_t want)
{
    int n = 0;
    for (int x = 0; x < VA_W; x++)
        for (int y = 0; y < VA_H; y++)
            for (int z = 0; z < VA_D; z++)
                if (ff_vault_mat(x, y, z) == want) n++;
    return n;
}

static int run_selftest(const char *shot_dir, int width, int height)
{
    printf("ANTINODE %s self-test\n", FF_VERSION);
    printf("GL_VERSION  : %s\n", (const char *)glGetString(GL_VERSION));
    printf("GL_RENDERER : %s\n", (const char *)glGetString(GL_RENDERER));

    const unsigned int SEED = 20260828u;
    ff_game_new(SEED, 0);
    ff_g.state = GS_PLAYING;
    pump(6, 1.0f / 60.0f);

    /* ---- chamber ---- */
    int bedrock = count_mat(MAT_BEDROCK), empty = count_mat(MAT_EMPTY);
    check("the chamber has rock", bedrock > 10000);
    check("the chamber has open space", empty > 10000);
    check("a core exists", count_mat(MAT_CORE) > 0);
    check("anchors were placed", ff_vault_anchor_count() == 3);
    check("the pilot starts in open space",
          !ff_vault_solid((int)ff_g.pilot.pos.x, (int)ff_g.pilot.pos.y, (int)ff_g.pilot.pos.z));
    check("nothing is linked before anything is built", ff_vault_anchors_linked() == 0);

    /* ---- waves condense matter ---- */
    {
        vec3 core = ff_vault_core_pos();
        /* Two emitters flanking the core, tuned the same so their crests add. */
        ff_emitter *a = ff_vault_emitter(0);
        ff_emitter *b = ff_vault_emitter(1);
        a->wavelength = b->wavelength = 9.0f;
        a->amplitude = b->amplitude = 0.9f;
        a->phase = b->phase = 0.0f;
        a->active = b->active = 1;
        ff_vault_place_emitter(0, v3(core.x - 9.0f, core.y + 3.0f, core.z));
        ff_vault_place_emitter(1, v3(core.x + 9.0f, core.y + 3.0f, core.z));
        ff_vault_touch_field();
        pump(30, 1.0f / 60.0f);

        int condensed = count_mat(MAT_CONDENSED);
        printf("  [info] condensate cells: %d\n", condensed);
        check("constructive interference condenses matter", condensed > 200);
        check("condensation did not eat the bedrock", count_mat(MAT_BEDROCK) == bedrock);
    }
    shot(shot_dir, "01-condensed", width, height);

    /* ---- waves do not pass through rock ---- */
    {
        /* Find a bedrock cell and confirm the field never wrote inside it. */
        int found = 0, leaked = 0;
        for (int x = 3; x < VA_W - 3 && found < 400; x += 3)
            for (int y = 3; y < VA_H - 3 && found < 400; y += 3)
                for (int z = 3; z < VA_D - 3 && found < 400; z += 3)
                    if (ff_vault_mat(x, y, z) == MAT_BEDROCK) {
                        found++;
                        if (fabsf(ff_vault_field(x, y, z)) > 0.0001f) leaked++;
                    }
        check("the wave field never enters solid rock", found > 0 && leaked == 0);
    }

    /* ---- destructive interference removes matter ---- */
    {
        int before = count_mat(MAT_CONDENSED);
        ff_emitter *b = ff_vault_emitter(1);
        b->phase = FF_PI;                 /* flip one emitter out of step */
        ff_vault_touch_field();
        pump(20, 1.0f / 60.0f);
        int after = count_mat(MAT_CONDENSED);
        printf("  [info] condensate %d -> %d after a half-wave phase flip\n", before, after);
        check("phase inversion reshapes the lattice", after != before);
    }
    shot(shot_dir, "02-phase-flip", width, height);

    /* ---- the Bloom ---- */
    {
        int start = ff_vault_bloom_cells();
        check("the chamber seeds the Bloom", start > 0);
        pump(240, 1.0f / 60.0f);          /* several spread ticks */
        int grown = ff_vault_bloom_cells();
        printf("  [info] bloom cells: %d -> %d\n", start, grown);
        check("the Bloom spreads over solid ground", grown > start);

        /* Sublimation has to be able to burn the crust back off. */
        int bx = -1, by = -1, bz = -1;
        for (int x = 1; x < VA_W - 1 && bx < 0; x++)
            for (int y = 1; y < VA_H - 1 && bx < 0; y++)
                for (int z = 1; z < VA_D - 1 && bx < 0; z++)
                    if (ff_vault_bloom(x, y, z)) { bx = x; by = y; bz = z; }
        check("a bloomed cell can be located", bx >= 0);
        if (bx >= 0) {
            /* Park a lone emitter in the open cell beside the crust with its
             * phase a quarter turn back, so distance zero lands on the bottom
             * of the trough rather than on a node. */
            static const int NB[6][3] = { {1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1} };
            int ox = -1, oy = -1, oz = -1;
            for (int d = 0; d < 6; d++) {
                int nx = bx + NB[d][0], ny = by + NB[d][1], nz = bz + NB[d][2];
                if (!ff_vault_solid(nx, ny, nz)) { ox = nx; oy = ny; oz = nz; break; }
            }
            check("the bloomed cell has an open face", ox >= 0);
            if (ox >= 0) {
                for (int i = 0; i < 2; i++) ff_vault_emitter(i)->active = 0;
                ff_emitter *e = ff_vault_emitter(2);
                e->wavelength = 24.0f;
                e->amplitude = 1.0f;
                e->phase = FF_PI * 1.5f;
                e->active = 1;
                ff_vault_place_emitter(2, v3((float)ox + 0.5f, (float)oy + 0.5f, (float)oz + 0.5f));
                ff_vault_touch_field();
                pump(20, 1.0f / 60.0f);
                check("destructive interference burns the Bloom off", !ff_vault_bloom(bx, by, bz));
                for (int i = 0; i < 2; i++) ff_vault_emitter(i)->active = 1;
                ff_vault_touch_field();
                pump(6, 1.0f / 60.0f);
            }
        }
    }
    shot(shot_dir, "03-bloom", width, height);

    /* ---- flight ---- */
    {
        clear_input();
        vec3 before = ff_g.pilot.pos;
        ff_plat.key_down[FF_KEY_W] = 1;
        pump(90, 1.0f / 60.0f);
        clear_input();
        pump(10, 1.0f / 60.0f);
        check("the pilot flies", v3len(v3sub(ff_g.pilot.pos, before)) > 2.0f);
        check("the pilot never ends up inside rock",
              !ff_vault_solid((int)ff_g.pilot.pos.x, (int)ff_g.pilot.pos.y, (int)ff_g.pilot.pos.z));
        check("the pilot stays inside the vault",
              va_inside((int)ff_g.pilot.pos.x, (int)ff_g.pilot.pos.y, (int)ff_g.pilot.pos.z));
    }

    /* ---- objective plumbing ---- */
    {
        int linked = ff_vault_anchors_linked();
        check("anchor linkage stays within range",
              linked >= 0 && linked <= ff_vault_anchor_count());
        /* Condensate reaching the core is what the win condition is built on. */
        vec3 core = ff_vault_core_pos();
        int touching = 0;
        for (int dx = -4; dx <= 4; dx++)
            for (int dy = -4; dy <= 4; dy++)
                for (int dz = -4; dz <= 4; dz++)
                    if (ff_vault_mat((int)core.x + dx, (int)core.y + dy, (int)core.z + dz) == MAT_CONDENSED)
                        touching++;
        printf("  [info] condensate within 4 cells of the core: %d\n", touching);
        check("matter can be grown against the core", touching > 0);
    }

    /* ---- save and reload ---- */
    {
        ff_emitter *e = ff_vault_emitter(0);
        e->wavelength = 13.5f;
        ff_vault_touch_field();
        ff_game_save();

        uint32_t old_seed = ff_g.seed;
        ff_game_new(4242u, 0);
        int loaded = ff_game_load();
        check("the stored state loads back", loaded == 1);
        check("the vault seed round-trips", ff_g.seed == old_seed);
        ff_emitter *r = ff_vault_emitter(0);
        check("emitter tuning round-trips", r && fabsf(r->wavelength - 13.5f) < 0.01f);
        check("emitter placement round-trips", r && r->placed);
        pump(20, 1.0f / 60.0f);
        check("the reloaded vault re-condenses from its emitters",
              count_mat(MAT_CONDENSED) > 0);
    }

    ff_g.state = GS_TITLE;
    clear_input();
    pump(12, 1.0f / 60.0f);
    shot(shot_dir, "04-title", width, height);

    {
        ff_g.state = GS_PLAYING;
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

int main(int argc, char **argv) { return ff_main(argc, argv); }

#ifdef _WIN32
#include <windows.h>
int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmdline, int show)
{
    (void)inst; (void)prev; (void)cmdline; (void)show;
    return ff_main(__argc, __argv);
}
#endif
