/* ff_game.c -- ANTINODE.
 *
 * You fly. You place emitters. The waves decide what is solid. The Bloom
 * decides how long you have.
 */
#include "ff_game.h"
#include "ff_platform.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

ff_game ff_g;

#define PILOT_RADIUS  0.34f
#define REACH         26.0f
#define SURVEY_PERIOD 0.25f

void ff_game_toast(const char *msg)
{
    snprintf(ff_g.toast, sizeof ff_g.toast, "%s", msg);
    ff_g.toast_timer = 3.4f;
}

/* ===================================================================== *
 *  Flight
 * ===================================================================== */

static int blocked_at(vec3 p)
{
    int x0 = (int)floorf(p.x - PILOT_RADIUS), x1 = (int)floorf(p.x + PILOT_RADIUS);
    int y0 = (int)floorf(p.y - PILOT_RADIUS), y1 = (int)floorf(p.y + PILOT_RADIUS);
    int z0 = (int)floorf(p.z - PILOT_RADIUS), z1 = (int)floorf(p.z + PILOT_RADIUS);
    for (int x = x0; x <= x1; x++)
        for (int y = y0; y <= y1; y++)
            for (int z = z0; z <= z1; z++)
                if (ff_vault_solid(x, y, z)) return 1;
    return 0;
}

/* No gravity in here. Thrust, drag, and a wall is just a wall. */
static void fly(ff_pilot *p, float dt)
{
    if (ff_plat.mouse_captured) {
        const float sens = 0.0022f;
        p->yaw   += ff_plat.mouse_dx * sens;
        p->pitch -= ff_plat.mouse_dy * sens;
        p->pitch = ff_clampf(p->pitch, -1.553f, 1.553f);
    }

    vec3 look = ff_dir_from_angles(p->yaw, p->pitch);
    vec3 right = v3norm(v3cross(look, v3(0, 1, 0)));

    float fwd_in = 0.0f, side_in = 0.0f;
    if (ff_plat.key_down[FF_KEY_W]) fwd_in += 1.0f;
    if (ff_plat.key_down[FF_KEY_S]) fwd_in -= 1.0f;
    if (ff_plat.key_down[FF_KEY_D]) side_in += 1.0f;
    if (ff_plat.key_down[FF_KEY_A]) side_in -= 1.0f;

    vec3 wish = v3add(v3mul(look, fwd_in), v3mul(right, side_in));
    if (ff_plat.key_down[FF_KEY_SPACE]) wish.y += 1.0f;
    if (ff_plat.key_down[FF_KEY_LCTRL]) wish.y -= 1.0f;

    float speed = ff_plat.key_down[FF_KEY_LSHIFT] ? 22.0f : 10.0f;
    if (v3len(wish) > 0.001f) {
        vec3 target = v3mul(v3norm(wish), speed);
        p->vel = v3add(p->vel, v3mul(v3sub(target, p->vel), ff_minf(1.0f, dt * 6.0f)));
    }
    p->vel = v3mul(p->vel, 1.0f - ff_minf(0.92f, 2.4f * dt));

    /* Sub-step and resolve per axis so grazing a pillar slides instead of
     * stopping dead. */
    vec3 delta = v3mul(p->vel, dt);
    float longest = ff_maxf(fabsf(delta.x), ff_maxf(fabsf(delta.y), fabsf(delta.z)));
    int steps = ff_mini(24, (int)(longest / 0.22f) + 1);
    vec3 step = v3mul(delta, 1.0f / (float)steps);
    for (int s = 0; s < steps; s++) {
        vec3 q = p->pos;
        q.x += step.x; if (blocked_at(q)) { q.x = p->pos.x; p->vel.x = 0.0f; step.x = 0.0f; }
        q.y += step.y; if (blocked_at(q)) { q.y = p->pos.y; p->vel.y = 0.0f; step.y = 0.0f; }
        q.z += step.z; if (blocked_at(q)) { q.z = p->pos.z; p->vel.z = 0.0f; step.z = 0.0f; }
        p->pos = q;
    }
}

/* ===================================================================== *
 *  Emitter handling
 * ===================================================================== */

static vec3 aim_point(void)
{
    ff_pilot *p = &ff_g.pilot;
    vec3 eye = p->pos;
    vec3 dir = ff_dir_from_angles(p->yaw, p->pitch);
    int hx, hy, hz, px, py, pz;
    if (ff_vault_raycast(eye, dir, REACH, &hx, &hy, &hz, &px, &py, &pz))
        return v3((float)px + 0.5f, (float)py + 0.5f, (float)pz + 0.5f);
    return v3add(eye, v3mul(dir, 14.0f));
}

