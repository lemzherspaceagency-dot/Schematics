/* ff_gl.h -- minimal OpenGL 3.3 core loader for ANTINODE.
 *
 * ANTINODE links against no GL headers and no loader library. Every entry
 * point the game uses is declared here through the FF_GL_FUNCS list and then
 * resolved at runtime by the platform layer. Keeping the list explicit means
 * the shipped binary depends on nothing but opengl32.dll (Windows) or
 * libGL.so (Linux), which is what lets the installer be a single file.
 */
#ifndef FF_GL_H
#define FF_GL_H

#include <stddef.h>

#ifdef _WIN32
#define FF_APIENTRY __stdcall
#else
#define FF_APIENTRY
#endif

typedef unsigned int   GLenum;
typedef unsigned char  GLboolean;
typedef unsigned int   GLbitfield;
typedef signed char    GLbyte;
typedef short          GLshort;
typedef int            GLint;
typedef int            GLsizei;
typedef unsigned char  GLubyte;
typedef unsigned short GLushort;
typedef unsigned int   GLuint;
typedef float          GLfloat;
typedef float          GLclampf;
typedef double         GLdouble;
typedef void           GLvoid;
typedef char           GLchar;
typedef ptrdiff_t      GLintptr;
typedef ptrdiff_t      GLsizeiptr;

#define GL_FALSE                          0
#define GL_TRUE                           1
#define GL_ZERO                           0
#define GL_ONE                            1
#define GL_POINTS                         0x0000
#define GL_LINES                          0x0001
#define GL_LINE_STRIP                     0x0003
#define GL_TRIANGLES                      0x0004
#define GL_TRIANGLE_STRIP                 0x0005
#define GL_DEPTH_BUFFER_BIT               0x00000100
#define GL_COLOR_BUFFER_BIT               0x00004000
#define GL_LEQUAL                         0x0203
#define GL_LESS                           0x0201
#define GL_ALWAYS                         0x0207
#define GL_SRC_ALPHA                      0x0302
#define GL_ONE_MINUS_SRC_ALPHA            0x0303
#define GL_FRONT                          0x0404
#define GL_BACK                           0x0405
#define GL_CW                             0x0900
#define GL_CCW                            0x0901
#define GL_CULL_FACE                      0x0B44
#define GL_DEPTH_TEST                     0x0B71
#define GL_BLEND                          0x0BE2
#define GL_UNPACK_ALIGNMENT               0x0CF5
#define GL_TEXTURE_2D                     0x0DE1
#define GL_UNSIGNED_BYTE                  0x1401
#define GL_SHORT                          0x1402
#define GL_UNSIGNED_SHORT                 0x1403
#define GL_INT                            0x1404
#define GL_UNSIGNED_INT                   0x1405
#define GL_FLOAT                          0x1406
#define GL_RGB                            0x1907
#define GL_RGBA                           0x1908
#define GL_VENDOR                         0x1F00
#define GL_RENDERER                       0x1F01
#define GL_VERSION                        0x1F02
#define GL_NEAREST                        0x2600
#define GL_LINEAR                         0x2601
#define GL_NEAREST_MIPMAP_NEAREST         0x2700
#define GL_LINEAR_MIPMAP_NEAREST          0x2701
#define GL_NEAREST_MIPMAP_LINEAR          0x2702
#define GL_LINEAR_MIPMAP_LINEAR           0x2703
#define GL_TEXTURE_MAG_FILTER             0x2800
#define GL_TEXTURE_MIN_FILTER             0x2801
#define GL_TEXTURE_WRAP_S                 0x2802
#define GL_TEXTURE_WRAP_T                 0x2803
#define GL_REPEAT                         0x2901
#define GL_POLYGON_OFFSET_FILL            0x8037
#define GL_RGBA8                          0x8058
#define GL_TEXTURE_MAX_LEVEL              0x813D
#define GL_CLAMP_TO_EDGE                  0x812F
#define GL_TEXTURE0                       0x84C0
#define GL_TEXTURE_MAX_ANISOTROPY         0x84FE
#define GL_MAX_TEXTURE_MAX_ANISOTROPY     0x84FF
#define GL_ARRAY_BUFFER                   0x8892
#define GL_ELEMENT_ARRAY_BUFFER           0x8893
#define GL_STREAM_DRAW                    0x88E0
#define GL_STATIC_DRAW                    0x88E4
#define GL_DYNAMIC_DRAW                   0x88E8
#define GL_FRAGMENT_SHADER                0x8B30
#define GL_VERTEX_SHADER                  0x8B31
#define GL_COMPILE_STATUS                 0x8B81
#define GL_LINK_STATUS                    0x8B82
#define GL_INFO_LOG_LENGTH                0x8B84
#define GL_MULTISAMPLE                    0x809D
#define GL_NO_ERROR                       0

