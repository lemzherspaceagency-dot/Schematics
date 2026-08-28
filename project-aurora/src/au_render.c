/* au_render.c -- shader, primitive mesh builders, the 2D overlay. */
#include "au_render.h"
#include "ff_gl.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ===================================================================== *
 *  Mesh buffers
 * ===================================================================== */

void au_mesh_init(au_mesh *m) { memset(m, 0, sizeof *m); }

static au_vertex *mesh_alloc(au_mesh *m, int n)
{
    if (m->count + n > m->cap) {
        int cap = m->cap ? m->cap * 2 : 256;
        while (cap < m->count + n) cap *= 2;
        au_vertex *nv = (au_vertex *)realloc(m->v, (size_t)cap * sizeof(au_vertex));
        if (!nv) return NULL;
        m->v = nv; m->cap = cap;
    }
    au_vertex *p = m->v + m->count;
    m->count += n;
    return p;
}

void au_mesh_upload(au_mesh *m)
{
    if (!m->count) return;
    if (!m->vao) { glGenVertexArrays(1, &m->vao); glGenBuffers(1, &m->vbo); }
    glBindVertexArray(m->vao);
    glBindBuffer(GL_ARRAY_BUFFER, m->vbo);
    glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(m->count * (int)sizeof(au_vertex)), m->v, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(au_vertex), (void *)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(au_vertex), (void *)(3 * sizeof(float)));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, sizeof(au_vertex), (void *)(6 * sizeof(float)));
    glEnableVertexAttribArray(3);
    glVertexAttribPointer(3, 2, GL_FLOAT, GL_FALSE, sizeof(au_vertex), (void *)(9 * sizeof(float)));
    glBindVertexArray(0);
}

void au_mesh_free(au_mesh *m)
{
    if (m->vbo) glDeleteBuffers(1, &m->vbo);
    if (m->vao) glDeleteVertexArrays(1, &m->vao);
    free(m->v);
    memset(m, 0, sizeof *m);
}

/* ---- box ---------------------------------------------------------- */

static const int FACE_N[6][3] = { {1,0,0}, {-1,0,0}, {0,1,0}, {0,-1,0}, {0,0,1}, {0,0,-1} };
static const float FACE_V[6][4][3] = {
    { {1,-1,1}, {1,-1,-1}, {1,1,-1}, {1,1,1} },
    { {-1,-1,-1}, {-1,-1,1}, {-1,1,1}, {-1,1,-1} },
    { {-1,1,1}, {1,1,1}, {1,1,-1}, {-1,1,-1} },
    { {-1,-1,-1}, {1,-1,-1}, {1,-1,1}, {-1,-1,1} },
    { {-1,-1,1}, {1,-1,1}, {1,1,1}, {-1,1,1} },
    { {1,-1,-1}, {-1,-1,-1}, {-1,1,-1}, {1,1,-1} },
};

void au_add_box(au_mesh *m, vec3 c, vec3 h, vec3 col, float emissive, float alpha)
{
    static const int TRI[6] = { 0,1,2, 0,2,3 };
    for (int f = 0; f < 6; f++) {
        au_vertex *v = mesh_alloc(m, 6);
        if (!v) return;
        for (int i = 0; i < 6; i++) {
            int cnr = TRI[i];
            v[i].x = c.x + FACE_V[f][cnr][0] * h.x;
            v[i].y = c.y + FACE_V[f][cnr][1] * h.y;
            v[i].z = c.z + FACE_V[f][cnr][2] * h.z;
            v[i].nx = (float)FACE_N[f][0]; v[i].ny = (float)FACE_N[f][1]; v[i].nz = (float)FACE_N[f][2];
            v[i].r = col.x; v[i].g = col.y; v[i].b = col.z;
            v[i].e = emissive; v[i].a = alpha;
        }
    }
}

/* ---- cylinder (also serves as a cone when radius_top==0) ---------- */

