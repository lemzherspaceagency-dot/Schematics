extends GameSim
# Ready, Set, Cook! v1.0: screens, input glue and all the drawing.
# Simulation lives in game_sim.gd, drawing helpers in draw_kit.gd.

const CUSTOM_CATS := [
	{"id": "skin", "label": "Skin"}, {"id": "hat", "label": "Hat"}, {"id": "hat_col", "label": "Hat colour"},
	{"id": "jacket", "label": "Jacket"}, {"id": "apron", "label": "Apron"}, {"id": "scarf", "label": "Scarf"},
	{"id": "acc", "label": "Face gear"},
]
const KEY_ROWS := ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]

# ---- loading screen ----
var load_total := 1
var load_done := 0
var load_stage := 0
var load_i := 0
var load_t := 0.0
var load_shown := 0.0
var load_ready := false
var load_tip := ""

# ---- screen state ----
var world_tab := 0
var edit_slot := 0
var edit_pid := ""
var custom_return: int = S.MENU
var players_return: int = S.MENU
var name_buf := ""
var name_mode := "new"
var name_target := ""
var confirm_delete := ""
var net: Node = null
var hud: HudLayer = null
var view_container: SubViewportContainer = null
var view_vp: SubViewport = null
var stage: StageView = null
var stage_container: SubViewportContainer = null
var stage_vp: SubViewport = null


func _ready() -> void:
	_init_fonts()
	sfx = Sfx.new()
	add_child(sfx)
	acc.load_all()
	sfx.enabled = acc.sound
	_init_slots()
	for i in 16:
		float_icons.append({"p": Vector2(randf() * W, randf() * H), "v": randf_range(14, 36), "r": randf() * TAU, "w": randf_range(-0.8, 0.8),
			"id": ["dish_salad", "dish_burger", "dish_soup", "dish_steak", "dish_stew", "item_veg", "item_meat", "item_bun", "item_patty"][i % 9], "s": randf_range(24, 38)})
	load_total = ArtList.NAMES.size() + Sfx.MUSIC_STEPS + 2
	load_tip = Data.TIPS[randi() % Data.TIPS.size()]
	state = S.LOADING
	fade = 0.0
	coins_shown = float(_prof().get("coins", 0))
	_make_view()
	hud = HudLayer.new()
	hud.g = self
	hud.name = "Hud"
	add_child(hud)
	var NetLink = load("res://net.gd")
	net = NetLink.new()
	net.name = "Net"
	net.main = self
	add_child(net)


# ====================================================================
# The 3D view
# ====================================================================

func _make_view() -> void:
	view_container = SubViewportContainer.new()
	view_container.name = "View"
	view_container.stretch = false
	view_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	view_container.visible = false
	view_vp = SubViewport.new()
	view_vp.size = Vector2i(1280, 720)
	view_vp.own_world_3d = true
	view_vp.msaa_3d = Viewport.MSAA_2X
	view_vp.handle_input_locally = false
	view_vp.gui_disable_input = true
	view_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	view_container.add_child(view_vp)
	view = KitchenView.new()
	view.g = self
	view.vp = view_vp
	view_vp.add_child(view)
	add_child(view_container)
	# transparent 3D layer for chefs shown on the menu screens
	stage_container = SubViewportContainer.new()
	stage_container.name = "Stage"
	stage_container.stretch = false
	stage_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stage_vp = SubViewport.new()
	stage_vp.size = Vector2i(1280, 720)
	stage_vp.own_world_3d = true
	stage_vp.transparent_bg = true
	stage_vp.msaa_3d = Viewport.MSAA_2X
	stage_vp.gui_disable_input = true
	stage_container.add_child(stage_vp)
	stage = StageView.new()
	stage.vp = stage_vp
	stage_vp.add_child(stage)
	add_child(stage_container)


# ask the 3D stage to show a full chef standing at feet_px (canvas px) / just a head+shoulders badge centred on c
func _stage_chef(id: String, look: Dictionary, feet_px: Vector2, scale_f: float, anim: String = "idle", face: String = "happy") -> void:
	stage.request(id, "chef", look, feet_px, scale_f, anim, face)


func _stage_bust(id: String, look: Dictionary, c: Vector2, radius: float) -> void:
	stage.request(id, "bust", look, c, radius / 90.0, "idle", "happy")


func _draw_head_icon(look: Dictionary, c: Vector2, size: float) -> void:
	draw_circle(c, size + 4, C_OUTLINE)
	draw_circle(c, size, Color("9bd1ff"))
	_stage_bust("bust_%d_%d" % [int(c.x), int(c.y)], look, c + Vector2(0, size * 0.1), size)


func _fit_view() -> void:
	var win := get_window().size
	var sc := clampf(minf(float(win.x) / W, float(win.y) / H), 0.5, 1.5)
	var want := Vector2i(int(W * sc), int(H * sc))
	if view_vp.size != want:
		view_vp.size = want
	view_container.scale = Vector2(W / float(want.x), H / float(want.y))
	if stage_vp.size != want:
		stage_vp.size = want
	stage_container.scale = view_container.scale
	stage.canvas_scale = W / float(want.x)


# ====================================================================
# Net hooks
# ====================================================================

func _on_level_started() -> void:
	view.build_level()
	if net_mode == 1:
		net.host_start_level()


func _on_level_ended() -> void:
	if net_mode == 1:
		net.host_result()


func _remote_defs() -> Array:
	if net_mode == 1 and net != null:
		return net.remote_list()
	return []


# ====================================================================
# Frame loop
# ====================================================================

func _process(delta: float) -> void:
	t_global += delta
	state_t += delta
	if pending >= 0:
		fade = minf(1.0, fade + delta / 0.16)
		if fade >= 1.0:
			var target: int = pending
			pending = -1
			state_t = 0.0
			if target == S.PLAY:
				_start_level(cur_level)
			else:
				state = target as S
		confirm_delete = ""
	elif fade > 0.0:
		fade = maxf(0.0, fade - delta / 0.22)
	coins_shown = lerpf(coins_shown, float(_prof().get("coins", 0)), 1.0 - exp(-8.0 * delta))
	earned_shown = lerpf(earned_shown, float(earned), 1.0 - exp(-7.0 * delta))
	if state == S.LOADING:
		_loader_step(delta)
	if state == S.RESULT:
		_result_fx(delta)
	_update_fx(delta)
	for ic in float_icons:
		var p: Vector2 = ic["p"]
		p.y -= float(ic["v"]) * delta
		if p.y < -60.0:
			p = Vector2(randf() * W, H + 60.0)
		ic["p"] = p
		ic["r"] = float(ic["r"]) + float(ic["w"]) * delta
	if state == S.PLAY or state == S.PAUSE or (state == S.RESULT and not chefs.is_empty()):
		if state == S.PLAY and net_mode != 2:
			_update_game(delta)
		if state == S.PLAY:
			_station_fx(delta)
		_anim_chefs(delta)
		_decay_pops(delta)
	if net_mode != 0:
		net.tick(delta)
	if state == S.PLAY and intro <= 0.0 and banner_t > 0.0:
		banner_t -= delta
	var cooking := 0
	if state == S.PLAY and intro <= 0.0:
		for key in stations:
			var s: Dictionary = stations[key]
			if map[Vector2i(key).y][Vector2i(key).x] != "C" and (s["st"] == "working" or s["st"] == "done"):
				cooking += 1
	sfx.set_sizzle(clampf(cooking / 3.0, 0.0, 1.0), delta)
	var show_view := _tilted()
	view_container.visible = show_view
	view_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS if show_view else SubViewport.UPDATE_DISABLED
	var show_stage := not show_view and state != S.NAME
	stage_container.visible = show_stage
	stage_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS if show_stage else SubViewport.UPDATE_DISABLED
	_fit_view()
	queue_redraw()
	hud.queue_redraw()


