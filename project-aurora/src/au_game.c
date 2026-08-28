/* au_game.c -- Room One: scene, Aurora, D.I.V.A., HUD.
 *
 * Room, timings and mechanic logic are a direct port of the validated
 * design proven in the (withdrawn) browser prototype -- same coordinates,
 * same state machine, same thresholds -- rewritten against this engine's
 * static-mesh renderer instead of Three.js.
 */
#include "au_game.h"
#include "ff_platform.h"

#include <stdio.h>
#include <string.h>

au_game au_g;
au_input au_in;

#define EYE_H 1.7f
#define REACH 8.0f

/* ---- room bounds, identical to the validated layout ------------------- */
#define ROOM_MIN_X -5.6f
#define ROOM_MAX_X  5.6f
#define ROOM_MIN_Z -7.6f
#define ROOM_MAX_Z  7.6f
#define DESK_MIN_X -5.3f
#define DESK_MAX_X -2.7f
#define DESK_MIN_Z -4.7f
#define DESK_MAX_Z -3.3f
#define DOORWAY_MIN_X -1.2f
#define DOORWAY_MAX_X  1.2f

static const vec3 AURORA_START    = { -3.0f, 0.0f, -3.0f };
static const vec3 AURORA_APPROACH = {  0.0f, 0.0f,  3.4f };
static const vec3 AURORA_HIDDEN   = { -4.0f, -2.5f, -4.0f };

vec3 au_aurora_hidden_pos(void) { return AURORA_HIDDEN; }

/* ---- meshes ------------------------------------------------------------ */
static au_mesh m_static, m_door, m_lock, m_terminal, m_diva,
               m_torso, m_head, m_visor, m_collar, m_arm,
               m_scanring, m_dots, m_pulse;

static const vec3 CONDUIT_PTS[5] = {
    { -4.0f, 3.15f, -4.0f }, { -2.6f, 3.15f, -5.4f }, { -0.8f, 3.15f, -7.0f },
    {  0.0f, 2.9f,  -7.6f }, {  0.0f, 2.6f,  -7.72f },
};
#define CONDUIT_N 5

static vec3 catmull(vec3 p0, vec3 p1, vec3 p2, vec3 p3, float t)
{
    float t2 = t * t, t3 = t2 * t;
    vec3 r;
    r.x = 0.5f*((2*p1.x)+(-p0.x+p2.x)*t+(2*p0.x-5*p1.x+4*p2.x-p3.x)*t2+(-p0.x+3*p1.x-3*p2.x+p3.x)*t3);
    r.y = 0.5f*((2*p1.y)+(-p0.y+p2.y)*t+(2*p0.y-5*p1.y+4*p2.y-p3.y)*t2+(-p0.y+3*p1.y-3*p2.y+p3.y)*t3);
    r.z = 0.5f*((2*p1.z)+(-p0.z+p2.z)*t+(2*p0.z-5*p1.z+4*p2.z-p3.z)*t2+(-p0.z+3*p1.z-3*p2.z+p3.z)*t3);
    return r;
}
static vec3 conduit_point(float t)
{
    t = ff_clampf(t, 0.0f, 1.0f);
    int segs = CONDUIT_N - 1;
    float scaled = t * (float)segs;
    int seg = (int)scaled;
    if (seg >= segs) seg = segs - 1;
    float local = scaled - (float)seg;
    vec3 p0 = (seg - 1 >= 0) ? CONDUIT_PTS[seg - 1] : CONDUIT_PTS[0];
    vec3 p1 = CONDUIT_PTS[seg];
    vec3 p2 = CONDUIT_PTS[seg + 1];
    vec3 p3 = (seg + 2 < CONDUIT_N) ? CONDUIT_PTS[seg + 2] : CONDUIT_PTS[CONDUIT_N - 1];
    return catmull(p0, p1, p2, p3, local);
}

