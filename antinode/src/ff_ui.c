/* ff_ui.c -- batched 2D overlay: HUD panels, item icons and text.
 *
 * The font is a 5x7 bitmap authored inline and baked into a 64x64 texture at
 * startup, so the HUD needs no font file and no text shaping library.
 */
#include "ff_render.h"
#include "ff_gl.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ASCII 32..95, seven rows of five columns each. Lowercase input is folded
 * to uppercase at draw time. */
static const char *FONT[64] = {
    "...................................",  /* space */
    "..#....#....#....#....#.........#..",  /* ! */
    ".#.#..#.#..........................",  /* " */
    ".#.#..#.#.#####.#.#.#####.#.#..#.#.",  /* # */
    "..#...#####.#...###...#.#####...#..",  /* $ */
    "##..###..#...#...#...#...#..###..##",  /* % */
    ".##..#..#.#.#...#...#.#.##..#..##.#",  /* & */
    "..#....#...........................",  /* ' */
    "...#...#...#....#....#.....#.....#.",  /* ( */
    ".#.....#.....#....#....#...#...#...",  /* ) */
    ".....#.#.#.###.#####.###.#.#.#.....",  /* * */
    ".......#....#..#####..#....#.......",  /* + */
    "...........................##...#..",  /* , */
    "...............#####...............",  /* - */
    "..........................##...##..",  /* . */
    "....#...#....#...#...#....#...#....",  /* / */
    ".###.#...##..###.#.###..##...#.###.",  /* 0 */
    "..#...##....#....#....#....#...###.",  /* 1 */
    ".###.#...#....#...#...#...#...#####",  /* 2 */
    "#####...#...#.....#.....##...#.###.",  /* 3 */
    "...#...##..#.#.#..#.#####...#....#.",  /* 4 */
    "######....####.....#....##...#.###.",  /* 5 */
    "..##..#...#....####.#...##...#.###.",  /* 6 */
    "#####....#...#...#...#....#....#...",  /* 7 */
    ".###.#...##...#.###.#...##...#.###.",  /* 8 */
    ".###.#...##...#.####....#...#..##..",  /* 9 */
    "......##...##........##...##.......",  /* : */
    "......##...##........##....#...#...",  /* ; */
    "...#...#...#...#.....#.....#.....#.",  /* < */
    "..........#####.....#####..........",  /* = */
    ".#.....#.....#.....#...#...#...#...",  /* > */
    ".###.#...#....#...#...#.........#..",  /* ? */
    ".###.#...##.####.#.##.####.....###.",  /* @ */
    "..#...#.#.#...##...#######...##...#",  /* A */
    "####.#...##...#####.#...##...#####.",  /* B */
    ".###.#...##....#....#....#...#.###.",  /* C */
    "###..#..#.#...##...##...##..#.###..",  /* D */
    "######....#....####.#....#....#####",  /* E */
    "######....#....####.#....#....#....",  /* F */
    ".###.#...##....#.####...##...#.####",  /* G */
    "#...##...##...#######...##...##...#",  /* H */
    ".###...#....#....#....#....#...###.",  /* I */
    "..###...#....#....#....#.#..#..##..",  /* J */
    "#...##..#.#.#..##...#.#..#..#.#...#",  /* K */
    "#....#....#....#....#....#....#####",  /* L */
    "#...###.###.#.##.#.##...##...##...#",  /* M */
    "#...###..##.#.##..###...##...##...#",  /* N */
    ".###.#...##...##...##...##...#.###.",  /* O */
    "####.#...##...#####.#....#....#....",  /* P */
    ".###.#...##...##...##.#.##..#..##.#",  /* Q */
    "####.#...##...#####.#.#..#..#.#...#",  /* R */
    ".#####....#.....###.....#....#####.",  /* S */
    "#####..#....#....#....#....#....#..",  /* T */
    "#...##...##...##...##...##...#.###.",  /* U */
    "#...##...##...##...##...#.#.#...#..",  /* V */
    "#...##...##...##.#.##.#.###.###...#",  /* W */
    "#...##...#.#.#...#...#.#.#...##...#",  /* X */
    "#...##...#.#.#...#....#....#....#..",  /* Y */
    "#####....#...#...#...#...#....#####",  /* Z */
    ".###..#....#....#....#....#....###.",  /* [ */
    "#.....#....#.....#.....#....#.....#",  /* backslash */
    ".###....#....#....#....#....#..###.",  /* ] */
    "..#...#.#.#...#....................",  /* ^ */
    "..............................#####",  /* _ */
};