func _anim_chefs(delta: float) -> void:
	for ch in chefs:
		ch.sq_v += (-ch.sq * 260.0 - ch.sq_v * 13.0) * delta
		ch.sq += ch.sq_v * delta
		ch.held_pos = ch.held_pos.lerp(ch.pos + Vector2(0, -62), 1.0 - exp(-22.0 * delta))
		if ch.held != ch.last_held:
			ch.last_held = ch.held
			ch.held_pop = 1.0
		ch.held_pop = maxf(0.0, ch.held_pop - delta * 4.0)
		if net_mode == 2:
			ch.walk += ch.vel.length() * delta * 0.11
			ch.moving = ch.vel.length() > 20.0
			if absf(ch.vel.x) > 8.0:
				ch.face = lerpf(ch.face, signf(ch.vel.x), 1.0 - exp(-18.0 * delta))
	if net_mode == 2:
		for c in customers:
			c["t"] = float(c["t"]) + delta


func _decay_pops(delta: float) -> void:
	for k in pops.keys():
		pops[k] = float(pops[k]) - delta
		if float(pops[k]) <= 0.0:
			pops.erase(k)


func _result_fx(delta: float) -> void:
	result_t += delta
	var star_times := [0.8, 1.4, 2.0]
	for i in result_stars:
		var before: float = result_t - delta
		if before < star_times[i] and result_t >= star_times[i]:
			sfx.play("star", 1.0 + i * 0.25)
			_burst(Vector2(245 + i * 150, 300 - (30.0 if i == 1 else 0.0)), C_GOLD, 26, 320.0)
			shake = 4.0
	if result_stars == 3 and result_t > 2.0 and randf() < 0.5:
		var cols := [C_GOLD, C_ACCENT, C_GOOD, Color("4cc9f0"), Color("ef476f")]
		particles.append({"p": Vector2(randf() * W, -10), "v": Vector2(randf_range(-40, 40), 120), "g": 60.0, "life": 4.0, "max": 4.0, "col": cols[randi() % 5], "r": randf_range(4, 7), "tex": ""})


func _loader_step(delta: float) -> void:
	load_t += delta
	var t0 := Time.get_ticks_usec()
	while load_stage < 3 and Time.get_ticks_usec() - t0 < 9000:
		match load_stage:
			0:
				_tex(ArtList.NAMES[load_i])
				load_i += 1
				load_done += 1
				if load_i >= ArtList.NAMES.size():
					load_stage = 1
					load_i = 0
					sfx.music_begin()
					load_done += 1
			1:
				sfx.music_step(load_i)
				load_i += 1
				load_done += 1
				if load_i >= Sfx.MUSIC_STEPS:
					load_stage = 2
			2:
				sfx.music_finish()
				load_done += 1
				load_stage = 3
	var real := float(load_done) / float(load_total)
	var cap := clampf((load_t - 0.3) / 2.6, 0.0, 1.0)
	load_shown = move_toward(load_shown, minf(real, cap), delta * 0.9)
	if load_stage >= 3 and load_shown >= 0.999:
		load_ready = true


# ====================================================================
# Input
# ====================================================================

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		mouse_down = event.pressed
		if event.pressed:
			_on_tap(get_local_mouse_position())
	elif event is InputEventKey and event.pressed and not event.echo:
		_on_key(event)
	elif event is InputEventJoypadButton and event.pressed:
		_on_pad(event)


func _on_tap(p: Vector2) -> void:
	if pending >= 0:
		return
	if state == S.LOADING:
		if load_ready:
			sfx.play("go")
			if sfx.music_ready and acc.sound and not sfx.music_player.playing:
				sfx.music_player.play()
			_goto(S.MENU)
		return
	var all_buttons: Array = buttons + hud.buttons
	for i in range(all_buttons.size() - 1, -1, -1):
		var b: Dictionary = all_buttons[i]
		var r: Rect2 = b["rect"]
		if r.has_point(p):
			sfx.play("click")
			_on_button(b["id"])
			return
	if state == S.PLAY and intro <= 0.0:
		var wp := _unproject(p)
		if net_mode == 2:
			net.client_tap(wp)
		else:
			_on_game_tap(wp)


func _on_key(event: InputEventKey) -> void:
	var code: Key = event.physical_keycode
	if state == S.LOADING and load_ready and (code == KEY_ENTER or code == KEY_SPACE):
		_on_tap(Vector2.ZERO)
		return
	if state == S.NAME:
		if code == KEY_BACKSPACE:
			name_buf = name_buf.substr(0, maxi(0, name_buf.length() - 1))
		elif code == KEY_ENTER or code == KEY_KP_ENTER:
			_on_button("key_ok")
		elif code == KEY_ESCAPE:
			_on_button("key_cancel")
		elif event.unicode >= 32 and event.unicode < 127 and name_buf.length() < 14:
			name_buf += char(event.unicode)
		return
	if state == S.ONLINE:
		net.on_key(event)
		return
	if code == KEY_ESCAPE:
		if state == S.PLAY:
			state = S.PAUSE
		elif state == S.PAUSE:
			state = S.PLAY
		return
	if state == S.PLAY and intro <= 0.0:
		if net_mode == 2:
			net.client_key(event)
			return
		for ch in chefs:
			if ch.remote:
				continue
			for si in _schemes_for(ch):
				if code in ((KEYS[si] as Dictionary)["act"] as Array):
					_chef_act(ch)
					break


func _on_pad(event: InputEventJoypadButton) -> void:
	if state == S.LOADING and load_ready:
		_on_tap(Vector2.ZERO)
		return
	if state != S.PLAY and state != S.PAUSE:
		return
	if event.button_index == JOY_BUTTON_START:
		state = S.PAUSE if state == S.PLAY else S.PLAY
		return
	if state == S.PLAY and intro <= 0.0 and event.button_index == JOY_BUTTON_A:
		if net_mode == 2:
			net.client_act()
			return
		for ch in chefs:
			if not ch.remote and ch.scheme == event.device:
				_chef_act(ch)


# ---------------------------------------------------------------- navigation

func _goto(next: int) -> void:
	if pending < 0:
		pending = next