static void build_scene(void)
{
    au_mesh_init(&m_static); au_mesh_init(&m_door); au_mesh_init(&m_lock);
    au_mesh_init(&m_terminal); au_mesh_init(&m_diva);
    au_mesh_init(&m_torso); au_mesh_init(&m_head); au_mesh_init(&m_visor);
    au_mesh_init(&m_collar); au_mesh_init(&m_arm);
    au_mesh_init(&m_scanring); au_mesh_init(&m_dots); au_mesh_init(&m_pulse);

    vec3 wallCol = v3(0.14f, 0.115f, 0.090f), floorCol = v3(0.11f, 0.09f, 0.07f);
    vec3 ceilCol = v3(0.07f, 0.055f, 0.04f), deskCol = v3(0.17f, 0.13f, 0.095f);
    vec3 posterCol = v3(0.926f, 0.882f, 0.804f), shelfCol = v3(0.20f, 0.15f, 0.11f);
    vec3 plushCol = v3(0.812f, 0.561f, 0.486f);

    au_add_box(&m_static, v3(0,-0.1f,0), v3(6,0.1f,8), floorCol, 0, 1);
    au_add_box(&m_static, v3(0,4.1f,0), v3(6,0.1f,8), ceilCol, 0, 1);
    au_add_box(&m_static, v3(-6,2,0), v3(0.2f,2,8), wallCol, 0, 1);
    au_add_box(&m_static, v3(6,2,0), v3(0.2f,2,8), wallCol, 0, 1);
    au_add_box(&m_static, v3(0,2,8), v3(6,2,0.2f), wallCol, 0, 1);
    au_add_box(&m_static, v3(-3.6f,2,-8), v3(2.4f,2,0.2f), wallCol, 0, 1);
    au_add_box(&m_static, v3(3.6f,2,-8), v3(2.4f,2,0.2f), wallCol, 0, 1);
    au_add_box(&m_static, v3(0,3.7f,-8), v3(1.2f,0.3f,0.2f), wallCol, 0, 1);

    au_add_box(&m_static, v3(-4,0.5f,-4), v3(1.3f,0.5f,0.7f), deskCol, 0, 1);
    au_add_box(&m_static, v3(-4,1.02f,-4), v3(1.3f,0.05f,0.7f), v3(0.20f,0.155f,0.11f), 0, 1);
    au_add_box(&m_static, v3(5.75f,2.2f,-2), v3(0.03f,0.8f,1.2f), posterCol, 0.05f, 1);
    au_add_box(&m_static, v3(5.7f,0.7f,3), v3(0.15f,0.6f,1.6f), shelfCol, 0, 1);
    for (int i = 0; i < 4; i++)
        au_add_sphere(&m_static, v3(5.55f, 1.42f, 1.9f + (float)i * 0.75f), 0.24f, 12, plushCol, 0, 1);
    au_mesh_upload(&m_static);

    au_add_box(&m_door, v3(0,0,0), v3(1.15f,1.8f,0.09f), v3(0.23f,0.23f,0.24f), 0.02f, 1);
    au_mesh_upload(&m_door);

    au_add_sphere(&m_lock, v3(0,0,0), 0.07f, 8, v3(0.694f,0.349f,0.298f), 1.0f, 1);
    au_mesh_upload(&m_lock);

    au_add_box(&m_terminal, v3(0,0,0), v3(0.25f,0.2f,0.04f), v3(0.094f,0.078f,0.059f), 0.35f, 1);
    au_mesh_upload(&m_terminal);

    au_add_box(&m_diva, v3(0,0,0), v3(0.17f,0.06f,0.1f), v3(0.078f,0.071f,0.063f), 0.55f, 1);
    au_mesh_upload(&m_diva);

    /* Aurora, part meshes in her own local space (feet at y=0). */
    vec3 auroraCol = v3(0.926f, 0.882f, 0.804f), accentCol = v3(0.812f, 0.561f, 0.486f);
    au_add_cylinder(&m_torso, v3(0,1.0f,0), 0.22f, 0.28f, 0.9f, 16, auroraCol, 0, 1);
    au_mesh_upload(&m_torso);
    au_add_sphere(&m_head, v3(0,1.62f,0), 0.19f, 16, auroraCol, 0, 1);
    au_mesh_upload(&m_head);
    au_add_sphere(&m_visor, v3(0,1.62f,0.08f), 0.10f, 14, accentCol, 0.15f, 1);
    au_mesh_upload(&m_visor);
    au_add_ring(&m_collar, v3(0,1.42f,0), 0.21f, 0.03f, 20, accentCol, 0.15f, 1);
    au_mesh_upload(&m_collar);
    au_add_cylinder(&m_arm, v3(0,0.95f,0), 0.05f, 0.05f, 0.7f, 10, auroraCol, 0, 1);
    au_mesh_upload(&m_arm);
    au_add_ring(&m_scanring, v3(0,0,0), 0.26f, 0.014f, 24, v3(0.373f,0.788f,0.761f), 1.0f, 0.9f);
    au_mesh_upload(&m_scanring);

    for (int i = 0; i <= 22; i++)
        au_add_sphere(&m_dots, conduit_point((float)i / 22.0f), 0.03f, 6, v3(0.184f,0.478f,0.463f), 1.0f, 0.85f);
    au_mesh_upload(&m_dots);
    au_add_sphere(&m_pulse, v3(0,0,0), 0.075f, 10, v3(0.373f,0.788f,0.761f), 1.0f, 1);
    au_mesh_upload(&m_pulse);
}

