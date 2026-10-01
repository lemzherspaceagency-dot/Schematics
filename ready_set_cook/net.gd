extends Node
# Online co-op over ENet. The host runs the whole simulation; everyone else sends their
# input and gets the game state back 20 times a second. Direct connect by IP (LAN, or a
# forwarded port). Not available in web builds (browsers can't open ENet sockets).

const PORT := 24680
const SEND_EVERY := 0.05

var main: Node                    # the GameSim / Main node
var phase := "menu"               # menu | hosting | join | connecting | connected
var ip_text := "192.168."
var info := ""
var peers: Dictionary = {}        # host: peer id -> {name, look}
var my_index := -1                # client: which chef is mine
var acc_t := 0.0
var in_dir_sent := Vector2i(99, 99)
var goals: Dictionary = {}        # client: chef id -> target position
var snap_vel: Dictionary = {}


func _ready() -> void:
	multiplayer.peer_connected.connect(_on_peer_connected)
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	multiplayer.connected_to_server.connect(_on_connected)
	multiplayer.connection_failed.connect(_on_failed)
	multiplayer.server_disconnected.connect(_on_server_gone)


func available() -> bool:
	return not OS.has_feature("web")


# ====================================================================
# Screens
# ====================================================================

func open_screen() -> void:
	if main.net_mode == 0:
		phase = "menu"
		info = "" if available() else "Online play needs the desktop or Android version."
	main._goto(main.S.ONLINE)


func leave() -> void:
	multiplayer.multiplayer_peer = null
	main.net_mode = 0
	peers.clear()
	phase = "menu"
	main.chefs.clear()


func on_button(id: String) -> void:
	match id:
		"host":
			if not available():
				return
			var p := ENetMultiplayerPeer.new()
			var err := p.create_server(PORT, 3)
			if err != OK:
				info = "Couldn't open port %d (error %d)." % [PORT, err]
				return
			multiplayer.multiplayer_peer = p
			main.net_mode = 1
			phase = "hosting"
			info = ""
		"join":
			if not available():
				return
			phase = "join"
			info = ""
		"back":
			if phase == "menu":
				main._goto(main.S.MENU)
			else:
				leave()
		"stop", "leave":
			leave()
			main._goto(main.S.MENU)
		"go":
			main._goto(main.S.LEVELS)
		"connect":
			var p2 := ENetMultiplayerPeer.new()
			var addr := ip_text.strip_edges()
			var port := PORT
			if addr.contains(":"):
				var parts := addr.split(":")
				addr = parts[0]
				port = int(parts[1])
			var err2 := p2.create_client(addr, port)
			if err2 != OK:
				info = "Couldn't connect (error %d)." % err2
				return
			multiplayer.multiplayer_peer = p2
			phase = "connecting"
			info = "Connecting to %s ..." % addr
		"kback":
			ip_text = ip_text.substr(0, maxi(0, ip_text.length() - 1))
		"kdot":
			ip_text += "."
		"kcolon":
			ip_text += ":"
		_:
			if id.begins_with("k") and id.length() == 2 and ip_text.length() < 21:
				ip_text += id.substr(1)


func on_key(event: InputEventKey) -> void:
	if phase != "join":
		if event.physical_keycode == KEY_ESCAPE:
			on_button("back")
		return
	if event.physical_keycode == KEY_BACKSPACE:
		on_button("kback")
	elif event.physical_keycode == KEY_ENTER or event.physical_keycode == KEY_KP_ENTER:
		on_button("connect")
	elif event.physical_keycode == KEY_ESCAPE:
		on_button("back")
	elif event.unicode >= 48 and event.unicode <= 58 or event.unicode == 46:
		if ip_text.length() < 21:
			ip_text += char(event.unicode)