static void tune_emitters(float dt)
{
    ff_emitter *e = ff_vault_emitter(ff_g.pilot.selected);
    if (!e) return;
    int changed = 0;
    char msg[96];

    for (int i = 0; i < ff_vault_emitter_count(); i++)
        if (ff_plat.key_pressed[FF_KEY_1 + i]) ff_g.pilot.selected = i;

    if (ff_plat.key_pressed[FF_KEY_F]) {
        vec3 at = aim_point();
        ff_vault_place_emitter(ff_g.pilot.selected, at);
        snprintf(msg, sizeof msg, "EMITTER %d ANCHORED", ff_g.pilot.selected + 1);
        ff_game_toast(msg);
        return;
    }
    if (!e->placed) return;

    if (ff_plat.key_down[FF_KEY_Q]) { e->wavelength = ff_maxf(2.0f,  e->wavelength - dt * 7.0f); changed = 1; }
    if (ff_plat.key_down[FF_KEY_E]) { e->wavelength = ff_minf(28.0f, e->wavelength + dt * 7.0f); changed = 1; }
    if (ff_plat.key_down[FF_KEY_Z]) { e->amplitude  = ff_maxf(0.0f,  e->amplitude  - dt * 0.7f); changed = 1; }
    if (ff_plat.key_down[FF_KEY_X]) { e->amplitude  = ff_minf(1.0f,  e->amplitude  + dt * 0.7f); changed = 1; }
    if (ff_plat.key_down[FF_KEY_C]) { e->phase -= dt * 3.4f; changed = 1; }
    if (ff_plat.key_down[FF_KEY_V]) { e->phase += dt * 3.4f; changed = 1; }
    if (ff_plat.key_pressed[FF_KEY_R]) {
        e->active = !e->active;
        changed = 1;
        snprintf(msg, sizeof msg, "EMITTER %d %s", ff_g.pilot.selected + 1, e->active ? "ON" : "OFF");
        ff_game_toast(msg);
    }
    if (ff_plat.scroll != 0.0f) {
        e->wavelength = ff_clampf(e->wavelength + ff_plat.scroll * 0.6f, 2.0f, 28.0f);
        changed = 1;
    }

    while (e->phase < 0.0f)     e->phase += FF_TAU;
    while (e->phase >= FF_TAU)  e->phase -= FF_TAU;

    /* The power budget is the real constraint: reach or precision, not both. */
    float used = ff_vault_power_used(), budget = ff_vault_power_budget();
    if (used > budget) {
        e->amplitude -= (used - budget);
        e->amplitude = ff_maxf(0.0f, e->amplitude);
        ff_game_toast("POWER BUDGET EXCEEDED");
    }
    if (changed) ff_vault_touch_field();
}

/* ===================================================================== *
 *  Chamber lifecycle
 * ===================================================================== */

static void place_pilot_in_open_space(void)
{
    vec3 core = ff_vault_core_pos();
    for (float r = 6.0f; r < 40.0f; r += 2.0f) {
        for (int a = 0; a < 24; a++) {
            float ang = (float)a / 24.0f * FF_TAU;
            vec3 p = v3(core.x + cosf(ang) * r, core.y + 5.0f, core.z + sinf(ang) * r);
            if (!blocked_at(p)) { ff_g.pilot.pos = p; return; }
        }
    }
    ff_g.pilot.pos = v3(core.x, core.y + 6.0f, core.z);
}

void ff_game_new(uint32_t seed, int chamber)
{
    memset(&ff_g.pilot, 0, sizeof ff_g.pilot);
    ff_g.seed = seed;
    ff_g.chamber = chamber;
    ff_g.linked = 0;
    ff_g.hold_timer = 0.0f;
    ff_g.hold_required = 14.0f + 4.0f * (float)chamber;
    ff_g.bloom_at_core = 0;
    ff_g.survey_timer = 0.0f;
    ff_g.show_wave = 1;
    ff_g.toast_timer = 0.0f;

    ff_vault_init(seed, chamber);
    place_pilot_in_open_space();
    ff_g.pilot.yaw = 0.6f;
    ff_g.pilot.pitch = -0.15f;
    ff_g.pilot.selected = 0;
}

typedef struct {
    uint32_t seed;
    int32_t  chamber;
    float    px, py, pz, yaw, pitch;
    int32_t  placed[VA_MAX_EMITTERS];
    int32_t  active[VA_MAX_EMITTERS];
    float    ex[VA_MAX_EMITTERS], ey[VA_MAX_EMITTERS], ez[VA_MAX_EMITTERS];
    float    wl[VA_MAX_EMITTERS], amp[VA_MAX_EMITTERS], ph[VA_MAX_EMITTERS];
} ff_save;

