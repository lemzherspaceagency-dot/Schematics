#include "ff_vault.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <float.h>

/*                          name          solid light tile */
const ff_material ff_materials[MAT_COUNT] = {
    { "Void",       0,  0, 0 },
    { "Bedrock",    1,  0, 1 },
    { "Condensate", 1,  5, 2 },
    { "Anchor",     1, 10, 4 },
    { "Core",       1, 14, 5 },
};
#define TILE_BLOOM 3

/* ===================================================================== *
 *  State
 * ===================================================================== */

static uint8_t *g_mat;
static uint8_t *g_bloom;
static uint8_t *g_light;
static float   *g_field;

static ff_emitter g_emitters[VA_MAX_EMITTERS];
static int        g_emitter_count;

static ff_vchunk  g_chunks[VA_CHUNK_COUNT];
static void     (*g_mesh_release)(ff_vchunk *);

static uint32_t g_seed;
static int      g_chamber;
static int      g_field_dirty;
static float    g_bloom_timer;
static float    g_bloom_interval = 1.15f;
static float    g_bloom_spread_condensed = 0.34f;
static float    g_bloom_spread_bedrock   = 0.05f;
static ff_rng   g_rng;

static vec3 g_anchor_pos[VA_MAX_ANCHORS];
static int  g_anchor_count;
static vec3 g_core_pos;

/* Condensation threshold, as a fraction of the normalised field. */
#define FIELD_THRESHOLD 0.34f

void ff_vault_set_mesh_release(void (*fn)(ff_vchunk *)) { g_mesh_release = fn; }

int      ff_vault_chamber(void) { return g_chamber; }
uint32_t ff_vault_seed(void)    { return g_seed; }
int      ff_vault_emitter_count(void) { return g_emitter_count; }
ff_emitter *ff_vault_emitter(int i) { return (i >= 0 && i < g_emitter_count) ? &g_emitters[i] : NULL; }
ff_vchunk  *ff_vault_chunk(int i)   { return (i >= 0 && i < VA_CHUNK_COUNT) ? &g_chunks[i] : NULL; }
int   ff_vault_anchor_count(void)   { return g_anchor_count; }
vec3  ff_vault_anchor_pos(int i)    { return g_anchor_pos[i]; }
vec3  ff_vault_core_pos(void)       { return g_core_pos; }

uint8_t ff_vault_mat(int x, int y, int z)
{
    if (!va_inside(x, y, z)) return MAT_BEDROCK;
    return g_mat[va_index(x, y, z)];
}
int ff_vault_bloom(int x, int y, int z)
{
    if (!va_inside(x, y, z)) return 0;
    return g_bloom[va_index(x, y, z)];
}
int ff_vault_solid(int x, int y, int z)
{
    if (!va_inside(x, y, z)) return 1;
    return ff_materials[g_mat[va_index(x, y, z)]].solid;
}
uint8_t ff_vault_light(int x, int y, int z)
{
    if (!va_inside(x, y, z)) return 0;
    return g_light[va_index(x, y, z)];
}
float ff_vault_field(int x, int y, int z)
{
    if (!va_inside(x, y, z)) return 0.0f;
    return g_field[va_index(x, y, z)];
}

/* ===================================================================== *
 *  Sine lookup -- the field is evaluated over half a million cells per
 *  update, so the transcendental has to be a table read.
 * ===================================================================== */

#define SIN_BITS  12
#define SIN_SIZE  (1 << SIN_BITS)
static float g_sin[SIN_SIZE];

static void sin_table_init(void)
{
    for (int i = 0; i < SIN_SIZE; i++)
        g_sin[i] = sinf((float)i / (float)SIN_SIZE * FF_TAU);
}
static inline float sin_lut(float rad)
{
    int i = (int)(rad * ((float)SIN_SIZE / FF_TAU));
    return g_sin[i & (SIN_SIZE - 1)];
}

/* ===================================================================== *
 *  Chunk bookkeeping
 * ===================================================================== */