func _on_button(id: String) -> void:
	match id:
		"play":
			_goto(S.LEVELS)
		"players":
			players_return = state
			_goto(S.PLAYERS)
		"players_done":
			_goto(players_return)
		"customize":
			edit_slot = 0
			edit_pid = ""
			custom_return = state
			_goto(S.CUSTOMIZE)
		"cust_done":
			acc.save_all()
			_goto(custom_return)
		"cust_random":
			_randomise_look()
		"cust_rename":
			_open_name("rename", edit_pid if edit_pid != "" else str(slots[edit_slot]["pid"]))
		"shop":
			_goto(S.SHOP)
		"menu":
			_goto(S.MENU)
		"profiles":
			_goto(S.PROFILES)
		"online":
			net.open_screen()
		"sound":
			acc.sound = not acc.sound
			sfx.set_enabled(acc.sound)
			acc.save_all()
		"pause":
			show_recipes = false
			state = S.PAUSE
		"recipes":
			show_recipes = true
			state = S.PAUSE
		"resume":
			show_recipes = false
			state = S.PLAY
		"restart":
			if net_mode != 2:
				_start_level(cur_level)
		"retry":
			_goto(S.BRIEF)
		"next":
			cur_level = mini(cur_level + 1, Data.LEVELS.size() - 1)
			world_tab = cur_level / 5
			_goto(S.BRIEF)
		"start":
			if net_mode == 2:
				pass
			else:
				_goto(S.PLAY)
		"levels":
			_goto(S.LEVELS)
		"prof_new":
			_open_name("new", "")
		"key_back":
			name_buf = name_buf.substr(0, maxi(0, name_buf.length() - 1))
		"key_space":
			if name_buf.length() < 14:
				name_buf += " "
		"key_random":
			name_buf = Data.random_name()
		"key_cancel":
			_goto(S.PROFILES if name_mode == "new" else S.CUSTOMIZE)
		"key_ok":
			_finish_name()
		_:
			_on_button_param(id)


func _on_button_param(id: String) -> void:
	if id.begins_with("lvl_"):
		cur_level = int(id.substr(4))
		_goto(S.BRIEF)
	elif id.begins_with("world_"):
		world_tab = int(id.substr(6))
	elif id.begins_with("buy_"):
		_buy(id.substr(4))
	elif id.begins_with("key_"):
		if name_buf.length() < 14:
			name_buf += id.substr(4)
	elif id.begins_with("slot_"):
		_slot_button(id.substr(5))
	elif id.begins_with("cust_"):
		_custom_button(id.substr(5))
	elif id.begins_with("prof_use_"):
		_use_profile(id.substr(9))
	elif id.begins_with("prof_del_"):
		var pid := id.substr(9)
		if confirm_delete == pid:
			acc.remove(pid)
			_fix_slots_after_profile_change()
			confirm_delete = ""
			acc.save_all()
		else:
			confirm_delete = pid
	elif id.begins_with("net_"):
		net.on_button(id.substr(4))


func _buy(id: String) -> void:
	var p := _prof()
	var up: Dictionary = p["upg"]
	var lvl := int(up.get(id, 0))
	var cost := Data.upgrade_cost(lvl)
	for u in Data.UPGRADES:
		if u["id"] == id and lvl < int(u["max"]) and int(p["coins"]) >= cost:
			p["coins"] = int(p["coins"]) - cost
			up[id] = lvl + 1
			acc.save_all()
			sfx.play("coin")
			sfx.play("ding", 1.2)
			return
	sfx.play("error")


# ---------------------------------------------------------------- accounts / slots

func _use_profile(pid: String) -> void:
	if not acc.profiles.has(pid):
		return
	acc.active = pid
	_fix_slots_after_profile_change()
	acc.save_all()


func _fix_slots_after_profile_change() -> void:
	slots[0]["pid"] = acc.active
	for i in range(1, Data.MAX_PLAYERS):
		var pid: String = slots[i]["pid"]
		if pid != "" and (not acc.profiles.has(pid) or pid == acc.active):
			slots[i]["pid"] = ""


func _slot_options(slot: int) -> Array:
	# guest + every account not already used by another joined slot
	var used := {}
	for i in Data.MAX_PLAYERS:
		if i != slot and bool(slots[i]["on"]):
			used[str(slots[i]["pid"])] = true
	var out: Array = [""]
	for pid in acc.order:
		if not used.has(pid):
			out.append(pid)
	return out


func _slot_button(rest: String) -> void:
	var parts := rest.split("_")
	var kind := parts[0]
	var i := int(parts[1])
	match kind:
		"on":
			slots[i]["on"] = true
			slots[i]["pid"] = ""
			sfx.play("pop")
		"off":
			slots[i]["on"] = false
		"prev", "next":
			var opts := _slot_options(i)
			var cur := opts.find(str(slots[i]["pid"]))
			cur = (cur + (1 if kind == "next" else -1) + opts.size()) % opts.size()
			slots[i]["pid"] = opts[cur]
		"cust":
			edit_slot = i
			edit_pid = ""
			custom_return = S.PLAYERS
			_goto(S.CUSTOMIZE)


func _edit_look() -> Dictionary:
	if edit_pid != "" and acc.profiles.has(edit_pid):
		return acc.profiles[edit_pid]["look"]
	return _slot_look(edit_slot)


func _custom_button(rest: String) -> void:
	var parts := rest.split("_")
	var kind := parts[0]
	# ids look like  "prev_hat_col"  /  "next_skin"  /  "set_skin_3"
	var look := _edit_look()
	if kind == "set":
		var idx := int(parts[parts.size() - 1])
		var cat := "_".join(parts.slice(1, parts.size() - 1))
		look[cat] = idx
		sfx.play("pop")
		return
	var cat2 := "_".join(parts.slice(1))
	var size := _cat_size(cat2)
	look[cat2] = (int(look.get(cat2, 0)) + (1 if kind == "next" else -1) + size) % size
	sfx.play("pop", 1.1)


func _cat_size(cat: String) -> int:
	match cat:
		"skin":
			return Data.SKINS.size()
		"hat":
			return Data.HATS.size()
		"acc":
			return Data.ACCS.size()
	return Data.COLORS.size()


func _randomise_look() -> void:
	var look := _edit_look()
	for c in CUSTOM_CATS:
		look[c["id"]] = randi() % _cat_size(c["id"])
	sfx.play("pop", 1.4)


func _open_name(mode: String, target: String) -> void:
	name_mode = mode
	name_target = target
	name_buf = "" if mode == "new" else str(acc.get_profile(target).get("name", ""))
	_goto(S.NAME)


func _finish_name() -> void:
	var nm := name_buf.strip_edges()
	if nm == "":
		nm = Data.random_name()
	if name_mode == "new":
		if acc.order.size() >= Accounts.MAX_PROFILES:
			sfx.play("error")
			return
		var pid := acc.create(nm)
		_use_profile(pid)
		edit_pid = pid
		edit_slot = 0
		custom_return = S.PROFILES
		_goto(S.CUSTOMIZE)
	else:
		if acc.profiles.has(name_target):
			acc.profiles[name_target]["name"] = nm
		acc.save_all()
		_goto(S.CUSTOMIZE)


# ====================================================================
# Drawing: main entry
# ====================================================================

func _draw() -> void:
	buttons = []
	_draw_background()
	match state:
		S.LOADING:
			_draw_loading()
		S.MENU:
			_draw_menu()
		S.LEVELS:
			_draw_levels()
		S.PLAYERS:
			_draw_players()
		S.CUSTOMIZE:
			_draw_customize()
		S.PROFILES:
			_draw_profiles()
		S.NAME:
			_draw_name()
		S.SHOP:
			_draw_shop()
		S.BRIEF:
			_draw_brief()
		S.ONLINE:
			net.draw_screen()
		S.PLAY, S.PAUSE:
			_draw_game()
		S.RESULT:
			_draw_result()
	if not _tilted():
		_draw_particles()