const char *ff_game_save_path(void)
{
    static char path[1024];
    snprintf(path, sizeof path, "%s%cchamber.antinode", ff_platform_save_dir(),
#ifdef _WIN32
             '\\'
#else
             '/'
#endif
             );
    return path;
}

void ff_game_save(void)
{
    ff_save s;
    memset(&s, 0, sizeof s);
    s.seed = ff_g.seed;
    s.chamber = ff_g.chamber;
    s.px = ff_g.pilot.pos.x; s.py = ff_g.pilot.pos.y; s.pz = ff_g.pilot.pos.z;
    s.yaw = ff_g.pilot.yaw; s.pitch = ff_g.pilot.pitch;
    for (int i = 0; i < VA_MAX_EMITTERS; i++) {
        ff_emitter *e = ff_vault_emitter(i);
        if (!e) continue;
        s.placed[i] = e->placed; s.active[i] = e->active;
        s.ex[i] = e->pos.x; s.ey[i] = e->pos.y; s.ez[i] = e->pos.z;
        s.wl[i] = e->wavelength; s.amp[i] = e->amplitude; s.ph[i] = e->phase;
    }
    FILE *f = fopen(ff_game_save_path(), "wb");
    if (!f) { ff_game_toast("COULD NOT WRITE SAVE"); return; }
    uint32_t magic = 0x314F4E41u;   /* "ANO1" */
    fwrite(&magic, 4, 1, f);
    fwrite(&s, sizeof s, 1, f);
    fclose(f);
    ff_game_toast("STATE STORED");
}

/* The chamber is rebuilt from its seed and the emitter settings replayed --
 * the condensate is a function of the field, so it never has to be stored. */
int ff_game_load(void)
{
    FILE *f = fopen(ff_game_save_path(), "rb");
    if (!f) return 0;
    uint32_t magic = 0;
    ff_save s;
    if (fread(&magic, 4, 1, f) != 1 || magic != 0x314F4E41u) { fclose(f); return 0; }
    if (fread(&s, sizeof s, 1, f) != 1) { fclose(f); return 0; }
    fclose(f);

    if (s.chamber < 0 || s.chamber >= FF_CHAMBER_COUNT) return 0;
    ff_game_new(s.seed, s.chamber);
    ff_g.pilot.pos = v3(s.px, s.py, s.pz);
    ff_g.pilot.yaw = s.yaw;
    ff_g.pilot.pitch = s.pitch;
    for (int i = 0; i < VA_MAX_EMITTERS; i++) {
        ff_emitter *e = ff_vault_emitter(i);
        if (!e) continue;
        e->active = s.active[i] ? 1 : 0;
        e->wavelength = ff_clampf(s.wl[i], 2.0f, 28.0f);
        e->amplitude = ff_clampf(s.amp[i], 0.0f, 1.0f);
        e->phase = s.ph[i];
        if (s.placed[i]) ff_vault_place_emitter(i, v3(s.ex[i], s.ey[i], s.ez[i]));
    }
    return 1;
}

/* ===================================================================== *
 *  Update
 * ===================================================================== */

static void survey(void)
{
    ff_g.linked = ff_vault_anchors_linked();
    ff_g.bloom_cells = ff_vault_bloom_cells();
    ff_g.bloom_at_core = ff_vault_bloom_at_core();
}

static void update_playing(float dt)
{
    if (ff_plat.key_pressed[FF_KEY_ESCAPE]) {
        ff_g.state = GS_PAUSED;
        ff_g.menu_index = 0;
        ff_platform_capture_mouse(0);
        return;
    }
    if (ff_plat.key_pressed[FF_KEY_TAB]) ff_g.show_wave = !ff_g.show_wave;
    if (ff_plat.key_pressed[FF_KEY_F3])  ff_g.show_debug = !ff_g.show_debug;
    if (ff_plat.key_pressed[FF_KEY_F5])  ff_game_save();

    fly(&ff_g.pilot, dt);
    tune_emitters(dt);
    ff_vault_step(dt);

    ff_g.survey_timer += dt;
    if (ff_g.survey_timer >= SURVEY_PERIOD) {
        ff_g.survey_timer = 0.0f;
        survey();
    }

    /* Win: every anchor tied to the core by clean condensate, held steady. */
    int target = ff_vault_anchor_count();
    if (target > 0 && ff_g.linked >= target) {
        float before = ff_g.hold_timer;
        ff_g.hold_timer += dt;
        if (before < 0.05f) ff_game_toast("LATTICE CLOSED - HOLD IT");
        if (ff_g.hold_timer >= ff_g.hold_required) {
            ff_g.state = (ff_g.chamber + 1 >= FF_CHAMBER_COUNT) ? GS_COMPLETE : GS_CLEARED;
            ff_g.menu_index = 0;
            ff_platform_capture_mouse(0);
        }
    } else {
        ff_g.hold_timer = ff_maxf(0.0f, ff_g.hold_timer - dt * 1.6f);
    }

    if (ff_g.bloom_at_core) {
        ff_g.state = GS_LOST;
        ff_g.menu_index = 0;
        ff_platform_capture_mouse(0);
    }
}

