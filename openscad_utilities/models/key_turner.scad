// Key Turner — a big, easy-grip handle for a house key.
// Made for anyone with arthritis, weak grip, or cold hands.
// The key head slides into the slot and a small M3 bolt passes through
// the key's ring hole to lock it in place.
// Print flat (as rendered). The slot roof bridges fine without supports.
//
// How to measure your key:
//   key_w      = widest part of the key head
//   key_t      = thickness of the key (calipers, usually 2-2.5 mm)
//   key_head_l = from the tip of the head to where the blade starts
//   hole_from_top = from the tip of the head to the centre of the ring hole

/* [Key] */
key_w = 24;             // [15:0.5:40]
key_t = 2.4;            // [1.5:0.1:4]
key_head_l = 24;        // [12:0.5:40]
hole_from_top = 5;      // [2:0.5:15]

/* [Handle] */
// Handle width (mm)
handle_w = 60;          // [40:1:100]
// Handle length (mm)
handle_l = 55;          // [35:1:100]
// Handle thickness (mm)
handle_t = 14;          // [8:1:25]
// Bolt clearance hole (mm). 3.4 for M3.
bolt_d = 3.4;           // [2:0.1:5]
// Nut across flats (mm). 5.5 for M3.
nut_af = 5.5;           // [4:0.1:9]

/* [Hidden] */
$fn = 64;
tol = 0.4;
slot_w = key_w + 2 * tol;
slot_t = key_t + tol;
// the key enters through the bottom edge (y = 0)
slot_depth = key_head_l + 1;
bolt_y = slot_depth - hole_from_top;

module outline() {
    hull() {
        translate([handle_w / 2, handle_l * 0.6]) resize([handle_w, handle_l * 0.8]) circle(d = 10);
        translate([handle_w / 2 - (key_w / 2 + 6), 0]) square([key_w + 12, 1]);
    }
}

difference() {
    // body with rounded top and bottom edges
    hull() {
        translate([0, 0, 2]) linear_extrude(handle_t - 4) outline();
        linear_extrude(handle_t) offset(delta = -2) outline();
    }
    // thumb dimples on both faces
    for (z = [handle_t + 22, -22])
        translate([handle_w / 2, handle_l * 0.62, z]) sphere(r = 24, $fn = 96);
    // key slot
    translate([handle_w / 2 - slot_w / 2, -1, handle_t / 2 - slot_t / 2])
        cube([slot_w, slot_depth + 1, slot_t]);
    // bolt hole, head recess on top, hex nut trap on the bottom
    translate([handle_w / 2, bolt_y, -1]) {
        cylinder(d = bolt_d, h = handle_t + 2);
        translate([0, 0, handle_t - 1.5]) cylinder(d = bolt_d * 1.9, h = 10);
        cylinder(d = nut_af / cos(30) + tol, h = 1 + 2.6, $fn = 6);
    }
}
