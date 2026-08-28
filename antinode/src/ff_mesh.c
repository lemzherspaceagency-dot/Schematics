/* ff_mesh.c -- turns a 16^3 slab of the Vault into triangles.
 *
 * Plain face culling with per-vertex ambient occlusion. The Vault remeshes
 * constantly as the field is retuned, so this stays deliberately simple and
 * only touches chunks the material pass actually changed.
 */
#include "ff_render.h"
#include "ff_gl.h"

#include <stdlib.h>
#include <string.h>

static ff_vertex *g_buf;
static int        g_count, g_cap;

static ff_vertex *buf_alloc(int n)
{
    if (g_count + n > g_cap) {
        int cap = g_cap ? g_cap : 8192;
        while (cap < g_count + n) cap *= 2;
        ff_vertex *nb = (ff_vertex *)realloc(g_buf, (size_t)cap * sizeof *nb);
        if (!nb) return NULL;
        g_buf = nb; g_cap = cap;
    }
    ff_vertex *p = g_buf + g_count;
    g_count += n;
    return p;
}

/* +X, -X, +Y, -Y, +Z, -Z */
static const int FACE_N[6][3] = { {1,0,0}, {-1,0,0}, {0,1,0}, {0,-1,0}, {0,0,1}, {0,0,-1} };

static const float FACE_V[6][4][3] = {
    { {1,0,1}, {1,0,0}, {1,1,0}, {1,1,1} },
    { {0,0,0}, {0,0,1}, {0,1,1}, {0,1,0} },
    { {0,1,1}, {1,1,1}, {1,1,0}, {0,1,0} },
    { {0,0,0}, {1,0,0}, {1,0,1}, {0,0,1} },
    { {0,0,1}, {1,0,1}, {1,1,1}, {0,1,1} },
    { {1,0,0}, {0,0,0}, {0,1,0}, {1,1,0} },
};
static const int FACE_TAN[6][2][3] = {
    { {0,0,-1}, {0,1,0} }, { {0,0, 1}, {0,1,0} },
    { {1,0, 0}, {0,0,-1} }, { {1,0, 0}, {0,0, 1} },
    { {1,0, 0}, {0,1,0} }, { {-1,0,0}, {0,1,0} },
};
static const int CORNER_SIGN[6][4][2] = {
    { {-1,-1}, {1,-1}, {1,1}, {-1,1} }, { {-1,-1}, {1,-1}, {1,1}, {-1,1} },
    { {-1, 1}, {1, 1}, {1,-1}, {-1,-1} }, { {-1,-1}, {1,-1}, {1, 1}, {-1, 1} },
    { {-1,-1}, {1,-1}, {1, 1}, {-1, 1} }, { {-1,-1}, {1,-1}, {1, 1}, {-1, 1} },
};
static const float FACE_TINT[6] = { 0.80f, 0.80f, 1.00f, 0.50f, 0.66f, 0.66f };

static void tile_uv(int tile, float *u0, float *v0, float *u1, float *v1)
{
    int tx = tile % FF_ATLAS_TILES, ty = tile / FF_ATLAS_TILES;
    const float inset = 0.35f / (float)FF_ATLAS_PX;
    *u0 = (float)tx / FF_ATLAS_TILES + inset;
    *v0 = (float)ty / FF_ATLAS_TILES + inset;
    *u1 = (float)(tx + 1) / FF_ATLAS_TILES - inset;
    *v1 = (float)(ty + 1) / FF_ATLAS_TILES - inset;
}