void ff_game_update(float dt)
{
    if (dt > 0.1f) dt = 0.1f;
    ff_g.time += dt;
    if (ff_g.toast_timer > 0.0f) ff_g.toast_timer -= dt;

    switch (ff_g.state) {
    case GS_TITLE:
        if (ff_plat.key_pressed[FF_KEY_UP])   ff_g.menu_index = (ff_g.menu_index + 2) % 3;
        if (ff_plat.key_pressed[FF_KEY_DOWN]) ff_g.menu_index = (ff_g.menu_index + 1) % 3;
        if (ff_plat.key_pressed[FF_KEY_ENTER] || ff_plat.key_pressed[FF_KEY_SPACE]) {
            if (ff_g.menu_index == 2) { ff_plat.should_close = 1; break; }
            if (ff_g.menu_index == 1)
                ff_game_new((uint32_t)(ff_platform_time() * 1000.0) ^ 0x51EDu, 0);
            ff_g.state = GS_PLAYING;
            ff_platform_capture_mouse(1);
        }
        /* The chamber keeps simulating so the menu has something behind it. */
        ff_vault_step(dt);
        break;

    case GS_PLAYING:
        update_playing(dt);
        break;

    case GS_PAUSED:
        if (ff_plat.key_pressed[FF_KEY_UP])   ff_g.menu_index = (ff_g.menu_index + 2) % 3;
        if (ff_plat.key_pressed[FF_KEY_DOWN]) ff_g.menu_index = (ff_g.menu_index + 1) % 3;
        if (ff_plat.key_pressed[FF_KEY_ESCAPE]) { ff_g.state = GS_PLAYING; ff_platform_capture_mouse(1); }
        if (ff_plat.key_pressed[FF_KEY_ENTER] || ff_plat.key_pressed[FF_KEY_SPACE]) {
            if (ff_g.menu_index == 0)      { ff_g.state = GS_PLAYING; ff_platform_capture_mouse(1); }
            else if (ff_g.menu_index == 1) { ff_game_save(); }
            else                           { ff_game_save(); ff_plat.should_close = 1; }
        }
        break;

    case GS_CLEARED:
        if (ff_plat.key_pressed[FF_KEY_ENTER] || ff_plat.key_pressed[FF_KEY_SPACE]) {
            ff_game_new(ff_g.seed, ff_g.chamber + 1);
            ff_g.state = GS_PLAYING;
            ff_platform_capture_mouse(1);
        }
        break;

    case GS_LOST:
        if (ff_plat.key_pressed[FF_KEY_ENTER] || ff_plat.key_pressed[FF_KEY_SPACE]) {
            ff_game_new(ff_g.seed + 1u, ff_g.chamber);
            ff_g.state = GS_PLAYING;
            ff_platform_capture_mouse(1);
        }
        break;

    case GS_COMPLETE:
        if (ff_plat.key_pressed[FF_KEY_ENTER] || ff_plat.key_pressed[FF_KEY_SPACE]) {
            ff_g.state = GS_TITLE;
            ff_g.menu_index = 1;
        }
        break;
    }
}

/* ===================================================================== *
 *  Presentation
 * ===================================================================== */

static void remesh_dirty(int budget)
{
    ff_g.chunks_meshed = 0;
    for (int i = 0; i < VA_CHUNK_COUNT && budget > 0; i++) {
        ff_vchunk *c = ff_vault_chunk(i);
        if (!c || !c->dirty) continue;
        ff_mesh_chunk(c);
        ff_g.chunks_meshed++;
        budget--;
    }
}

/* A sparse sample of the live field, drawn as motes: cyan where the waves
 * are reinforcing toward matter, magenta where they are cancelling it. */
