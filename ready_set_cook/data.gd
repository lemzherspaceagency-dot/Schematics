class_name Data
extends RefCounted
# All the tweakable game content lives here: machines, recipes, worlds, levels, upgrades, customisation.

const COLS := 16
const ROWS := 9
const MAX_PLAYERS := 4

# Timed machines. "map" = what goes in -> what comes out.
# "burn" < 0 means the machine never burns things (chopping board).
const RULES := {
	"C": {"time": 1.6, "burn": -1.0, "map": {"veg": "veg_chop", "meat": "meat_chop"}, "need": "veg or meat"},
	"S": {"time": 4.0, "burn": 9.0, "map": {"veg_chop": "veg_cook", "meat": "meat_cooked", "meat_chop": "patty"}, "need": "chopped veg or meat"},
	"O": {"time": 5.0, "burn": 11.0, "map": {"dough": "bun"}, "need": "dough"},
}

const CRATES := {"M": "meat", "V": "veg", "D": "dough"}

const RECIPES := {
	"salad": {"name": "Salad", "items": ["veg_chop", "veg_chop"], "price": 12, "steps": "Veg > Chop, x2 > Plate"},
	"steak": {"name": "Steak", "items": ["meat_cooked", "veg_chop"], "price": 20, "steps": "Meat > Pan + Veg > Chop > Plate"},
	"soup": {"name": "Soup", "items": ["veg_cook", "veg_cook"], "price": 18, "steps": "Veg > Chop > Pan, x2 > Plate"},
	"burger": {"name": "Burger", "items": ["bun", "patty", "veg_chop"], "price": 32, "steps": "Dough>Oven, Meat>Chop>Pan, Veg>Chop"},
	"stew": {"name": "Stew", "items": ["meat_cooked", "veg_cook"], "price": 28, "steps": "Meat > Pan + Veg > Chop > Pan"},
}

# Three restaurants, each ONE room (16 x 9): dining with tables and chairs, a pass counter, and the kitchen.
# Legend: M meat, V veg, D dough crate | C chop board, S pan, O oven, A plate, B bin | X counter
# T table (serve here), c chair (the customer sits here) | . tile floor, w wood floor | # wall
const WORLDS := [
	{
		"name": "Cozy Diner", "blurb": "Tables up front, kitchen at the back.",
		"top": "ffbe6b", "bot": "f0506e",
		"spawns": [Vector2i(6, 6), Vector2i(8, 6), Vector2i(4, 6), Vector2i(10, 6)],
		"map": [
			"################",
			"#wwcwwcwwwcwwcw#",
			"#wwTwwTwwwTwwTw#",
			"#wwwwwwwwwwwwww#",
			"#XXAAwXXXXwAAXX#",
			"#..............#",
			"#..............#",
			"#MVDBSSOOCCSSCC#",
			"################",
		],
	},
	{
		"name": "Bistro Bay", "blurb": "Dining on the left, kitchen on the right.",
		"top": "7fd6c2", "bot": "2a7d85",
		"spawns": [Vector2i(9, 3), Vector2i(11, 3), Vector2i(12, 4), Vector2i(13, 3)],
		"map": [
			"################",
			"#wwwwwwXMVDBOO.#",
			"#wcTwcwA.......#",
			"#wwwwTww.......#",
			"#wcTwwwA.......#",
			"#wwwwwww.CCSS..#",
			"#wcTwwwA.......#",
			"#wwwwwwXCCBSS..#",
			"################",
		],
	},
	{
		"name": "Grand Hall", "blurb": "A long kitchen line between two counters.",
		"top": "e9a8ff", "bot": "7a2e3f",
		"spawns": [Vector2i(3, 5), Vector2i(6, 5), Vector2i(9, 5), Vector2i(12, 5)],
		"map": [
			"################",
			"#wwcwwcwwcwwcww#",
			"#wwTwwTwwTwwTww#",
			"#wwwwwwwwwwwwww#",
			"#.CCAASSMVDBOO.#",
			"#.............w#",
			"#.CCAASSCCSSOO.#",
			"#..............#",
			"################",
		],
	},
]