void au_add_cylinder(au_mesh *m, vec3 c, float rt, float rb, float height, int segs,
                     vec3 col, float emissive, float alpha)
{
    float half = height * 0.5f;
    for (int i = 0; i < segs; i++) {
        float a0 = (float)i / segs * FF_TAU, a1 = (float)(i + 1) / segs * FF_TAU;
        float x0 = cosf(a0), z0 = sinf(a0), x1 = cosf(a1), z1 = sinf(a1);

        vec3 p[4] = {
            v3(c.x + x0 * rb, c.y - half, c.z + z0 * rb),
            v3(c.x + x1 * rb, c.y - half, c.z + z1 * rb),
            v3(c.x + x1 * rt, c.y + half, c.z + z1 * rt),
            v3(c.x + x0 * rt, c.y + half, c.z + z0 * rt),
        };
        vec3 nrm = v3norm(v3((x0 + x1) * 0.5f, (rb - rt) / (height + 1e-5f), (z0 + z1) * 0.5f));

        au_vertex *v = mesh_alloc(m, 6);
        if (!v) return;
        static const int TRI[6] = { 0,1,2, 0,2,3 };
        for (int k = 0; k < 6; k++) {
            int cnr = TRI[k];
            v[k].x = p[cnr].x; v[k].y = p[cnr].y; v[k].z = p[cnr].z;
            v[k].nx = nrm.x; v[k].ny = nrm.y; v[k].nz = nrm.z;
            v[k].r = col.x; v[k].g = col.y; v[k].b = col.z;
            v[k].e = emissive; v[k].a = alpha;
        }

        /* end caps */
        au_vertex *cb = mesh_alloc(m, 3);
        if (cb) {
            cb[0] = (au_vertex){ c.x, c.y - half, c.z, 0,-1,0, col.x,col.y,col.z, emissive, alpha };
            cb[1] = (au_vertex){ p[1].x, p[1].y, p[1].z, 0,-1,0, col.x,col.y,col.z, emissive, alpha };
            cb[2] = (au_vertex){ p[0].x, p[0].y, p[0].z, 0,-1,0, col.x,col.y,col.z, emissive, alpha };
        }
        au_vertex *ct = mesh_alloc(m, 3);
        if (ct) {
            ct[0] = (au_vertex){ c.x, c.y + half, c.z, 0,1,0, col.x,col.y,col.z, emissive, alpha };
            ct[1] = (au_vertex){ p[2].x, p[2].y, p[2].z, 0,1,0, col.x,col.y,col.z, emissive, alpha };
            ct[2] = (au_vertex){ p[3].x, p[3].y, p[3].z, 0,1,0, col.x,col.y,col.z, emissive, alpha };
        }
    }
}

/* ---- UV sphere ------------------------------------------------------ */

void au_add_sphere(au_mesh *m, vec3 c, float r, int segs, vec3 col, float emissive, float alpha)
{
    int rings = segs / 2 < 3 ? 3 : segs / 2;
    for (int ring = 0; ring < rings; ring++) {
        float v0 = (float)ring / rings * FF_PI, v1 = (float)(ring + 1) / rings * FF_PI;
        for (int seg = 0; seg < segs; seg++) {
            float u0 = (float)seg / segs * FF_TAU, u1 = (float)(seg + 1) / segs * FF_TAU;

            vec3 corners[4];
            float vs[2] = { v0, v1 }, us[2] = { u0, u1 };
            int idx = 0;
            vec3 quad[4];
            for (int a = 0; a < 2; a++)
                for (int b = 0; b < 2; b++) {
                    float vv = vs[a], uu = us[(a == 0) ? b : (1 - b)];
                    quad[idx].x = sinf(vv) * cosf(uu);
                    quad[idx].y = cosf(vv);
                    quad[idx].z = sinf(vv) * sinf(uu);
                    idx++;
                }
            /* quad[] is v0/u0, v0/u1, v1/u1, v1/u0 -- already wound CCW seen from outside */
            for (int i = 0; i < 4; i++) corners[i] = quad[i];

            au_vertex *vtx = mesh_alloc(m, 6);
            if (!vtx) return;
            static const int TRI[6] = { 0,1,2, 0,2,3 };
            for (int k = 0; k < 6; k++) {
                vec3 n = corners[TRI[k]];
                vtx[k].x = c.x + n.x * r; vtx[k].y = c.y + n.y * r; vtx[k].z = c.z + n.z * r;
                vtx[k].nx = n.x; vtx[k].ny = n.y; vtx[k].nz = n.z;
                vtx[k].r = col.x; vtx[k].g = col.y; vtx[k].b = col.z;
                vtx[k].e = emissive; vtx[k].a = alpha;
            }
        }
    }
}