func _draw_background() -> void:
	draw_rect(Rect2(-20, -20, W + 40, H + 40), C_BG)
	if state == S.PLAY or state == S.PAUSE:
		return
	var top := Color("ffbe6b")
	var bot := Color("f0506e")
	match state:
		S.LOADING:
			top = Color("ff9a62")
			bot = Color("8a2f6a")
		S.SHOP, S.PROFILES, S.NAME, S.CUSTOMIZE, S.PLAYERS, S.ONLINE:
			top = Color("7a5cb0")
			bot = Color("3a2a66")
		S.LEVELS:
			top = Color(Data.WORLDS[world_tab]["top"])
			bot = Color(Data.WORLDS[world_tab]["bot"])
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(W, 0), Vector2(W, H), Vector2(0, H)]), PackedColorArray([top, top, bot, bot]))
	var cc := Vector2(W / 2, 330)
	for i in 14:
		var a0 := t_global * 0.12 + i * TAU / 14.0
		var a1 := a0 + TAU / 28.0
		draw_colored_polygon(PackedVector2Array([cc, cc + Vector2(cos(a0), sin(a0)) * 1500.0, cc + Vector2(cos(a1), sin(a1)) * 1500.0]), Color(1, 1, 1, 0.09))
	for ic in float_icons:
		_spr(str(ic["id"]), ic["p"], float(ic["s"]) / 20.0, float(ic["r"]), Color(1, 1, 1, 0.5))


# ====================================================================
# Loading screen
# ====================================================================

func _draw_loading() -> void:
	var k := _ease_back(state_t / 0.6)
	_xf_about(Vector2(W / 2, 150), k, k)
	var bob := sin(t_global * 3.0) * 4.0
	_ctext("READY", Vector2(W / 2 - 330, 150 + bob), 110, Color.WHITE)
	_ctext("SET", Vector2(W / 2 - 20, 150 - bob), 110, C_GOLD)
	_ctext("COOK!", Vector2(W / 2 + 290, 160 + bob), 130, Color("ff5a36"))
	_xf_reset()
	# the scene: a chef sprinting on a conveyor of floor tiles with a dish on his head
	var gy := 470.0
	var off := fmod(t_global * 180.0, 64.0)
	var shift := int(t_global * 180.0 / 64.0)
	for i in range(-1, 22):
		var x := i * 64.0 - off
		_tile_spr("floor_0a" if (i + shift) % 2 == 0 else "floor_0b", Rect2(x, gy + 24, 64, 64))
		_tile_spr("wall_0", Rect2(x, gy + 88, 64, 64))
	var look: Dictionary = _slot_look(0)
	var runner := Vector2(W / 2 - 20, gy - 20 + sin(t_global * 14.0) * 3.0)
	_stage_chef("runner", look, Vector2(W / 2 - 20, gy + 12), 0.8, "run")
	var dish: String = ["dish_burger", "dish_salad", "dish_steak", "dish_soup", "dish_stew"][int(t_global * 1.5) % 5]
	_spr(dish, runner + Vector2(0, -250 + sin(t_global * 7.0) * 4.0), 1.5, sin(t_global * 5.0) * 0.1)
	for i in 6:
		var lx := fmod(t_global * 400.0 + i * 220.0, 1500.0)
		draw_line(Vector2(W - lx, gy - 10 - i * 22), Vector2(W - lx + 90, gy - 10 - i * 22), Color(1, 1, 1, 0.35), 5.0)
	# progress bar: a burger rolls along it
	var bar := Rect2(240, 598, 800, 34)
	_bar(bar, load_shown, C_GOLD)
	var bx := bar.position.x + 20 + (bar.size.x - 40) * load_shown
	_spr("dish_burger", Vector2(bx, bar.position.y + 17), 1.1, load_shown * 24.0)
	var pct := int(round(load_shown * 100.0))
	_ctext("%d%%" % pct, Vector2(W / 2, 566), 56, Color.WHITE)
	if load_ready:
		var pulse := 1.0 + sin(t_global * 5.0) * 0.06
		_xf_about(Vector2(W / 2, 668), pulse, pulse)
		_ctext("TAP OR PRESS ENTER TO START", Vector2(W / 2, 672), 34, C_GOLD)
		_xf_reset()
	else:
		_ctext("Loading..." if load_stage < 1 else ("Tuning the kitchen band..." if load_stage < 3 else "Heating the pans..."), Vector2(W / 2, 672), 28, Color(1, 1, 1, 0.9))
	_ctext("Tip: " + load_tip, Vector2(W / 2, 704), 20, Color(1, 1, 1, 0.8))


# ====================================================================
# Menu
# ====================================================================

func _coin_bar() -> void:
	var bump := 1.0 + hud_bump * 0.25
	_nine("panel", Rect2(W - 232, 14, 214, 54), C_DARK, 36.0, 36.0, 36.0)
	_spr("coin", Vector2(W - 202, 41), 0.9 * bump)
	_txt(str(int(round(coins_shown))), Vector2(W - 174, 53), 30, C_GOLD)


func _profile_chip(pos: Vector2) -> void:
	var r := Rect2(pos, Vector2(300, 60))
	buttons.append({"rect": r, "id": "profiles"})
	var hover := r.has_point(get_local_mouse_position())
	_nine("panel", r, C_DARK.lightened(0.15 if hover else 0.0), 36.0, 36.0, 36.0)
	_draw_head_icon(_slot_look(0), pos + Vector2(32, 34), 20)
	_txt(str(_prof()["name"]), pos + Vector2(66, 28), 24, Color.WHITE, HORIZONTAL_ALIGNMENT_LEFT, 220)
	_txt("tap to switch account", pos + Vector2(66, 50), 14, Color(1, 1, 1, 0.65))


func _menu_title(text: String, c: Vector2, size: int, col: Color, delay: float, tilt: float = 0.0) -> void:
	var k := _pop_in(delay, 0.5)
	if k <= 0.0:
		return
	var bobv := sin(t_global * 2.6 + delay * 4.0) * 5.0
	_xf_about(c, k, k, tilt + sin(t_global * 1.7 + delay) * 0.02)
	_ctext(text, c + Vector2(0, bobv), size, col)
	_xf_reset()


