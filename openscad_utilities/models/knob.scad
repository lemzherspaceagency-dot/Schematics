// Universal Knob — grip knob for a bolt or threaded rod.
// Fits M3–M8 hex nuts or hex-head bolts. Use it for clamps, jigs,
// 3D-printer beds, camera mounts, furniture, replacing a lost knob…
// Print flat (as rendered). Press the nut in (a dab of glue helps).

/* [Fastener] */
// Metric thread size
size = 6;               // [3, 4, 5, 6, 8]
// "nut": nut trap on the bottom, rod passes through.
// "bolt": hex bolt head trapped in the top, thread sticks out the bottom (thumbscrew).
mode = "nut";           // ["nut", "bolt"]
// Extra clearance for the hex pocket (mm). Increase if it's too tight.
tol = 0.25;             // [0:0.05:0.6]

/* [Knob] */
// Knob diameter (mm)
knob_d = 32;            // [15:1:80]
// Knob height (mm)
knob_h = 14;            // [6:1:40]
// Number of finger flutes
flutes = 8;             // [0:1:20]

/* [Hidden] */
$fn = 96;
// [size, clearance hole, hex across flats, nut height, bolt head height]
table = [[3, 3.4, 5.5, 2.4, 2.0],
         [4, 4.5, 7.0, 3.2, 2.8],
         [5, 5.5, 8.0, 4.0, 3.5],
         [6, 6.6, 10.0, 5.0, 4.0],
         [8, 9.0, 13.0, 6.5, 5.3]];
row = table[search(size, table)[0]];
hole_d = row[1];
hex_d = (row[2] + tol) / cos(30);
hex_h = (mode == "nut" ? row[3] : row[4]) + 0.4;
assert(hex_d < knob_d - 6, "knob_d too small for this fastener");
assert(hex_h < knob_h - 2, "knob_h too small for this fastener");
flute_r = PI * knob_d / flutes / 3.2;

difference() {
    // body with chamfered edges
    hull() {
        translate([0, 0, 1]) cylinder(d = knob_d, h = knob_h - 2);
        cylinder(d = knob_d - 2, h = knob_h);
    }
    if (flutes > 0)
        for (a = [0 : 360 / flutes : 359])
            rotate(a) translate([knob_d / 2 + flute_r * 0.35, 0, -1])
                cylinder(r = flute_r, h = knob_h + 2);
    translate([0, 0, -1]) cylinder(d = hole_d, h = knob_h + 2);
    if (mode == "nut")
        translate([0, 0, -1]) cylinder(d = hex_d, h = hex_h + 1, $fn = 6);
    else
        translate([0, 0, knob_h - hex_h]) cylinder(d = hex_d, h = hex_h + 1, $fn = 6);
}