static void draw_wave_overlay(vec3 eye)
{
    const int   reach = 21;
    const int   step  = 3;
    const float thresh = 0.16f;
    int ex = (int)eye.x, ey = (int)eye.y, ez = (int)eye.z;

    for (int x = ex - reach; x <= ex + reach; x += step)
        for (int y = ey - reach; y <= ey + reach; y += step)
            for (int z = ez - reach; z <= ez + reach; z += step) {
                if (!va_inside(x, y, z)) continue;
                if (ff_vault_solid(x, y, z)) continue;
                float f = ff_vault_field(x, y, z);
                float m = fabsf(f);
                if (m < thresh) continue;
                float a = ff_clampf((m - thresh) * 1.5f, 0.0f, 0.55f);
                vec3 p = v3((float)x + 0.5f, (float)y + 0.5f, (float)z + 0.5f);
                /* Motes right on the lens read as a smear, not as data. */
                if (v3len(v3sub(p, eye)) < 3.0f) continue;
                if (f > 0.0f) ff_render_particle(p, 0.10f, 0.35f, 0.85f, 1.00f, a);
                else          ff_render_particle(p, 0.10f, 1.00f, 0.30f, 0.70f, a * 0.85f);
            }
}

static void draw_emitters(const ff_camera *cam)
{
    for (int i = 0; i < ff_vault_emitter_count(); i++) {
        ff_emitter *e = ff_vault_emitter(i);
        if (!e || !e->placed) continue;
        int sel = (i == ff_g.pilot.selected);
        float on = e->active ? 1.0f : 0.22f;
        /* Pulse the brightness, not the hue -- swinging one channel turned the
         * emitter violet at the bottom of the cycle. */
        float pulse = 0.78f + 0.22f * sinf(ff_g.time * 3.0f + (float)i);
        float body = on * pulse;

        /* An emitter you are sitting on top of just fills the screen with one
         * flat face, so hide it the way a first-person game hides the body. */
        int too_close = v3len(v3sub(e->pos, ff_g.pilot.pos)) < 1.3f
                        && ff_g.state != GS_TITLE;
        if (!too_close) {
            ff_render_box(e->pos, v3(0.34f, 0.34f, 0.34f), ff_g.time * 0.8f + (float)i,
                          0.55f * body, 0.92f * body, 1.00f * body,
                          e->active ? 1.0f : 0.25f, cam);
            if (sel)
                ff_render_box(e->pos, v3(0.62f, 0.05f, 0.62f), -ff_g.time * 1.3f,
                              1.0f, 0.85f, 0.35f, 1.0f, cam);
        }

        /* A ring of motes marks the first crest, so the wavelength is legible
         * in the world and not only on the panel. */
        if (e->active && e->amplitude > 0.01f) {
            int n = 22;
            for (int k = 0; k < n; k++) {
                float a = (float)k / (float)n * FF_TAU + ff_g.time * 0.35f;
                float r = e->wavelength;
                vec3 p = v3(e->pos.x + cosf(a) * r, e->pos.y + sinf(a * 2.0f) * 0.8f,
                            e->pos.z + sinf(a) * r);
                if (!va_inside((int)p.x, (int)p.y, (int)p.z)) continue;
                if (ff_vault_solid((int)p.x, (int)p.y, (int)p.z)) continue;
                ff_render_particle(p, 0.09f, 0.45f, 0.85f, 1.0f, 0.30f * e->amplitude);
            }
        }
    }
}

static void draw_beacons(void)
{
    vec3 core = ff_vault_core_pos();
    for (int i = 0; i < 14; i++) {
        float t = (float)i;
        float a = 0.42f - t * 0.026f;
        ff_render_particle(v3(core.x, core.y + 2.0f + t * 1.5f, core.z), 0.22f,
                           0.70f, 0.92f, 1.0f, ff_maxf(0.0f, a));
    }
    for (int k = 0; k < ff_vault_anchor_count(); k++) {
        vec3 ap = ff_vault_anchor_pos(k);
        int linked_hint = (k < ff_g.linked);
        for (int i = 0; i < 10; i++) {
            float t = (float)i;
            float a = 0.36f - t * 0.032f;
            ff_render_particle(v3(ap.x, ap.y + 2.0f + t * 1.4f, ap.z), 0.20f,
                               linked_hint ? 0.45f : 1.00f,
                               linked_hint ? 1.00f : 0.72f,
                               linked_hint ? 0.60f : 0.25f, ff_maxf(0.0f, a));
        }
    }
}

/* ---- HUD ------------------------------------------------------------- */

