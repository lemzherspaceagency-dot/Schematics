/* ff_render.c -- the 3D renderer for ANTINODE.
 *
 * Every texture is synthesised at startup rather than loaded, so the shipped
 * executable is a single file with no data directory beside it.
 */
#include "ff_render.h"
#include "ff_gl.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ===================================================================== *
 *  Shader helpers
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
        fprintf(stderr, "[shader] %s failed to compile:\n%s\n", label, log);
        glDeleteShader(s);
        return 0;
    }
    return s;
}

static GLuint link_program(const char *vs_src, const char *fs_src, const char *label)
{
    GLuint vs = compile(GL_VERTEX_SHADER, vs_src, label);
    GLuint fs = compile(GL_FRAGMENT_SHADER, fs_src, label);
    if (!vs || !fs) return 0;
    GLuint p = glCreateProgram();
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glLinkProgram(p);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetProgramInfoLog(p, sizeof log, NULL, log);
        fprintf(stderr, "[shader] %s failed to link:\n%s\n", label, log);
        glDeleteProgram(p);
        p = 0;
    }
    glDeleteShader(vs);
    glDeleteShader(fs);
    return p;
}

/* ===================================================================== *
 *  Procedural atlas
 * ===================================================================== */

static GLuint  g_atlas;
static uint8_t *g_pixels;

static void px_set(int tile, int x, int y, int r, int g, int b, int a)
{
    int tx = (tile % FF_ATLAS_TILES) * 16 + x;
    int ty = (tile / FF_ATLAS_TILES) * 16 + y;
    if (tx < 0 || ty < 0 || tx >= FF_ATLAS_PX || ty >= FF_ATLAS_PX) return;
    uint8_t *p = g_pixels + ((size_t)ty * FF_ATLAS_PX + tx) * 4;
    p[0] = (uint8_t)ff_clampi(r, 0, 255);
    p[1] = (uint8_t)ff_clampi(g, 0, 255);
    p[2] = (uint8_t)ff_clampi(b, 0, 255);
    p[3] = (uint8_t)ff_clampi(a, 0, 255);
}

static float tnoise(int tile, int x, int y, int scale)
{
    float n = 0.0f, amp = 1.0f, tot = 0.0f;
    for (int o = 0; o < 2; o++) {
        int s = scale << o;
        n += amp * ff_hash3f(x * s / 16, y * s / 16, tile * 31 + o, 0xA17A5u);
        tot += amp;
        amp *= 0.5f;
    }
    return n / tot;
}

static void build_atlas(void)
{
    memset(g_pixels, 0, (size_t)FF_ATLAS_PX * FF_ATLAS_PX * 4);

    /* 1 bedrock -- near-black rock with cold mineral threads */
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
            float n = ff_hash3f(x, y, 1, 0x51A7u);
            float m = tnoise(1, x, y, 4);
            int v = (int)(46 + n * 18 + m * 16);
            int vein = (m > 0.63f && m < 0.69f);
            px_set(1, x, y, v + (vein ? 14 : 0), v + 2 + (vein ? 20 : 0), v + 7 + (vein ? 30 : 0), 255);
        }

    /* 2 condensate -- pale crystal with faceted striations */
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
            float facet = sinf((float)(x + y) * 0.85f) * 0.5f + 0.5f;
            float n = ff_hash3f(x, y, 2, 0x33Bu);
            int v = (int)(150 + facet * 62 + n * 26);
            px_set(2, x, y, (int)(v * 0.72f), (int)(v * 0.94f), v, 255);
        }

    /* 3 bloom -- wet magenta crust threaded with hot orange */
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
            float m = tnoise(3, x, y, 5);
            float n = ff_hash3f(x, y, 3, 0x9Fu);
            if (m > 0.60f) px_set(3, x, y, (int)(224 + n * 20), (int)(96 + n * 40), 38, 255);
            else if (m < 0.36f) px_set(3, x, y, (int)(64 + n * 22), 12, (int)(44 + n * 20), 255);
            else px_set(3, x, y, (int)(158 + n * 40), (int)(30 + n * 26), (int)(88 + n * 30), 255);
        }

    /* 4 anchor -- machined amber alloy */
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
            int groove = (y % 4 == 0);
            int edge = (x == 0 || x == 15);
            float n = ff_hash3f(x, y, 4, 0x4Du);
            int v = (int)(176 + n * 26) - (groove ? 52 : 0) - (edge ? 34 : 0);
            px_set(4, x, y, v, (int)(v * 0.74f), (int)(v * 0.30f), 255);
        }

    /* 5 core -- concentric rings around a bright centre */
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
            float dx = (float)x - 7.5f, dy = (float)y - 7.5f;
            float d = sqrtf(dx * dx + dy * dy);
            float ring = sinf(d * 1.65f) * 0.5f + 0.5f;
            int v = (int)(150 + ring * 95);
            px_set(5, x, y, (int)(v * 0.78f), (int)(v * 0.92f), v, 255);
        }

    glGenTextures(1, &g_atlas);
    glBindTexture(GL_TEXTURE_2D, g_atlas);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, FF_ATLAS_PX, FF_ATLAS_PX, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, g_pixels);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 3);
    glGenerateMipmap(GL_TEXTURE_2D);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST_MIPMAP_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