static inline int chunk_of(int x, int y, int z)
{
    return ((x / VA_CHUNK) * VA_CHUNKS_Y + (y / VA_CHUNK)) * VA_CHUNKS_Z + (z / VA_CHUNK);
}

void ff_vault_mark_all_dirty(void)
{
    for (int i = 0; i < VA_CHUNK_COUNT; i++) g_chunks[i].dirty = 1;
}

static void mark_cell_dirty(int x, int y, int z)
{
    g_chunks[chunk_of(x, y, z)].dirty = 1;
    /* A face on a chunk edge is shared with its neighbour. */
    if (x % VA_CHUNK == 0 && x > 0)            g_chunks[chunk_of(x - 1, y, z)].dirty = 1;
    if (x % VA_CHUNK == VA_CHUNK - 1 && x < VA_W - 1) g_chunks[chunk_of(x + 1, y, z)].dirty = 1;
    if (y % VA_CHUNK == 0 && y > 0)            g_chunks[chunk_of(x, y - 1, z)].dirty = 1;
    if (y % VA_CHUNK == VA_CHUNK - 1 && y < VA_H - 1) g_chunks[chunk_of(x, y + 1, z)].dirty = 1;
    if (z % VA_CHUNK == 0 && z > 0)            g_chunks[chunk_of(x, y, z - 1)].dirty = 1;
    if (z % VA_CHUNK == VA_CHUNK - 1 && z < VA_D - 1) g_chunks[chunk_of(x, y, z + 1)].dirty = 1;
}

/* ===================================================================== *
 *  Chamber generation
 * ===================================================================== */

static void carve_blob(float cx, float cy, float cz, float rx, float ry, float rz, float wobble)
{
    int x0 = ff_maxi(0, (int)(cx - rx - 4)), x1 = ff_mini(VA_W - 1, (int)(cx + rx + 4));
    int y0 = ff_maxi(0, (int)(cy - ry - 4)), y1 = ff_mini(VA_H - 1, (int)(cy + ry + 4));
    int z0 = ff_maxi(0, (int)(cz - rz - 4)), z1 = ff_mini(VA_D - 1, (int)(cz + rz + 4));

    for (int x = x0; x <= x1; x++)
        for (int y = y0; y <= y1; y++)
            for (int z = z0; z <= z1; z++) {
                float dx = ((float)x - cx) / rx;
                float dy = ((float)y - cy) / ry;
                float dz = ((float)z - cz) / rz;
                float d = sqrtf(dx * dx + dy * dy + dz * dz);
                float n = ff_fbm3(x * 0.055f, y * 0.055f, z * 0.055f, 3, 2.0f, 0.5f) * wobble;
                if (d + n < 1.0f) g_mat[va_index(x, y, z)] = MAT_EMPTY;
            }
}

/* First open cell standing on bedrock in this column, or -1. */
static int floor_at(int x, int z)
{
    for (int y = 2; y < VA_H - 2; y++) {
        if (g_mat[va_index(x, y, z)] == MAT_EMPTY &&
            g_mat[va_index(x, y - 1, z)] == MAT_BEDROCK)
            return y;
    }
    return -1;
}