/* ===================================================================== *
 *  Collision, movement, camera
 * ===================================================================== */

int au_collides(float x, float z)
{
    if (x < ROOM_MIN_X || x > ROOM_MAX_X) return 1;
    if (z > ROOM_MAX_Z) return 1;
    if (z < ROOM_MIN_Z) {
        if (au_g.doorLocked) return 1;
        if (x < DOORWAY_MIN_X || x > DOORWAY_MAX_X) return 1;
        return 0;
    }
    if (x > DESK_MIN_X && x < DESK_MAX_X && z > DESK_MIN_Z && z < DESK_MAX_Z) return 1;
    return 0;
}

static void update_movement(float dt)
{
    vec3 look = ff_dir_from_angles(au_g.player.yaw, 0.0f);
    vec3 fwd = v3norm(v3(look.x, 0, look.z));
    vec3 right = v3norm(v3cross(fwd, v3(0, 1, 0)));

    float mx = 0, mz = 0;
    if (au_in.forward) { mx += fwd.x; mz += fwd.z; }
    if (au_in.back)    { mx -= fwd.x; mz -= fwd.z; }
    if (au_in.right)   { mx += right.x; mz += right.z; }
    if (au_in.left)    { mx -= right.x; mz -= right.z; }
    float len = sqrtf(mx * mx + mz * mz);
    if (len > 0.0001f) { mx /= len; mz /= len; }

    float speed = 3.4f;
    float nx = au_g.player.pos.x + mx * speed * dt;
    float nz = au_g.player.pos.z + mz * speed * dt;
    if (!au_collides(nx, au_g.player.pos.z)) au_g.player.pos.x = nx;
    if (!au_collides(au_g.player.pos.x, nz)) au_g.player.pos.z = nz;
}

/* ===================================================================== *
 *  Aurora
 * ===================================================================== */

static float smoothstepf(float t) { t = ff_clampf(t, 0.0f, 1.0f); return t * t * (3.0f - 2.0f * t); }
static void set_aurora_state(int s) { au_g.auroraState = s; au_g.auroraStateT = 0.0f; }

static void say_orpheon(const char *text, float secs)
{
    snprintf(au_g.subOrpheon, sizeof au_g.subOrpheon, "%s", text);
    au_g.subOrpheonT = secs;
}
static void say_cue(const char *text, float secs)
{
    snprintf(au_g.subCue, sizeof au_g.subCue, "%s", text);
    au_g.subCueT = secs;
}

static void face_player(void)
{
    vec3 toP = v3sub(au_g.player.pos, au_g.auroraPos);
    au_g.auroraYaw = atan2f(toP.z, toP.x);
}