/* ---- ring (flattened torus, used for Aurora's collar and the scan pulse) */

void au_add_ring(au_mesh *m, vec3 c, float radius, float tube, int segs, vec3 col, float emissive, float alpha)
{
    int tsegs = 8;
    for (int i = 0; i < segs; i++) {
        float a0 = (float)i / segs * FF_TAU, a1 = (float)(i + 1) / segs * FF_TAU;
        for (int t = 0; t < tsegs; t++) {
            float t0 = (float)t / tsegs * FF_TAU, t1 = (float)(t + 1) / tsegs * FF_TAU;

            vec3 quad[4];
            float as[2] = { a0, a1 }, ts[2] = { t0, t1 };
            int idx = 0;
            for (int ai = 0; ai < 2; ai++)
                for (int bi = 0; bi < 2; bi++) {
                    float aa = as[ai], tt = ts[(ai == 0) ? bi : (1 - bi)];
                    float cx = cosf(aa) * (radius + tube * cosf(tt));
                    float cz = sinf(aa) * (radius + tube * cosf(tt));
                    float cy = tube * sinf(tt);
                    quad[idx++] = v3(c.x + cx, c.y + cy, c.z + cz);
                }
            vec3 nrm = v3norm(v3(quad[0].x - c.x, quad[0].y - c.y, quad[0].z - c.z));

            au_vertex *v = mesh_alloc(m, 6);
            if (!v) return;
            static const int TRI[6] = { 0,1,2, 0,2,3 };
            for (int k = 0; k < 6; k++) {
                vec3 p = quad[TRI[k]];
                v[k].x = p.x; v[k].y = p.y; v[k].z = p.z;
                v[k].nx = nrm.x; v[k].ny = nrm.y; v[k].nz = nrm.z;
                v[k].r = col.x; v[k].g = col.y; v[k].b = col.z;
                v[k].e = emissive; v[k].a = alpha;
            }
        }
    }
}

/* ===================================================================== *
 *  Shaders
 * ===================================================================== */

static GLuint compile(GLenum type, const char *src, const char *label)
{
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, NULL);
    glCompileShader(s);
    GLint ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetShaderInfoLog(s, sizeof log, NULL, log);
        fprintf(stderr, "[shader] %s failed:\n%s\n", label, log);
        glDeleteShader(s);
        return 0;
    }
    return s;
}
static GLuint link_program(const char *vs, const char *fs, const char *label)
{
    GLuint v = compile(GL_VERTEX_SHADER, vs, label), f = compile(GL_FRAGMENT_SHADER, fs, label);
    if (!v || !f) return 0;
    GLuint p = glCreateProgram();
    glAttachShader(p, v); glAttachShader(p, f); glLinkProgram(p);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetProgramInfoLog(p, sizeof log, NULL, log);
        fprintf(stderr, "[shader] %s link failed:\n%s\n", label, log);
        glDeleteProgram(p); p = 0;
    }
    glDeleteShader(v); glDeleteShader(f);
    return p;
}

static const char *VS_STATIC =
"#version 330 core\n"
"layout(location=0) in vec3 a_pos;\n"
"layout(location=1) in vec3 a_nrm;\n"
"layout(location=2) in vec3 a_col;\n"
"layout(location=3) in vec2 a_ea;   // emissive, alpha\n"
"uniform mat4 u_viewproj, u_model;\n"
"out vec3 v_wp; out vec3 v_nrm; out vec3 v_col; out vec2 v_ea;\n"
"void main(){\n"
"  vec4 wp = u_model * vec4(a_pos, 1.0);\n"
"  gl_Position = u_viewproj * wp;\n"
"  v_wp = wp.xyz;\n"
"  v_nrm = mat3(u_model) * a_nrm;\n"
"  v_col = a_col; v_ea = a_ea;\n"
"}\n";

