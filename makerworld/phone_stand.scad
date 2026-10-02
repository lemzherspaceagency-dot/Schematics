// Foldless phone/tablet stand with charging-cable slot. Print standing as modeled (profile on bed). No supports.
w        = 75;    // stand width
base_len = 95;
t        = 4;
angle    = 68;    // back angle from horizontal
back_len = 85;
lip_h    = 14;    // front lip holding the device
slot_w   = 14;    // cable slot width
$fn = 64;

module profile() {
    x0 = back_len * cos(angle) + t;     // pivot so the back leans rearward over the base
    // base
    square([x0 + base_len, t]);
    // front lip
    translate([x0 + base_len - t, 0]) square([t, lip_h]);
    // leaning back
    translate([x0, 0]) rotate(90 - angle) square([t, back_len]);
    // gusset where back meets base (device side), overlapping both walls
    fx = x0 + t * sin(90 - angle) * 0 + t * cos(90 - angle);       // front-face foot of the back panel
    fy = t * sin(90 - angle);
    polygon([[fx - 1, 0.5], [fx + 22, 0.5], [fx + 22, t], [fx - 30 * cos(angle) - 1, fy + 30 * sin(angle)]]);
}

difference() {
    linear_extrude(height = w) profile();
    // cable slot through lip + base middle
    translate([base_len - 10, -1, w / 2 - slot_w / 2]) cube([60, t + 2, slot_w]);
}
