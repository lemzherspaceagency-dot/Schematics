#include "ff_gl.h"
#include <stdio.h>

#define X(ret, name, args) PFN_##name name = 0;
FF_GL_FUNCS
#undef X

int ff_gl_load(void *(*get_proc)(const char *name))
{
    int missing = 0;
#define X(ret, name, args) \
    name = (PFN_##name)get_proc(#name); \
    if (!name) { fprintf(stderr, "[gl] missing entry point: %s\n", #name); missing++; }
    FF_GL_FUNCS
#undef X
    return missing;
}