unsigned int ff_render_atlas_texture(void) { return g_atlas; }

/* ===================================================================== *
 *  Shaders
 * ===================================================================== */

static const char *VS_CHUNK =
"#version 330 core\n"
"layout(location=0) in vec3 a_pos;\n"
"layout(location=1) in vec2 a_uv;\n"
"layout(location=2) in vec3 a_shade;   // light, pulse, ao*tint\n"
"uniform mat4 u_viewproj;\n"
"uniform vec3 u_eye;\n"
"out vec2 v_uv; out vec3 v_shade; out float v_dist;\n"
"void main(){\n"
"  gl_Position = u_viewproj * vec4(a_pos, 1.0);\n"
"  v_uv = a_uv; v_shade = a_shade;\n"
"  v_dist = length(a_pos - u_eye);\n"
"}\n";

static const char *FS_CHUNK =
"#version 330 core\n"
"in vec2 v_uv; in vec3 v_shade; in float v_dist;\n"
"uniform sampler2D u_atlas;\n"
"uniform vec3  u_fog_color;\n"
"uniform float u_fog_density, u_time, u_lamp_range;\n"
"out vec4 frag;\n"
"void main(){\n"
"  vec4 tex = texture(u_atlas, v_uv);\n"
"  float lit = v_shade.x;\n"
"  // Propagated light is warm-neutral; the residue of the wave field adds a\n"
"  // cold shimmer that breathes, so live condensate never looks like stone.\n"
"  vec3 light = vec3(0.95,0.99,1.05) * lit;\n"
"  // The suit lamp. Everything here is unlit rock until you point at it.\n"
"  float lamp = pow(clamp(1.0 - v_dist / u_lamp_range, 0.0, 1.0), 1.6);\n"
"  light += vec3(1.00,0.96,0.88) * lamp * 0.80;\n"
"  float breathe = 0.62 + 0.38 * sin(u_time * 2.1 + v_shade.y * 9.0);\n"
"  light += vec3(0.30,0.72,0.95) * v_shade.y * breathe * 0.85;\n"
"  light = clamp(light, vec3(0.055,0.062,0.080), vec3(1.25));\n"
"  vec3 col = tex.rgb * v_shade.z * light;\n"
"  float f = exp(-pow(max(v_dist,0.0) * u_fog_density, 1.30));\n"
"  frag = vec4(mix(u_fog_color, col, clamp(f,0.0,1.0)), 1.0);\n"
"}\n";

static const char *VS_VOID =
"#version 330 core\n"
"layout(location=0) in vec2 a_pos;\n"
"uniform vec3 u_right, u_up, u_fwd;\n"
"uniform float u_tan_half, u_aspect;\n"
"out vec3 v_ray;\n"
"void main(){\n"
"  gl_Position = vec4(a_pos, 0.0, 1.0);\n"
"  v_ray = normalize(u_fwd + u_right * a_pos.x * u_tan_half * u_aspect + u_up * a_pos.y * u_tan_half);\n"
"}\n";

