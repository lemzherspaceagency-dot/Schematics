// Phone / Tablet Stand — fixed-angle stand with a charging-cable slot.
// Works portrait or landscape, with or without a case.
// Print lying on its side (as rendered); no supports needed.

/* [Device] */
// Thickness of your phone/tablet INCLUDING the case (mm)
device_t = 12;          // [5:0.5:20]
// Viewing angle from the table (degrees). 60-70 is comfy on a desk.
angle = 65;             // [45:1:80]
// Height of the back rest (mm). ~60 for phones, ~100 for tablets.
rest_len = 75;          // [40:1:150]

/* [Stand] */
// Width of the stand (mm) — this is the print height
width = 70;             // [30:1:200]
// Front lip height above the seat (mm)
lip_h = 9;              // [4:1:20]
// Height of the seat above the table (mm)
seat_h = 8;             // [4:1:30]
// Material thickness (mm)
wall = 4;               // [2.5:0.5:8]
// Cut a slot for a charging cable
cable_slot = true;
// Cable slot width (mm)
cable_w = 13;           // [6:1:30]

/* [Hidden] */
$fn = 32;
lip_t = wall;
front = 30 + device_t;                               // x of front face
bx = front - lip_t - device_t / sin(angle) - 0.8;   // foot of the back rest
p_top = [bx - rest_len * cos(angle), seat_h + rest_len * sin(angle)];
p_back = p_top + wall * [-sin(angle), -cos(angle)];
x0 = p_back[0];

module body() {
    polygon([
        [x0, 0], [front, 0],
        [front, seat_h + lip_h], [front - lip_t, seat_h + lip_h],
        [front - lip_t, seat_h], [bx, seat_h],
        p_top, p_back
    ]);
}

module lightening() {
    // triangle under the back rest, shrunk by `wall`
    tri = [[x0, 0], [p_back[0] + p_back[1] / tan(angle), 0], p_back];
    offset(r = 2) offset(delta = -wall - 2) polygon(tri);
}

translate([-x0, 0, 0])
difference() {
    linear_extrude(width) difference() { body(); lightening(); }
    if (cable_slot)
        translate([bx, -1, width / 2 - cable_w / 2])
            cube([front - bx + 1, seat_h + lip_h + 2, cable_w]);
}