func draw_screen() -> void:
	var m = main
	m._button(Rect2(16, 14, 130, 54), "BACK", "net_back" if phase != "hosting" and phase != "connected" else "net_leave", Color("8d99ae"), 24)
	m._ctext("Play online", Vector2(m.W / 2, 56), 52)
	m._ctext("Host runs the kitchen, friends join with the host's address (up to 4 chefs total).", Vector2(m.W / 2, 98), 20, Color(1, 1, 1, 0.9))
	match phase:
		"menu":
			m._button(Rect2(m.W / 2 - 330, 200, 300, 130), "HOST GAME", "net_host", Color("39b36b"), 40, available())
			m._button(Rect2(m.W / 2 + 30, 200, 300, 130), "JOIN GAME", "net_join", Color("4c8bf5"), 40, available())
			m._ctext(info if info != "" else "Both players need the same game version.", Vector2(m.W / 2, 420), 24, C_INFO if info != "" else Color(1, 1, 1, 0.8))
		"hosting":
			var addrs: Array = []
			for a in IP.get_local_addresses():
				var s := str(a)
				if s.count(".") == 3 and not s.begins_with("127.") and not s.begins_with("169.254"):
					addrs.append(s)
			var pr := Rect2(60, 140, 540, 400)
			m._panel(pr, Color("c99a6b"))
			m._ctext("You are hosting", Vector2(pr.get_center().x, 190), 36)
			m._ctext("Tell friends to join with:", Vector2(pr.get_center().x, 232), 22, Color(1, 1, 1, 0.9))
			for i in mini(addrs.size(), 5):
				m._ctext("%s : %d" % [addrs[i], PORT], Vector2(pr.get_center().x, 286 + i * 44), 32, m.C_GOLD)
			m._ctext("Allow UDP port %d through your firewall." % PORT, Vector2(pr.get_center().x, 500), 18, Color(1, 1, 1, 0.85))
			if addrs.is_empty():
				m._ctext("(no network found)", Vector2(pr.get_center().x, 290), 28, Color(1, 1, 1, 0.7))
			var lr := Rect2(640, 140, 580, 400)
			m._panel(lr, Color("8a6aa8"))
			m._ctext("Chefs in the kitchen", Vector2(lr.get_center().x, 190), 32)
			m._draw_head_icon(m._slot_look(0), Vector2(700, 250), 24)
			m._txt("%s  (you)" % m._slot_name(0), Vector2(740, 260), 26, Color.WHITE)
			var i := 0
			for pid in peers:
				var pr2: Dictionary = peers[pid]
				m._draw_head_icon(pr2["look"], Vector2(700, 316 + i * 64), 24)
				m._txt(str(pr2["name"]), Vector2(740, 326 + i * 64), 26, Color.WHITE)
				i += 1
			if peers.is_empty():
				m._ctext("waiting for friends...", Vector2(lr.get_center().x, 340), 24, Color(1, 1, 1, 0.7))
			m._button(Rect2(m.W / 2 - 200, 570, 400, 96), "PICK A LEVEL", "net_go", Color("ff6b3d"), 40)
			m._button(Rect2(m.W - 220, 586, 190, 60), "STOP", "net_stop", Color("8d99ae"), 24)
		"join":
			m._ctext("Host address", Vector2(m.W / 2, 160), 34)
			var box := Rect2(m.W / 2 - 300, 180, 600, 80)
			m._panel(box, Color("fff4dc"))
			var cur := "|" if int(m.t_global * 2.0) % 2 == 0 else " "
			m._ctext(ip_text + cur, box.get_center() + Vector2(0, 16), 44, Color("ff6b3d"))
			var keys := "1234567890"
			for i in 10:
				var r := Rect2(m.W / 2 - 5 * 84 + i * 84 + 4, 290, 76, 70)
				m._button(r, keys.substr(i, 1), "net_k" + keys.substr(i, 1), Color("ffb457"), 34)
			m._button(Rect2(m.W / 2 - 340, 380, 200, 70), ".", "net_kdot", Color("8d99ae"), 40)
			m._button(Rect2(m.W / 2 - 120, 380, 240, 70), "DEL", "net_kback", Color("ef476f"), 28)
			m._button(Rect2(m.W / 2 + 140, 380, 200, 70), ":", "net_kcolon", Color("8d99ae"), 40)
			m._button(Rect2(m.W / 2 - 180, 500, 360, 90), "CONNECT", "net_connect", Color("39b36b"), 42)
			m._ctext(info, Vector2(m.W / 2, 640), 24, C_INFO)
		"connecting":
			m._ctext(info, Vector2(m.W / 2, 340), 36)
		"connected":
			m._ctext("Connected!", Vector2(m.W / 2, 280), 64, m.C_GOOD)
			m._ctext("Waiting for the host to pick a level...", Vector2(m.W / 2, 350), 30)
			m._draw_head_icon(m._slot_look(0), Vector2(m.W / 2, 440), 40)
			m._ctext(m._slot_name(0), Vector2(m.W / 2, 520), 30, Color.WHITE)
			m._button(Rect2(m.W / 2 - 150, 580, 300, 70), "LEAVE", "net_leave", Color("8d99ae"), 28)