static void update_aurora(float dt)
{
    au_g.auroraStateT += dt;
    int s = au_g.auroraState;

    if (s == AU_IDLE) {
        au_g.auroraPos.y = sinf(au_g.t * 1.6f) * 0.015f;
        if (au_g.auroraStateT > 1.1f) set_aurora_state(AU_APPROACH);
    } else if (s == AU_APPROACH) {
        float t = smoothstepf(au_g.auroraStateT / 2.6f);
        au_g.auroraPos = v3add(AURORA_START, v3mul(v3sub(AURORA_APPROACH, AURORA_START), t));
        face_player();
        if (t >= 1.0f) set_aurora_state(AU_SCAN);
    } else if (s == AU_SCAN) {
        face_player();
        au_g.scanRingT = ff_clampf(au_g.auroraStateT / 1.3f, 0.0f, 1.0f);
        if (au_g.auroraStateT > 1.3f) {
            say_orpheon("Oh -- hello! I don't think we've met.", 3.2f);
            set_aurora_state(AU_SPEAK1);
        }
    } else if (s == AU_SPEAK1) {
        face_player();
        if (au_g.auroraStateT > 2.6f) {
            say_orpheon("Welcome to Orpheon. Let our song guide you here.", 3.6f);
            set_aurora_state(AU_SPEAK2);
        }
    } else if (s == AU_SPEAK2) {
        face_player();
        if (au_g.auroraStateT > 2.8f) {
            say_orpheon("Go on and look around -- I'll just be a moment.", 3.2f);
            set_aurora_state(AU_AWAIT_LOOK);
        }
    } else if (s == AU_AWAIT_LOOK) {
        au_g.auroraPos.y = sinf(au_g.t * 1.6f) * 0.015f;
        vec3 eye = v3(au_g.player.pos.x, EYE_H, au_g.player.pos.z);
        vec3 fwd3d = ff_dir_from_angles(au_g.player.yaw, au_g.player.pitch);
        vec3 toAurora = v3norm(v3sub(au_g.auroraPos, eye));
        float facing = v3dot(fwd3d, toAurora);
        au_g.lookAwayT = (facing < 0.35f) ? au_g.lookAwayT + dt : 0.0f;
        if (au_g.lookAwayT > 0.45f || au_g.auroraStateT > 20.0f) {
            au_g.auroraPos = AURORA_HIDDEN;
            say_cue("[ a mechanical shuffling, somewhere close ]", 2.6f);
            set_aurora_state(AU_GONE);
        }
    }
}

/* ===================================================================== *
 *  D.I.V.A.
 * ===================================================================== */

static int near_desk(void)
{
    float dx = au_g.player.pos.x - (-4.0f), dz = au_g.player.pos.z - (-3.9f);
    return sqrtf(dx * dx + dz * dz) < 2.0f;
}

static int looking_at_pulse(void)
{
    if (!(au_g.tracing && au_g.hasDiva)) return 0;
    vec3 eye = v3(au_g.player.pos.x, EYE_H, au_g.player.pos.z);
    vec3 dir = ff_dir_from_angles(au_g.player.yaw, au_g.player.pitch);
    vec3 pulsePos = conduit_point(au_g.pulseT);
    vec3 toP = v3sub(pulsePos, eye);
    float along = v3dot(toP, dir);
    if (along <= 0.0f) return 0;
    vec3 closest = v3add(eye, v3mul(dir, along));
    float perp = v3len(v3sub(pulsePos, closest));
    return perp < 0.35f && v3len(toP) < REACH;
}

static void commit_redirect(void)
{
    au_g.redirected = 1;
    au_g.redirectArmed = 0;
    au_g.doorLocked = 0;
    au_g.doorAnimT = 0.0f;
    say_cue("Something re-addressed that.", 2.4f);
}

static void try_interact(void)
{
    if (au_g.state != GS_PLAYING) return;
    if (!au_g.hasDiva && near_desk()) {
        au_g.hasDiva = 1;
        say_cue("D.I.V.A. acquired. Hold right-click to trace.", 2.6f);
        return;
    }
    if (au_g.hasDiva && !au_g.redirected && au_g.tracing && looking_at_pulse()) {
        if (!au_g.redirectArmed) au_g.redirectArmed = 1;
        else commit_redirect();
    }
}

static void update_conduit(float dt)
{
    if (!au_g.tracing && au_g.redirectArmed) au_g.redirectArmed = 0;
    if (!(au_g.tracing && au_g.hasDiva)) return;
    if (!au_g.redirectArmed) au_g.pulseT = fmodf(au_g.pulseT + dt * 0.18f, 1.0f);
}

static void update_door(float dt)
{
    if (au_g.doorAnimT < 0.0f) return;
    au_g.doorAnimT = ff_minf(1.0f, au_g.doorAnimT + dt / 1.1f);
}

static void update_ending(void)
{
    if (au_g.state == GS_ENDED) return;
    if (au_g.player.pos.z < -8.8f &&
        au_g.player.pos.x > DOORWAY_MIN_X - 0.4f && au_g.player.pos.x < DOORWAY_MAX_X + 0.4f)
        au_g.state = GS_ENDED;
}