static void generate_chamber(void)
{
    memset(g_mat, MAT_BEDROCK, VA_CELLS);
    memset(g_bloom, 0, VA_CELLS);

    const float cx = VA_W * 0.5f, cz = VA_D * 0.5f, cy = VA_H * 0.5f;

    /* One broad cavern, then lobes hung off it so the space has rooms
     * rather than being a single balloon. */
    carve_blob(cx, cy, cz, 33.0f, 16.0f, 33.0f, 0.34f);
    for (int i = 0; i < 5; i++) {
        float a = ff_rng_f(&g_rng) * FF_TAU;
        float r = ff_rng_range(&g_rng, 20.0f, 34.0f);
        carve_blob(cx + cosf(a) * r, ff_rng_range(&g_rng, 12.0f, 34.0f), cz + sinf(a) * r,
                   ff_rng_range(&g_rng, 11.0f, 19.0f), ff_rng_range(&g_rng, 7.0f, 12.0f),
                   ff_rng_range(&g_rng, 11.0f, 19.0f), 0.42f);
    }

    /* Pillars: columns of rock left standing through the cavern. They are the
     * only thing that blocks a wave, so they are what makes placement a
     * puzzle rather than an arithmetic exercise. */
    for (int x = 0; x < VA_W; x++)
        for (int z = 0; z < VA_D; z++) {
            float n = ff_fbm2(x * 0.075f + 40.0f, z * 0.075f - 22.0f, 3, 2.0f, 0.5f);
            if (n > 0.40f) {
                for (int y = 0; y < VA_H; y++) g_mat[va_index(x, y, z)] = MAT_BEDROCK;
            }
        }

    /* Seal the shell so nothing can leave the volume. */
    for (int x = 0; x < VA_W; x++)
        for (int y = 0; y < VA_H; y++)
            for (int z = 0; z < VA_D; z++)
                if (x < 2 || z < 2 || y < 2 || x >= VA_W - 2 || z >= VA_D - 2 || y >= VA_H - 2)
                    g_mat[va_index(x, y, z)] = MAT_BEDROCK;

    /* ---- core ---- */
    int core_y = floor_at((int)cx, (int)cz);
    if (core_y < 0) core_y = (int)cy;
    g_core_pos = v3(cx + 0.5f, (float)core_y + 1.5f, cz + 0.5f);
    for (int x = -1; x <= 1; x++)
        for (int y = 0; y <= 2; y++)
            for (int z = -1; z <= 1; z++) {
                int px = (int)cx + x, py = core_y + y, pz = (int)cz + z;
                if (va_inside(px, py, pz)) g_mat[va_index(px, py, pz)] = MAT_CORE;
            }

    /* ---- anchors, spread around the chamber ---- */
    g_anchor_count = 0;
    int want = 3;
    for (int attempt = 0; attempt < 240 && g_anchor_count < want; attempt++) {
        float a = (float)g_anchor_count / (float)want * FF_TAU + ff_rng_range(&g_rng, -0.5f, 0.5f);
        float r = ff_rng_range(&g_rng, 22.0f, 36.0f);
        int ax = (int)(cx + cosf(a) * r), az = (int)(cz + sinf(a) * r);
        if (!va_inside(ax, 4, az)) continue;
        int ay = floor_at(ax, az);
        if (ay < 0) continue;
        /* keep them apart */
        int too_close = 0;
        for (int i = 0; i < g_anchor_count; i++)
            if (v3len(v3sub(g_anchor_pos[i], v3((float)ax, (float)ay, (float)az))) < 16.0f) too_close = 1;
        if (too_close) continue;

        for (int y = 0; y < 4 && ay + y < VA_H - 2; y++)
            g_mat[va_index(ax, ay + y, az)] = MAT_ANCHOR;
        g_anchor_pos[g_anchor_count++] = v3((float)ax + 0.5f, (float)ay + 1.5f, (float)az + 0.5f);
    }

    /* ---- bloom seeds on the far walls ---- */
    int seeds = 2 + g_chamber;
    for (int attempt = 0, made = 0; attempt < 900 && made < seeds; attempt++) {
        int x = 3 + (int)(ff_rng_u32(&g_rng) % (VA_W - 6));
        int y = 3 + (int)(ff_rng_u32(&g_rng) % (VA_H - 6));
        int z = 3 + (int)(ff_rng_u32(&g_rng) % (VA_D - 6));
        if (g_mat[va_index(x, y, z)] != MAT_BEDROCK) continue;
        /* must be an exposed wall, and a long way from the core */
        int exposed = (g_mat[va_index(x + 1, y, z)] == MAT_EMPTY || g_mat[va_index(x - 1, y, z)] == MAT_EMPTY ||
                       g_mat[va_index(x, y + 1, z)] == MAT_EMPTY || g_mat[va_index(x, y - 1, z)] == MAT_EMPTY ||
                       g_mat[va_index(x, y, z + 1)] == MAT_EMPTY || g_mat[va_index(x, y, z - 1)] == MAT_EMPTY);
        if (!exposed) continue;
        if (v3len(v3sub(v3((float)x, (float)y, (float)z), g_core_pos)) < 30.0f) continue;
        g_bloom[va_index(x, y, z)] = 1;
        made++;
    }
}

