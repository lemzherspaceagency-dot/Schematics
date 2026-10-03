// Cable Tie Mount — screw-down anchor for zip ties. Bundle cables under
// desks, along skirting boards, in cars, garages, PCs and sheds.
// Print flat (as rendered); the tunnel roof bridges cleanly.

/* [Mount] */
// Zip tie width (mm) + a little clearance
tie_w = 5;              // [2.5:0.5:10]
// Zip tie thickness (mm) + clearance
tie_t = 1.8;            // [1:0.1:3]
// Screw shank diameter (mm)
screw_d = 3.5;          // [2:0.1:5]
// How many mounts to print
count = 4;              // [1:1:20]

/* [Hidden] */
$fn = 40;
L = 30; W = tie_w + 10; H = tie_t + 3.2;

module mount() {
    difference() {
        hull() {
            translate([2, 2, 0]) cube([L - 4, W - 4, H]);
            cube([L, W, 0.01]);
        }
        // tie tunnel straight across the middle
        translate([L / 2 - tie_w / 2, -1, 1.2]) cube([tie_w, W + 2, tie_t]);
        // countersunk screw holes either side
        for (x = [5, L - 5])
            translate([x, W / 2, -1]) {
                cylinder(d = screw_d, h = H + 2);
                translate([0, 0, H + 1 - screw_d * 0.9])
                    cylinder(d1 = screw_d, d2 = screw_d * 2.1, h = screw_d * 0.9 + 0.01);
            }
    }
}

for (i = [0 : count - 1]) translate([0, i * (W + 4), 0]) mount();
