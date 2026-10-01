class_name Accounts
extends RefCounted
# Local player accounts (profiles) saved on this device.
# Each account has a name, a chef look, coins, stars per level, upgrades and a few stats.
# (These are device-local. Cloud accounts need a server; see README.)

const PATH := "user://profiles_v3.json"
const OLD_PATH := "user://save_v2.json"
const MAX_PROFILES := 8
const LEVEL_COUNT := 15

var profiles: Dictionary = {}      # id -> profile
var order: Array = []              # ids in creation order
var active := ""
var sound := true


static func make_profile(id: String, pname: String, slot: int) -> Dictionary:
	var up := {}
	for u in Data.UPGRADES:
		up[u["id"]] = 0
	var st: Array = []
	for i in LEVEL_COUNT:
		st.append(0)
	return {"id": id, "name": pname, "look": Data.default_look(slot), "coins": 0, "stars": st, "upg": up,
		"stats": {"served": 0, "games": 0, "coop_games": 0, "best_combo": 0, "coins_earned": 0}}


func load_all() -> void:
	profiles = {}
	order = []
	if FileAccess.file_exists(PATH):
		var f := FileAccess.open(PATH, FileAccess.READ)
		if f != null:
			var data = JSON.parse_string(f.get_as_text())
			if data is Dictionary:
				active = str(data.get("active", ""))
				sound = bool(data.get("sound", true))
				var plist = data.get("profiles", [])
				if plist is Array:
					for p in plist:
						if p is Dictionary:
							_sanitise(p)
	if profiles.is_empty():
		var id := create(Data.random_name())
		# bring over progress from the v0.2 single save if it exists
		if FileAccess.file_exists(OLD_PATH):
			var f2 := FileAccess.open(OLD_PATH, FileAccess.READ)
			var old = JSON.parse_string(f2.get_as_text()) if f2 != null else null
			if old is Dictionary:
				var p: Dictionary = profiles[id]
				p["coins"] = int(old.get("coins", 0))
				var os = old.get("stars", [])
				if os is Array:
					for i in mini(os.size(), (p["stars"] as Array).size()):
						(p["stars"] as Array)[i] = int(os[i])
		active = id
		save_all()
	if not profiles.has(active):
		active = order[0]


func _sanitise(p: Dictionary) -> void:
	var id := str(p.get("id", ""))
	if id == "":
		return
	var base := make_profile(id, str(p.get("name", "Chef")), order.size())
	base["coins"] = int(p.get("coins", 0))
	var s = p.get("stars", [])
	if s is Array:
		for i in mini(s.size(), LEVEL_COUNT):
			(base["stars"] as Array)[i] = int(s[i])
	var u = p.get("upg", {})
	if u is Dictionary:
		for k in base["upg"]:
			base["upg"][k] = int(u.get(k, 0))
	var lk = p.get("look", {})
	if lk is Dictionary:
		for k in base["look"]:
			base["look"][k] = int(lk.get(k, base["look"][k]))
	var st = p.get("stats", {})
	if st is Dictionary:
		for k in base["stats"]:
			base["stats"][k] = int(st.get(k, 0))
	profiles[id] = base
	order.append(id)


func save_all() -> void:
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	if f == null:
		return
	var plist: Array = []
	for id in order:
		plist.append(profiles[id])
	f.store_string(JSON.stringify({"active": active, "sound": sound, "profiles": plist}))


func create(pname: String) -> String:
	var id := "p%d_%d" % [Time.get_unix_time_from_system(), randi() % 100000]
	profiles[id] = make_profile(id, pname.strip_edges().substr(0, 14), order.size())
	order.append(id)
	return id


func remove(id: String) -> void:
	if order.size() <= 1:
		return
	profiles.erase(id)
	order.erase(id)
	if active == id:
		active = order[0]


func get_profile(id: String) -> Dictionary:
	return profiles.get(id, {})
