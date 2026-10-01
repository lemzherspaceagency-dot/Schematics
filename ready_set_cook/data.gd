class_name Data
extends RefCounted
# All the tweakable game content lives here: machines, recipes, levels, upgrades.

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
}

# spawn = [min, max] seconds between customers, patience in seconds, goals = coins for 1/2/3 stars
const LEVELS := [
	{"name": "Lunch Break", "time": 60, "seats": 2, "recipes": ["salad"], "spawn": [6.0, 9.0], "patience": 45.0, "goals": [30, 60, 90]},
	{"name": "Steak Night", "time": 75, "seats": 3, "recipes": ["salad", "steak"], "spawn": [6.0, 9.0], "patience": 42.0, "goals": [60, 110, 160]},
	{"name": "Soup Season", "time": 75, "seats": 3, "recipes": ["salad", "soup"], "spawn": [5.0, 8.0], "patience": 40.0, "goals": [70, 120, 170]},
	{"name": "Burger Joint", "time": 90, "seats": 3, "recipes": ["burger", "salad"], "spawn": [5.0, 8.0], "patience": 40.0, "goals": [90, 150, 210]},
	{"name": "Full Menu", "time": 90, "seats": 4, "recipes": ["salad", "steak", "soup", "burger"], "spawn": [5.0, 7.0], "patience": 38.0, "goals": [120, 190, 260]},
	{"name": "Rush Hour", "time": 100, "seats": 4, "recipes": ["salad", "steak", "soup", "burger"], "spawn": [4.0, 6.0], "patience": 34.0, "goals": [160, 250, 340]},
	{"name": "Burger Blitz", "time": 90, "seats": 4, "recipes": ["burger", "soup"], "spawn": [4.0, 6.0], "patience": 34.0, "goals": [170, 260, 350]},
	{"name": "Fancy Feast", "time": 100, "seats": 4, "recipes": ["steak", "soup", "burger"], "spawn": [3.5, 5.5], "patience": 32.0, "goals": [220, 330, 440]},
	{"name": "Chaos Kitchen", "time": 110, "seats": 4, "recipes": ["salad", "steak", "soup", "burger"], "spawn": [3.0, 5.0], "patience": 30.0, "goals": [260, 380, 500]},
	{"name": "Master Chef", "time": 120, "seats": 4, "recipes": ["salad", "steak", "soup", "burger"], "spawn": [3.0, 4.5], "patience": 28.0, "goals": [320, 460, 600]},
]

const UPGRADES := [
	{"id": "boots", "name": "Speedy Shoes", "desc": "Walk 12% faster per level", "max": 5},
	{"id": "knife", "name": "Sharp Knife", "desc": "Chop 15% faster per level", "max": 5},
	{"id": "pan", "name": "Hot Pans", "desc": "Cook 12% faster per level", "max": 5},
	{"id": "chairs", "name": "Cozy Chairs", "desc": "Guests wait 15% longer", "max": 5},
	{"id": "tips", "name": "Tip Jar", "desc": "Tips are 25% bigger", "max": 5},
]


static func upgrade_cost(level: int) -> int:
	return 60 + level * 60