static const char *FS_VOID =
"#version 330 core\n"
"in vec3 v_ray;\n"
"uniform vec3 u_fog_color;\n"
"uniform float u_time;\n"
"out vec4 frag;\n"
"void main(){\n"
"  vec3 d = normalize(v_ray);\n"
"  // Barely-there vertical gradient so the dark still reads as a volume.\n"
"  vec3 col = u_fog_color * (0.72 + 0.55 * clamp(d.y * 0.5 + 0.5, 0.0, 1.0));\n"
"  vec3 g = floor(d * 240.0);\n"
"  float r = fract(sin(dot(g, vec3(12.9898,78.233,37.719))) * 43758.5453);\n"
"  if (r > 0.9990) col += vec3(0.30,0.52,0.68) * (r - 0.9990) * 520.0;\n"
"  frag = vec4(col, 1.0);\n"
"}\n";

static const char *VS_SOLID =
"#version 330 core\n"
"layout(location=0) in vec3 a_pos;\n"
"layout(location=1) in vec3 a_nrm;\n"
"uniform mat4 u_viewproj, u_model;\n"
"uniform vec3 u_eye;\n"
"out vec3 v_nrm; out float v_dist;\n"
"void main(){\n"
"  vec4 wp = u_model * vec4(a_pos,1.0);\n"
"  gl_Position = u_viewproj * wp;\n"
"  v_nrm = mat3(u_model) * a_nrm;\n"
"  v_dist = length(wp.xyz - u_eye);\n"
"}\n";

static const char *FS_SOLID =
"#version 330 core\n"
"in vec3 v_nrm; in float v_dist;\n"
"uniform vec4 u_color;\n"
"uniform vec3 u_fog_color;\n"
"uniform float u_fog_density, u_emissive;\n"
"out vec4 frag;\n"
"void main(){\n"
"  vec3 n = normalize(v_nrm);\n"
"  float d = 0.55 + 0.45 * max(dot(n, normalize(vec3(0.4,0.85,0.3))), 0.0);\n"
"  vec3 col = u_color.rgb * mix(d * 0.5, 1.35, u_emissive);\n"
"  float f = exp(-pow(max(v_dist,0.0) * u_fog_density, 1.30));\n"
"  frag = vec4(mix(u_fog_color, col, clamp(f,0.0,1.0)), u_color.a);\n"
"}\n";

static const char *VS_LINE =
"#version 330 core\n"
"layout(location=0) in vec3 a_pos;\n"
"uniform mat4 u_viewproj; uniform vec3 u_offset;\n"
"void main(){ gl_Position = u_viewproj * vec4(a_pos + u_offset, 1.0); }\n";

static const char *FS_LINE =
"#version 330 core\n"
"uniform vec4 u_color; out vec4 frag;\n"
"void main(){ frag = u_color; }\n";

static const char *VS_PART =
"#version 330 core\n"
"layout(location=0) in vec3 a_pos;\n"
"layout(location=1) in vec4 a_col;\n"
"layout(location=2) in float a_size;\n"
"uniform mat4 u_viewproj; uniform float u_vh;\n"
"out vec4 v_col;\n"
"void main(){\n"
"  gl_Position = u_viewproj * vec4(a_pos,1.0);\n"
"  gl_PointSize = clamp(a_size * u_vh / max(gl_Position.w,0.01), 1.0, 30.0);\n"
"  v_col = a_col;\n"
"}\n";

static const char *FS_PART =
"#version 330 core\n"
"in vec4 v_col;\n"
"out vec4 frag;\n"
"void main(){\n"
"  vec2 d = gl_PointCoord - vec2(0.5);\n"
"  float r = dot(d,d);\n"
"  if (r > 0.25) discard;\n"
"  frag = vec4(v_col.rgb, clamp(v_col.a * (1.0 - r*3.4), 0.0, 1.0));\n"
"}\n";

/* ===================================================================== *
 *  State
 * ===================================================================== */

static GLuint P_chunk, P_void, P_solid, P_line, P_part;
static GLuint VAO_quad, VBO_quad, VAO_cube, VBO_cube, VAO_line, VBO_line, VAO_part, VBO_part;
static float  g_fog_color[3];
static float  g_fog_density = 0.021f;
static int    g_vp_h = 720;

static struct { float x, y, z, r, g, b, a, size; } g_particles[8192];
static int g_particle_count;

#define GET(p, n) glGetUniformLocation(p, n)

