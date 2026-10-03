// Desk Cable Grommet — finishes a cable hole in a desk or worktop.
// Two parts: a SLEEVE that drops into the hole and a CAP with a cable notch.
// Measure the hole (common sizes: 35, 50, 60, 80 mm) and your desk thickness.
// Both parts print flange-down (as rendered), no supports.

/* [Hole] */
// Diameter of the hole in the desk (mm)
hole_d = 60;            // [20:1:120]
// Desk thickness (mm). The sleeve can be shorter than the desk.
desk_t = 25;            // [10:1:60]

/* [Grommet] */
// Flange overhang around the hole (mm)
flange = 8;             // [4:1:20]
// Flange / cap thickness (mm)
flange_t = 2.4;         // [1.6:0.2:5]
// Sleeve wall thickness (mm)
wall = 2;               // [1.2:0.2:4]
// Width of the cable notch in the cap (mm)
notch_w = 22;           // [8:1:60]
// Fit clearance (mm)
tol = 0.4;              // [0.1:0.05:1]

/* [Hidden] */
$fn = 128;
sleeve_od = hole_d - tol;
sleeve_id = sleeve_od - 2 * wall;
flange_d = hole_d + 2 * flange;
sleeve_h = min(desk_t, 20) + flange_t;
recess = 1.2;                         // cap sits slightly into the flange
plug_h = 6;

module sleeve() {
    difference() {
        union() {
            cylinder(d1 = flange_d - 2, d2 = flange_d, h = flange_t);  // chamfered rim
            cylinder(d = sleeve_od, h = sleeve_h);
        }
        translate([0, 0, -1]) cylinder(d = sleeve_id, h = sleeve_h + 2);
    }
}

module cap() {
    difference() {
        union() {
            cylinder(d1 = flange_d - 2, d2 = flange_d, h = flange_t);
            cylinder(d = sleeve_id - tol, h = flange_t + plug_h);
        }
        translate([0, 0, flange_t]) cylinder(d = sleeve_id - tol - 2 * 1.6, h = plug_h + 1);
        // cable notch from the edge toward the centre
        translate([sleeve_id / 2 - notch_w * 0.9, -notch_w / 2, -1])
            hull() {
                cube([flange_d, notch_w, flange_t + plug_h + 2]);
                translate([0, notch_w / 2, 0]) cylinder(d = notch_w, h = flange_t + plug_h + 2);
            }
    }
}

sleeve();
translate([flange_d + 5, 0, 0]) cap();