/* ret, name, args -- the complete set of GL entry points the game calls. */
#define FF_GL_FUNCS \
    X(void,   glClear,                  (GLbitfield mask)) \
    X(void,   glClearColor,             (GLfloat r, GLfloat g, GLfloat b, GLfloat a)) \
    X(void,   glEnable,                 (GLenum cap)) \
    X(void,   glDisable,                (GLenum cap)) \
    X(void,   glViewport,               (GLint x, GLint y, GLsizei w, GLsizei h)) \
    X(void,   glDepthFunc,              (GLenum func)) \
    X(void,   glDepthMask,              (GLboolean flag)) \
    X(void,   glBlendFunc,              (GLenum sfactor, GLenum dfactor)) \
    X(void,   glCullFace,               (GLenum mode)) \
    X(void,   glFrontFace,              (GLenum mode)) \
    X(void,   glPixelStorei,            (GLenum pname, GLint param)) \
    X(void,   glGetIntegerv,            (GLenum pname, GLint *data)) \
    X(void,   glGetFloatv,              (GLenum pname, GLfloat *data)) \
    X(GLenum, glGetError,               (void)) \
    X(const GLubyte *, glGetString,     (GLenum name)) \
    X(void,   glDrawArrays,             (GLenum mode, GLint first, GLsizei count)) \
    X(void,   glDrawElements,           (GLenum mode, GLsizei count, GLenum type, const void *indices)) \
    X(void,   glGenTextures,            (GLsizei n, GLuint *textures)) \
    X(void,   glDeleteTextures,         (GLsizei n, const GLuint *textures)) \
    X(void,   glBindTexture,            (GLenum target, GLuint texture)) \
    X(void,   glTexImage2D,             (GLenum target, GLint level, GLint internalformat, GLsizei w, GLsizei h, GLint border, GLenum format, GLenum type, const void *pixels)) \
    X(void,   glTexSubImage2D,          (GLenum target, GLint level, GLint xo, GLint yo, GLsizei w, GLsizei h, GLenum format, GLenum type, const void *pixels)) \
    X(void,   glTexParameteri,          (GLenum target, GLenum pname, GLint param)) \
    X(void,   glTexParameterf,          (GLenum target, GLenum pname, GLfloat param)) \
    X(void,   glReadPixels,             (GLint x, GLint y, GLsizei w, GLsizei h, GLenum format, GLenum type, void *pixels)) \
    X(void,   glActiveTexture,          (GLenum texture)) \
    X(void,   glGenerateMipmap,         (GLenum target)) \
    X(void,   glGenBuffers,             (GLsizei n, GLuint *buffers)) \
    X(void,   glDeleteBuffers,          (GLsizei n, const GLuint *buffers)) \
    X(void,   glBindBuffer,             (GLenum target, GLuint buffer)) \
    X(void,   glBufferData,             (GLenum target, GLsizeiptr size, const void *data, GLenum usage)) \
    X(void,   glBufferSubData,          (GLenum target, GLintptr offset, GLsizeiptr size, const void *data)) \
    X(void,   glGenVertexArrays,        (GLsizei n, GLuint *arrays)) \
    X(void,   glDeleteVertexArrays,     (GLsizei n, const GLuint *arrays)) \
    X(void,   glBindVertexArray,        (GLuint array)) \
    X(void,   glVertexAttribPointer,    (GLuint index, GLint size, GLenum type, GLboolean normalized, GLsizei stride, const void *pointer)) \
    X(void,   glEnableVertexAttribArray,(GLuint index)) \
    X(GLuint, glCreateShader,           (GLenum type)) \
    X(void,   glShaderSource,           (GLuint shader, GLsizei count, const GLchar *const *string, const GLint *length)) \
    X(void,   glCompileShader,          (GLuint shader)) \
    X(void,   glGetShaderiv,            (GLuint shader, GLenum pname, GLint *params)) \
    X(void,   glGetShaderInfoLog,       (GLuint shader, GLsizei bufSize, GLsizei *length, GLchar *infoLog)) \
    X(void,   glDeleteShader,           (GLuint shader)) \
    X(GLuint, glCreateProgram,          (void)) \
    X(void,   glAttachShader,           (GLuint program, GLuint shader)) \
    X(void,   glLinkProgram,            (GLuint program)) \
    X(void,   glGetProgramiv,           (GLuint program, GLenum pname, GLint *params)) \
    X(void,   glGetProgramInfoLog,      (GLuint program, GLsizei bufSize, GLsizei *length, GLchar *infoLog)) \
    X(void,   glUseProgram,             (GLuint program)) \
    X(void,   glDeleteProgram,          (GLuint program)) \
    X(GLint,  glGetUniformLocation,     (GLuint program, const GLchar *name)) \
    X(void,   glBindAttribLocation,     (GLuint program, GLuint index, const GLchar *name)) \
    X(void,   glUniform1i,              (GLint location, GLint v0)) \
    X(void,   glUniform1f,              (GLint location, GLfloat v0)) \
    X(void,   glUniform2f,              (GLint location, GLfloat v0, GLfloat v1)) \
    X(void,   glUniform3f,              (GLint location, GLfloat v0, GLfloat v1, GLfloat v2)) \
    X(void,   glUniform4f,              (GLint location, GLfloat v0, GLfloat v1, GLfloat v2, GLfloat v3)) \
    X(void,   glUniformMatrix4fv,       (GLint location, GLsizei count, GLboolean transpose, const GLfloat *value))

#define X(ret, name, args) typedef ret (FF_APIENTRY *PFN_##name) args; extern PFN_##name name;
FF_GL_FUNCS
#undef X

/* Resolves every entry point above. get_proc comes from the platform layer.
 * Returns the number of functions that could not be resolved. */
int ff_gl_load(void *(*get_proc)(const char *name));

#endif /* FF_GL_H */
