// Cable Clip — snap cables into a row of C-shaped holders.
// Stick it under a desk with double-sided tape, or screw it down.
// Print flat (as rendered). PETG is best for the snap; PLA works.

/* [Cables] */
// Diameter of the cable you want to hold (mm). Measure it, add ~0.3.
cable_d = 6;            // [2:0.5:20]
// How many cables side by side
cable_count = 3;        // [1:1:10]
// Opening width as a fraction of cable diameter (smaller = tighter snap)
opening_ratio = 0.75;   // [0.5:0.05:0.95]

/* [Body] */
// Length of each holder along the cable (mm)
clip_len = 12;          // [6:1:40]
// Wall thickness around the cable (mm)
wall = 1.8;             // [1.2:0.2:4]
// Base plate thickness (mm)
base_t = 2.4;           // [1.6:0.2:5]
// Add screw ears at both ends
screw_ears = true;
// Screw shank diameter (mm). 3.5 fits common #6 / 3.5mm wood screws.
screw_d = 3.5;          // [2:0.1:6]

/* [Hidden] */
$fn = 64;
r_in = cable_d / 2;
r_out = r_in + wall;
pitch = 2 * r_out - wall;            // neighbouring rings share a wall
row_len = (cable_count - 1) * pitch + 2 * r_out;
ear = screw_ears ? screw_d * 2 + 4 : 0;
top = base_t + r_in + r_out;
open_w = cable_d * opening_ratio;
mouth_y = base_t + r_in + sqrt(r_in * r_in - open_w * open_w / 4);

function cx(i) = r_out + i * pitch;

module profile() {
    difference() {
        union() {
            translate([-ear, 0]) square([row_len + 2 * ear, base_t]);
            for (i = [0 : cable_count - 1]) {
                translate([cx(i), base_t + r_in]) circle(r_out);
                translate([cx(i) - r_out, 0]) square([2 * r_out, base_t + r_in]);
            }
        }
        for (i = [0 : cable_count - 1]) {
            translate([cx(i), base_t + r_in]) circle(r_in);
            // the ring stays closed until it narrows to open_w, then a
            // funnel-shaped mouth makes pushing the cable in easy
            polygon([
                [cx(i) - open_w / 2, base_t + r_in],
                [cx(i) + open_w / 2, base_t + r_in],
                [cx(i) + open_w / 2, mouth_y],
                [cx(i) + open_w / 2 + wall * 0.8, top + 0.01],
                [cx(i) - open_w / 2 - wall * 0.8, top + 0.01],
                [cx(i) - open_w / 2, mouth_y]
            ]);
        }
    }
}

difference() {
    rotate([90, 0, 0]) linear_extrude(clip_len, center = true) profile();
    if (screw_ears)
        for (x = [-ear / 2, row_len + ear / 2])
            translate([x, 0, -1]) {
                cylinder(d = screw_d, h = base_t + 2);
                // countersink
                translate([0, 0, base_t + 1 - screw_d * 0.9])
                    cylinder(d1 = screw_d, d2 = screw_d * 2.2, h = screw_d * 0.9 + 0.01);
            }
}
