/* ff_game.h -- ANTINODE: pilot, emitters, chamber objective, screens. */
#ifndef FF_GAME_H
#define FF_GAME_H

#include "ff_math.h"
#include "ff_vault.h"
#include "ff_render.h"

enum { GS_TITLE, GS_PLAYING, GS_PAUSED, GS_CLEARED, GS_LOST, GS_COMPLETE };

#define FF_CHAMBER_COUNT 3

typedef struct {
    vec3  pos, vel;
    float yaw, pitch;
    int   selected;        /* which emitter the controls act on */
} ff_pilot;

typedef struct {
    int      state;
    ff_pilot pilot;
    int      chamber;
    uint32_t seed;

    int   linked;           /* anchors joined to the core right now */
    float hold_timer;       /* progress toward stabilising the core */
    float hold_required;
    int   bloom_cells;
    int   bloom_at_core;
    float survey_timer;     /* throttles the whole-volume queries    */

    int   show_wave;
    int   show_debug;
    int   menu_index;
    float time;
    float fps;
    int   chunks_meshed;
    char  toast[96];
    float toast_timer;
} ff_game;

extern ff_game ff_g;

void ff_game_new(uint32_t seed, int chamber);
int  ff_game_load(void);
void ff_game_save(void);
void ff_game_update(float dt);
void ff_game_render(int width, int height);
void ff_game_toast(const char *msg);
const char *ff_game_save_path(void);

#endif /* FF_GAME_H */
