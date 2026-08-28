/* ff_vault.h -- the Vault: a bounded cavern, the wave field that fills it,
 * and the Bloom that creeps across whatever is solid.
 *
 * ANTINODE has no block placement. Matter is a *consequence* of the wave
 * field: every emitter floods the open space with a travelling wave, the
 * waves sum, and cells where the sum peaks condense into crystal while cells
 * where it troughs sublime away. The player edits emitters, never cells.
 */
#ifndef FF_VAULT_H
#define FF_VAULT_H

#include <stdint.h>
#include "ff_math.h"

#define VA_W      96
#define VA_H      48
#define VA_D      96
#define VA_CELLS  (VA_W * VA_H * VA_D)

#define VA_CHUNK      16
#define VA_CHUNKS_X   (VA_W / VA_CHUNK)
#define VA_CHUNKS_Y   (VA_H / VA_CHUNK)
#define VA_CHUNKS_Z   (VA_D / VA_CHUNK)
#define VA_CHUNK_COUNT (VA_CHUNKS_X * VA_CHUNKS_Y * VA_CHUNKS_Z)

#define VA_MAX_EMITTERS 5
#define VA_MAX_ANCHORS  4

/* Materials. Bedrock is the chamber itself and is immune to the field;
 * only condensed matter answers to it. */
enum {
    MAT_EMPTY = 0,
    MAT_BEDROCK,
    MAT_CONDENSED,
    MAT_ANCHOR,
    MAT_CORE,
    MAT_COUNT
};

typedef struct {
    const char *name;
    uint8_t solid;
    uint8_t light;        /* emission 0..15 */
    uint8_t tile;
} ff_material;

extern const ff_material ff_materials[MAT_COUNT];

typedef struct {
    int   placed;         /* has been anchored in the chamber   */
    int   active;         /* radiating                          */
    vec3  pos;
    float wavelength;     /* metres between crests              */
    float amplitude;      /* 0..1, drawn from the power budget  */
    float phase;          /* radians                            */
    float radius;         /* range before the wave dies out     */
    float *dist;          /* geodesic distance from this emitter */
    int   dist_dirty;
} ff_emitter;

typedef struct {
    int cx, cy, cz;
    uint8_t dirty;
    unsigned int vao, vbo, vert_count;
} ff_vchunk;

static inline int va_index(int x, int y, int z) { return (x * VA_H + y) * VA_D + z; }
static inline int va_inside(int x, int y, int z) {
    return x >= 0 && y >= 0 && z >= 0 && x < VA_W && y < VA_H && z < VA_D;
}

/* ---- lifetime -------------------------------------------------------- */
void  ff_vault_init(uint32_t seed, int chamber);
void  ff_vault_free(void);
int   ff_vault_chamber(void);
uint32_t ff_vault_seed(void);

/* ---- cell queries ---------------------------------------------------- */
uint8_t ff_vault_mat(int x, int y, int z);
int     ff_vault_bloom(int x, int y, int z);
int     ff_vault_solid(int x, int y, int z);
uint8_t ff_vault_light(int x, int y, int z);
float   ff_vault_field(int x, int y, int z);

/* ---- emitters -------------------------------------------------------- */
ff_emitter *ff_vault_emitter(int i);
int   ff_vault_emitter_count(void);
void  ff_vault_place_emitter(int i, vec3 pos);
void  ff_vault_touch_field(void);       /* parameters changed              */
float ff_vault_power_used(void);
float ff_vault_power_budget(void);

/* Advances the simulation: one distance rebuild, the field, the material
 * pass, lighting and the Bloom tick. Returns non-zero if geometry changed. */
int   ff_vault_step(float dt);

/* ---- objective ------------------------------------------------------- */
int   ff_vault_anchor_count(void);
vec3  ff_vault_anchor_pos(int i);
vec3  ff_vault_core_pos(void);
/* Number of anchors currently joined to the core by clean condensed matter. */
int   ff_vault_anchors_linked(void);
int   ff_vault_bloom_at_core(void);
int   ff_vault_bloom_cells(void);

/* ---- chunks / raycast ------------------------------------------------ */
ff_vchunk *ff_vault_chunk(int i);
void  ff_vault_mark_all_dirty(void);
int   ff_vault_raycast(vec3 origin, vec3 dir, float max_dist,
                       int *hx, int *hy, int *hz, int *px, int *py, int *pz);

void  ff_vault_set_mesh_release(void (*fn)(ff_vchunk *));

#endif /* FF_VAULT_H */
