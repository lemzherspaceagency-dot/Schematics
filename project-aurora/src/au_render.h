/* au_render.h -- static-mesh renderer for Project Aurora.
 *
 * Unlike the voxel engines this project's platform layer was proven on, the
 * lobby is a small hand-authored set piece: a handful of primitives baked
 * into one static VBO at startup, plus a few parts (Aurora's body, the door,
 * the signal pulse) that move and get their own small mesh drawn with a
 * per-call model matrix. There is exactly one shader: lit + emissive + alpha,
 * because nothing in one lobby needs more than that.
 */
#ifndef AU_RENDER_H
#define AU_RENDER_H

#include "ff_math.h"

typedef struct { float x,y,z, nx,ny,nz, r,g,b, e,a; } au_vertex;

/* A growable vertex list used both for the one big static buffer and for the
 * small per-part meshes (built once at init, then just transformed). */
typedef struct {
    au_vertex *v;
    int count, cap;
    unsigned int vao, vbo;
} au_mesh;

void au_mesh_init(au_mesh *m);
void au_mesh_upload(au_mesh *m);         /* call once after all appends */
void au_mesh_free(au_mesh *m);

/* Appenders -- all in the mesh's own local space, so a part built once (e.g.
 * "torso cylinder at local y=1.0") can be reused frame after frame with only
 * a model matrix changing. */
void au_add_box(au_mesh *m, vec3 center, vec3 half, vec3 color, float emissive, float alpha);
void au_add_cylinder(au_mesh *m, vec3 center, float radius_top, float radius_bot, float height,
                     int segs, vec3 color, float emissive, float alpha);
void au_add_sphere(au_mesh *m, vec3 center, float radius, int segs, vec3 color, float emissive, float alpha);
void au_add_ring(au_mesh *m, vec3 center, float radius, float tube, int segs,
                 vec3 color, float emissive, float alpha);

int  au_render_init(void);
int  au_ui_init(void);
void au_render_resize(int w, int h);

typedef struct {
    vec3 eye; float yaw, pitch, fov, aspect;
    mat4 view, proj, viewproj;
} au_camera;

void au_render_frame_begin(const au_camera *cam);
/* model: world transform. tint: multiplies the mesh's baked color/alpha --
 * (1,1,1,1) draws it as authored; used at runtime for the door lock light,
 * the pulse and the conduit going from amber to solved-green. */
void au_render_mesh(const au_mesh *m, mat4 model, float tr, float tg, float tb, float ta, const au_camera *cam);

/* ---- 2D overlay -------------------------------------------------------- */
void  au_ui_begin(int w, int h);
void  au_ui_end(void);
void  au_ui_rect(float x, float y, float w, float h, float r, float g, float b, float a);
void  au_ui_text(float x, float y, float scale, float r, float g, float b, float a, const char *text);
float au_ui_text_width(float scale, const char *text);

int ff_render_screenshot(const char *path, int w, int h);   /* shared TGA writer */

#endif /* AU_RENDER_H */