/* Two warm point lights (desk lamp, ceiling fill) and one cold spill from
 * the locked door -- the lighting itself is doing the story's job: a warm
 * facade and a cold mechanism underneath it. */
static const char *FS_STATIC =
"#version 330 core\n"
"in vec3 v_wp; in vec3 v_nrm; in vec3 v_col; in vec2 v_ea;\n"
"uniform vec3 u_lampPos, u_lampCol, u_doorPos, u_doorCol, u_fillPos, u_fillCol;\n"
"uniform vec4 u_tint;\n"
"out vec4 frag;\n"
"vec3 pointLight(vec3 p, vec3 col, float range, vec3 n, vec3 wp){\n"
"  vec3 d = p - wp; float dist = length(d);\n"
"  float atten = clamp(1.0 - dist/range, 0.0, 1.0);\n"
"  // Half-lambert: keeps a face turned away from every light readable\n"
"  // instead of dropping straight to ambient-black.\n"
"  float ndotl = max(dot(n, normalize(d)), 0.0) * 0.7 + 0.3;\n"
"  return col * ndotl * atten;\n"
"}\n"
"void main(){\n"
"  vec3 n = normalize(v_nrm);\n"
"  vec3 lit = vec3(0.20,0.17,0.14);\n"
"  lit += pointLight(u_lampPos, u_lampCol, 17.0, n, v_wp);\n"
"  lit += pointLight(u_doorPos, u_doorCol, 12.0, n, v_wp);\n"
"  lit += pointLight(u_fillPos, u_fillCol, 21.0, n, v_wp);\n"
"  vec3 col = v_col * lit + v_col * v_ea.x * 1.4;\n"
"  frag = vec4(col * u_tint.rgb, v_ea.y * u_tint.a);\n"
"}\n";

static GLuint P_static;

/* ---- UI shader (unlit textured quads: solid rects + bitmap-font glyphs) */

static const char *VS_UI =
"#version 330 core\n"
"layout(location=0) in vec2 a_pos;\n"
"layout(location=1) in vec2 a_uv;\n"
"layout(location=2) in vec4 a_col;\n"
"uniform vec2 u_screen;\n"
"out vec2 v_uv; out vec4 v_col;\n"
"void main(){\n"
"  vec2 p = vec2(a_pos.x / u_screen.x * 2.0 - 1.0, 1.0 - a_pos.y / u_screen.y * 2.0);\n"
"  gl_Position = vec4(p, 0.0, 1.0);\n"
"  v_uv = a_uv; v_col = a_col;\n"
"}\n";
static const char *FS_UI =
"#version 330 core\n"
"in vec2 v_uv; in vec4 v_col;\n"
"uniform sampler2D u_tex; uniform int u_mode;\n"
"out vec4 frag;\n"
"void main(){\n"
"  if (u_mode == 0) { frag = v_col; return; }\n"
"  float a = texture(u_tex, v_uv).r;\n"
"  if (a < 0.5) discard;\n"
"  frag = vec4(v_col.rgb, v_col.a);\n"
"}\n";

static GLuint P_ui, VAO_ui, VBO_ui, g_font_tex;

int au_render_init(void)
{
    P_static = link_program(VS_STATIC, FS_STATIC, "static");
    if (!P_static) return 0;
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glFrontFace(GL_CCW);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    return 1;
}
void au_render_resize(int w, int h) { glViewport(0, 0, w, h); }

void au_render_frame_begin(const au_camera *cam)
{
    (void)cam;
    glClearColor(0.047f, 0.039f, 0.031f, 1.0f);   /* --void */
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
}

#define GET(p, n) glGetUniformLocation(p, n)

