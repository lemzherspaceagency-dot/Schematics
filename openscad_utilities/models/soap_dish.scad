// Draining Soap Dish — raised ribs keep the soap dry, and slots let the
// water drip straight through. Also a sponge holder by the sink.
// Print upright (as rendered). PETG recommended (it lives in water).

/* [Size] */
length = 110;           // [60:1:180]
width = 80;             // [40:1:140]
height = 18;            // [10:1:40]

/* [Hidden] */
$fn = 40;
wall = 2;
floor_t = 2;
foot_h = 3;
r = 12;

module rr(l, w, rad) { offset(r = rad) offset(delta = -rad) square([l, w]); }

difference() {
    union() {
        translate([0, 0, foot_h]) linear_extrude(height - foot_h) rr(length, width, r);
        // feet raise the dish so it drains underneath
        for (x = [12, length - 12], y = [12, width - 12])
            translate([x, y, 0]) cylinder(d = 10, h = foot_h + 0.01);
    }
    translate([wall, wall, foot_h + floor_t])
        linear_extrude(height) rr(length - 2 * wall, width - 2 * wall, r - wall);
    // drain slots between the ribs
    for (x = [14 : 8 : length - 14])
        hull() for (y = [16, width - 16])
            translate([x, y, -1]) cylinder(d = 3, h = height);
}
// ribs the soap sits on
intersection() {
    for (x = [10 : 8 : length - 10])
        translate([x - 1.4, 0, foot_h]) cube([2.8, width, floor_t + 5]);
    translate([wall, wall, 0]) linear_extrude(height) rr(length - 2 * wall, width - 2 * wall, r - wall);
}