static void bar(float x, float y, float w, float h, float frac, float r, float g, float b)
{
    ff_ui_rect(x - 2, y - 2, w + 4, h + 4, 0.02f, 0.04f, 0.06f, 0.75f);
    ff_ui_rect(x, y, w, h, 0.09f, 0.12f, 0.15f, 0.85f);
    ff_ui_rect(x, y, w * ff_clampf(frac, 0.0f, 1.0f), h, r, g, b, 0.95f);
}

static void draw_centered(float cx, float y, float s, float r, float g, float b, float a, const char *t)
{
    ff_ui_text(cx - ff_ui_text_width(s, t) * 0.5f, y, s, r, g, b, a, t);
}

static void draw_hud(int w, int h, float sc)
{
    char line[160];
    float cx = w * 0.5f;

    /* crosshair */
    float cs = 8 * sc, ct = ff_maxf(1.0f, 1.5f * sc);
    ff_ui_rect(cx - cs, h * 0.5f - ct * 0.5f, cs * 2, ct, 0.75f, 0.95f, 1.0f, 0.75f);
    ff_ui_rect(cx - ct * 0.5f, h * 0.5f - cs, ct, cs * 2, 0.75f, 0.95f, 1.0f, 0.75f);

    /* objective */
    int anchors = ff_vault_anchor_count();
    snprintf(line, sizeof line, "CHAMBER %d/%d", ff_g.chamber + 1, FF_CHAMBER_COUNT);
    draw_centered(cx, 18 * sc, sc * 1.3f, 0.55f, 0.72f, 0.80f, 0.95f, line);
    snprintf(line, sizeof line, "ANCHORS LINKED %d/%d", ff_g.linked, anchors);
    draw_centered(cx, 34 * sc, sc * 1.8f,
                  ff_g.linked >= anchors ? 0.50f : 1.00f,
                  ff_g.linked >= anchors ? 1.00f : 0.88f,
                  ff_g.linked >= anchors ? 0.70f : 0.55f, 1.0f, line);

    if (ff_g.hold_timer > 0.01f) {
        float bw = 300 * sc;
        bar(cx - bw * 0.5f, 58 * sc, bw, 12 * sc, ff_g.hold_timer / ff_g.hold_required,
            0.45f, 0.95f, 0.70f);
        snprintf(line, sizeof line, "STABILISING  %ds",
                 (int)(ff_g.hold_required - ff_g.hold_timer + 0.99f));
        draw_centered(cx, 60 * sc, sc * 1.0f, 0.03f, 0.09f, 0.07f, 1.0f, line);
    }

    /* bloom pressure, top right */
    snprintf(line, sizeof line, "BLOOM %d", ff_g.bloom_cells);
    ff_ui_text(w - ff_ui_text_width(sc * 1.4f, line) - 16 * sc, 18 * sc, sc * 1.4f,
               1.0f, 0.42f, 0.55f, 1.0f, line);

    /* emitter panel */
    int count = ff_vault_emitter_count();
    float sw = 132 * sc, gap = 6 * sc;
    float total = count * sw + (count - 1) * gap;
    float px = cx - total * 0.5f, py = h - 84 * sc;
    for (int i = 0; i < count; i++) {
        ff_emitter *e = ff_vault_emitter(i);
        float x = px + i * (sw + gap);
        int sel = (i == ff_g.pilot.selected);
        ff_ui_rect(x, py, sw, 62 * sc, 0.03f, 0.06f, 0.08f, sel ? 0.90f : 0.62f);
        if (sel) {
            ff_ui_rect(x, py - 2 * sc, sw, 2 * sc, 0.55f, 0.92f, 1.0f, 1.0f);
            ff_ui_rect(x, py + 62 * sc, sw, 2 * sc, 0.55f, 0.92f, 1.0f, 1.0f);
        }
        int on = e && e->placed && e->active;
        snprintf(line, sizeof line, "%d %s", i + 1,
                 !e || !e->placed ? "UNSET" : (e->active ? "ON" : "OFF"));
        ff_ui_text(x + 7 * sc, py + 6 * sc, sc * 1.1f,
                   on ? 0.60f : 0.55f, on ? 0.98f : 0.58f, on ? 1.00f : 0.62f, 1.0f, line);
        if (e && e->placed) {
            snprintf(line, sizeof line, "WAVE %.1f", e->wavelength);
            ff_ui_text(x + 7 * sc, py + 22 * sc, sc * 0.95f, 0.72f, 0.84f, 0.92f, 1.0f, line);
            bar(x + 7 * sc, py + 36 * sc, sw - 14 * sc, 5 * sc, e->amplitude, 0.40f, 0.80f, 1.0f);
            /* phase drawn as a travelling tick so it reads at a glance */
            float t = e->phase / FF_TAU;
            ff_ui_rect(x + 7 * sc + (sw - 14 * sc) * t, py + 46 * sc, 3 * sc, 8 * sc,
                       1.0f, 0.82f, 0.35f, 0.95f);
        }
    }

    /* power budget */
    {
        float used = ff_vault_power_used(), budget = ff_vault_power_budget();
        float bw = 200 * sc;
        bar(cx - bw * 0.5f, h - 110 * sc, bw, 8 * sc, used / budget,
            used > budget * 0.92f ? 1.0f : 0.55f, 0.85f, 0.45f);
        snprintf(line, sizeof line, "POWER %.2f / %.2f", used, budget);
        draw_centered(cx, h - 109 * sc, sc * 0.9f, 0.03f, 0.07f, 0.05f, 1.0f, line);
    }

    if (ff_g.toast_timer > 0.0f) {
        float a = ff_clampf(ff_g.toast_timer / 0.8f, 0.0f, 1.0f);
        draw_centered(cx, h - 132 * sc, sc * 1.4f, 1.0f, 0.94f, 0.72f, a, ff_g.toast);
    }

    if (ff_g.time < 40.0f) {
        const char *hint = "F ANCHOR EMITTER   Q/E WAVELENGTH   Z/X POWER   C/V PHASE   R TOGGLE   TAB FIELD";
        draw_centered(cx, h - 8 * sc, sc * 0.88f, 0.55f, 0.72f, 0.80f, 0.70f, hint);
    }

    if (ff_g.show_debug) {
        float y = 12 * sc;
        snprintf(line, sizeof line, "ANTINODE ALPHA 0.1  %d FPS", (int)(ff_g.fps + 0.5f));
        ff_ui_text(12 * sc, y, sc, 0.55f, 1.0f, 0.80f, 0.9f, line); y += 11 * sc;
        snprintf(line, sizeof line, "POS %d %d %d", (int)ff_g.pilot.pos.x, (int)ff_g.pilot.pos.y, (int)ff_g.pilot.pos.z);
        ff_ui_text(12 * sc, y, sc, 0.55f, 1.0f, 0.80f, 0.9f, line); y += 11 * sc;
        snprintf(line, sizeof line, "SEED %u  REMESH %d", (unsigned)ff_g.seed, ff_g.chunks_meshed);
        ff_ui_text(12 * sc, y, sc, 0.55f, 1.0f, 0.80f, 0.9f, line);
    }
}

