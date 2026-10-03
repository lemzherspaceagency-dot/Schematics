// Drawer Organizer Bin — tile a drawer with bins of any size.
// Sizes are in grid units so different bins line up with each other.
// Measure your drawer, pick a unit that divides it, and print a set.
// Print upright (as rendered), no supports.

/* [Size] */
// Grid unit (mm). 42 matches common drawer-grid systems.
unit = 42;              // [20:1:100]
// Width in units
units_x = 2;            // [1:1:8]
// Depth in units
units_y = 1;            // [1:1:8]
// Height (mm)
height = 40;            // [10:1:150]

/* [Details] */
// Compartments along X
div_x = 2;              // [1:1:10]
// Compartments along Y
div_y = 1;              // [1:1:10]
// Wall thickness (mm). Multiples of your nozzle width print best.
wall = 1.6;             // [0.8:0.4:4]
// Floor thickness (mm)
floor_t = 1.2;          // [0.6:0.2:4]
// Corner radius (mm)
corner_r = 4;           // [0:0.5:15]
// Gap left between neighbouring bins (mm)
gap = 0.5;              // [0:0.1:2]
// Divider height as a fraction of bin height
div_h_ratio = 0.85;     // [0.3:0.05:1]
// Rounded scoop inside each compartment so small parts slide out
scoop = true;

/* [Hidden] */
$fn = 48;
L = units_x * unit - gap;
W = units_y * unit - gap;
cell_x = (L - 2 * wall - (div_x - 1) * wall) / div_x;
cell_y = (W - 2 * wall - (div_y - 1) * wall) / div_y;
scoop_r = min(12, cell_y / 2, height / 3);

module rrect(l, w, r, h) {
    r2 = max(0.01, min(r, l / 2, w / 2));
    linear_extrude(h)
        offset(r = r2) offset(delta = -r2) square([l, w]);
}

difference() {
    rrect(L, W, corner_r, height);
    for (i = [0 : div_x - 1], j = [0 : div_y - 1]) {
        x = wall + i * (cell_x + wall);
        y = wall + j * (cell_y + wall);
        // compartments merge above the dividers
        translate([x, y, floor_t])
            difference() {
                rrect(cell_x, cell_y, max(0, corner_r - wall), height);
                if (scoop)
                    translate([-1, 0, 0])
                        difference() {
                            cube([cell_x + 2, scoop_r, scoop_r]);
                            translate([0, scoop_r, scoop_r]) rotate([0, 90, 0])
                                cylinder(r = scoop_r, h = cell_x + 2);
                        }
            }
    }
    // cut dividers down to their height
    translate([wall, wall, height * div_h_ratio])
        rrect(L - 2 * wall, W - 2 * wall, max(0, corner_r - wall), height);
}