/* ===================================================================== *
 *  Geodesic wave distance
 *
 *  A wave leaves an emitter and fills the open volume, bending around
 *  pillars instead of passing through them. Distance is relaxed over a
 *  26-neighbourhood with chamfer weights, which keeps the wavefronts round
 *  enough that the interference pattern reads as spherical.
 * ===================================================================== */

static int32_t *g_queue;
static int      g_queue_cap;

static int ensure_queue(void)
{
    if (g_queue) return 1;
    g_queue_cap = VA_CELLS * 2;      /* headroom for re-pushed cells */
    g_queue = (int32_t *)malloc((size_t)g_queue_cap * sizeof(int32_t));
    return g_queue != NULL;
}

static void emitter_alloc(ff_emitter *e)
{
    if (!e->dist) e->dist = (float *)malloc((size_t)VA_CELLS * sizeof(float));
}

static void compute_distance(ff_emitter *e)
{
    emitter_alloc(e);
    if (!e->dist || !ensure_queue()) return;

    for (int i = 0; i < VA_CELLS; i++) e->dist[i] = FLT_MAX;

    int sx = ff_clampi((int)e->pos.x, 1, VA_W - 2);
    int sy = ff_clampi((int)e->pos.y, 1, VA_H - 2);
    int sz = ff_clampi((int)e->pos.z, 1, VA_D - 2);
    if (g_mat[va_index(sx, sy, sz)] == MAT_BEDROCK) { e->dist_dirty = 0; return; }  /* buried: silent */

    /* Straight FIFO relaxation. Chamfer weights over the 26-neighbourhood
     * keep the wavefront round; bedrock is simply never entered, so the wave
     * flows around pillars the way it should. */
    int head = 0, tail = 0;
    e->dist[va_index(sx, sy, sz)] = 0.0f;
    g_queue[tail++] = va_index(sx, sy, sz);

    while (head < tail) {
        int idx = g_queue[head++];
        int z = idx % VA_D;
        int y = (idx / VA_D) % VA_H;
        int x = idx / (VA_D * VA_H);
        float d = e->dist[idx];
        if (d >= e->radius) continue;

        for (int dx = -1; dx <= 1; dx++)
            for (int dy = -1; dy <= 1; dy++)
                for (int dz = -1; dz <= 1; dz++) {
                    if (!dx && !dy && !dz) continue;
                    int nx = x + dx, ny = y + dy, nz = z + dz;
                    if (!va_inside(nx, ny, nz)) continue;
                    int ni = va_index(nx, ny, nz);
                    if (g_mat[ni] == MAT_BEDROCK) continue;    /* rock stops it */
                    int steps = (dx ? 1 : 0) + (dy ? 1 : 0) + (dz ? 1 : 0);
                    float w = (steps == 1) ? 1.0f : (steps == 2 ? 1.41421356f : 1.73205081f);
                    float nd = d + w;
                    if (nd < e->dist[ni] - 0.001f) {
                        e->dist[ni] = nd;
                        if (tail < g_queue_cap) g_queue[tail++] = ni;
                    }
                }
        /* Compact the queue if it is running out of room. */
        if (tail >= g_queue_cap && head > 0) {
            memmove(g_queue, g_queue + head, (size_t)(tail - head) * sizeof(int32_t));
            tail -= head;
            head = 0;
        }
    }
    e->dist_dirty = 0;
}

/* ===================================================================== *
 *  Field, materials and light
 * ===================================================================== */

float ff_vault_power_budget(void) { return 1.0f + 0.5f * (float)g_emitter_count; }

