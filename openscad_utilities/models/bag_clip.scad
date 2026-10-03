// Slide-On Bag Clip — no springs, no hinges, nothing to break.
// Fold the bag top over the ROD, then slide the CHANNEL along it.
// Prints as two parts side by side, flat, no supports.
// Tip: PETG gives the best grip; PLA works fine.

/* [Size] */
// Length of the clip (mm). Should be a bit longer than the bag is wide.
length = 110;           // [40:1:250]
// Rod diameter (mm)
rod_d = 8;              // [5:0.5:14]
// Extra space for the folded bag (mm). Thicker bags need more.
bag_gap = 0.45;         // [0.2:0.05:1.2]
// Channel wall thickness (mm)
wall = 2.4;             // [1.6:0.2:4]

/* [Hidden] */
$fn = 64;
flat = 0.8;                    // flat bottom on the rod so it sits on the bed
in_r = rod_d / 2 + bag_gap;
out_r = in_r + wall;
slot = rod_d * 0.72;           // narrower than the rod so it can't pull out

module rod() {
    translate([0, 0, rod_d / 2 - flat])
    difference() {
        rotate([0, 90, 0]) cylinder(d = rod_d, h = length);
        translate([-1, -rod_d, -rod_d - rod_d / 2 + flat]) cube([length + 2, 2 * rod_d, rod_d]);
    }
    // grip tab on the end
    translate([-12, -rod_d / 2, 0]) cube([13, rod_d, rod_d - flat]);
}

// teardrop (point up, tip trimmed) so the top of the bore prints without supports
module teardrop2d(r) {
    intersection() {
        union() { circle(r); rotate(45) square(r); }
        translate([-r, -r]) square([2 * r, 2 * r + wall / 2]);
    }
}

module channel_profile() {
    difference() {
        hull() {
            translate([0, out_r]) circle(out_r);
            translate([-out_r, 0]) square([2 * out_r, 0.01]);
        }
        translate([0, out_r]) {
            teardrop2d(in_r);
            // slot faces sideways
            translate([0, -slot / 2]) square([out_r + 1, slot]);
        }
    }
}

module channel() {
    rotate([90, 0, 90]) linear_extrude(length) channel_profile();
    translate([-12, -out_r, 0]) cube([13, 2 * out_r, wall * 1.5]);
}

rod();
translate([0, rod_d + out_r + 6, 0]) channel();