const C_INFO := Color("ffd166")


# ====================================================================
# Connection events
# ====================================================================

func _on_peer_connected(id: int) -> void:
	pass


func _on_peer_disconnected(id: int) -> void:
	if main.net_mode == 1 and peers.has(id):
		peers.erase(id)
		for ch in main.chefs:
			if ch.remote and ch.peer == id:
				ch.in_dir = Vector2i.ZERO
				ch.name += " (left)"


func _on_connected() -> void:
	phase = "connected"
	main.net_mode = 2
	rpc_id(1, "c_hello", main._slot_name(0), main._slot_look(0))


func _on_failed() -> void:
	multiplayer.multiplayer_peer = null
	phase = "join"
	info = "Couldn't reach the host. Check the address and firewall."


func _on_server_gone() -> void:
	multiplayer.multiplayer_peer = null
	main.net_mode = 0
	main.chefs.clear()
	phase = "menu"
	info = "The host left the game."
	main.state = main.S.ONLINE
	main.state_t = 0.0


# ====================================================================
# Host side
# ====================================================================

func remote_list() -> Array:
	var out: Array = []
	for pid in peers:
		out.append({"name": peers[pid]["name"], "look": peers[pid]["look"], "peer": pid})
	return out


@rpc("any_peer", "reliable")
func c_hello(pname: String, look: Dictionary) -> void:
	if main.net_mode != 1:
		return
	var id := multiplayer.get_remote_sender_id()
	if peers.size() >= 3:
		return
	peers[id] = {"name": pname.substr(0, 14), "look": look}


@rpc("any_peer", "unreliable_ordered")
func c_input(dir: Vector2i) -> void:
	if main.net_mode != 1:
		return
	var id := multiplayer.get_remote_sender_id()
	for ch in main.chefs:
		if ch.remote and ch.peer == id:
			ch.in_dir = Vector2i(clampi(dir.x, -1, 1), clampi(dir.y, -1, 1))


@rpc("any_peer", "reliable")
func c_act() -> void:
	if main.net_mode != 1:
		return
	var id := multiplayer.get_remote_sender_id()
	for ch in main.chefs:
		if ch.remote and ch.peer == id:
			main._chef_act(ch)


@rpc("any_peer", "reliable")
func c_tap(p: Vector2) -> void:
	if main.net_mode != 1:
		return
	var id := multiplayer.get_remote_sender_id()
	for ch in main.chefs:
		if ch.remote and ch.peer == id:
			main._chef_tap(ch, p)


func host_start_level() -> void:
	var defs: Array = []
	for ch in main.chefs:
		defs.append({"name": ch.name, "look": ch.look, "peer": ch.peer if ch.remote else 1, "pos": ch.pos})
	var seat_list: Array = []
	for s in main.seats:
		seat_list.append(s)
	rpc("s_start", main.cur_level, defs, seat_list)


func host_result() -> void:
	var payload := {"stars": main.result_stars, "earned": main.earned, "served": main.served, "lost": main.lost,
		"best": main.best_streak, "bonus": main.result_bonus, "payouts": main.result_payouts, "new_best": main.result_new_best}
	rpc("s_result", payload)


func tick(delta: float) -> void:
	if main.net_mode == 1:
		acc_t += delta
		if acc_t >= SEND_EVERY:
			acc_t = 0.0
			_host_send()
	elif main.net_mode == 2:
		_client_tick(delta)


