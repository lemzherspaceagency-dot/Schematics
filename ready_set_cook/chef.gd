class_name Chef
extends RefCounted
# One player-controlled cook. Pure data: the simulation lives in main.gd.

var id := 0
var name := "Chef"
var profile_id := ""
var look: Dictionary = {}

var pos := Vector2.ZERO
var vel := Vector2.ZERO
var face := 1.0                    # smoothed -1..1 (looking left/right)
var dir := Vector2i(0, 1)          # grid direction the chef faces
var held := ""
var path: Array[Vector2i] = []
var target := Vector2i(-1, -1)     # station to use when the path ends
var in_dir := Vector2i.ZERO        # direction currently requested by the controller
var blocked := 0.0                 # how long another chef has been in the way

var scheme := 0                    # keyboard scheme index (0 = WASD ...)
var remote := false                # driven by a network peer
var peer := 1

var served := 0                    # dishes served (for the results screen)
var coins_made := 0

# animation
var sq := 0.0
var sq_v := 0.0
var walk := 0.0
var moving := false
var held_pos := Vector2.ZERO
var held_pop := 0.0
var last_held := ""
var bump := 0.0                    # little wobble when bumping into someone
