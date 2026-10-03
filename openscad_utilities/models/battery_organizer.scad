// Battery Organizer — tidy tray for spare batteries, with optional
// keyhole slots to hang it on a wall or inside a cupboard door.
// Print upright (as rendered), no supports.

/* [Battery] */
battery = "AA";         // ["AAA", "AA", "C", "D", "18650", "9V"]
// Columns
cols = 6;               // [1:1:20]
// Rows
rows = 3;               // [1:1:20]

/* [Tray] */
// How much of the battery sits in the tray (0.5 = half)
depth_ratio = 0.55;     // [0.3:0.05:0.9]
// Space between pockets (mm)
spacing = 2;            // [1:0.5:6]
// Border around the pockets (mm)
border = 4;             // [2:0.5:10]
// Keyhole slots on the back for wall mounting
wall_mount = false;

/* [Hidden] */
$fn = 48;
// [name, size x, size y, length]  (pocket sizes include clearance)
cells = [["AAA",   11.0, 11.0, 44.5],
         ["AA",    15.0, 15.0, 50.5],
         ["C",     26.8, 26.8, 50.0],
         ["D",     34.8, 34.8, 61.5],
         ["18650", 19.0, 19.0, 65.0],
         ["9V",    27.0, 18.0, 48.5]];
cell = cells[search([battery], cells)[0]];
round_cell = battery != "9V";
sx = cell[1]; sy = cell[2];
pocket_h = cell[3] * depth_ratio;
floor_t = wall_mount ? 6 : 2;   // keyholes need a thicker back
L = cols * sx + (cols - 1) * spacing + 2 * border;
W = rows * sy + (rows - 1) * spacing + 2 * border;
H = pocket_h + floor_t;

module rrect(l, w, r) { offset(r = r) offset(delta = -r) square([l, w]); }

difference() {
    linear_extrude(H) rrect(L, W, 4);
    for (i = [0 : cols - 1], j = [0 : rows - 1])
        translate([border + i * (sx + spacing), border + j * (sy + spacing), floor_t]) {
            if (round_cell)
                translate([sx / 2, sy / 2, 0]) cylinder(d = sx, h = H);
            else
                linear_extrude(H) rrect(sx, sy, 1.5);
        }
    if (wall_mount)
        // keyhole: the screw head enters the big hole, then the tray drops
        // down so the shank sits in the narrow slot and the head is trapped.
        for (x = [L * 0.2, L * 0.8])
            translate([x, W * 0.7, 0]) {
                translate([0, 0, -1]) cylinder(d = 9, h = 1 + 1.5 + 3);
                hull() for (y = [0, 8]) translate([0, y, -1]) cylinder(d = 4.5, h = 1 + 1.5 + 0.01);
                hull() for (y = [0, 8]) translate([0, y, 1.5]) cylinder(d = 9, h = 3);
            }
}