static void update_prompt(void)
{
    au_g.prompt[0] = 0;
    if (au_g.state != GS_PLAYING) return;
    if (!au_g.hasDiva && near_desk()) snprintf(au_g.prompt, sizeof au_g.prompt, "E - TAKE D.I.V.A.");
    else if (au_g.hasDiva && !au_g.redirected && au_g.tracing && looking_at_pulse() && !au_g.redirectArmed)
        snprintf(au_g.prompt, sizeof au_g.prompt, "E - TAP SIGNAL");
}

/* ===================================================================== *
 *  Lifecycle
 * ===================================================================== */

void au_game_init(void)
{
    static int scene_built = 0;
    if (!scene_built) { build_scene(); scene_built = 1; }

    memset(&au_g, 0, sizeof au_g);
    au_g.state = GS_TITLE;
    au_g.player.pos = v3(0, EYE_H, 6.5f);
    au_g.player.yaw = -FF_PI * 0.5f;   /* face -Z: into the lobby, toward the desk and door */
    au_g.player.pitch = 0.0f;
    au_g.auroraPos = AURORA_START;
    au_g.doorLocked = 1;
    au_g.doorAnimT = -1.0f;
    au_g.pulseT = 0.0f;
}

void au_game_update(float dt)
{
    if (dt > 0.1f) dt = 0.1f;
    au_g.t += dt;
    if (au_g.subOrpheonT > 0.0f) au_g.subOrpheonT -= dt;
    if (au_g.subCueT > 0.0f) au_g.subCueT -= dt;

    switch (au_g.state) {
    case GS_TITLE:
        if (ff_plat.key_pressed[FF_KEY_ENTER] || ff_plat.key_pressed[FF_KEY_SPACE]) {
            au_g.state = GS_PLAYING;
            ff_platform_capture_mouse(1);
        }
        break;
    case GS_PLAYING:
        if (ff_plat.key_pressed[FF_KEY_ESCAPE]) {
            au_g.state = GS_PAUSED;
            ff_platform_capture_mouse(0);
            break;
        }
        au_g.player.yaw   -= au_in.mouse_dx * 0.0022f;
        au_g.player.pitch -= au_in.mouse_dy * 0.0022f;
        au_g.player.pitch = ff_clampf(au_g.player.pitch, -1.35f, 1.35f);

        au_g.tracing = au_in.trace_held && au_g.hasDiva;
        if (au_in.interact_pressed) try_interact();

        update_movement(dt);
        update_aurora(dt);
        update_conduit(dt);
        update_door(dt);
        update_ending();
        if (au_g.state == GS_ENDED) ff_platform_capture_mouse(0);
        break;
    case GS_PAUSED:
        if (ff_plat.key_pressed[FF_KEY_ESCAPE]) { au_g.state = GS_PLAYING; ff_platform_capture_mouse(1); }
        break;
    case GS_ENDED:
        if (ff_plat.key_pressed[FF_KEY_ENTER]) au_game_init();
        break;
    }
    update_prompt();
}

/* ===================================================================== *
 *  Render
 * ===================================================================== */

static mat4 model_at(vec3 pos, float yaw)
{
    return mat4_mul(mat4_translate(pos), mat4_rotate_y(yaw));
}

