# ANTINODE build.
#
#   make            native build for development and the self-test
#   make windows    cross-compiled, statically linked Antinode.exe
#   make installer  the exe plus an NSIS installer in dist/
#   make test       run the headless self-test under Xvfb

SRC_COMMON := src/main.c src/ff_gl.c src/ff_math.c src/ff_vault.c \
              src/ff_mesh.c src/ff_render.c src/ff_ui.c src/ff_game.c
WARN       := -Wall -Wextra -Wno-unused-parameter
CFLAGS     := -O2 -std=gnu11 $(WARN)

VERSION    := 0.1.0
WINCC      := x86_64-w64-mingw32-gcc
# wglGetProcAddress hands back a generic PROC that has to be cast to each
# entry point's real signature; that cast is correct here and unavoidable.
WINWARN    := -Wno-cast-function-type

.PHONY: all windows installer test clean

all: build/antinode

build/antinode: $(SRC_COMMON) src/plat_x11.c | build
	$(CC) $(CFLAGS) -o $@ $(SRC_COMMON) src/plat_x11.c -lX11 -lGL -lm

# -mwindows selects the GUI subsystem (no console window) and enters at
# WinMain; -static bundles the mingw runtime so the shipped exe needs no
# redistributable DLLs.
windows: dist/Antinode.exe

dist/Antinode.exe: $(SRC_COMMON) src/plat_win32.c build/icon.res | dist
	$(WINCC) $(CFLAGS) $(WINWARN) -mwindows -o $@ \
	    $(SRC_COMMON) src/plat_win32.c build/icon.res \
	    -static -static-libgcc -lopengl32 -lgdi32 -luser32 -lkernel32 -lm
	x86_64-w64-mingw32-strip $@

build/icon.res: installer/icon.rc installer/antinode.ico | build
	x86_64-w64-mingw32-windres installer/icon.rc -O coff -o $@

installer: dist/Antinode.exe
	makensis -V2 -DVERSION=$(VERSION) installer/antinode.nsi

test: build/antinode
	@mkdir -p build/shots
	./scripts/run-headless.sh ./build/antinode --selftest --shots build/shots

build dist:
	mkdir -p $@

clean:
	rm -rf build dist