static void emit_face(int x, int y, int z, int tile, int face, float pulse)
{
    ff_vertex *v = buf_alloc(6);
    if (!v) return;

    int nx = x + FACE_N[face][0], ny = y + FACE_N[face][1], nz = z + FACE_N[face][2];
    float light = (float)ff_vault_light(nx, ny, nz) / 15.0f;

    float u0, v0, u1, v1;
    tile_uv(tile, &u0, &v0, &u1, &v1);
    const float uvs[4][2] = { {u0, v1}, {u1, v1}, {u1, v0}, {u0, v0} };

    float shade[4];
    for (int i = 0; i < 4; i++) {
        int su = CORNER_SIGN[face][i][0], sv = CORNER_SIGN[face][i][1];
        const int *ta = FACE_TAN[face][0], *tb = FACE_TAN[face][1];
        int ax = nx + ta[0] * su, ay = ny + ta[1] * su, az = nz + ta[2] * su;
        int bx = nx + tb[0] * sv, by = ny + tb[1] * sv, bz = nz + tb[2] * sv;
        int s1 = ff_vault_solid(ax, ay, az);
        int s2 = ff_vault_solid(bx, by, bz);
        int cr = ff_vault_solid(ax + tb[0] * sv, ay + tb[1] * sv, az + tb[2] * sv);
        int level = (s1 && s2) ? 0 : 3 - (s1 + s2 + cr);
        shade[i] = (0.40f + 0.60f * (float)level / 3.0f) * FACE_TINT[face];
    }

    int flip = (shade[0] + shade[2]) < (shade[1] + shade[3]);
    static const int TRI_A[6] = { 0, 1, 2, 0, 2, 3 };
    static const int TRI_B[6] = { 1, 2, 3, 1, 3, 0 };
    const int *tri = flip ? TRI_B : TRI_A;

    for (int i = 0; i < 6; i++) {
        int c = tri[i];
        v[i].x = (float)x + FACE_V[face][c][0];
        v[i].y = (float)y + FACE_V[face][c][1];
        v[i].z = (float)z + FACE_V[face][c][2];
        v[i].u = uvs[c][0];
        v[i].v = uvs[c][1];
        v[i].light = light;
        v[i].pulse = pulse;
        v[i].shade = shade[c];
    }
}

void ff_mesh_chunk(ff_vchunk *c)
{
    g_count = 0;
    const int bx = c->cx * VA_CHUNK, by = c->cy * VA_CHUNK, bz = c->cz * VA_CHUNK;

    for (int lx = 0; lx < VA_CHUNK; lx++)
        for (int ly = 0; ly < VA_CHUNK; ly++)
            for (int lz = 0; lz < VA_CHUNK; lz++) {
                int x = bx + lx, y = by + ly, z = bz + lz;
                uint8_t m = ff_vault_mat(x, y, z);
                if (!ff_materials[m].solid) continue;

                int bloom = ff_vault_bloom(x, y, z);
                int tile = bloom ? 3 : ff_materials[m].tile;
                /* Condensate glimmers with whatever the field is doing to it. */
                float pulse = (m == MAT_CONDENSED && !bloom)
                            ? ff_clampf(fabsf(ff_vault_field(x, y, z)), 0.0f, 1.0f) : 0.0f;

                for (int f = 0; f < 6; f++) {
                    int nx = x + FACE_N[f][0], ny = y + FACE_N[f][1], nz = z + FACE_N[f][2];
                    if (ff_vault_solid(nx, ny, nz)) continue;
                    emit_face(x, y, z, tile, f, pulse);
                }
            }

    if (g_count == 0) { c->vert_count = 0; c->dirty = 0; return; }

    if (!c->vao) {
        glGenVertexArrays(1, &c->vao);
        glGenBuffers(1, &c->vbo);
    }
    glBindVertexArray(c->vao);
    glBindBuffer(GL_ARRAY_BUFFER, c->vbo);
    glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(g_count * (int)sizeof(ff_vertex)), g_buf, GL_DYNAMIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(ff_vertex), (void *)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, sizeof(ff_vertex), (void *)(3 * sizeof(float)));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, sizeof(ff_vertex), (void *)(5 * sizeof(float)));
    glBindVertexArray(0);

    c->vert_count = (unsigned int)g_count;
    c->dirty = 0;
}

void ff_mesh_release(ff_vchunk *c)
{
    if (c->vbo) glDeleteBuffers(1, &c->vbo);
    if (c->vao) glDeleteVertexArrays(1, &c->vao);
    c->vao = c->vbo = c->vert_count = 0;
}
