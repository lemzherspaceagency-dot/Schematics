// Under-desk headphone hook - screw mount. Print on its SIDE (profile flat on bed), no supports.
w        = 30;   // hook width (Z when printing)
plate_h  = 70;   // back plate height
t        = 5;    // wall thickness
arm      = 55;   // how far hook sticks out
lip      = 28;   // upward lip height
screw_d  = 4.5;  // screw shaft hole
head_d   = 9;    // countersink diameter
$fn = 64;

module profile() {
    // back plate
    square([t, plate_h]);
    // arm, slightly rising for grip
    hull() {
        translate([0, 0]) square([t, t]);
        translate([arm, 0]) circle(d = t);
    }
    // upward lip with rounded tip
    hull() {
        translate([arm, 0]) circle(d = t);
        translate([arm, lip]) circle(d = t);
    }
    // fillet between plate and arm
    polygon([[t, 0], [t + 12, 0], [t, 12]]);
}

difference() {
    linear_extrude(height = w) profile();
    // two countersunk screw holes through back plate (diamond cross-section = no overhang trouble)
    for (z = [w / 2]) for (y = [plate_h * 0.25, plate_h * 0.8]) {
        translate([-0.1, y, z]) rotate([0, 90, 0]) rotate([0, 0, 45]) {
            cylinder(d = screw_d, h = t + 0.2, $fn = 4);
        }
        translate([t - 2.2, y, z]) rotate([0, 90, 0]) rotate([0, 0, 45])
            cylinder(d1 = screw_d, d2 = head_d, h = 2.3, $fn = 4);
    }
}