func _draw_menu() -> void:
	_coin_bar()
	_profile_chip(Vector2(14, 12))
	_menu_title("READY", Vector2(360, 190), 112, Color.WHITE, 0.05, -0.05)
	_menu_title("SET", Vector2(360, 292), 112, C_GOLD, 0.15, 0.04)
	_menu_title("COOK!", Vector2(360, 420), 150, Color("ff5a36"), 0.25, -0.04)
	# the crew dances along the bottom
	var n := _nplayers()
	var idx := 0
	var hk := _pop_in(0.35, 0.6)
	for i in Data.MAX_PLAYERS:
		if not bool(slots[i]["on"]):
			continue
		var cx := 360.0 + (idx - (n - 1) / 2.0) * 130.0
		var bobv := absf(sin(t_global * 3.4 + idx * 0.9)) * 12.0
		_xf_about(Vector2(cx, 590), hk, hk)
		_stage_chef("hero_%d" % idx, _slot_look(i), Vector2(cx, 652), 0.62 if n <= 2 else 0.52, "dance")
		_xf_reset()
		idx += 1
	_draw_dish("burger", Vector2(120, 520 + sin(t_global * 2.0) * 9.0), 36 * hk)
	_draw_dish("stew", Vector2(600, 530 + cos(t_global * 2.2) * 9.0), 36 * hk)
	var x0 := 830.0
	var pk := _pop_in(0.5, 0.5)
	if pk > 0.0:
		var pulse := 1.0 + sin(t_global * 5.0) * 0.02
		_button(Rect2(x0 + 180 - 180 * pk * pulse, 150, 360 * pk * pulse, 104), "PLAY", "play", Color("ff6b3d"), 56)
	var specs := [
		[Rect2(x0, 280, 176, 76), "PLAYERS: %d" % n, "players", Color("4c8bf5"), 24],
		[Rect2(x0 + 184, 280, 176, 76), "ONLINE", "online", Color("39b36b"), 26],
		[Rect2(x0, 372, 176, 76), "CUSTOMIZE", "customize", Color("9b5de5"), 22],
		[Rect2(x0 + 184, 372, 176, 76), "UPGRADES", "shop", Color("ff9f1c"), 24],
		[Rect2(x0, 464, 176, 70), "ACCOUNTS", "profiles", Color("2ec4b6"), 22],
		[Rect2(x0 + 184, 464, 176, 70), "SOUND: ON" if acc.sound else "SOUND: OFF", "sound", Color("8d99ae"), 22],
	]
	for i in specs.size():
		var k := _pop_in(0.6 + 0.06 * i, 0.45)
		if k <= 0.0:
			continue
		var sp: Array = specs[i]
		var r: Rect2 = sp[0]
		var rr := Rect2(r.get_center() - r.size * k / 2.0, r.size * k)
		_button(rr, sp[1], sp[2], sp[3], int(sp[4]))
	var total := 0
	for s in (_prof()["stars"] as Array):
		total += int(s)
	_spr("star_on", Vector2(x0 + 110, 590), 0.55)
	_txt("%d / %d" % [total, Data.LEVELS.size() * 3], Vector2(x0 + 134, 600), 28, C_GOLD)
	_ctext("v1.0  -  1 to 4 players", Vector2(x0 + 180, 690), 18, Color(1, 1, 1, 0.55))


# ====================================================================
# Levels
# ====================================================================

func _draw_levels() -> void:
	_coin_bar()
	_button(Rect2(16, 14, 130, 54), "BACK", "menu", Color("8d99ae"), 24)
	_ctext("Choose a level", Vector2(W / 2, 54), 46)
	for w in 3:
		var r := Rect2(190 + w * 300, 84, 280, 62)
		var on := w == world_tab
		_button(r, str(Data.WORLDS[w]["name"]), "world_%d" % w, Color(Data.WORLDS[w]["bot"]).lightened(0.25) if on else Color("6c7088"), 26)
		if on:
			_spr("spark", r.position + Vector2(14, 14), 0.5, t_global * 2.0)
	_ctext(str(Data.WORLDS[world_tab]["blurb"]), Vector2(W / 2, 176), 22, Color(1, 1, 1, 0.9))
	var goals_k := 1.0 + 0.55 * float(_nplayers() - 1)
	for n in 5:
		var i := world_tab * 5 + n
		var k := _pop_in(0.05 * n, 0.4)
		if k <= 0.0:
			continue
		var r := Rect2(32 + n * 246, 196, 232, 330)
		_xf_about(r.get_center(), k, k)
		var d: Dictionary = Data.LEVELS[i]
		var open := _unlocked(i)
		var st := _stars_of(i)
		var tint := Color("ffb457") if open else Color("8a8da6")
		if open and st >= 1:
			tint = Color("7fd98f")
		if open and st >= 3:
			tint = Color("ffd84a")
		_panel(r, tint)
		if open:
			buttons.append({"rect": r, "id": "lvl_%d" % i})
			for s in 3:
				_star(r.position + Vector2(66 + s * 50, 52), 20, s < st)
			_ctext(str(i + 1), r.position + Vector2(116, 168), 100, Color("ff6b3d"))
			_ctext(str(d["name"]), r.position + Vector2(116, 214), 26, Color.WHITE)
			var recs: Array = d["recipes"]
			var span := (recs.size() - 1) * 40.0
			for m in recs.size():
				_draw_dish(recs[m], r.position + Vector2(116 - span / 2.0 + m * 40.0, 256), 15)
			_ctext("%ds   goal %d" % [int(d["time"]), int(round(float((d["goals"] as Array)[0]) * goals_k / 5.0)) * 5], r.position + Vector2(116, 304), 20, Color(1, 1, 1, 0.95))
		else:
			_draw_lock(r.get_center() + Vector2(0, -30))
			_ctext("Get a star on", r.get_center() + Vector2(0, 62), 20, Color(1, 1, 1, 0.9))
			_ctext("level %d first" % i, r.get_center() + Vector2(0, 88), 20, Color(1, 1, 1, 0.9))
		_xf_reset()
	_players_chip(Vector2(W / 2 - 330, 560))


func _players_chip(pos: Vector2) -> void:
	var r := Rect2(pos, Vector2(660, 90))
	_panel(r, Color("c99a6b"))
	var n := _nplayers()
	var idx := 0
	for i in Data.MAX_PLAYERS:
		if bool(slots[i]["on"]):
			_draw_head_icon(_slot_look(i), pos + Vector2(48 + idx * 54, 46), 22)
			idx += 1
	_txt("%d PLAYER%s" % [n, "" if n == 1 else "S"], pos + Vector2(48 + n * 54 + 6, 40), 26, Color.WHITE)
	_txt("coins x%.2f  -  goals x%.2f" % [Data.coop_multiplier(n), 1.0 + 0.55 * float(n - 1)], pos + Vector2(48 + n * 54 + 6, 66), 18, Color(1, 1, 1, 0.9))
	_button(Rect2(pos + Vector2(488, 14), Vector2(160, 56)), "CHANGE", "players", Color("4c8bf5"), 22)


func _draw_lock(c: Vector2) -> void:
	draw_arc(c + Vector2(0, -12), 17, PI, TAU, 14, C_OUTLINE, 11.0)
	draw_arc(c + Vector2(0, -12), 17, PI, TAU, 14, Color("d7dae8"), 6.0)
	_rr(Rect2(c + Vector2(-26, -12), Vector2(52, 42)), Color("ffd166"), 10, C_OUTLINE, 4)
	draw_circle(c + Vector2(0, 7), 6, C_OUTLINE)


# ====================================================================
# Players (co-op set-up)
# ====================================================================

