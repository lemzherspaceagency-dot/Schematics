extends SceneTree
# Renders art/splash.png (the boot / web loading image). Run with a display:
#   xvfb-run -a godot --rendering-driver opengl3 --resolution 1280x720 -s art_src/make_splash.gd
class Splash extends DrawKit:
	func _ready() -> void:
		_init_fonts()
	func _draw() -> void:
		var top := Color("ff9a62")
		var bot := Color("8a2f6a")
		draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(W, 0), Vector2(W, H), Vector2(0, H)]), PackedColorArray([top, top, bot, bot]))
		var cc := Vector2(W / 2, 330)
		for i in 14:
			var a0 := i * TAU / 14.0
			var a1 := a0 + TAU / 28.0
			draw_colored_polygon(PackedVector2Array([cc, cc + Vector2(cos(a0), sin(a0)) * 1500.0, cc + Vector2(cos(a1), sin(a1)) * 1500.0]), Color(1, 1, 1, 0.09))
		for i in 6:
			var ids := ["dish_burger", "dish_salad", "dish_steak", "dish_soup", "dish_stew", "item_veg"]
			_spr(ids[i], Vector2(120 + i * 210, 540 + (i % 2) * 40), 1.6, (i - 3) * 0.2, Color(1, 1, 1, 0.8))
		_ctext("READY", Vector2(W / 2 - 370, 190), 120, Color.WHITE)
		_ctext("SET", Vector2(W / 2 - 30, 190), 120, C_GOLD)
		_ctext("COOK!", Vector2(W / 2 + 320, 200), 140, Color("ff5a36"))
		_draw_chef_look(Data.default_look(0), Vector2(W / 2, 420), 1.0, 0.0, 1.9, 0.0, 0.0, 0.0, 1.0, 0.0, false)
		_ctext("Loading...", Vector2(W / 2, 680), 34, Color(1, 1, 1, 0.9))
func _init() -> void:
	var n := Splash.new()
	root.add_child(n)
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	var img := root.get_viewport().get_texture().get_image()
	img.save_png("res://art/splash.png")
	print("saved splash ", img.get_size())
	quit()
