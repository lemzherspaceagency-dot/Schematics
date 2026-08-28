/* ff_math.h -- vectors, column-major 4x4 matrices, RNG and gradient noise. */
#ifndef FF_MATH_H
#define FF_MATH_H

#include <math.h>
#include <stdint.h>

#define FF_PI  3.14159265358979323846f
#define FF_TAU 6.28318530717958647692f
#define FF_DEG2RAD (FF_PI / 180.0f)

typedef struct { float x, y, z; } vec3;
typedef struct { float m[16]; } mat4;   /* column-major, GL layout */

static inline vec3  v3(float x, float y, float z)   { vec3 r = {x, y, z}; return r; }
static inline vec3  v3add(vec3 a, vec3 b)           { return v3(a.x+b.x, a.y+b.y, a.z+b.z); }
static inline vec3  v3sub(vec3 a, vec3 b)           { return v3(a.x-b.x, a.y-b.y, a.z-b.z); }
static inline vec3  v3mul(vec3 a, float s)          { return v3(a.x*s, a.y*s, a.z*s); }
static inline float v3dot(vec3 a, vec3 b)           { return a.x*b.x + a.y*b.y + a.z*b.z; }
static inline float v3len(vec3 a)                   { return sqrtf(v3dot(a, a)); }
static inline vec3  v3cross(vec3 a, vec3 b) {
    return v3(a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x);
}
static inline vec3 v3norm(vec3 a) {
    float l = v3len(a);
    return (l > 1e-6f) ? v3mul(a, 1.0f / l) : v3(0, 0, 0);
}

static inline float ff_clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
static inline float ff_minf(float a, float b) { return a < b ? a : b; }
static inline float ff_maxf(float a, float b) { return a > b ? a : b; }
static inline float ff_lerp(float a, float b, float t) { return a + (b - a) * t; }
static inline int   ff_mini(int a, int b) { return a < b ? a : b; }
static inline int   ff_maxi(int a, int b) { return a > b ? a : b; }
static inline int   ff_clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* Floor division / modulo that stay correct for negative coordinates, which
 * matters everywhere we map world blocks onto chunk grids. */
static inline int ff_floordiv(int a, int b) { int q = a / b; if ((a % b) && ((a < 0) != (b < 0))) q--; return q; }
static inline int ff_floormod(int a, int b) { int r = a % b; if (r && ((r < 0) != (b < 0))) r += b; return r; }

/* ---- matrices ---------------------------------------------------------- */

static inline mat4 mat4_identity(void) {
    mat4 r = {{1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1}};
    return r;
}

static inline mat4 mat4_mul(mat4 a, mat4 b) {
    mat4 r;
    for (int c = 0; c < 4; c++)
        for (int row = 0; row < 4; row++) {
            float s = 0.0f;
            for (int k = 0; k < 4; k++) s += a.m[k*4 + row] * b.m[c*4 + k];
            r.m[c*4 + row] = s;
        }
    return r;
}

static inline mat4 mat4_perspective(float fov_deg, float aspect, float znear, float zfar) {
    mat4 r = {{0}};
    float f = 1.0f / tanf(fov_deg * FF_DEG2RAD * 0.5f);
    r.m[0]  = f / aspect;
    r.m[5]  = f;
    r.m[10] = (zfar + znear) / (znear - zfar);
    r.m[11] = -1.0f;
    r.m[14] = (2.0f * zfar * znear) / (znear - zfar);
    return r;
}

static inline mat4 mat4_ortho(float l, float r_, float b, float t, float n, float f) {
    mat4 r = {{0}};
    r.m[0]  =  2.0f / (r_ - l);
    r.m[5]  =  2.0f / (t - b);
    r.m[10] = -2.0f / (f - n);
    r.m[12] = -(r_ + l) / (r_ - l);
    r.m[13] = -(t + b) / (t - b);
    r.m[14] = -(f + n) / (f - n);
    r.m[15] =  1.0f;
    return r;
}