static void draw_menu(int w, int h, float sc, const char *title, const char *sub,
                      const char **items, int count, int selected, const char *footer)
{
    float cx = w * 0.5f;
    ff_ui_rect(0, 0, (float)w, (float)h, 0.01f, 0.02f, 0.04f, 0.74f);
    draw_centered(cx, h * 0.22f, sc * 3.0f, 0.62f, 0.92f, 1.0f, 1.0f, title);
    if (sub) draw_centered(cx, h * 0.22f + 34 * sc, sc * 1.15f, 0.50f, 0.68f, 0.78f, 1.0f, sub);
    for (int i = 0; i < count; i++) {
        float y = h * 0.46f + i * 30 * sc;
        int sel = (i == selected);
        if (sel) {
            float wd = ff_ui_text_width(sc * 1.8f, items[i]);
            ff_ui_rect(cx - wd * 0.5f - 12 * sc, y - 6 * sc, wd + 24 * sc, 24 * sc,
                       0.08f, 0.32f, 0.40f, 0.6f);
        }
        draw_centered(cx, y, sc * 1.8f, sel ? 1.0f : 0.62f, sel ? 1.0f : 0.76f,
                      sel ? 0.92f : 0.82f, 1.0f, items[i]);
    }
    if (footer) draw_centered(cx, h - 34 * sc, sc, 0.52f, 0.68f, 0.76f, 0.85f, footer);
}

