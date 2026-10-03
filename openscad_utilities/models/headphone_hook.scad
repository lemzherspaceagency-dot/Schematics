// Under-Desk Headphone Hook — screws to the underside of a desk or shelf.
// The mounting plate points backwards so the screws are easy to reach.
// Prints lying on its side (as rendered) for strength. PETG or PLA.

/* [Hook] */
// Width of the hook (mm). Wider = gentler on the headband.
width = 40;             // [20:1:80]
// How far below the desk the headphones hang (mm)
drop = 30;              // [10:1:120]
// Length of the arm the headband rests on (mm)
arm_l = 45;             // [25:1:90]
// Lip height at the end of the arm (mm)
lip_h = 10;             // [4:1:25]
// Material thickness (mm)
t = 6;                  // [4:0.5:12]

/* [Mounting] */
// Length of the mounting plate (mm)
plate_l = 45;           // [30:1:80]
// Screw shank diameter (mm)
screw_d = 4;            // [2.5:0.1:6]
// Screw head diameter (mm)
head_d = 8;             // [5:0.1:12]

/* [Hidden] */
$fn = 48;
fillet = 4;
top = drop + t;

module profile() {
    offset(r = -fillet) offset(delta = fillet)
    offset(r = 2) offset(delta = -2) {
        translate([-plate_l, top - t]) square([plate_l + t, t]);   // plate
        square([t, top]);                                          // drop
        square([t + arm_l, t]);                                    // arm
        translate([t + arm_l - t, 0]) square([t, t + lip_h]);      // lip
    }
}

difference() {
    linear_extrude(width) profile();
    for (x = [-10, -plate_l + 10])
        translate([x, 0, width / 2]) rotate([-90, 0, 0]) {
            cylinder(d = screw_d, h = top + 1);
            // countersink on the underside of the plate
            translate([0, 0, top - t - 0.01])
                cylinder(d1 = head_d, d2 = screw_d, h = (head_d - screw_d) / 2);
            translate([0, 0, -1]) cylinder(d = head_d, h = top - t + 1);
        }
}