void au_render_mesh(const au_mesh *m, mat4 model, float tr, float tg, float tb, float ta, const au_camera *cam)
{
    if (!m->count) return;
    glUseProgram(P_static);
    glUniformMatrix4fv(GET(P_static, "u_viewproj"), 1, GL_FALSE, cam->viewproj.m);
    glUniformMatrix4fv(GET(P_static, "u_model"), 1, GL_FALSE, model.m);
    glUniform4f(GET(P_static, "u_tint"), tr, tg, tb, ta);
    glUniform3f(GET(P_static, "u_lampPos"), -4.0f, 2.6f, -4.0f);
    glUniform3f(GET(P_static, "u_lampCol"), 1.30f, 1.02f, 0.76f);
    glUniform3f(GET(P_static, "u_doorPos"), 0.0f, 2.4f, -7.6f);
    glUniform3f(GET(P_static, "u_doorCol"), 0.85f, 0.42f, 0.34f);
    glUniform3f(GET(P_static, "u_fillPos"), 0.0f, 3.6f, 2.0f);
    glUniform3f(GET(P_static, "u_fillCol"), 0.95f, 0.82f, 0.66f);

    if (ta < 0.999f) { glEnable(GL_BLEND); glDepthMask(GL_FALSE); glDisable(GL_CULL_FACE); }
    glBindVertexArray(m->vao);
    glDrawArrays(GL_TRIANGLES, 0, m->count);
    glBindVertexArray(0);
    if (ta < 0.999f) { glDisable(GL_BLEND); glDepthMask(GL_TRUE); glEnable(GL_CULL_FACE); }
}

/* ===================================================================== *
 *  Inline 5x7 bitmap font -- validated glyph table, generated once and
 *  reused verbatim from the prior project rather than re-derived by hand.
 * ===================================================================== */

#include "au_font.inc"

#define GLYPH_W 5
#define GLYPH_H 7

typedef struct { float x, y, u, v, r, g, b, a; } ui_vert;
#define UI_MAX_VERTS 8192
static ui_vert g_verts[UI_MAX_VERTS];
static int g_nverts, g_mode, g_w, g_h;

static void build_font_texture(void)
{
    static uint8_t rgba[64 * 64 * 4];
    memset(rgba, 0, sizeof rgba);
    for (int g = 0; g < 64; g++) {
        const char *rows = FONT[g];
        int cx = (g % 8) * 8, cy = (g / 8) * 8;
        for (int y = 0; y < GLYPH_H; y++)
            for (int x = 0; x < GLYPH_W; x++) {
                if (rows[y * GLYPH_W + x] != '#') continue;
                int i = ((cy + y) * 64 + (cx + x)) * 4;
                rgba[i] = rgba[i+1] = rgba[i+2] = rgba[i+3] = 255;
            }
    }
    glGenTextures(1, &g_font_tex);
    glBindTexture(GL_TEXTURE_2D, g_font_tex);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 64, 64, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 0);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

int au_ui_init(void)
{
    P_ui = link_program(VS_UI, FS_UI, "ui");
    if (!P_ui) return 0;
    build_font_texture();
    glGenVertexArrays(1, &VAO_ui);
    glGenBuffers(1, &VBO_ui);
    glBindVertexArray(VAO_ui);
    glBindBuffer(GL_ARRAY_BUFFER, VBO_ui);
    glBufferData(GL_ARRAY_BUFFER, sizeof g_verts, NULL, GL_STREAM_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, sizeof(ui_vert), (void *)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, sizeof(ui_vert), (void *)(2*sizeof(float)));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, sizeof(ui_vert), (void *)(4*sizeof(float)));
    glBindVertexArray(0);
    return 1;
}

static void ui_flush(void)
{
    if (!g_nverts) return;
    glUseProgram(P_ui);
    glUniform2f(GET(P_ui, "u_screen"), (float)g_w, (float)g_h);
    glUniform1i(GET(P_ui, "u_mode"), g_mode);
    glUniform1i(GET(P_ui, "u_tex"), 0);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, g_font_tex);
    glBindVertexArray(VAO_ui);
    glBindBuffer(GL_ARRAY_BUFFER, VBO_ui);
    glBufferSubData(GL_ARRAY_BUFFER, 0, (GLsizeiptr)(g_nverts * (int)sizeof(ui_vert)), g_verts);
    glDrawArrays(GL_TRIANGLES, 0, g_nverts);
    glBindVertexArray(0);
    g_nverts = 0;
}
static void ui_set_mode(int mode) { if (mode != g_mode) { ui_flush(); g_mode = mode; } }