func _draw_players() -> void:
	_button(Rect2(16, 14, 130, 54), "BACK", "players_done", Color("8d99ae"), 24)
	_ctext("Who's cooking?", Vector2(W / 2, 54), 48)
	_ctext("1-4 players on one screen. More chefs = more coins!", Vector2(W / 2, 98), 22, Color(1, 1, 1, 0.9))
	var n := _nplayers()
	for i in Data.MAX_PLAYERS:
		var k := _pop_in(0.06 * i, 0.4)
		if k <= 0.0:
			continue
		var r := Rect2(24 + i * 310, 124, 290, 480)
		_xf_about(r.get_center(), k, k)
		var on: bool = slots[i]["on"]
		var pcol := Color(Data.PLAYER_COLORS[i])
		_panel(r, pcol.lerp(Color("6a5a8a"), 0.35) if on else Color("55587a"))
		_txt("PLAYER %d" % (i + 1), r.position + Vector2(20, 44), 28, pcol.lightened(0.35) if on else Color(1, 1, 1, 0.6))
		if on:
			var cx := r.position.x + 145
			_ell(Vector2(cx, r.position.y + 240), 54, 12, Color(0, 0, 0, 0.25))
			_stage_chef("slot_%d" % i, _slot_look(i), Vector2(cx, r.position.y + 254), 0.56, "idle")
			_ctext(_slot_name(i), Vector2(cx, r.position.y + 282), 26, Color.WHITE)
			var ctrl: String = str((KEYS[i] as Dictionary)["label"])
			if Input.get_connected_joypads().has(i):
				ctrl += " / Gamepad"
			if i == 0:
				ctrl += " / Mouse"
			_ctext(ctrl, Vector2(cx, r.position.y + 310), 16, Color(1, 1, 1, 0.8))
			if i == 0:
				_ctext("(main account)", Vector2(cx, r.position.y + 356), 18, Color(1, 1, 1, 0.7))
			else:
				var gl := "Guest" if str(slots[i]["pid"]) == "" else "Account"
				_arrow_button(Vector2(r.position.x + 36, r.position.y + 346), true, "slot_prev_%d" % i)
				_arrow_button(Vector2(r.position.x + 254, r.position.y + 346), false, "slot_next_%d" % i)
				_ctext(gl, Vector2(cx, r.position.y + 354), 22, C_GOLD)
			_button(Rect2(r.position + Vector2(20, 384), Vector2(250, 56)), "CUSTOMIZE", "slot_cust_%d" % i, Color("9b5de5"), 22)
			if i > 0:
				_button(Rect2(r.position + Vector2(20, 446), Vector2(250, 30)), "REMOVE", "slot_off_%d" % i, Color("8d99ae"), 16)
		else:
			_ctext("Empty", Vector2(r.position.x + 145, r.position.y + 190), 34, Color(1, 1, 1, 0.5))
			_button(Rect2(r.position + Vector2(40, 250), Vector2(210, 80)), "+ JOIN", "slot_on_%d" % i, Color("39b36b"), 34)
			_ctext("%s" % str((KEYS[i] as Dictionary)["label"]), Vector2(r.position.x + 145, r.position.y + 380), 18, Color(1, 1, 1, 0.7))
		_xf_reset()
	_ctext("%d player%s  =  coins x%.2f   (goals x%.2f, guests come faster)" % [n, "" if n == 1 else "s", Data.coop_multiplier(n), 1.0 + 0.55 * float(n - 1)], Vector2(W / 2, 640), 26, C_GOLD)
	_button(Rect2(W / 2 - 150, 654, 300, 60), "DONE", "players_done", Color("ff6b3d"), 30)


# ====================================================================
# Customise
# ====================================================================

func _draw_customize() -> void:
	var look := _edit_look()
	var pname := str(acc.get_profile(edit_pid).get("name", "")) if edit_pid != "" else _slot_name(edit_slot)
	_button(Rect2(16, 14, 160, 54), "DONE", "cust_done", Color("39b36b"), 26)
	_ctext("Customize your chef", Vector2(W / 2, 54), 46)
	_spr("glow", Vector2(330, 360), 4.8, 0.0, Color(1, 1, 1, 0.55))
	_ell(Vector2(330, 540), 150, 28, Color(0, 0, 0, 0.3))
	var k := 1.0 + sin(t_global * 3.0) * 0.012
	_stage_chef("custom", look, Vector2(330, 565), 1.0, "turn", "smile")
	_ctext(pname, Vector2(330, 596), 38, Color.WHITE)
	if edit_pid != "" or str(slots[edit_slot]["pid"]) != "":
		_button(Rect2(210, 608, 240, 46), "RENAME", "cust_rename", Color("4c8bf5"), 22)
	_button(Rect2(210, 664, 240, 42), "RANDOM", "cust_random", Color("ff9f1c"), 20)
	var y := 100.0
	for c in CUSTOM_CATS:
		var id: String = c["id"]
		var size := _cat_size(id)
		var cur := clampi(int(look.get(id, 0)), 0, size - 1)
		var r := Rect2(640, y, 620, 78)
		_panel(r, Color("c99a6b"))
		_txt(str(c["label"]), r.position + Vector2(24, 48), 26, Color.WHITE)
		_arrow_button(r.position + Vector2(300, 39), true, "cust_prev_" + id)
		_arrow_button(r.position + Vector2(584, 39), false, "cust_next_" + id)
		var vc := r.position + Vector2(442, 39)
		if id == "skin" or id.ends_with("col") or id == "jacket" or id == "apron" or id == "scarf":
			var list: Array = Data.SKINS if id == "skin" else Data.COLORS
			var show := 5
			var start := clampi(cur - 2, 0, maxi(0, size - show))
			for m in show:
				var idx := start + m
				if idx >= size:
					break
				var sc := Vector2(vc.x - 2 * 40 + m * 40, vc.y)
				var rect := Rect2(sc - Vector2(17, 17), Vector2(34, 34))
				buttons.append({"rect": rect, "id": "cust_set_%s_%d" % [id, idx]})
				draw_circle(sc, 18 if idx == cur else 15, C_OUTLINE)
				draw_circle(sc, 14 if idx == cur else 12, Color(str(list[idx])))
				if idx == cur:
					draw_arc(sc, 21, 0, TAU, 20, C_GOLD, 3.0)
		else:
			var label := str(Data.HATS[cur]) if id == "hat" else str(Data.ACCS[cur])
			_ctext(label.capitalize(), vc + Vector2(0, 10), 28, Color.WHITE)
		y += 86.0


# ====================================================================
# Accounts
# ====================================================================

func _draw_profiles() -> void:
	_button(Rect2(16, 14, 130, 54), "BACK", "menu", Color("8d99ae"), 24)
	_ctext("Accounts", Vector2(W / 2, 54), 48)
	_ctext("Saved on this device. Tap an account to play as it.", Vector2(W / 2, 96), 22, Color(1, 1, 1, 0.9))
	for i in acc.order.size():
		var pid: String = acc.order[i]
		var p: Dictionary = acc.get_profile(pid)
		var kk := _pop_in(0.04 * i, 0.35)
		if kk <= 0.0:
			continue
		var r := Rect2(30 + (i % 2) * 620, 120 + (i / 2) * 118, 600, 106)
		_xf_about(r.get_center(), kk, kk)
		var active := pid == acc.active
		_panel(r, Color("ffd84a") if active else Color("c99a6b"))
		buttons.append({"rect": Rect2(r.position, Vector2(r.size.x - 120, r.size.y)), "id": "prof_use_" + pid})
		_draw_head_icon(p["look"], r.position + Vector2(56, 54), 34)
		_txt(str(p["name"]), r.position + Vector2(112, 44), 30, Color.WHITE, HORIZONTAL_ALIGNMENT_LEFT, 330)
		var total := 0
		for s in (p["stars"] as Array):
			total += int(s)
		_spr("coin", r.position + Vector2(128, 74), 0.6)
		_txt(str(int(p["coins"])), r.position + Vector2(146, 82), 22, C_GOLD)
		_spr("star_on", r.position + Vector2(246, 74), 0.5)
		_txt("%d" % total, r.position + Vector2(264, 82), 22, C_GOLD)
		var st: Dictionary = p["stats"]
		_txt("served %d" % int(st["served"]), r.position + Vector2(318, 82), 16, Color(1, 1, 1, 0.8))
		if active:
			_txt("PLAYING", r.position + Vector2(r.size.x - 200, 36), 18, Color("39b36b"))
		if acc.order.size() > 1:
			var sure := confirm_delete == pid
			_button(Rect2(r.position + Vector2(r.size.x - 112, 40), Vector2(98, 48)), "SURE?" if sure else "DELETE", "prof_del_" + pid, C_BAD if sure else Color("8d99ae"), 16)
		_xf_reset()
	if acc.order.size() < Accounts.MAX_PROFILES:
		_button(Rect2(W / 2 - 180, 612, 360, 80), "+ NEW ACCOUNT", "prof_new", Color("39b36b"), 32)


