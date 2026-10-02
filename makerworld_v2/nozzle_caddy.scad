// Printer-maintenance caddy: spare nozzle holes, hex-key slots, cleaning-needle slots. Print flat, no supports.
// Hole sizes are parameters - measure your nozzles and keys and adjust.
nozzle_d   = 9.5;   // hole for one nozzle (hex ~7-8 mm across + clearance)
nozzle_dp  = 14;    // hole depth
cols = 6; rows = 2; pitch = 14;
key_d      = 4.5;   // hex key slot
needle_d   = 2.0;   // cleaning needle / small tool slot
h = 22; wall = 3;
$fn = 48;

W = cols * pitch + 2 * wall;
D = rows * pitch + 36 + 2 * wall;

difference() {
    // body with rounded vertical edges
    hull() for (x = [4, W - 4], y = [4, D - 4]) translate([x, y, 0]) cylinder(r = 4, h = h);
    // nozzle grid
    for (c = [0 : cols - 1], r = [0 : rows - 1])
        translate([wall + pitch / 2 + c * pitch, wall + pitch / 2 + r * pitch, h - nozzle_dp])
            cylinder(d = nozzle_d, h = nozzle_dp + 1);
    // hex key slots
    for (i = [0 : 3])
        translate([wall + 6 + i * 10, rows * pitch + wall + 8, 4]) cylinder(d = key_d, h = h);
    // needle slots
    for (i = [0 : cols - 1])
        translate([wall + pitch / 2 + i * pitch, rows * pitch + wall + 24, 4]) cylinder(d = needle_d, h = h);
    // thumb notch on front edge to pull the caddy out of a drawer
    translate([W / 2, -1, h]) rotate([-90, 0, 0]) cylinder(d = 14, h = 5);
}
