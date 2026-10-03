// Spacers & Washers — the bits you never have. Shim a shelf, pad a
// wobbly bracket, space a PCB, a wheel or a hinge.
// Prints a grid of identical spacers, flat (as rendered).

/* [Spacer] */
// Hole diameter (mm). Bolt size + 0.3 (M3 = 3.3, M4 = 4.3, M5 = 5.3…)
hole_d = 4.3;           // [1:0.1:30]
// Outer diameter (mm)
outer_d = 10;           // [3:0.5:60]
// Height (mm). 0.6–2 for washers, longer for spacers.
height = 5;             // [0.4:0.2:60]
// Hexagonal outside (grip with a spanner)
hex = false;
// How many
count = 8;              // [1:1:50]

/* [Hidden] */
$fn = 64;
assert(outer_d > hole_d + 1, "outer_d must be bigger than hole_d");
cols = ceil(sqrt(count));
pitch = outer_d + 3;

for (i = [0 : count - 1])
    translate([(i % cols) * pitch, floor(i / cols) * pitch, 0])
        difference() {
            if (hex) cylinder(d = outer_d / cos(30), h = height, $fn = 6);
            else cylinder(d = outer_d, h = height);
            translate([0, 0, -1]) cylinder(d = hole_d, h = height + 2);
            // tiny chamfer so the hole isn't squashed by elephant's foot
            translate([0, 0, -0.01]) cylinder(d1 = hole_d + 0.8, d2 = hole_d, h = 0.4);
        }