float ff_vault_power_used(void)
{
    float sum = 0.0f;
    for (int i = 0; i < g_emitter_count; i++)
        if (g_emitters[i].placed && g_emitters[i].active) sum += g_emitters[i].amplitude;
    return sum;
}

void ff_vault_touch_field(void) { g_field_dirty = 1; }

void ff_vault_place_emitter(int i, vec3 pos)
{
    ff_emitter *e = ff_vault_emitter(i);
    if (!e) return;
    e->pos = pos;
    e->placed = 1;
    e->dist_dirty = 1;
    g_field_dirty = 1;
}

static void evaluate_field(void)
{
    float wsum = 0.0f;
    for (int i = 0; i < g_emitter_count; i++) {
        ff_emitter *e = &g_emitters[i];
        if (e->placed && e->active && e->dist) wsum += e->amplitude;
    }
    if (wsum < 0.0001f) {
        memset(g_field, 0, (size_t)VA_CELLS * sizeof(float));
        return;
    }
    float inv = 1.0f / wsum;

    memset(g_field, 0, (size_t)VA_CELLS * sizeof(float));
    for (int i = 0; i < g_emitter_count; i++) {
        ff_emitter *e = &g_emitters[i];
        if (!e->placed || !e->active || !e->dist) continue;
        float k = FF_TAU / ff_maxf(0.75f, e->wavelength);
        float inv_r = 1.0f / ff_maxf(1.0f, e->radius);
        float amp = e->amplitude * inv;
        float ph = e->phase;
        while (ph < 0.0f) ph += FF_TAU;

        for (int c = 0; c < VA_CELLS; c++) {
            float d = e->dist[c];
            if (d >= e->radius) continue;
            float att = 1.0f - d * inv_r;
            att *= att;                       /* energy falls off with spread */
            g_field[c] += amp * att * sin_lut(d * k + ph);
        }
    }
}

/* Turn the field into matter. Bedrock, anchors and the core are inert; only
 * condensate answers, and only the Bloom's crust can be burned off rock. */
static int apply_field(void)
{
    static const int NB[6][3] = { {1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1} };
    int changed = 0;

    for (int x = 1; x < VA_W - 1; x++)
        for (int y = 1; y < VA_H - 1; y++)
            for (int z = 1; z < VA_D - 1; z++) {
                int c = va_index(x, y, z);
                uint8_t m = g_mat[c];
                float f;

                if (m == MAT_BEDROCK) {
                    /* No wave travels inside rock, so a bedrock cell has no
                     * field of its own. What matters is the wave washing over
                     * its exposed face -- that is what scours the Bloom's
                     * crust off a wall. Without this the Bloom would be
                     * untouchable everywhere it grew on bare stone. */
                    if (!g_bloom[c]) continue;
                    f = 0.0f;
                    for (int d = 0; d < 6; d++) {
                        int ni = va_index(x + NB[d][0], y + NB[d][1], z + NB[d][2]);
                        if (g_mat[ni] != MAT_BEDROCK) f = ff_minf(f, g_field[ni]);
                    }
                } else {
                    f = g_field[c];
                }

                if (f < -FIELD_THRESHOLD) {
                    if (g_bloom[c]) { g_bloom[c] = 0; mark_cell_dirty(x, y, z); changed = 1; }
                    if (m == MAT_CONDENSED) {
                        g_mat[c] = MAT_EMPTY;
                        mark_cell_dirty(x, y, z);
                        changed = 1;
                    }
                } else if (f > FIELD_THRESHOLD && m == MAT_EMPTY) {
                    g_mat[c] = MAT_CONDENSED;
                    mark_cell_dirty(x, y, z);
                    changed = 1;
                }
            }
    return changed;
}