static void build_cube(void)
{
    static const float F[6][3] = { {1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1} };
    static const float V[6][4][3] = {
        { {.5f,-.5f,.5f},{.5f,-.5f,-.5f},{.5f,.5f,-.5f},{.5f,.5f,.5f} },
        { {-.5f,-.5f,-.5f},{-.5f,-.5f,.5f},{-.5f,.5f,.5f},{-.5f,.5f,-.5f} },
        { {-.5f,.5f,.5f},{.5f,.5f,.5f},{.5f,.5f,-.5f},{-.5f,.5f,-.5f} },
        { {-.5f,-.5f,-.5f},{.5f,-.5f,-.5f},{.5f,-.5f,.5f},{-.5f,-.5f,.5f} },
        { {-.5f,-.5f,.5f},{.5f,-.5f,.5f},{.5f,.5f,.5f},{-.5f,.5f,.5f} },
        { {.5f,-.5f,-.5f},{-.5f,-.5f,-.5f},{-.5f,.5f,-.5f},{.5f,.5f,-.5f} },
    };
    float data[6 * 6 * 6];
    int n = 0;
    for (int f = 0; f < 6; f++) {
        static const int TRI[6] = { 0,1,2, 0,2,3 };
        for (int i = 0; i < 6; i++) {
            int c = TRI[i];
            data[n++] = V[f][c][0]; data[n++] = V[f][c][1]; data[n++] = V[f][c][2];
            data[n++] = F[f][0];    data[n++] = F[f][1];    data[n++] = F[f][2];
        }
    }
    glGenVertexArrays(1, &VAO_cube);
    glGenBuffers(1, &VBO_cube);
    glBindVertexArray(VAO_cube);
    glBindBuffer(GL_ARRAY_BUFFER, VBO_cube);
    glBufferData(GL_ARRAY_BUFFER, sizeof data, data, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void *)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void *)(3 * sizeof(float)));
    glBindVertexArray(0);
}

static void build_line_cube(void)
{
    static const float E[24][3] = {
        {0,0,0},{1,0,0}, {1,0,0},{1,0,1}, {1,0,1},{0,0,1}, {0,0,1},{0,0,0},
        {0,1,0},{1,1,0}, {1,1,0},{1,1,1}, {1,1,1},{0,1,1}, {0,1,1},{0,1,0},
        {0,0,0},{0,1,0}, {1,0,0},{1,1,0}, {1,0,1},{1,1,1}, {0,0,1},{0,1,1},
    };
    glGenVertexArrays(1, &VAO_line);
    glGenBuffers(1, &VBO_line);
    glBindVertexArray(VAO_line);
    glBindBuffer(GL_ARRAY_BUFFER, VBO_line);
    glBufferData(GL_ARRAY_BUFFER, sizeof E, E, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(float), (void *)0);
    glBindVertexArray(0);
}

int ff_render_init(void)
{
    g_pixels = (uint8_t *)malloc((size_t)FF_ATLAS_PX * FF_ATLAS_PX * 4);
    if (!g_pixels) return 0;

    P_chunk = link_program(VS_CHUNK, FS_CHUNK, "chunk");
    P_void  = link_program(VS_VOID,  FS_VOID,  "void");
    P_solid = link_program(VS_SOLID, FS_SOLID, "solid");
    P_line  = link_program(VS_LINE,  FS_LINE,  "line");
    P_part  = link_program(VS_PART,  FS_PART,  "particle");
    if (!P_chunk || !P_void || !P_solid || !P_line || !P_part) return 0;

    build_atlas();
    build_cube();
    build_line_cube();

    {
        static const float q[8] = { -1,-1, 1,-1, -1,1, 1,1 };
        glGenVertexArrays(1, &VAO_quad);
        glGenBuffers(1, &VBO_quad);
        glBindVertexArray(VAO_quad);
        glBindBuffer(GL_ARRAY_BUFFER, VBO_quad);
        glBufferData(GL_ARRAY_BUFFER, sizeof q, q, GL_STATIC_DRAW);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float), (void *)0);
        glBindVertexArray(0);
    }
    {
        glGenVertexArrays(1, &VAO_part);
        glGenBuffers(1, &VBO_part);
        glBindVertexArray(VAO_part);
        glBindBuffer(GL_ARRAY_BUFFER, VBO_part);
        glBufferData(GL_ARRAY_BUFFER, sizeof g_particles, NULL, GL_STREAM_DRAW);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void *)0);
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void *)(3 * sizeof(float)));
        glEnableVertexAttribArray(2);
        glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void *)(7 * sizeof(float)));
        glBindVertexArray(0);
    }

    ff_vault_set_mesh_release(ff_mesh_release);

    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glFrontFace(GL_CCW);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    return 1;
}

