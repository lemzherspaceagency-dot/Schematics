// Plant Pot + Drip Saucer — tapered pot with drainage holes and feet,
// plus a matching saucer. Both print upright (as rendered), side by side.
// PETG is best for anything that holds water; PLA is fine for indoor pots.

/* [Pot] */
// Diameter at the top rim (mm)
top_d = 100;            // [40:1:200]
// Height (mm)
height = 90;            // [30:1:200]
// Bottom diameter as a fraction of the top
taper = 0.75;           // [0.5:0.05:1]
// Wall thickness (mm)
wall = 2;               // [1.2:0.2:4]
// Number of drainage holes (0 = no holes, no saucer)
drain_holes = 5;        // [0:1:12]
// Shape
sides = 0;              // [0:Round, 4:Square, 6:Hexagon, 8:Octagon]

/* [Hidden] */
$fn = sides == 0 ? 120 : sides;
bot_d = top_d * taper;
floor_t = 2.4;
feet_h = 3;
saucer_d = bot_d + 22;

module pot() {
    difference() {
        union() {
            translate([0, 0, feet_h]) cylinder(d1 = bot_d, d2 = top_d, h = height - feet_h);
            // three feet so water can escape from under the pot
            for (a = [0 : 120 : 359]) rotate(a + 30)
                translate([bot_d * 0.32, 0, 0]) cylinder(d = 10, h = feet_h + 0.01, $fn = 24);
        }
        translate([0, 0, feet_h + floor_t])
            cylinder(d1 = bot_d - 2 * wall, d2 = top_d - 2 * wall, h = height);
        if (drain_holes > 0) {
            translate([0, 0, feet_h - 1]) cylinder(d = 8, h = floor_t + 2, $fn = 24);
            for (a = [0 : 360 / max(1, drain_holes - 1) : 359.9])
                if (drain_holes > 1) rotate(a)
                    translate([bot_d * 0.22, 0, feet_h - 1]) cylinder(d = 5, h = floor_t + 2, $fn = 16);
        }
    }
}

module saucer() {
    difference() {
        hull() {
            cylinder(d = saucer_d - 4, h = 1, $fn = 120);
            translate([0, 0, 12]) cylinder(d = saucer_d, h = 0.01, $fn = 120);
        }
        translate([0, 0, 1.6]) hull() {
            cylinder(d = saucer_d - 8, h = 1, $fn = 120);
            translate([0, 0, 11]) cylinder(d = saucer_d - 2 * 1.6, h = 0.01, $fn = 120);
        }
    }
}

pot();
if (drain_holes > 0) translate([(top_d + saucer_d) / 2 + 5, 0, 0]) saucer();