func _draw_name() -> void:
	_button(Rect2(16, 14, 160, 54), "CANCEL", "key_cancel", Color("8d99ae"), 24)
	_ctext("New account" if name_mode == "new" else "Rename", Vector2(W / 2, 70), 50)
	var box := Rect2(W / 2 - 300, 100, 600, 80)
	_panel(box, Color("fff4dc"))
	var cur := "|" if int(t_global * 2.0) % 2 == 0 else " "
	_ctext(name_buf + cur if name_buf != "" else "type a name" + cur, box.get_center() + Vector2(0, 16), 44, Color("ff6b3d") if name_buf != "" else Color(1, 1, 1, 0.5))
	var y := 230.0
	for row_v in KEY_ROWS:
		var row: String = row_v
		var w := 78.0
		var x0 := W / 2 - (row.length() * (w + 8)) / 2.0 + 4
		for i in row.length():
			var ch := row.substr(i, 1)
			_button(Rect2(x0 + i * (w + 8), y, w, 70), ch, "key_" + ch, Color("ffb457"), 34)
		y += 92.0
	_button(Rect2(W / 2 - 330, y + 8, 200, 70), "RANDOM", "key_random", Color("9b5de5"), 24)
	_button(Rect2(W / 2 - 110, y + 8, 220, 70), "SPACE", "key_space", Color("8d99ae"), 24)
	_button(Rect2(W / 2 + 130, y + 8, 200, 70), "DEL", "key_back", Color("ef476f"), 28)
	_button(Rect2(W / 2 - 160, y + 106, 320, 80), "OK", "key_ok", Color("39b36b"), 40)


# ====================================================================
# Shop
# ====================================================================

func _upgrade_icon(id: String, c: Vector2) -> void:
	match id:
		"boots":
			_spr("shoe", c, 2.6, 0.0, Color("ff9f1c"))
		"knife":
			_spr("chop_board", c, 1.1)
		"pan":
			_spr("pot", c, 1.1)
		"chairs":
			_spr("seat", c, 1.1)
		"tips":
			_spr("coin", c, 1.7)


func _draw_shop() -> void:
	_coin_bar()
	_button(Rect2(16, 14, 130, 54), "BACK", "menu", Color("8d99ae"), 24)
	_ctext("Upgrades", Vector2(W / 2, 56), 50)
	_ctext("for %s  -  upgrades apply to every chef in the kitchen" % str(_prof()["name"]), Vector2(W / 2, 100), 22, Color(1, 1, 1, 0.9))
	var up: Dictionary = _prof()["upg"]
	var n := 0
	for u in Data.UPGRADES:
		var id: String = u["id"]
		var k := _pop_in(0.06 * n, 0.4)
		var col := n % 3
		var row := n / 3
		var xo := 40.0 + col * 410.0 + (205.0 if row == 1 else 0.0)
		var r := Rect2(xo, 130 + row * 280, 390, 262)
		n += 1
		if k <= 0.0:
			continue
		_xf_about(r.get_center(), k, k)
		var lvl := int(up.get(id, 0))
		var mx: int = u["max"]
		_panel(r, Color("c99a6b"))
		_spr("puff", r.position + Vector2(70, 80), 1.9, 0.0, Color(1, 1, 1, 0.9))
		_upgrade_icon(id, r.position + Vector2(70, 80))
		_txt(str(u["name"]), r.position + Vector2(130, 62), 30, Color.WHITE, HORIZONTAL_ALIGNMENT_LEFT, 250)
		_txt(str(u["desc"]), r.position + Vector2(130, 94), 17, Color(1, 1, 1, 0.95), HORIZONTAL_ALIGNMENT_LEFT, 250)
		for p in mx:
			_rr(Rect2(r.position + Vector2(130 + p * 46, 112), Vector2(38, 24)), C_GOOD if p < lvl else Color(0, 0, 0, 0.25), 8, C_OUTLINE, 3)
		if lvl >= mx:
			_ctext("MAX", r.position + Vector2(195, 214), 44, C_GOLD)
		else:
			var cost := Data.upgrade_cost(lvl)
			_button(Rect2(r.position + Vector2(60, 156), Vector2(270, 80)), "     %d" % cost, "buy_" + id, Color("39b36b"), 38, int(_prof()["coins"]) >= cost)
			_coin(r.position + Vector2(112, 196), 18)
		_xf_reset()


# ====================================================================
# Brief
# ====================================================================

func _ingredient_icons(id: String, c: Vector2, size: float, gap: float) -> void:
	var items: Array = (Data.RECIPES[id]["items"] as Array).duplicate()
	items.sort()
	for i in items.size():
		_draw_item(items[i], c + Vector2(i * gap, 0), size)


func _draw_brief() -> void:
	var d: Dictionary = Data.LEVELS[cur_level]
	_button(Rect2(16, 14, 130, 54), "BACK", "levels", Color("8d99ae"), 24)
	_ctext("%s  -  Level %d" % [str(Data.WORLDS[cur_level / 5]["name"]), cur_level + 1], Vector2(430, 50), 28, Color(1, 1, 1, 0.9))
	_menu_title(str(d["name"]), Vector2(430, 126), 72, C_GOLD, 0.0)
	_ctext("%d seconds  -  %d tables" % [int(d["time"]), mini(4, int(d["seats"]) + (_nplayers() - 1) / 2)], Vector2(430, 168), 24)
	var recs: Array = d["recipes"]
	var n := 0
	for id in recs:
		var k := _pop_in(0.1 + 0.07 * n, 0.4)
		var r := Rect2(30 + (n % 2) * 392, 196 + (n / 2) * 160, 380, 148)
		n += 1
		if k <= 0.0:
			continue
		_xf_about(r.get_center(), k, k)
		_panel(r, Color("c99a6b"))
		_draw_dish(id, r.position + Vector2(66, 60), 28)
		_txt("%s  (%d)" % [str(Data.RECIPES[id]["name"]), int(Data.RECIPES[id]["price"])], r.position + Vector2(124, 50), 28, Color.WHITE)
		_ingredient_icons(id, r.position + Vector2(160, 104), 15, 58)
		_xf_reset()
	var gp := Rect2(820, 90, 440, 460)
	_panel(gp, Color("8a6aa8"))
	_ctext("Earn coins for stars", Vector2(gp.get_center().x, gp.position.y + 46), 28)
	var goals := _goals()
	for k in 3:
		var cy := gp.position.y + 100 + k * 60
		_star(Vector2(gp.position.x + 80, cy), 24, k < _stars_of(cur_level))
		_txt(str(int(goals[k])), Vector2(gp.position.x + 130, cy + 12), 34, C_GOLD)
		_coin(Vector2(gp.position.x + 250, cy), 14)
	var idx := 0
	for i in Data.MAX_PLAYERS:
		if bool(slots[i]["on"]):
			var py := gp.position.y + 290 + idx * 38
			_draw_head_icon(_slot_look(i), Vector2(gp.position.x + 44, py), 15)
			var ctrl: String = str((KEYS[i] as Dictionary)["label"]) + ("  /  mouse" if i == 0 else "")
			_txt("%s  %s" % [_slot_name(i), ctrl], Vector2(gp.position.x + 72, py + 7), 17, Color(Data.PLAYER_COLORS[i]).lightened(0.4), HORIZONTAL_ALIGNMENT_LEFT, 360)
			idx += 1
	_ctext("coins x%.2f for everyone" % Data.coop_multiplier(_nplayers()), Vector2(gp.get_center().x, gp.end.y - 16), 20, Color.WHITE)
	_button(Rect2(820, 562, 210, 54), "PLAYERS", "players", Color("4c8bf5"), 24)
	_button(Rect2(1050, 562, 210, 54), "SHOP", "shop", Color("ff9f1c"), 24)
	if net_mode == 2:
		_ctext("Waiting for the host to start...", Vector2(1040, 670), 26, C_GOLD)
	else:
		_button(Rect2(820, 628, 440, 80), "START!", "start", Color("ff6b3d"), 50)


