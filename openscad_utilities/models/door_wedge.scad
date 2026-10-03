// Door Stop Wedge — keeps a door open (slide under the door edge).
// Grip grooves on the bottom stop it sliding on hard floors.
// Print on its flat bottom (as rendered). PETG or TPU grips best.

/* [Size] */
// Length (mm)
length = 120;           // [60:1:200]
// Width (mm)
width = 40;             // [20:1:80]
// Height at the tall end (mm). Measure the gap under your door + a bit.
height = 25;            // [8:1:60]
// Height at the thin tip (mm)
tip_h = 2;              // [1:0.5:6]

/* [Extras] */
// Grip grooves across the bottom
grooves = true;
// Hole at the tall end for hanging on a hook
hang_hole = true;

/* [Hidden] */
$fn = 48;
r = 3;

module side_profile() {
    polygon([[0, 0], [length, 0], [length, height], [0, tip_h]]);
}

difference() {
    // rounded vertical edges
    intersection() {
        rotate([90, 0, 0]) translate([0, 0, -width])
            linear_extrude(width) side_profile();
        linear_extrude(height + 1)
            offset(r = r) offset(delta = -r) square([length, width]);
    }
    if (grooves)
        for (x = [10 : 8 : length - 10])
            translate([x, -1, 0]) rotate([-90, 0, 0])
                cylinder(r = 1.2, h = width + 2, $fn = 4);
    if (hang_hole)
        translate([length - height / 2 - 2, width / 2, -1])
            cylinder(d = min(12, width / 3), h = height + 2);
    // finger notch at the tall end to pull it out
    translate([length + 4, width / 2, height]) scale([1, 2, 1]) sphere(r = 8);
}