func _host_send() -> void:
	if peers.is_empty():
		main.ev_out.clear()
		return
	if main.state == main.S.PLAY:
		var chs: Array = []
		for ch in main.chefs:
			chs.append([ch.pos, ch.vel, ch.face, ch.held, ch.dir, ch.bump])
		var sn: Array = []
		for key in main.stations:
			var s: Dictionary = main.stations[key]
			sn.append([s["in"], s["out"], s["t"], s["st"]])
		var pl: Array = []
		for key in main.plates:
			pl.append(main.plates[key])
		var cu: Array = []
		for c in main.customers:
			cu.append([c["seat"], c["order"], c["pat"], c["max"], c["st"], c["t"], c["look"], c["vip"]])
		rpc("s_state", {"t": main.time_left, "e": main.earned, "sv": main.served, "lo": main.lost, "sk": main.streak, "i": main.intro,
			"ch": chs, "sn": sn, "pl": pl, "cu": cu})
	if not main.ev_out.is_empty():
		rpc("s_events", main.ev_out.duplicate())
		main.ev_out.clear()


# ====================================================================
# Client side
# ====================================================================

@rpc("authority", "reliable")
func s_start(level: int, defs: Array, seat_list: Array) -> void:
	if main.net_mode != 2:
		return
	var m = main
	m.cur_level = level
	m.lv = Data.LEVELS[level]
	m._setup_map(level / 5)
	m.time_left = float(m.lv["time"])
	m.earned = 0
	m.served = 0
	m.lost = 0
	m.streak = 0
	m.customers = []
	m.particles = []
	m.popups = []
	m.pops = {}
	m.stations = {}
	m.plates = {}
	for y in Data.ROWS:
		for x in Data.COLS:
			var k: String = m.map[y][x]
			if Data.RULES.has(k):
				m.stations[Vector2i(x, y)] = {"in": "", "out": "", "t": 0.0, "st": "idle", "puff": 0.0}
			elif k == "A":
				m.plates[Vector2i(x, y)] = []
	m.seats = []
	for s in seat_list:
		m.seats.append(s)
	m.chefs.clear()
	my_index = -1
	goals.clear()
	for i in defs.size():
		var d: Dictionary = defs[i]
		var ch := Chef.new()
		ch.id = i
		ch.name = str(d["name"])
		ch.look = d["look"]
		ch.pos = d["pos"]
		ch.held_pos = ch.pos
		ch.remote = true
		ch.peer = int(d["peer"])
		if ch.peer == multiplayer.get_unique_id():
			my_index = i
		m.chefs.append(ch)
		goals[i] = ch.pos
	m.view.build_level()
	m.intro = 3.0
	m.earned_shown = 0.0
	m.state_t = 0.0
	m.fade = 0.0
	m.pending = -1
	m.state = m.S.PLAY


@rpc("authority", "unreliable_ordered")
func s_state(snap: Dictionary) -> void:
	if main.net_mode != 2 or main.state != main.S.PLAY and main.state != main.S.PAUSE:
		return
	var m = main
	m.time_left = float(snap["t"])
	m.earned = int(snap["e"])
	m.served = int(snap["sv"])
	m.lost = int(snap["lo"])
	m.streak = int(snap["sk"])
	m.best_streak = maxi(m.best_streak, m.streak)
	m.intro = float(snap["i"])
	var chs: Array = snap["ch"]
	for i in mini(chs.size(), m.chefs.size()):
		var a: Array = chs[i]
		var ch: Chef = m.chefs[i]
		goals[i] = a[0]
		ch.vel = a[1]
		ch.held = str(a[3])
		ch.dir = a[4]
		ch.bump = float(a[5])
	var sn: Array = snap["sn"]
	var idx := 0
	for key in m.stations:
		if idx >= sn.size():
			break
		var s: Dictionary = m.stations[key]
		var a2: Array = sn[idx]
		s["in"] = a2[0]
		s["out"] = a2[1]
		s["t"] = a2[2]
		s["st"] = a2[3]
		idx += 1
	var pl: Array = snap["pl"]
	idx = 0
	for key in m.plates:
		if idx >= pl.size():
			break
		m.plates[key] = pl[idx]
		idx += 1
	var cu: Array = snap["cu"]
	var fresh: Array = []
	for a3 in cu:
		var arr: Array = a3
		var existing: Dictionary = {}
		for c in m.customers:
			if Vector2i(c["seat"]) == Vector2i(arr[0]) and c["look"] == arr[6] and c["order"] == arr[1]:
				existing = c
		if existing.is_empty():
			existing = {"seat": arr[0], "order": arr[1], "look": arr[6], "vip": arr[7], "t": float(arr[5])}
		existing["pat"] = arr[2]
		existing["max"] = arr[3]
		existing["st"] = arr[4]
		if absf(float(existing["t"]) - float(arr[5])) > 0.2:
			existing["t"] = float(arr[5])
		fresh.append(existing)
	m.customers = fresh


