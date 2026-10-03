// Drawer / Cabinet Pull Handle — replace a broken or ugly handle.
// Measure the distance between the existing screw holes (centre to centre).
// Standard spacings: 64, 76, 96, 128, 160 mm.
// Prints on its side (as rendered) so the bar is strong, no supports.
// Fix with M4 machine screws (they self-tap into the 3.4 mm holes) or
// melt in M4 heat-set inserts (set hole_d to the insert size, ~5.6).

/* [Handle] */
// Screw hole spacing, centre to centre (mm)
spacing = 96;           // [32:1:320]
// Overhang past each screw (mm)
overhang = 12;          // [0:1:40]
// How far the handle stands off the drawer (mm)
standoff = 28;          // [15:1:50]
// Bar thickness, front to back (mm)
bar_t = 9;              // [6:0.5:15]
// Handle width (mm) — this is the print height
width = 12;             // [8:1:25]

/* [Screws] */
// Screw hole diameter (mm)
hole_d = 3.4;           // [2.5:0.1:6]
// Screw hole depth (mm)
hole_depth = 14;        // [6:1:25]

/* [Hidden] */
$fn = 48;
post_w = 12;
L = spacing + 2 * overhang;

module profile() {
    offset(r = -5) offset(delta = 5)
    offset(r = 3) offset(delta = -3) {
        translate([-L / 2, standoff - bar_t]) square([L, bar_t]);
        for (s = [-1, 1])
            translate([s * spacing / 2 - post_w / 2, 0]) square([post_w, standoff]);
    }
}

difference() {
    linear_extrude(width) profile();
    for (s = [-1, 1])
        translate([s * spacing / 2, -1, width / 2]) rotate([-90, 0, 0])
            cylinder(d = hole_d, h = hole_depth + 1);
}
