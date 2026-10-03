// Wall Hook — screw-mounted J hook for coats, bags, keys, towels, tools.
// Prints lying on its side (as rendered) so the layers follow the curve
// of the hook: much stronger than printing it standing up.
// Use PETG or PLA with 4+ perimeters for heavy loads.

/* [Hook] */
// Width of the hook (mm) — this is the print height
width = 20;             // [10:1:60]
// How far the hook sticks out from the wall (mm)
depth = 35;             // [15:1:100]
// Height of the front lip (mm)
lip_h = 18;             // [5:1:60]
// Thickness of the hook arm (mm)
arm_t = 7;              // [4:0.5:15]

/* [Back plate] */
// Height of the back plate (mm)
plate_h = 70;           // [40:1:150]
// Thickness of the back plate (mm)
plate_t = 5;            // [3:0.5:10]

/* [Screws] */
// Screw shank diameter (mm)
screw_d = 4;            // [2.5:0.1:6]
// Screw head diameter (mm)
head_d = 8;             // [5:0.1:12]

/* [Hidden] */
$fn = 48;
fillet = 3;
hole_lo = lip_h + head_d / 2 + 6;   // keep clear of the lip for a screwdriver
hole_hi = plate_h - head_d / 2 - 4;
assert(hole_hi - hole_lo > head_d, "plate_h too small for this lip_h — increase plate_h");

module profile() {
    // round convex corners, then fill concave ones
    offset(r = -fillet) offset(delta = fillet)
    offset(r = fillet) offset(delta = -fillet) {
        square([plate_t, plate_h]);
        square([plate_t + depth, arm_t]);
        translate([plate_t + depth - arm_t, 0]) square([arm_t, lip_h]);
    }
}

difference() {
    linear_extrude(width) profile();
    for (y = [hole_lo, hole_hi])
        translate([0, y, width / 2]) rotate([0, 90, 0]) {
            translate([0, 0, -1]) cylinder(d = screw_d, h = plate_t + 2);
            // countersink on the outside face
            translate([0, 0, plate_t - (head_d - screw_d) / 2])
                cylinder(d1 = screw_d, d2 = head_d, h = (head_d - screw_d) / 2 + 0.01);
            translate([0, 0, plate_t]) cylinder(d = head_d, h = depth);
        }
}