/* Each entry above is exactly GLYPH_W * GLYPH_H cells, row-major. */
#define GLYPH_W 5
#define GLYPH_H 7

static GLuint g_font_tex;
static GLuint P_ui, VAO_ui, VBO_ui;

typedef struct { float x, y, u, v, r, g, b, a; } ui_vert;

#define UI_MAX_VERTS 16384
static ui_vert g_verts[UI_MAX_VERTS];
static int     g_nverts;
static int     g_mode;          /* 0 solid, 1 font, 2 block atlas */
static int     g_w, g_h;

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
"  if (u_mode == 0) { frag = v_col; }\n"
"  else if (u_mode == 1) {\n"
"    float a = texture(u_tex, v_uv).r;\n"
"    if (a < 0.5) discard;\n"
"    frag = vec4(v_col.rgb, v_col.a);\n"
"  } else {\n"
"    vec4 t = texture(u_tex, v_uv);\n"
"    if (t.a < 0.35) discard;\n"
"    frag = vec4(t.rgb * v_col.rgb, t.a * v_col.a);\n"
"  }\n"
"}\n";

static void build_font_texture(void)
{
    /* 8x8 grid of 8x8 cells = 64x64, single channel. */
    static uint8_t px[64 * 64];
    memset(px, 0, sizeof px);
    for (int g = 0; g < 64; g++) {
        const char *rows = FONT[g];
        int len = (int)strlen(rows);
        int cx = (g % 8) * 8, cy = (g / 8) * 8;
        for (int y = 0; y < GLYPH_H; y++)
            for (int x = 0; x < GLYPH_W; x++) {
                int idx = y * GLYPH_W + x;
                char ch = (idx < len) ? rows[idx] : '.';
                if (ch == '#') px[(cy + y) * 64 + (cx + x)] = 255;
            }
    }
    glGenTextures(1, &g_font_tex);
    glBindTexture(GL_TEXTURE_2D, g_font_tex);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    /* Stored as RGBA so the shader can sample .r without needing GL_RED
     * swizzle support on every driver. */
    static uint8_t rgba[64 * 64 * 4];
    for (int i = 0; i < 64 * 64; i++) {
        rgba[i*4+0] = px[i]; rgba[i*4+1] = px[i];
        rgba[i*4+2] = px[i]; rgba[i*4+3] = px[i];
    }
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 64, 64, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 0);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

static GLuint ui_compile(void);

static void ui_flush(void)
{
    if (!g_nverts) return;
    glUseProgram(P_ui);
    glUniform2f(glGetUniformLocation(P_ui, "u_screen"), (float)g_w, (float)g_h);
    glUniform1i(glGetUniformLocation(P_ui, "u_mode"), g_mode);
    glUniform1i(glGetUniformLocation(P_ui, "u_tex"), 0);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, g_mode == 1 ? g_font_tex : ff_render_atlas_texture());

    glBindVertexArray(VAO_ui);
    glBindBuffer(GL_ARRAY_BUFFER, VBO_ui);
    glBufferSubData(GL_ARRAY_BUFFER, 0, (GLsizeiptr)(g_nverts * (int)sizeof(ui_vert)), g_verts);
    glDrawArrays(GL_TRIANGLES, 0, g_nverts);
    glBindVertexArray(0);
    g_nverts = 0;
}

static void ui_set_mode(int mode)
{
    if (mode != g_mode) { ui_flush(); g_mode = mode; }
}

static void push_quad(float x, float y, float w, float h,
                      float u0, float v0, float u1, float v1,
                      float r, float g, float b, float a)
{
    if (g_nverts + 6 > UI_MAX_VERTS) ui_flush();
    const float xs[6] = { x, x + w, x + w, x, x + w, x };
    const float ys[6] = { y, y, y + h, y, y + h, y + h };
    const float us[6] = { u0, u1, u1, u0, u1, u0 };
    const float vs[6] = { v0, v0, v1, v0, v1, v1 };
    for (int i = 0; i < 6; i++) {
        ui_vert *p = &g_verts[g_nverts++];
        p->x = xs[i]; p->y = ys[i];
        p->u = us[i]; p->v = vs[i];
        p->r = r; p->g = g; p->b = b; p->a = a;
    }
}