void ff_render_shutdown(void) { free(g_pixels); g_pixels = NULL; }

void ff_render_resize(int w, int h)
{
    glViewport(0, 0, w, h);
    g_vp_h = h > 0 ? h : 720;
}

void ff_render_frame_begin(const ff_camera *cam, const ff_env *env)
{
    (void)cam;
    /* The chamber is lightless; the fog is what the dark actually looks like.
     * It reddens as the Bloom closes on the core. */
    float a = ff_clampf(env->alert, 0.0f, 1.0f);
    g_fog_color[0] = ff_lerp(0.016f, 0.085f, a);
    g_fog_color[1] = ff_lerp(0.022f, 0.012f, a);
    g_fog_color[2] = ff_lerp(0.038f, 0.028f, a);
    g_fog_density  = 0.0205f;
    glClearColor(g_fog_color[0], g_fog_color[1], g_fog_color[2], 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
}

void ff_render_void(const ff_camera *cam, const ff_env *env)
{
    glDisable(GL_DEPTH_TEST);
    glDepthMask(GL_FALSE);
    glUseProgram(P_void);
    vec3 fwd = ff_dir_from_angles(cam->yaw, cam->pitch);
    vec3 right = v3norm(v3cross(fwd, v3(0, 1, 0)));
    vec3 up = v3cross(right, fwd);
    glUniform3f(GET(P_void, "u_right"), right.x, right.y, right.z);
    glUniform3f(GET(P_void, "u_up"), up.x, up.y, up.z);
    glUniform3f(GET(P_void, "u_fwd"), fwd.x, fwd.y, fwd.z);
    glUniform1f(GET(P_void, "u_tan_half"), tanf(cam->fov * FF_DEG2RAD * 0.5f));
    glUniform1f(GET(P_void, "u_aspect"), cam->aspect);
    glUniform3f(GET(P_void, "u_fog_color"), g_fog_color[0], g_fog_color[1], g_fog_color[2]);
    glUniform1f(GET(P_void, "u_time"), env->time);
    glBindVertexArray(VAO_quad);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    glBindVertexArray(0);
    glEnable(GL_DEPTH_TEST);
    glDepthMask(GL_TRUE);
}

void ff_render_chunks(const ff_camera *cam, const ff_env *env)
{
    glUseProgram(P_chunk);
    glUniformMatrix4fv(GET(P_chunk, "u_viewproj"), 1, GL_FALSE, cam->viewproj.m);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, g_atlas);
    glUniform1i(GET(P_chunk, "u_atlas"), 0);
    glUniform3f(GET(P_chunk, "u_fog_color"), g_fog_color[0], g_fog_color[1], g_fog_color[2]);
    glUniform1f(GET(P_chunk, "u_fog_density"), g_fog_density);
    glUniform1f(GET(P_chunk, "u_time"), env->time);
    glUniform3f(GET(P_chunk, "u_eye"), cam->eye.x, cam->eye.y, cam->eye.z);
    glUniform1f(GET(P_chunk, "u_lamp_range"), 40.0f);

    glDisable(GL_BLEND);
    for (int i = 0; i < VA_CHUNK_COUNT; i++) {
        ff_vchunk *c = ff_vault_chunk(i);
        if (!c || !c->vert_count) continue;
        glBindVertexArray(c->vao);
        glDrawArrays(GL_TRIANGLES, 0, (GLsizei)c->vert_count);
    }
    glBindVertexArray(0);
}

void ff_render_selection_setup(const ff_camera *cam)
{
    glUseProgram(P_line);
    glUniformMatrix4fv(GET(P_line, "u_viewproj"), 1, GL_FALSE, cam->viewproj.m);
}

