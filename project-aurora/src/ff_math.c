#include "ff_math.h"

/* Classic Perlin gradient noise over a seeded permutation table. The table is
 * built once per world so a seed always reproduces the same ocean floor. */

static unsigned char g_perm[512];

void ff_noise_init(uint32_t seed)
{
    unsigned char p[256];
    ff_rng rng;
    ff_rng_seed(&rng, ((uint64_t)seed << 16) ^ 0xDEADBEEFCAFEull ^ seed);

    for (int i = 0; i < 256; i++) p[i] = (unsigned char)i;
    for (int i = 255; i > 0; i--) {           /* Fisher-Yates */
        int j = (int)(ff_rng_u32(&rng) % (uint32_t)(i + 1));
        unsigned char t = p[i]; p[i] = p[j]; p[j] = t;
    }
    for (int i = 0; i < 512; i++) g_perm[i] = p[i & 255];
}

static inline float fade(float t) { return t * t * t * (t * (t * 6.0f - 15.0f) + 10.0f); }

static inline float grad3(int hash, float x, float y, float z)
{
    switch (hash & 15) {
        case 0:  return  x + y;   case 1:  return -x + y;
        case 2:  return  x - y;   case 3:  return -x - y;
        case 4:  return  x + z;   case 5:  return -x + z;
        case 6:  return  x - z;   case 7:  return -x - z;
        case 8:  return  y + z;   case 9:  return -y + z;
        case 10: return  y - z;   case 11: return -y - z;
        case 12: return  x + y;   case 13: return -y + z;
        case 14: return -x + y;   default: return -y - z;
    }
}

float ff_noise3(float x, float y, float z)
{
    int xi = (int)floorf(x) & 255, yi = (int)floorf(y) & 255, zi = (int)floorf(z) & 255;
    float xf = x - floorf(x), yf = y - floorf(y), zf = z - floorf(z);
    float u = fade(xf), v = fade(yf), w = fade(zf);

    int a  = g_perm[xi] + yi,     aa = g_perm[a] + zi,     ab = g_perm[a + 1] + zi;
    int b  = g_perm[xi + 1] + yi, ba = g_perm[b] + zi,     bb = g_perm[b + 1] + zi;

    float x1 = ff_lerp(grad3(g_perm[aa],     xf,        yf,        zf),
                       grad3(g_perm[ba],     xf - 1.0f, yf,        zf), u);
    float x2 = ff_lerp(grad3(g_perm[ab],     xf,        yf - 1.0f, zf),
                       grad3(g_perm[bb],     xf - 1.0f, yf - 1.0f, zf), u);
    float y1 = ff_lerp(x1, x2, v);

    x1 = ff_lerp(grad3(g_perm[aa + 1],       xf,        yf,        zf - 1.0f),
                 grad3(g_perm[ba + 1],       xf - 1.0f, yf,        zf - 1.0f), u);
    x2 = ff_lerp(grad3(g_perm[ab + 1],       xf,        yf - 1.0f, zf - 1.0f),
                 grad3(g_perm[bb + 1],       xf - 1.0f, yf - 1.0f, zf - 1.0f), u);
    float y2 = ff_lerp(x1, x2, v);

    return ff_lerp(y1, y2, w);           /* roughly [-1, 1] */
}

float ff_noise2(float x, float y) { return ff_noise3(x, y, 0.371f); }

float ff_fbm2(float x, float y, int octaves, float lacunarity, float gain)
{
    float sum = 0.0f, amp = 1.0f, freq = 1.0f, norm = 0.0f;
    for (int i = 0; i < octaves; i++) {
        sum  += amp * ff_noise2(x * freq, y * freq);
        norm += amp;
        amp  *= gain;
        freq *= lacunarity;
    }
    return norm > 0.0f ? sum / norm : 0.0f;
}

float ff_fbm3(float x, float y, float z, int octaves, float lacunarity, float gain)
{
    float sum = 0.0f, amp = 1.0f, freq = 1.0f, norm = 0.0f;
    for (int i = 0; i < octaves; i++) {
        sum  += amp * ff_noise3(x * freq, y * freq, z * freq);
        norm += amp;
        amp  *= gain;
        freq *= lacunarity;
    }
    return norm > 0.0f ? sum / norm : 0.0f;
}

/* Ridged noise: absolute value inverted, which turns the smooth valleys of
 * Perlin into sharp crests -- the shape that reads as trench walls. */
float ff_ridged2(float x, float y, int octaves)
{
    float sum = 0.0f, amp = 0.5f, freq = 1.0f, norm = 0.0f;
    for (int i = 0; i < octaves; i++) {
        float n = 1.0f - fabsf(ff_noise2(x * freq, y * freq));
        sum  += amp * n * n;
        norm += amp;
        amp  *= 0.5f;
        freq *= 2.0f;
    }
    return norm > 0.0f ? sum / norm : 0.0f;
}
