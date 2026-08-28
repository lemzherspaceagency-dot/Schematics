/* ff_render.h -- renderer: chunk meshes, the chamber pass, overlay UI. */
#ifndef FF_RENDER_H
#define FF_RENDER_H

#include "ff_math.h"
#include "ff_vault.h"

/* Per-vertex: position, atlas uv, then the three shading channels --
 * propagated light, wave-field pulse (what makes condensate shimmer), and a
 * baked ambient-occlusion times face-tint term. */
typedef struct {
    float x, y, z;
    float u, v;
    float light, pulse, shade;
} ff_vertex;

#define FF_ATLAS_TILES 16
#define FF_ATLAS_PX    (FF_ATLAS_TILES * 16)

typedef struct {
    vec3  eye;
    float yaw, pitch;
    float fov, aspect;
    mat4  view, proj, viewproj;
} ff_camera;

typedef struct {
    float time;
    float alert;        /* 0..1, how close the Bloom is to the core */
} ff_env;

int  ff_render_init(void);
int  ff_ui_init(void);
void ff_render_shutdown(void);
void ff_render_resize(int w, int h);

void ff_mesh_chunk(ff_vchunk *c);
void ff_mesh_release(ff_vchunk *c);

void ff_render_frame_begin(const ff_camera *cam, const ff_env *env);
void ff_render_void(const ff_camera *cam, const ff_env *env);
void ff_render_chunks(const ff_camera *cam, const ff_env *env);
void ff_render_selection_setup(const ff_camera *cam);
void ff_render_selection(int x, int y, int z, float tint);
void ff_render_box(vec3 center, vec3 half, float yaw, float r, float g, float b,
                   float emissive, const ff_camera *cam);
void ff_render_particle(vec3 pos, float size, float r, float g, float b, float a);
void ff_render_particles_flush(const ff_camera *cam);

/* ---- 2D overlay ------------------------------------------------------ */
void  ff_ui_begin(int w, int h);
void  ff_ui_end(void);
void  ff_ui_rect(float x, float y, float w, float h, float r, float g, float b, float a);
void  ff_ui_tile(float x, float y, float size, int tile, float bright);
void  ff_ui_text(float x, float y, float scale, float r, float g, float b, float a, const char *text);
float ff_ui_text_width(float scale, const char *text);

int  ff_render_screenshot(const char *path, int w, int h);
unsigned int ff_render_atlas_texture(void);

#endif /* FF_RENDER_H */