void ff_game_render(int width, int height)
{
    float sc = ff_clampf((float)height / 720.0f, 0.72f, 2.6f);
    remesh_dirty(ff_g.state == GS_PLAYING ? 6 : 14);

    ff_camera cam;
    if (ff_g.state == GS_TITLE) {
        vec3 core = ff_vault_core_pos();
        float t = ff_g.time * 0.10f;
        cam.eye = v3(core.x + cosf(t) * 30.0f, core.y + 12.0f, core.z + sinf(t) * 30.0f);
        cam.yaw = t + FF_PI;
        cam.pitch = -0.28f;
    } else {
        cam.eye = ff_g.pilot.pos;
        cam.yaw = ff_g.pilot.yaw;
        cam.pitch = ff_g.pilot.pitch;
    }
    cam.fov = 74.0f;
    cam.aspect = (height > 0) ? (float)width / (float)height : 1.7778f;
    vec3 fwd = ff_dir_from_angles(cam.yaw, cam.pitch);
    cam.view = mat4_look(cam.eye, fwd, v3(0, 1, 0));
    cam.proj = mat4_perspective(cam.fov, cam.aspect, 0.06f, 400.0f);
    cam.viewproj = mat4_mul(cam.proj, cam.view);

    ff_env env;
    env.time = ff_g.time;
    env.alert = ff_clampf((float)ff_g.bloom_cells / 2600.0f, 0.0f, 1.0f);

    ff_render_frame_begin(&cam, &env);
    ff_render_void(&cam, &env);
    ff_render_chunks(&cam, &env);
    draw_emitters(&cam);

    if (ff_g.state == GS_PLAYING) {
        int hx, hy, hz;
        if (ff_vault_raycast(cam.eye, fwd, REACH, &hx, &hy, &hz, NULL, NULL, NULL)) {
            ff_render_selection_setup(&cam);
            ff_render_selection(hx, hy, hz, 0.0f);
        }
    }

    draw_beacons();
    if (ff_g.show_wave && ff_g.state != GS_TITLE) draw_wave_overlay(cam.eye);
    ff_render_particles_flush(&cam);

    ff_ui_begin(width, height);
    switch (ff_g.state) {
    case GS_TITLE: {
        static const char *items[3] = { "RESUME", "NEW VAULT", "LEAVE" };
        float cx = width * 0.5f;
        ff_ui_rect(0, 0, (float)width, (float)height, 0.01f, 0.02f, 0.04f, 0.52f);
        draw_centered(cx, height * 0.16f, sc * 5.0f, 0.62f, 0.94f, 1.0f, 1.0f, "ANTINODE");
        draw_centered(cx, height * 0.16f + 46 * sc, sc * 1.25f, 0.46f, 0.70f, 0.80f, 1.0f,
                      "WHERE THE WAVES AGREE, THE WORLD BECOMES SOLID");
        for (int i = 0; i < 3; i++) {
            float y = height * 0.47f + i * 32 * sc;
            int sel = (i == ff_g.menu_index);
            if (sel) {
                float wd = ff_ui_text_width(sc * 1.9f, items[i]);
                ff_ui_rect(cx - wd * 0.5f - 14 * sc, y - 7 * sc, wd + 28 * sc, 26 * sc,
                           0.08f, 0.34f, 0.42f, 0.6f);
            }
            draw_centered(cx, y, sc * 1.9f, sel ? 1.0f : 0.62f, sel ? 1.0f : 0.76f,
                          sel ? 0.92f : 0.82f, 1.0f, items[i]);
        }
        draw_centered(cx, height - 40 * sc, sc, 0.50f, 0.66f, 0.74f, 0.85f,
                      "ARROWS TO CHOOSE, ENTER TO DESCEND");
        break;
    }
    case GS_PLAYING:
        draw_hud(width, height, sc);
        break;
    case GS_PAUSED: {
        static const char *items[3] = { "RESUME", "STORE STATE", "STORE AND LEAVE" };
        char footer[96];
        snprintf(footer, sizeof footer, "SEED %u   CHAMBER %d", (unsigned)ff_g.seed, ff_g.chamber + 1);
        draw_menu(width, height, sc, "HELD", NULL, items, 3, ff_g.menu_index, footer);
        break;
    }
    case GS_CLEARED: {
        static const char *items[1] = { "DESCEND" };
        draw_menu(width, height, sc, "CHAMBER STABLE",
                  "THE LATTICE HELD. THE VAULT GOES DEEPER.",
                  items, 1, 0, "ENTER TO CONTINUE");
        break;
    }
    case GS_LOST: {
        static const char *items[1] = { "TRY AGAIN" };
        ff_ui_rect(0, 0, (float)width, (float)height, 0.18f, 0.01f, 0.05f, 0.55f);
        draw_menu(width, height, sc, "THE CORE IS TAKEN",
                  "THE BLOOM REACHED IT. CUT THE ROADS SOONER.",
                  items, 1, 0, "ENTER TO RESET THE CHAMBER");
        break;
    }
    case GS_COMPLETE: {
        static const char *items[1] = { "BACK TO THE SURFACE" };
        draw_menu(width, height, sc, "VAULT SILENCED",
                  "EVERY CHAMBER HOLDS. NOTHING IS SPREADING.",
                  items, 1, 0, "ALPHA 0.1 - THANK YOU FOR PLAYING");
        break;
    }
    }
    ff_ui_end();
}
