// Stepped Jar Opener — one tool for lids from 30 to 90 mm.
// Hold the handle, push the lid into the step that fits, and twist the jar.
// The teeth bite into the lid edge. Great for weak or painful hands.
// Print pockets-up (as rendered). PETG works; TPU grips even better.
// Screw it under a cupboard with the two holes for one-handed use.

/* [Sizes] */
// Smallest lid diameter (mm)
min_d = 30;             // [20:1:60]
// Largest lid diameter (mm)
max_d = 90;             // [40:1:130]
// Diameter increase per step (mm)
step_d = 10;            // [5:1:20]
// Depth of each step (mm)
step_h = 6;             // [3:0.5:12]
// Handle length (mm), 0 for none
handle_l = 90;          // [0:5:200]

/* [Hidden] */
$fn = 120;
steps = floor((max_d - min_d) / step_d) + 1;
wall = 4;
floor_t = 3;
H = floor_t + steps * step_h;
outer = min_d + (steps - 1) * step_d + 2 * wall;

function d_at(i) = min_d + i * step_d;
function z_at(i) = floor_t + i * step_h;

difference() {
    union() {
        cylinder(d = outer, h = H);
        if (handle_l > 0)
            hull() {
                cylinder(d = 34, h = 12);
                translate([outer / 2 + handle_l - 15, 0, 0]) cylinder(d = 30, h = 12);
            }
    }
    for (i = [0 : steps - 1])
        translate([0, 0, z_at(i)]) cylinder(d = d_at(i), h = H);
    if (handle_l > 0)
        for (x = [outer / 2 + 20, outer / 2 + handle_l - 15])
            translate([x, 0, -1]) {
                cylinder(d = 4, h = 14);
                translate([0, 0, 13 - 2.5]) cylinder(d1 = 4, d2 = 8.5, h = 2.51);
            }
}
// teeth around the wall of every step
for (i = [0 : steps - 1]) {
    n = round(PI * d_at(i) / 6);
    for (a = [0 : 360 / n : 359.9])
        rotate(a) translate([d_at(i) / 2, 0, z_at(i)])
            rotate(45) cylinder(d = 2.4, h = step_h, $fn = 4);
}
