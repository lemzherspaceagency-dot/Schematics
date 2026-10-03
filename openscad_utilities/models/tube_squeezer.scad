// Tube Squeezer — get the last bit out of toothpaste, creams, glue, paint,
// tomato paste… Thread the flat end of the tube through the slot and roll.
// Print flat (as rendered).

/* [Size] */
// Width of the flattened tube end (mm). Toothpaste is ~50–55.
tube_w = 55;            // [20:1:120]
// Slot gap (mm). 2.5–3 works for most tubes.
slot_gap = 2.8;         // [1.5:0.1:6]
// Thickness of the squeezer (mm)
thickness = 8;          // [5:1:15]

/* [Hidden] */
$fn = 48;
L = tube_w + 16;
W = slot_gap + 16;

difference() {
    hull()
        for (x = [W / 2, L - W / 2])
            translate([x, W / 2, 0]) {
                cylinder(d = W - 2, h = thickness);
                translate([0, 0, 1]) cylinder(d = W, h = thickness - 2);
            }
    // slot with rounded ends and flared entry so the tube threads easily
    hull()
        for (x = [8, L - 8])
            translate([x, W / 2, -1]) cylinder(d = slot_gap, h = thickness + 2);
    for (z = [-1, thickness - 1.2])
        hull()
            for (x = [8, L - 8])
                translate([x, W / 2, z])
                    cylinder(d1 = z < 0 ? slot_gap + 2.4 : slot_gap,
                             d2 = z < 0 ? slot_gap : slot_gap + 2.4, h = 2.2);
}
