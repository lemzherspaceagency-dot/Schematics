// Original litter scoop for clumping litter. Print flat (blade down), no supports; 0.2 layers, 4 walls.
blade_w = 96; blade_l = 100; wall_h = 24; t = 2.4;
slot_w = 5.2;       // clumping litter: 5-6 mm; use ~3.5 for fine/crystal litter
slot_l = 52; slot_pitch = slot_w + 2.6;
handle_l = 58; handle_w = 24; handle_t = 4;
$fn = 48;

module outline() {
    hull() {
        translate([8, 8]) circle(r = 8); translate([blade_w - 8, 8]) circle(r = 8);
        translate([8, blade_l - 8]) square(1); translate([blade_w - 9, blade_l - 8]) square(1);
    }
}

difference() {
    union() {
        linear_extrude(height = t) outline();
        // side + back walls
        linear_extrude(height = wall_h) difference() {
            outline();
            offset(delta = -t) outline();
            // open front edge so litter slides in
            translate([-1, -1]) square([blade_w + 2, 18]);
        }
        // handle (continues from the back edge)
        translate([blade_w / 2 - handle_w / 2, blade_l - 2, 0]) {
            cube([handle_w, handle_l, handle_t]);
            // ribbed grip
            for (y = [20 : 9 : handle_l - 6]) translate([0, y, 0]) cube([handle_w, 3, handle_t + 3]);
        }
    }
    // slots
    for (i = [0 : floor((blade_w - 20 - slot_w) / slot_pitch)])
        translate([10 + i * slot_pitch, 18, -1]) cube([slot_w, slot_l, t + 2]);
    // hang hole in handle
    translate([blade_w / 2, blade_l + handle_l - 2 - 9, -1]) cylinder(d = 10, h = 10);
}