@rpc("authority", "reliable")
func s_events(list: Array) -> void:
	if main.net_mode != 2:
		return
	var m = main
	for e in list:
		var ev: Array = e
		match str(ev[0]):
			"snd":
				m.sfx.play(str(ev[1]), float(ev[2]))
			"burst":
				m._burst(ev[1], ev[2], int(ev[3]), float(ev[4]))
			"pop":
				m._popup(ev[1], str(ev[2]), ev[3], int(ev[4]))
			"coins":
				m._coin_fly(ev[1], Vector2(52, 38), int(ev[2]))
			"shake":
				m.shake = maxf(m.shake, float(ev[1]))
			"banner":
				m.banner = str(ev[1])
				m.banner_t = 1.4


@rpc("authority", "reliable")
func s_result(res: Dictionary) -> void:
	if main.net_mode != 2:
		return
	var m = main
	m.result_stars = int(res["stars"])
	m.earned = int(res["earned"])
	m.served = int(res["served"])
	m.lost = int(res["lost"])
	m.best_streak = int(res["best"])
	m.result_bonus = float(res["bonus"])
	m.result_payouts = res["payouts"]
	m.result_new_best = bool(res["new_best"])
	m.level_unlocked_msg = false
	# pay myself and record the stars on my own account
	if my_index >= 0 and my_index < m.result_payouts.size():
		var p: Dictionary = m._prof()
		var pay := int((m.result_payouts[my_index] as Dictionary)["coins"])
		p["coins"] = int(p["coins"]) + pay
		var arr: Array = p["stars"]
		arr[m.cur_level] = maxi(int(arr[m.cur_level]), m.result_stars)
		var st: Dictionary = p["stats"]
		st["games"] = int(st["games"]) + 1
		st["coop_games"] = int(st["coop_games"]) + 1
		st["served"] = int(st["served"]) + int((m.result_payouts[my_index] as Dictionary)["served"])
		m.acc.save_all()
	m.result_t = 0.0
	m.state_t = 0.0
	m.state = m.S.RESULT
	m.sfx.play("win" if m.result_stars > 0 else "lose")


func _client_tick(delta: float) -> void:
	# smooth the other chefs' positions between snapshots
	if main.state == main.S.PLAY or main.state == main.S.PAUSE:
		for i in main.chefs.size():
			var ch: Chef = main.chefs[i]
			if goals.has(i):
				ch.pos = ch.pos.lerp(goals[i], 1.0 - exp(-20.0 * delta))
				ch.face = lerpf(ch.face, signf(ch.vel.x) if absf(ch.vel.x) > 8.0 else ch.face, 0.3)
		# my own keyboard / pad direction
		if main.state == main.S.PLAY and main.intro <= 0.0:
			var d := Vector2i.ZERO
			var c0 := Chef.new()
			c0.scheme = 0
			c0.dir = main.chefs[my_index].dir if my_index >= 0 and my_index < main.chefs.size() else Vector2i(0, 1)
			var d0: Vector2i = main._scheme_dir(c0)
			c0.scheme = 1
			var d1: Vector2i = main._scheme_dir(c0)
			d = d0 if d0 != Vector2i.ZERO else d1
			if d != in_dir_sent:
				in_dir_sent = d
				rpc_id(1, "c_input", d)


func client_tap(p: Vector2) -> void:
	rpc_id(1, "c_tap", p)


func client_act() -> void:
	rpc_id(1, "c_act")


func client_key(event: InputEventKey) -> void:
	var code: Key = event.physical_keycode
	for k in [0, 1]:
		if code in ((main.KEYS[k] as Dictionary)["act"] as Array):
			rpc_id(1, "c_act")
			return