static void relight(void)
{
    memset(g_light, 0, VA_CELLS);
    if (!ensure_queue()) return;
    int head = 0, tail = 0;

    for (int c = 0; c < VA_CELLS; c++) {
        uint8_t emit = g_bloom[c] ? 6 : ff_materials[g_mat[c]].light;
        if (emit) {
            g_light[c] = emit;
            if (tail < g_queue_cap) g_queue[tail++] = c;
        }
    }
    for (int i = 0; i < g_emitter_count; i++) {
        ff_emitter *e = &g_emitters[i];
        if (!e->placed || !e->active) continue;
        int x = ff_clampi((int)e->pos.x, 0, VA_W - 1);
        int y = ff_clampi((int)e->pos.y, 0, VA_H - 1);
        int z = ff_clampi((int)e->pos.z, 0, VA_D - 1);
        int c = va_index(x, y, z);
        if (g_light[c] < 15) {
            g_light[c] = 15;
            if (tail < g_queue_cap) g_queue[tail++] = c;
        }
    }

    static const int NB[6][3] = { {1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1} };
    while (head < tail) {
        int idx = g_queue[head++];
        int lvl = g_light[idx];
        if (lvl <= 1) continue;
        int z = idx % VA_D, y = (idx / VA_D) % VA_H, x = idx / (VA_D * VA_H);
        for (int d = 0; d < 6; d++) {
            int nx = x + NB[d][0], ny = y + NB[d][1], nz = z + NB[d][2];
            if (!va_inside(nx, ny, nz)) continue;
            int ni = va_index(nx, ny, nz);
            if (g_mat[ni] == MAT_BEDROCK) continue;
            if (g_light[ni] >= lvl - 1) continue;
            g_light[ni] = (uint8_t)(lvl - 1);
            if (tail < g_queue_cap) g_queue[tail++] = ni;
        }
    }
}

/* ===================================================================== *
 *  The Bloom
 * ===================================================================== */

static int32_t *g_bloom_new;
static int      g_bloom_new_cap;

static void bloom_tick(void)
{
    static const int NB[6][3] = { {1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1} };
    if (!g_bloom_new) {
        g_bloom_new_cap = 65536;
        g_bloom_new = (int32_t *)malloc((size_t)g_bloom_new_cap * sizeof(int32_t));
        if (!g_bloom_new) return;
    }
    int n = 0;

    for (int x = 1; x < VA_W - 1; x++)
        for (int y = 1; y < VA_H - 1; y++)
            for (int z = 1; z < VA_D - 1; z++) {
                int c = va_index(x, y, z);
                if (!g_bloom[c]) continue;
                for (int d = 0; d < 6; d++) {
                    int nx = x + NB[d][0], ny = y + NB[d][1], nz = z + NB[d][2];
                    int ni = va_index(nx, ny, nz);
                    if (g_bloom[ni]) continue;
                    uint8_t m = g_mat[ni];
                    if (!ff_materials[m].solid) continue;
                    if (m == MAT_CORE) continue;         /* the core is the goal, not a road */
                    /* Condensate is a highway; bare rock is slow going. */
                    float p = (m == MAT_CONDENSED) ? g_bloom_spread_condensed : g_bloom_spread_bedrock;
                    if (ff_rng_f(&g_rng) < p && n < g_bloom_new_cap) g_bloom_new[n++] = ni;
                }
            }

    for (int i = 0; i < n; i++) {
        int idx = g_bloom_new[i];
        if (g_bloom[idx]) continue;
        g_bloom[idx] = 1;
        int z = idx % VA_D, y = (idx / VA_D) % VA_H, x = idx / (VA_D * VA_H);
        mark_cell_dirty(x, y, z);
    }
    if (n) relight();
}

int ff_vault_bloom_cells(void)
{
    int n = 0;
    for (int c = 0; c < VA_CELLS; c++) if (g_bloom[c]) n++;
    return n;
}

int ff_vault_bloom_at_core(void)
{
    static const int NB[6][3] = { {1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1} };
    for (int x = 1; x < VA_W - 1; x++)
        for (int y = 1; y < VA_H - 1; y++)
            for (int z = 1; z < VA_D - 1; z++) {
                if (g_mat[va_index(x, y, z)] != MAT_CORE) continue;
                for (int d = 0; d < 6; d++)
                    if (g_bloom[va_index(x + NB[d][0], y + NB[d][1], z + NB[d][2])]) return 1;
            }
    return 0;
}