static void push_quad(float x, float y, float w, float h, float u0, float v0, float u1, float v1,
                      float r, float g, float b, float a)
{
    if (g_nverts + 6 > UI_MAX_VERTS) ui_flush();
    const float xs[6] = { x,x+w,x+w, x,x+w,x }, ys[6] = { y,y,y+h, y,y+h,y+h };
    const float us[6] = { u0,u1,u1, u0,u1,u0 }, vs[6] = { v0,v0,v1, v0,v1,v1 };
    for (int i = 0; i < 6; i++) {
        ui_vert *p = &g_verts[g_nverts++];
        p->x=xs[i]; p->y=ys[i]; p->u=us[i]; p->v=vs[i]; p->r=r; p->g=g; p->b=b; p->a=a;
    }
}

void au_ui_begin(int w, int h)
{
    g_w = w; g_h = h; g_nverts = 0; g_mode = 0;
    glDisable(GL_DEPTH_TEST); glDisable(GL_CULL_FACE); glEnable(GL_BLEND);
}
void au_ui_end(void)
{
    ui_flush();
    glEnable(GL_DEPTH_TEST); glEnable(GL_CULL_FACE);
}
void au_ui_rect(float x, float y, float w, float h, float r, float g, float b, float a)
{
    ui_set_mode(0);
    push_quad(x, y, w, h, 0,0,1,1, r,g,b,a);
}
void au_ui_text(float x, float y, float scale, float r, float g, float b, float a, const char *text)
{
    ui_set_mode(1);
    float cx = x;
    for (const unsigned char *p = (const unsigned char *)text; *p; p++) {
        unsigned char ch = *p;
        if (ch == '\n') { cx = x; y += (GLYPH_H + 2) * scale; continue; }
        if (ch >= 'a' && ch <= 'z') ch = (unsigned char)(ch - 'a' + 'A');
        if (ch < 32 || ch > 95) ch = '?';
        int gi = ch - 32, cxi = (gi % 8) * 8, cyi = (gi / 8) * 8;
        float u0=(float)cxi/64.0f, v0=(float)cyi/64.0f, u1=(float)(cxi+GLYPH_W)/64.0f, v1=(float)(cyi+GLYPH_H)/64.0f;
        if (ch != ' ') push_quad(cx, y, GLYPH_W*scale, GLYPH_H*scale, u0,v0,u1,v1, r,g,b,a);
        cx += (GLYPH_W + 1) * scale;
    }
}
float au_ui_text_width(float scale, const char *text)
{
    int n = 0;
    for (const char *p = text; *p; p++) n++;
    return (float)n * (GLYPH_W + 1) * scale;
}

int ff_render_screenshot(const char *path, int w, int h)
{
    uint8_t *buf = (uint8_t *)malloc((size_t)w * h * 3);
    if (!buf) return 0;
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, buf);
    FILE *f = fopen(path, "wb");
    if (!f) { free(buf); return 0; }
    uint8_t hdr[18]; memset(hdr, 0, sizeof hdr);
    hdr[2] = 2;
    hdr[12]=(uint8_t)(w&0xFF); hdr[13]=(uint8_t)((w>>8)&0xFF);
    hdr[14]=(uint8_t)(h&0xFF); hdr[15]=(uint8_t)((h>>8)&0xFF);
    hdr[16] = 24;
    fwrite(hdr, sizeof hdr, 1, f);
    for (int i = 0; i < w*h; i++) { uint8_t bgr[3]={buf[i*3+2],buf[i*3+1],buf[i*3+0]}; fwrite(bgr,3,1,f); }
    fclose(f); free(buf);
    return 1;
}
