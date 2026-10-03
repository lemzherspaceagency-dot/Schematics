// Furniture Riser / Leg Cup — lift a bed, sofa, table or desk,
// or stop a leg from scratching the floor. Print one per leg.
// Print upright (as rendered). Use 4+ walls and 30%+ infill:
// in this orientation the load is pure compression, which plastic handles well.

/* [Leg] */
// Leg shape
leg_shape = "round";    // ["round", "square"]
// Leg diameter, or side length for square legs (mm). Add ~1 mm.
leg_size = 41;          // [10:0.5:120]
// How deep the leg sits in the cup (mm)
pocket_depth = 12;      // [3:1:40]

/* [Riser] */
// How much the furniture is lifted (mm)
lift = 40;              // [0:1:150]
// Wall around the leg (mm)
wall = 6;               // [3:0.5:20]
// Base flare: how much wider the foot is than the top (mm)
flare = 10;             // [0:1:40]

/* [Hidden] */
$fn = 96;
top_w = leg_size + 2 * wall;
bot_w = top_w + 2 * flare;
total_h = lift + pocket_depth;

module footprint(w) {
    if (leg_shape == "round") circle(d = w);
    else offset(r = 3) square(w - 6, center = true);
}

difference() {
    hull() {
        linear_extrude(0.01) footprint(bot_w);
        translate([0, 0, total_h - 0.01]) linear_extrude(0.01) footprint(top_w);
    }
    translate([0, 0, lift]) linear_extrude(pocket_depth + 1) footprint(leg_size);
    // shallow recess on the bottom so it sits flat on uneven floors
    if (bot_w > 30)
        translate([0, 0, -1]) linear_extrude(1.6) footprint(bot_w - 16);
}