static inline mat4 mat4_look(vec3 eye, vec3 fwd, vec3 up) {
    vec3 f = v3norm(fwd);
    vec3 s = v3norm(v3cross(f, up));
    vec3 u = v3cross(s, f);
    mat4 r = mat4_identity();
    r.m[0] = s.x; r.m[4] = s.y; r.m[8]  = s.z;
    r.m[1] = u.x; r.m[5] = u.y; r.m[9]  = u.z;
    r.m[2] = -f.x; r.m[6] = -f.y; r.m[10] = -f.z;
    r.m[12] = -v3dot(s, eye);
    r.m[13] = -v3dot(u, eye);
    r.m[14] =  v3dot(f, eye);
    return r;
}

static inline mat4 mat4_translate(vec3 t) {
    mat4 r = mat4_identity();
    r.m[12] = t.x; r.m[13] = t.y; r.m[14] = t.z;
    return r;
}

static inline mat4 mat4_scale(vec3 s) {
    mat4 r = mat4_identity();
    r.m[0] = s.x; r.m[5] = s.y; r.m[10] = s.z;
    return r;
}

static inline mat4 mat4_rotate_y(float rad) {
    mat4 r = mat4_identity();
    float c = cosf(rad), s = sinf(rad);
    r.m[0] = c; r.m[2] = -s; r.m[8] = s; r.m[10] = c;
    return r;
}

/* Direction vector from yaw (around Y) and pitch, the convention the camera
 * and every creature uses. */
static inline vec3 ff_dir_from_angles(float yaw, float pitch) {
    float cp = cosf(pitch);
    return v3(cosf(yaw) * cp, sinf(pitch), sinf(yaw) * cp);
}

/* ---- deterministic RNG -------------------------------------------------- */

typedef struct { uint64_t s; } ff_rng;

static inline void ff_rng_seed(ff_rng *r, uint64_t seed) { r->s = seed ? seed : 0x9E3779B97F4A7C15ull; }

static inline uint32_t ff_rng_u32(ff_rng *r) {
    uint64_t x = r->s;
    x ^= x << 13; x ^= x >> 7; x ^= x << 17;
    r->s = x;
    return (uint32_t)(x >> 32);
}
static inline float ff_rng_f(ff_rng *r) { return (float)(ff_rng_u32(r) >> 8) / 16777216.0f; }
static inline float ff_rng_range(ff_rng *r, float lo, float hi) { return lo + ff_rng_f(r) * (hi - lo); }

/* Stateless integer hash -- used for per-block texture jitter and scatter
 * decisions that must stay identical between runs. */
static inline uint32_t ff_hash3(int x, int y, int z, uint32_t seed) {
    uint32_t h = seed ^ 0x9E3779B9u;
    h ^= (uint32_t)x * 0x85EBCA6Bu; h = (h << 13) | (h >> 19);
    h ^= (uint32_t)y * 0xC2B2AE35u; h = (h << 17) | (h >> 15);
    h ^= (uint32_t)z * 0x27D4EB2Fu; h = (h << 11) | (h >> 21);
    h ^= h >> 15; h *= 0x2545F491u; h ^= h >> 13;
    return h;
}
static inline float ff_hash3f(int x, int y, int z, uint32_t seed) {
    return (float)(ff_hash3(x, y, z, seed) >> 8) / 16777216.0f;
}

/* ---- gradient noise ----------------------------------------------------- */

void  ff_noise_init(uint32_t seed);
float ff_noise3(float x, float y, float z);
float ff_noise2(float x, float y);
/* Fractal sums. ridged() is what carves the trench walls and cave systems. */
float ff_fbm2(float x, float y, int octaves, float lacunarity, float gain);
float ff_fbm3(float x, float y, float z, int octaves, float lacunarity, float gain);
float ff_ridged2(float x, float y, int octaves);

#endif /* FF_MATH_H */
