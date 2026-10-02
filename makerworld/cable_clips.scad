// Adhesive cable clip set: 3, 5, 7 mm single clips + a 3-slot desk organizer. Print flat, no supports.
$fn = 64;
wall = 2; h = 8; base = 2; gap_ratio = 0.8;

module clip(d, extra_w = 0) {
    od = d + 2 * wall;
    difference() {
        union() {
            translate([-od / 2 - 4, -od / 2, 0]) cube([od + 8, od + 2, base]);       // sticker pad
            translate([0, 0, 0]) cylinder(d = od, h = h);
        }
        translate([0, 0, base]) cylinder(d = d, h = h);
        // opening on top, narrower than the cable so it snaps
        translate([-d * gap_ratio / 2, 0, base]) cube([d * gap_ratio, od, h]);
    }
}

module organizer(ds = [4, 6, 8]) {
    total = sum_d(ds) + (len(ds) + 1) * wall;
    difference() {
        translate([0, 0, 0]) cube([total, 22, 16]);
        x = wall;
        for (i = [0 : len(ds) - 1]) {
            xo = wall * (i + 1) + sum_to(ds, i) + ds[i] / 2;
            translate([xo, 11, 6 + ds[i] / 2]) cylinder(d = ds[i], h = 20);
            translate([xo - ds[i] * gap_ratio / 2, 11, 6 + ds[i] / 2]) cube([ds[i] * gap_ratio, 20, 20]);
        }
    }
}
function sum_d(v, i = 0) = i >= len(v) ? 0 : v[i] + sum_d(v, i + 1);
function sum_to(v, n, i = 0) = i >= n ? 0 : v[i] + sum_to(v, n, i + 1);

// layout
translate([0, 0, 0])   clip(3);
translate([20, 0, 0])  clip(5);
translate([42, 0, 0])  clip(7);
translate([-8, 24, 0]) organizer([4, 6, 8]);