# ====================================================================
# Result
# ====================================================================

func _draw_result() -> void:
	var t := result_t
	var win := result_stars > 0
	var bk := _ease_back(t / 0.5)
	_xf_about(Vector2(W / 2, 80), bk, bk)
	_spr("ribbon", Vector2(W / 2, 80), 1.35, 0.0, Color.WHITE if win else Color("8d99ae"))
	_ctext("TIME'S UP!" if win else "TRY AGAIN", Vector2(W / 2, 96), 56, Color.WHITE)
	_xf_reset()
	_ctext(str(lv["name"]), Vector2(395, 168), 30, Color(1, 1, 1, 0.95))
	var goals := _goals()
	for k in 3:
		var cx := 245.0 + k * 150.0
		var cy := 300.0 - (30.0 if k == 1 else 0.0)
		_star(Vector2(cx, cy), 62, false)
		var show_t: float = [0.8, 1.4, 2.0][k]
		if k < result_stars and t >= show_t:
			var sc := 1.0 + maxf(0.0, 0.7 - (t - show_t) * 2.4)
			var rot := sin((t - show_t) * 9.0) * 0.12 * maxf(0.0, 1.0 - (t - show_t))
			_spr("glow", Vector2(cx, cy), 2.0 * minf(1.0, (t - show_t) * 3.0), 0.0, Color(1, 1, 1, 0.55))
			_spr("star_on", Vector2(cx, cy), 62.0 / 22.0 * sc, rot)
		_ctext(str(int(goals[k])), Vector2(cx, cy + 92), 24, Color(1, 1, 1, 0.9))
	var shown := int(minf(1.0, t / 0.8) * earned)
	_coin(Vector2(290, 480), 28)
	_txt("+%d" % shown, Vector2(332, 500), 66, C_GOLD)
	_ctext("Served %d     Lost %d     Best combo x%d" % [served, lost, best_streak], Vector2(395, 550), 24)
	if result_new_best and result_stars > 0:
		_ctext("NEW BEST!", Vector2(395, 604 + sin(t * 8.0) * 4.0), 40, Color("ff5a36"))
	if level_unlocked_msg:
		_ctext("Next level unlocked!", Vector2(395, 646), 28, C_GOOD)
	var pr := Rect2(790, 120, 460, 400)
	_panel(pr, Color("8a6aa8"))
	_ctext("Payout", Vector2(pr.get_center().x, pr.position.y + 44), 32)
	var multtxt := "co-op bonus x%.2f" % result_bonus if result_bonus > 1.0 else "solo"
	_ctext("team earned %d   (%s)" % [earned, multtxt], Vector2(pr.get_center().x, pr.position.y + 76), 18, Color(1, 1, 1, 0.9))
	for i in result_payouts.size():
		var p: Dictionary = result_payouts[i]
		var py := pr.position.y + 118 + i * 66
		var kk := clampf((t - 0.6 - i * 0.15) * 4.0, 0.0, 1.0)
		if kk <= 0.0:
			continue
		_xf_about(Vector2(pr.get_center().x, py + 24), kk, kk)
		_draw_head_icon(p["look"], Vector2(pr.position.x + 56, py + 26), 24)
		_txt(str(p["name"]), Vector2(pr.position.x + 96, py + 22), 24, Color.WHITE, HORIZONTAL_ALIGNMENT_LEFT, 190)
		_txt("served %d%s" % [int(p["served"]), "  (guest)" if bool(p["guest"]) else ""], Vector2(pr.position.x + 96, py + 44), 15, Color(1, 1, 1, 0.8))
		_coin(Vector2(pr.position.x + 330, py + 24), 14)
		_txt("+%d" % int(p["coins"]), Vector2(pr.position.x + 352, py + 34), 28, C_GOLD)
		_xf_reset()
	if t > 1.0:
		var bkk := _ease_back((t - 1.0) / 0.4)
		var can_next := result_stars > 0 and cur_level + 1 < Data.LEVELS.size()
		if net_mode == 2:
			_ctext("Waiting for the host...", Vector2(1020, 600), 26, C_GOLD)
			_button(Rect2(790, 632, 460, 60), "LEAVE", "levels", Color("8d99ae"), 24)
		else:
			if can_next:
				_button(Rect2(790 + 230 - 230 * bkk, 540, 460 * bkk, 80), "NEXT LEVEL", "next", Color("ff6b3d"), 38)
			_button(Rect2(790, 632, 140, 60), "RETRY", "retry", Color("4c8bf5"), 24)
			_button(Rect2(940, 632, 150, 60), "LEVELS", "levels", Color("8d99ae"), 22)
			_button(Rect2(1100, 632, 150, 60), "SHOP", "shop", Color("39b36b"), 22)


# ====================================================================
# Gameplay drawing
# ====================================================================

func _tutorial_text() -> String:
	if cur_level != 0 or chefs.is_empty():
		return ""
	var ch: Chef = chefs[0]
	if ch.held.begins_with("dish:"):
		return "Walk next to the customer and press E (or tap them)"
	if ch.held == "veg":
		return "Take it to a CHOP board"
	if ch.held == "veg_chop":
		return "Put it on the PLATE"
	if ch.held == "":
		for k in plates:
			if _recipe_for(plates[k]) != "":
				return "Pick up the finished salad from the PLATE"
		for k in stations:
			var s: Dictionary = stations[k]
			if map[Vector2i(k).y][Vector2i(k).x] == "C" and s["st"] == "done":
				return "Grab the chopped veg from the board"
		return "Tap the VEG crate. Salad = 2 chopped veg. Move: WASD, use: E"
	return ""


func _draw_game() -> void:
	pass   # the kitchen is rendered by world3d.gd; overlays are drawn by hud_layer.gd
