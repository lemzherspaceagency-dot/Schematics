/* au_game.h -- Project Aurora, Room One: the lobby, Aurora, D.I.V.A. */
#ifndef AU_GAME_H
#define AU_GAME_H

#include "ff_math.h"
#include "au_render.h"

enum { GS_TITLE, GS_PLAYING, GS_PAUSED, GS_ENDED };
enum { AU_IDLE, AU_APPROACH, AU_SCAN, AU_SPEAK1, AU_SPEAK2, AU_AWAIT_LOOK, AU_GONE };

typedef struct {
    vec3 pos; float yaw, pitch;
} au_player;

typedef struct {
    int   state;
    au_player player;

    int   auroraState;
    float auroraStateT;
    float lookAwayT;
    vec3  auroraPos;
    float auroraYaw;
    float scanRingT;      /* 0..1, drives the expanding scan ring */

    int   hasDiva;
    int   tracing;
    int   redirectArmed;
    int   redirected;
    int   doorLocked;
    float pulseT;
    float doorAnimT;      /* < 0 == not animating */

    float t;
    float fps;
    char  subOrpheon[128]; float subOrpheonT;
    char  subCue[128];     float subCueT;
    char  prompt[64];

    int   menuIndex;
} au_game;

extern au_game au_g;

/* Input snapshot the platform layer fills each frame -- kept separate from
 * ff_platform so the self-test can drive it directly without a real window. */
typedef struct {
    int   forward, back, left, right;
    int   interact_pressed;     /* edge */
    int   trace_held;
    float mouse_dx, mouse_dy;
} au_input;
extern au_input au_in;

void au_game_init(void);
void au_game_update(float dt);
void au_game_render(int width, int height);

/* exposed for the self-test */
int  au_collides(float x, float z);
vec3 au_aurora_hidden_pos(void);

#endif /* AU_GAME_H */