static void draw_scene(const au_camera *cam)
{
    au_render_mesh(&m_static, mat4_identity(), 1, 1, 1, 1, cam);

    float doorX = (au_g.doorAnimT >= 0.0f) ? -2.4f * smoothstepf(au_g.doorAnimT) : 0.0f;
    au_render_mesh(&m_door, mat4_translate(v3(doorX, 1.9f, -7.85f)), 1, 1, 1, 1, cam);

    float lockTint = au_g.redirected ? 1.0f : 0.0f;   /* blended via colour swap below */
    (void)lockTint;
    if (au_g.redirected)
        au_render_mesh(&m_lock, mat4_translate(v3(0, 2.6f, -7.74f)), 0.72f, 1.30f, 0.80f, 1, cam);
    else
        au_render_mesh(&m_lock, mat4_translate(v3(0, 2.6f, -7.74f)), 1, 1, 1, 1, cam);

    au_render_mesh(&m_terminal, mat4_translate(v3(-4, 1.28f, -3.75f)), 1, 1, 1,
                   au_g.redirected ? 1.6f : 1.0f, cam);

    if (!au_g.hasDiva)
        au_render_mesh(&m_diva, mat4_translate(v3(-4.55f, 1.14f, -3.55f)), 1, 1, 1, 1, cam);

    mat4 auroraM = model_at(au_g.auroraPos, au_g.auroraYaw);
    au_render_mesh(&m_torso, auroraM, 1, 1, 1, 1, cam);
    au_render_mesh(&m_head, auroraM, 1, 1, 1, 1, cam);
    au_render_mesh(&m_visor, auroraM, 1, 1, 1, 1, cam);
    au_render_mesh(&m_collar, auroraM, 1, 1, 1, 1, cam);
    au_render_mesh(&m_arm, mat4_mul(auroraM, mat4_translate(v3(0.28f, 0, 0))), 1, 1, 1, 1, cam);
    au_render_mesh(&m_arm, mat4_mul(auroraM, mat4_translate(v3(-0.28f, 0, 0))), 1, 1, 1, 1, cam);

    float ringAlpha = sinf(au_g.scanRingT * FF_PI) * 0.9f;
    if (ringAlpha > 0.01f) {
        vec3 ringPos = v3(au_g.auroraPos.x, au_g.auroraPos.y + 0.5f + au_g.scanRingT * 1.0f, au_g.auroraPos.z);
        au_render_mesh(&m_scanring, mat4_translate(ringPos), 1, 1, 1, ringAlpha / 0.9f, cam);
    }

    if (au_g.tracing && au_g.hasDiva) {
        float dr = au_g.redirected ? 0.55f : 1.0f, dg = au_g.redirected ? 1.35f : 1.0f, db = au_g.redirected ? 0.90f : 1.0f;
        au_render_mesh(&m_dots, mat4_identity(), dr, dg, db, 1, cam);
        au_render_mesh(&m_pulse, mat4_translate(conduit_point(au_g.pulseT)), dr, dg, db, 1, cam);
    }
}

static void draw_centered(float cx, float y, float s, float r, float g, float b, float a, const char *t)
{
    au_ui_text(cx - au_ui_text_width(s, t) * 0.5f, y, s, r, g, b, a, t);
}

static void draw_hud(int w, int h, float sc)
{
    float cx = w * 0.5f;
    float cs = 3 * sc;
    au_ui_rect(cx - cs, h * 0.5f - cs, cs * 2, cs * 2, 0.926f, 0.882f, 0.804f, 0.65f);

    if (au_g.tracing && au_g.hasDiva)
        au_ui_rect(0, 0, (float)w, (float)h, 0.086f, 0.157f, 0.157f, 0.16f);

    if (au_g.subOrpheonT > 0.0f) {
        float pw = ff_minf(560.0f, w * 0.8f);
        au_ui_rect(cx - pw * 0.5f - 10*sc, h*0.80f - 8*sc, pw + 20*sc, 40*sc, 0.926f, 0.882f, 0.804f, 0.95f);
        draw_centered(cx, h*0.80f, sc*1.05f, 0.14f, 0.11f, 0.078f, 1.0f, au_g.subOrpheon);
    }
    if (au_g.subCueT > 0.0f)
        draw_centered(cx, h*0.89f, sc*0.85f, 0.72f, 0.66f, 0.56f, ff_minf(1.0f, au_g.subCueT), au_g.subCue);
    if (au_g.prompt[0])
        draw_centered(cx, h*0.71f, sc*0.85f, 0.93f, 0.90f, 0.82f, 0.95f, au_g.prompt);

    if (au_g.hasDiva) {
        const char *state = au_g.redirected ? "D.I.V.A. -- SOLVED" : "D.I.V.A. -- READY";
        float tw = au_ui_text_width(sc*0.85f, state);
        au_ui_rect(w - tw - 34*sc, h - 34*sc, tw + 20*sc, 22*sc, 0.043f, 0.035f, 0.027f, 0.72f);
        au_ui_text(w - tw - 24*sc, h - 28*sc, sc*0.85f, 0.373f, 0.788f, 0.761f, 1.0f, state);
    }

    if (au_g.redirectArmed) {
        float pw = ff_minf(360.0f, w*0.8f), px = cx - pw*0.5f, py = 16*sc;
        au_ui_rect(px, py, pw, 66*sc, 0.059f, 0.086f, 0.086f, 0.88f);
        au_ui_text(px+10*sc, py+8*sc, sc*0.8f, 0.373f,0.788f,0.761f, 1, "CONDUIT TAP");
        au_ui_text(px+10*sc, py+24*sc, sc*0.78f, 0.72f,0.66f,0.56f, 1, "ORIGIN:   LOCK -> INNER DOOR");
        au_ui_text(px+10*sc, py+38*sc, sc*0.78f, 0.373f,0.788f,0.761f, 1, "REDIRECT: LOCK -> DESK TERMINAL");
        au_ui_text(px+10*sc, py+52*sc, sc*0.78f, 0.812f,0.561f,0.486f, 1, "[E] COMMIT REROUTE");
    }
}