# spawn = [min, max] seconds between customers, patience in seconds, goals = coins for 1/2/3 stars (solo),
# vip = chance a customer is a VIP (double tips, impatient).
const LEVELS := [
	{"name": "Lunch Break", "time": 60, "seats": 2, "recipes": ["salad"], "spawn": [6.0, 9.0], "patience": 45.0, "goals": [30, 60, 90], "vip": 0.0},
	{"name": "Steak Night", "time": 75, "seats": 3, "recipes": ["salad", "steak"], "spawn": [6.0, 9.0], "patience": 42.0, "goals": [60, 110, 160], "vip": 0.0},
	{"name": "Soup Season", "time": 75, "seats": 3, "recipes": ["salad", "soup"], "spawn": [5.0, 8.0], "patience": 40.0, "goals": [70, 120, 170], "vip": 0.0},
	{"name": "Burger Joint", "time": 90, "seats": 3, "recipes": ["burger", "salad"], "spawn": [5.0, 8.0], "patience": 40.0, "goals": [90, 150, 210], "vip": 0.0},
	{"name": "Diner Rush", "time": 90, "seats": 4, "recipes": ["salad", "steak", "soup", "burger"], "spawn": [4.5, 7.0], "patience": 38.0, "goals": [120, 190, 260], "vip": 0.05},
	{"name": "Bistro Bay", "time": 90, "seats": 4, "recipes": ["steak", "soup", "stew"], "spawn": [5.0, 7.5], "patience": 38.0, "goals": [140, 220, 300], "vip": 0.1},
	{"name": "Stew Time", "time": 90, "seats": 4, "recipes": ["stew", "burger"], "spawn": [4.5, 7.0], "patience": 36.0, "goals": [170, 260, 350], "vip": 0.1},
	{"name": "Lunch Crowd", "time": 100, "seats": 4, "recipes": ["salad", "steak", "soup", "burger", "stew"], "spawn": [4.0, 6.0], "patience": 34.0, "goals": [200, 300, 400], "vip": 0.15},
	{"name": "VIP Night", "time": 100, "seats": 4, "recipes": ["steak", "stew", "burger"], "spawn": [4.0, 6.0], "patience": 32.0, "goals": [230, 340, 450], "vip": 0.3},
	{"name": "Bistro Chaos", "time": 110, "seats": 4, "recipes": ["salad", "steak", "soup", "burger", "stew"], "spawn": [3.5, 5.5], "patience": 30.0, "goals": [260, 380, 500], "vip": 0.2},
	{"name": "Grand Opening", "time": 100, "seats": 4, "recipes": ["salad", "steak", "soup", "burger", "stew"], "spawn": [4.5, 6.5], "patience": 34.0, "goals": [250, 370, 490], "vip": 0.15},
	{"name": "The Banquet", "time": 110, "seats": 4, "recipes": ["burger", "stew", "steak"], "spawn": [3.5, 5.5], "patience": 32.0, "goals": [300, 430, 560], "vip": 0.2},
	{"name": "Soup Run", "time": 100, "seats": 4, "recipes": ["soup", "stew", "salad"], "spawn": [2.8, 4.5], "patience": 30.0, "goals": [280, 400, 520], "vip": 0.1},
	{"name": "Gala Dinner", "time": 110, "seats": 4, "recipes": ["salad", "steak", "soup", "burger", "stew"], "spawn": [3.0, 5.0], "patience": 30.0, "goals": [340, 480, 620], "vip": 0.3},
	{"name": "Master Chef", "time": 120, "seats": 4, "recipes": ["salad", "steak", "soup", "burger", "stew"], "spawn": [2.8, 4.5], "patience": 28.0, "goals": [400, 560, 720], "vip": 0.3},
]

const UPGRADES := [
	{"id": "boots", "name": "Speedy Shoes", "desc": "Walk 12% faster per level", "max": 5},
	{"id": "knife", "name": "Sharp Knife", "desc": "Chop 15% faster per level", "max": 5},
	{"id": "pan", "name": "Hot Pans", "desc": "Cook 12% faster per level", "max": 5},
	{"id": "chairs", "name": "Cozy Chairs", "desc": "Guests wait 15% longer", "max": 5},
	{"id": "tips", "name": "Tip Jar", "desc": "Tips are 25% bigger", "max": 5},
]

# ---- chef customisation ----
const SKINS := ["ffd5b5", "f1c27d", "d9a066", "a8714a", "7a4a2d", "f6c9a8", "c98a62", "5a3a24"]
const COLORS := ["ffffff", "ef476f", "ff9f1c", "ffd166", "06d6a0", "2ec4b6", "4c8bf5", "9b5de5", "ff8fab", "4a4a58", "8a5a3b"]
const COLOR_NAMES := ["White", "Red", "Orange", "Sunny", "Green", "Teal", "Blue", "Purple", "Pink", "Charcoal", "Brown"]
const HATS := ["toque", "cap", "beanie", "bandana", "tall", "hair"]
const ACCS := ["none", "glasses", "sunglasses", "mustache", "beard"]
const PLAYER_COLORS := ["ef476f", "4cc9f0", "7bd389", "ffd166"]

const ADJECTIVES := ["Happy", "Spicy", "Crispy", "Sunny", "Zesty", "Tasty", "Salty", "Sweet", "Speedy", "Jolly"]
const NOUNS := ["Chef", "Whisk", "Ladle", "Pickle", "Muffin", "Noodle", "Waffle", "Taco", "Biscuit", "Cookie"]

const TIPS := [
	"Pans and ovens burn food if you wait too long!",
	"More chefs means more coins. Cook together!",
	"Back-to-back orders build a combo bonus.",
	"VIP guests tip double, but they're impatient.",
	"Chop while the pan sizzles. Always be moving!",
	"Unlucky? Wrong dish? Take it back off the plate.",
	"Spend coins on upgrades to cook faster.",
]


static func upgrade_cost(level: int) -> int:
	return 60 + level * 60


static func coop_multiplier(players: int) -> float:
	return 1.0 + 0.25 * float(players - 1)


static func default_look(slot: int) -> Dictionary:
	var looks := [
		{"skin": 0, "hat": 0, "hat_col": 0, "jacket": 0, "apron": 6, "scarf": 1, "acc": 0},
		{"skin": 3, "hat": 1, "hat_col": 1, "jacket": 6, "apron": 0, "scarf": 3, "acc": 1},
		{"skin": 1, "hat": 3, "hat_col": 4, "jacket": 4, "apron": 3, "scarf": 0, "acc": 3},
		{"skin": 5, "hat": 2, "hat_col": 7, "jacket": 7, "apron": 8, "scarf": 2, "acc": 2},
	]
	return (looks[slot % 4] as Dictionary).duplicate()


static func random_name() -> String:
	return "%s %s" % [ADJECTIVES[randi() % ADJECTIVES.size()], NOUNS[randi() % NOUNS.size()]]