/* ===================================================================== *
 *  Objective: anchors joined to the core by clean condensate
 * ===================================================================== */

int ff_vault_anchors_linked(void)
{
    static uint8_t *seen;
    if (!seen) seen = (uint8_t *)malloc(VA_CELLS);
    if (!seen || !ensure_queue()) return 0;
    memset(seen, 0, VA_CELLS);

    static const int NB[6][3] = { {1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1} };
    int head = 0, tail = 0;

    for (int c = 0; c < VA_CELLS; c++)
        if (g_mat[c] == MAT_CORE && !g_bloom[c]) { seen[c] = 1; if (tail < g_queue_cap) g_queue[tail++] = c; }

    int reached[VA_MAX_ANCHORS] = { 0 };
    while (head < tail) {
        int idx = g_queue[head++];
        int z = idx % VA_D, y = (idx / VA_D) % VA_H, x = idx / (VA_D * VA_H);
        for (int d = 0; d < 6; d++) {
            int nx = x + NB[d][0], ny = y + NB[d][1], nz = z + NB[d][2];
            if (!va_inside(nx, ny, nz)) continue;
            int ni = va_index(nx, ny, nz);
            if (seen[ni] || g_bloom[ni]) continue;
            uint8_t m = g_mat[ni];
            if (m == MAT_ANCHOR) {
                seen[ni] = 1;
                for (int a = 0; a < g_anchor_count; a++) {
                    vec3 ap = g_anchor_pos[a];
                    if (fabsf(ap.x - 0.5f - (float)nx) < 1.5f && fabsf(ap.z - 0.5f - (float)nz) < 1.5f)
                        reached[a] = 1;
                }
                if (tail < g_queue_cap) g_queue[tail++] = ni;
            } else if (m == MAT_CONDENSED || m == MAT_CORE) {
                seen[ni] = 1;
                if (tail < g_queue_cap) g_queue[tail++] = ni;
            }
        }
    }
    int total = 0;
    for (int a = 0; a < g_anchor_count; a++) total += reached[a];
    return total;
}

/* ===================================================================== *
 *  Step
 * ===================================================================== */

int ff_vault_step(float dt)
{
    int changed = 0;

    /* At most one distance rebuild per step; they are the expensive part. */
    for (int i = 0; i < g_emitter_count; i++) {
        if (g_emitters[i].placed && g_emitters[i].dist_dirty) {
            compute_distance(&g_emitters[i]);
            g_field_dirty = 1;
            break;
        }
    }

    if (g_field_dirty) {
        g_field_dirty = 0;
        evaluate_field();
        changed |= apply_field();
        relight();
    }

    g_bloom_timer += dt;
    if (g_bloom_timer >= g_bloom_interval) {
        g_bloom_timer = 0.0f;
        bloom_tick();
        changed = 1;
    }
    return changed;
}

/* ===================================================================== *
 *  Raycast
 * ===================================================================== */