void au_game_render(int width, int height)
{
    float sc = ff_clampf((float)height / 720.0f, 0.72f, 2.4f);

    au_camera cam;
    cam.eye = v3(au_g.player.pos.x, EYE_H, au_g.player.pos.z);
    cam.yaw = au_g.player.yaw;
    cam.pitch = au_g.player.pitch;
    cam.fov = 70.0f;
    cam.aspect = (height > 0) ? (float)width / (float)height : 1.7778f;
    vec3 fwd = ff_dir_from_angles(cam.yaw, cam.pitch);
    cam.view = mat4_look(cam.eye, fwd, v3(0, 1, 0));
    cam.proj = mat4_perspective(cam.fov, cam.aspect, 0.05f, 60.0f);
    cam.viewproj = mat4_mul(cam.proj, cam.view);

    au_render_frame_begin(&cam);
    draw_scene(&cam);

    au_ui_begin(width, height);
    switch (au_g.state) {
    case GS_TITLE:
        au_ui_rect(0, 0, (float)width, (float)height, 0.024f, 0.020f, 0.016f, 0.60f);
        draw_centered(width*0.5f, height*0.30f, sc*3.4f, 0.926f,0.882f,0.804f, 1, "PROJECT AURORA");
        draw_centered(width*0.5f, height*0.30f+38*sc, sc*1.1f, 0.812f,0.561f,0.486f, 1, "THE LAST CHILD - ROOM ONE");
        draw_centered(width*0.5f, height*0.30f+58*sc, sc*0.9f, 0.72f,0.66f,0.56f, 1, "A vertical slice. One room. One mechanic.");
        draw_centered(width*0.5f, height*0.52f, sc*1.1f, 0.926f,0.882f,0.804f, 1, "PRESS ENTER TO STEP INSIDE");
        draw_centered(width*0.5f, height*0.86f, sc*0.85f, 0.60f,0.68f,0.64f, 0.9f,
                      "WASD MOVE   MOUSE LOOK   E INTERACT   HOLD RMB TRACE");
        break;
    case GS_PLAYING:
        draw_hud(width, height, sc);
        break;
    case GS_PAUSED:
        au_ui_rect(0, 0, (float)width, (float)height, 0.02f,0.02f,0.02f, 0.62f);
        draw_centered(width*0.5f, height*0.44f, sc*2.2f, 0.926f,0.882f,0.804f, 1, "PAUSED");
        draw_centered(width*0.5f, height*0.53f, sc*1.0f, 0.72f,0.66f,0.56f, 1, "ESC TO RESUME");
        break;
    case GS_ENDED:
        au_ui_rect(0, 0, (float)width, (float)height, 0.024f,0.020f,0.016f, 0.90f);
        draw_centered(width*0.5f, height*0.40f, sc*2.6f, 0.926f,0.882f,0.804f, 1, "PROJECT AURORA");
        draw_centered(width*0.5f, height*0.40f+34*sc, sc*1.1f, 0.812f,0.561f,0.486f, 1, "THE LAST CHILD");
        draw_centered(width*0.5f, height*0.40f+56*sc, sc*0.9f, 0.72f,0.66f,0.56f, 1, "End of prototype -- Room One");
        draw_centered(width*0.5f, height*0.60f, sc*0.9f, 0.60f,0.68f,0.64f, 0.9f, "ENTER TO RESTART THE ROOM");
        break;
    }
    au_ui_end();
}