void ff_render_selection(int x, int y, int z, float tint)
{
    glUseProgram(P_line);
    glUniform3f(GET(P_line, "u_offset"), (float)x - 0.003f, (float)y - 0.003f, (float)z - 0.003f);
    glUniform4f(GET(P_line, "u_color"), 0.55f + tint * 0.45f, 0.95f, 1.0f, 0.85f);
    glEnable(GL_BLEND);
    glBindVertexArray(VAO_line);
    glDrawArrays(GL_LINES, 0, 24);
    glBindVertexArray(0);
}

void ff_render_box(vec3 center, vec3 half, float yaw, float r, float g, float b,
                   float emissive, const ff_camera *cam)
{
    mat4 model = mat4_mul(mat4_translate(center),
                  mat4_mul(mat4_rotate_y(yaw), mat4_scale(v3(half.x * 2, half.y * 2, half.z * 2))));
    glUseProgram(P_solid);
    glUniformMatrix4fv(GET(P_solid, "u_viewproj"), 1, GL_FALSE, cam->viewproj.m);
    glUniformMatrix4fv(GET(P_solid, "u_model"), 1, GL_FALSE, model.m);
    glUniform4f(GET(P_solid, "u_color"), r, g, b, 1.0f);
    glUniform3f(GET(P_solid, "u_fog_color"), g_fog_color[0], g_fog_color[1], g_fog_color[2]);
    glUniform1f(GET(P_solid, "u_fog_density"), g_fog_density);
    glUniform1f(GET(P_solid, "u_emissive"), emissive);
    glUniform3f(GET(P_solid, "u_eye"), cam->eye.x, cam->eye.y, cam->eye.z);
    glBindVertexArray(VAO_cube);
    glDrawArrays(GL_TRIANGLES, 0, 36);
    glBindVertexArray(0);
}

void ff_render_particle(vec3 pos, float size, float r, float g, float b, float a)
{
    if (g_particle_count >= (int)(sizeof g_particles / sizeof g_particles[0])) return;
    int i = g_particle_count++;
    g_particles[i].x = pos.x; g_particles[i].y = pos.y; g_particles[i].z = pos.z;
    g_particles[i].r = r; g_particles[i].g = g; g_particles[i].b = b; g_particles[i].a = a;
    g_particles[i].size = size;
}

void ff_render_particles_flush(const ff_camera *cam)
{
    if (!g_particle_count) return;
    glUseProgram(P_part);
    glUniformMatrix4fv(GET(P_part, "u_viewproj"), 1, GL_FALSE, cam->viewproj.m);
    glUniform1f(GET(P_part, "u_vh"), (float)g_vp_h);
    glBindVertexArray(VAO_part);
    glBindBuffer(GL_ARRAY_BUFFER, VBO_part);
    glBufferSubData(GL_ARRAY_BUFFER, 0, (GLsizeiptr)(g_particle_count * 8 * (int)sizeof(float)), g_particles);
    glEnable(GL_BLEND);
    glDepthMask(GL_FALSE);
    glDrawArrays(GL_POINTS, 0, g_particle_count);
    glDepthMask(GL_TRUE);
    glBindVertexArray(0);
    g_particle_count = 0;
}

/* ===================================================================== *
 *  Screenshot -- uncompressed TGA, no image library needed
 * ===================================================================== */

int ff_render_screenshot(const char *path, int w, int h)
{
    uint8_t *buf = (uint8_t *)malloc((size_t)w * h * 3);
    if (!buf) return 0;
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, buf);

    FILE *f = fopen(path, "wb");
    if (!f) { free(buf); return 0; }
    uint8_t hdr[18];
    memset(hdr, 0, sizeof hdr);
    hdr[2] = 2;
    hdr[12] = (uint8_t)(w & 0xFF); hdr[13] = (uint8_t)((w >> 8) & 0xFF);
    hdr[14] = (uint8_t)(h & 0xFF); hdr[15] = (uint8_t)((h >> 8) & 0xFF);
    hdr[16] = 24;
    fwrite(hdr, sizeof hdr, 1, f);
    for (int i = 0; i < w * h; i++) {
        uint8_t bgr[3] = { buf[i*3+2], buf[i*3+1], buf[i*3+0] };
        fwrite(bgr, 3, 1, f);
    }
    fclose(f);
    free(buf);
    return 1;
}