int ff_vault_raycast(vec3 o, vec3 dir, float max_dist,
                     int *hx, int *hy, int *hz, int *px, int *py, int *pz)
{
    vec3 d = v3norm(dir);
    int x = (int)floorf(o.x), y = (int)floorf(o.y), z = (int)floorf(o.z);
    int step_x = d.x > 0 ? 1 : -1, step_y = d.y > 0 ? 1 : -1, step_z = d.z > 0 ? 1 : -1;
    float inf = 1e30f;
    float tdx = (fabsf(d.x) < 1e-6f) ? inf : fabsf(1.0f / d.x);
    float tdy = (fabsf(d.y) < 1e-6f) ? inf : fabsf(1.0f / d.y);
    float tdz = (fabsf(d.z) < 1e-6f) ? inf : fabsf(1.0f / d.z);
    float tmx = (fabsf(d.x) < 1e-6f) ? inf : (((d.x > 0) ? (x + 1 - o.x) : (o.x - x)) * tdx);
    float tmy = (fabsf(d.y) < 1e-6f) ? inf : (((d.y > 0) ? (y + 1 - o.y) : (o.y - y)) * tdy);
    float tmz = (fabsf(d.z) < 1e-6f) ? inf : (((d.z > 0) ? (z + 1 - o.z) : (o.z - z)) * tdz);

    int lx = x, ly = y, lz = z;
    float travelled = 0.0f;
    for (int guard = 0; guard < 900 && travelled <= max_dist; guard++) {
        if (!va_inside(x, y, z)) return 0;
        if (ff_vault_solid(x, y, z)) {
            if (hx) { *hx = x; *hy = y; *hz = z; }
            if (px) { *px = lx; *py = ly; *pz = lz; }
            return 1;
        }
        lx = x; ly = y; lz = z;
        if (tmx < tmy && tmx < tmz) { x += step_x; travelled = tmx; tmx += tdx; }
        else if (tmy < tmz)         { y += step_y; travelled = tmy; tmy += tdy; }
        else                        { z += step_z; travelled = tmz; tmz += tdz; }
    }
    return 0;
}

/* ===================================================================== *
 *  Lifetime
 * ===================================================================== */

void ff_vault_init(uint32_t seed, int chamber)
{
    ff_vault_free();
    sin_table_init();

    g_seed = seed;
    g_chamber = chamber;
    ff_noise_init(seed + (uint32_t)chamber * 7919u);
    ff_rng_seed(&g_rng, ((uint64_t)seed << 8) ^ (uint64_t)(chamber + 1) * 0x9E3779B9ull);

    g_mat   = (uint8_t *)malloc(VA_CELLS);
    g_bloom = (uint8_t *)calloc(1, VA_CELLS);
    g_light = (uint8_t *)calloc(1, VA_CELLS);
    g_field = (float *)calloc(1, (size_t)VA_CELLS * sizeof(float));
    if (!g_mat || !g_bloom || !g_light || !g_field) return;

    for (int i = 0; i < VA_CHUNK_COUNT; i++) {
        int cz = i % VA_CHUNKS_Z, cy = (i / VA_CHUNKS_Z) % VA_CHUNKS_Y, cx = i / (VA_CHUNKS_Z * VA_CHUNKS_Y);
        g_chunks[i].cx = cx; g_chunks[i].cy = cy; g_chunks[i].cz = cz;
        g_chunks[i].dirty = 1;
    }

    generate_chamber();

    /* Difficulty ramps with the chamber: more emitters to work with, but a
     * Bloom that moves faster and starts from more places. */
    g_emitter_count = ff_mini(VA_MAX_EMITTERS, 3 + chamber);
    for (int i = 0; i < VA_MAX_EMITTERS; i++) {
        ff_emitter *e = &g_emitters[i];
        e->placed = 0;
        e->active = 1;
        e->wavelength = 7.0f + (float)i * 2.0f;
        e->amplitude = 0.5f;
        e->phase = 0.0f;
        e->radius = 44.0f;
        e->dist_dirty = 1;
    }
    g_bloom_interval = ff_maxf(0.55f, 1.15f - 0.18f * (float)chamber);
    g_bloom_spread_condensed = 0.30f + 0.06f * (float)chamber;
    g_bloom_spread_bedrock   = 0.045f + 0.015f * (float)chamber;
    g_bloom_timer = 0.0f;

    relight();
    ff_vault_mark_all_dirty();
}

void ff_vault_free(void)
{
    for (int i = 0; i < VA_MAX_EMITTERS; i++) {
        free(g_emitters[i].dist);
        g_emitters[i].dist = NULL;
    }
    if (g_mesh_release)
        for (int i = 0; i < VA_CHUNK_COUNT; i++) g_mesh_release(&g_chunks[i]);
    free(g_mat);   g_mat = NULL;
    free(g_bloom); g_bloom = NULL;
    free(g_light); g_light = NULL;
    free(g_field); g_field = NULL;
    g_emitter_count = 0;
    g_anchor_count = 0;
}