int ff_ui_init(void);
int ff_ui_init(void)
{
    P_ui = ui_compile();
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
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, sizeof(ui_vert), (void *)(2 * sizeof(float)));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, sizeof(ui_vert), (void *)(4 * sizeof(float)));
    glBindVertexArray(0);
    return 1;
}

void ff_ui_begin(int w, int h)
{
    g_w = w; g_h = h;
    g_nverts = 0;
    g_mode = 0;
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
    glEnable(GL_BLEND);
}

void ff_ui_end(void)
{
    ui_flush();
    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);
}

void ff_ui_rect(float x, float y, float w, float h, float r, float g, float b, float a)
{
    ui_set_mode(0);
    push_quad(x, y, w, h, 0, 0, 1, 1, r, g, b, a);
}

void ff_ui_tile(float x, float y, float size, int tile, float bright)
{
    ui_set_mode(2);
    int tx = tile % FF_ATLAS_TILES, ty = tile / FF_ATLAS_TILES;
    const float inset = 0.5f / (float)FF_ATLAS_PX;
    float u0 = (float)tx / FF_ATLAS_TILES + inset, u1 = (float)(tx + 1) / FF_ATLAS_TILES - inset;
    float v0 = (float)ty / FF_ATLAS_TILES + inset, v1 = (float)(ty + 1) / FF_ATLAS_TILES - inset;
    push_quad(x, y, size, size, u0, v0, u1, v1, bright, bright, bright, 1.0f);
}

void ff_ui_text(float x, float y, float scale, float r, float g, float b, float a, const char *text)
{
    ui_set_mode(1);
    float cx = x;
    for (const unsigned char *p = (const unsigned char *)text; *p; p++) {
        unsigned char ch = *p;
        if (ch == '\n') { cx = x; y += (GLYPH_H + 2) * scale; continue; }
        if (ch >= 'a' && ch <= 'z') ch = (unsigned char)(ch - 'a' + 'A');
        if (ch < 32 || ch > 95) ch = '?';
        int g_index = ch - 32;
        int cxi = (g_index % 8) * 8, cyi = (g_index / 8) * 8;
        float u0 = (float)cxi / 64.0f, v0 = (float)cyi / 64.0f;
        float u1 = (float)(cxi + GLYPH_W) / 64.0f, v1 = (float)(cyi + GLYPH_H) / 64.0f;
        if (ch != ' ')
            push_quad(cx, y, GLYPH_W * scale, GLYPH_H * scale, u0, v0, u1, v1, r, g, b, a);
        cx += (GLYPH_W + 1) * scale;
    }
}

float ff_ui_text_width(float scale, const char *text)
{
    int n = 0;
    for (const char *p = text; *p; p++) n++;
    return (float)n * (GLYPH_W + 1) * scale;
}

static GLuint ui_compile(void)
{
    GLuint vs = glCreateShader(GL_VERTEX_SHADER);
    glShaderSource(vs, 1, &VS_UI, NULL);
    glCompileShader(vs);
    GLuint fs = glCreateShader(GL_FRAGMENT_SHADER);
    glShaderSource(fs, 1, &FS_UI, NULL);
    glCompileShader(fs);
    GLint ok = 0;
    glGetShaderiv(vs, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[1024]; glGetShaderInfoLog(vs, sizeof log, NULL, log); fprintf(stderr, "[ui vs] %s\n", log); }
    glGetShaderiv(fs, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[1024]; glGetShaderInfoLog(fs, sizeof log, NULL, log); fprintf(stderr, "[ui fs] %s\n", log); }
    GLuint p = glCreateProgram();
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glLinkProgram(p);
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) { char log[1024]; glGetProgramInfoLog(p, sizeof log, NULL, log); fprintf(stderr, "[ui link] %s\n", log); return 0; }
    glDeleteShader(vs);
    glDeleteShader(fs);
    return p;
}
