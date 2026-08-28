# Project Aurora -- Room One build.
#
#   make            native build for development and the self-test
#   make windows    cross-compiled, statically linked ProjectAurora.exe
#   make installer  the exe plus an NSIS installer in dist/
#   make test       run the headless self-test under Xvfb

SRC_COMMON := src/main.c src/ff_gl.c src/ff_math.c src/au_render.c src/au_game.c
WARN       := -Wall -Wextra -Wno-unused-parameter
CFLAGS     := -O2 -std=gnu11 $(WARN)

VERSION    := 0.1.0
WINCC      := x86_64-w64-mingw32-gcc
WINWARN    := -Wno-cast-function-type

.PHONY: all windows installer test clean

all: build/project-aurora

build/project-aurora: $(SRC_COMMON) src/plat_x11.c | build
	$(CC) $(CFLAGS) -o $@ $(SRC_COMMON) src/plat_x11.c -lX11 -lGL -lm

windows: dist/ProjectAurora.exe

dist/ProjectAurora.exe: $(SRC_COMMON) src/plat_win32.c build/icon.res | dist
	$(WINCC) $(CFLAGS) $(WINWARN) -mwindows -o $@ \
	    $(SRC_COMMON) src/plat_win32.c build/icon.res \
	    -static -static-libgcc -lopengl32 -lgdi32 -luser32 -lkernel32 -lm
	x86_64-w64-mingw32-strip $@

build/icon.res: installer/icon.rc installer/aurora.ico | build
	x86_64-w64-mingw32-windres installer/icon.rc -O coff -o $@

installer: dist/ProjectAurora.exe
	makensis -V2 -DVERSION=$(VERSION) installer/aurora.nsi

test: build/project-aurora
	@mkdir -p build/shots
	./scripts/run-headless.sh ./build/project-aurora --selftest --shots build/shots

build dist:
	mkdir -p $@

clean:
	rm -rf build dist
