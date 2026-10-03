// Bit & Hex Key Holder — keeps screwdriver bits or Allen keys sorted.
// mode "bits":     grid of 1/4" hex pockets for standard screwdriver bits.
// mode "hex_keys": a row of labelled holes, one per Allen key size.
// Print upright (as rendered).

mode = "bits";          // ["bits", "hex_keys"]

/* [Bits] */
cols = 8;               // [1:1:20]
rows = 2;               // [1:1:10]
// Pocket depth (mm). Standard bits are 25 mm long.
bit_depth = 12;         // [6:1:20]
// Hex across-flats + clearance (mm). 1/4" = 6.35.
bit_af = 6.75;          // [6.4:0.05:7.2]

/* [Hex keys] */
// Allen key sizes (mm)
key_sizes = [1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
// Hole depth (mm)
key_depth = 18;         // [8:1:30]

/* [Hidden] */
$fn = 6;
pitch = bit_af + 4;

// x position of each hex key hole
function px(i) = i == 0 ? 6 : px(i - 1) + key_sizes[i - 1] / 2 + key_sizes[i] / 2 + 7;

module rr(l, w) { offset(r = 3, $fn = 24) offset(delta = -3) square([l, w]); }

if (mode == "bits") {
    L = cols * pitch + 4; W = rows * pitch + 4; H = bit_depth + 2;
    difference() {
        linear_extrude(H) rr(L, W);
        for (i = [0 : cols - 1], j = [0 : rows - 1])
            translate([2 + pitch * (i + 0.5), 2 + pitch * (j + 0.5), 2])
                rotate(30) cylinder(d = bit_af / cos(30), h = H);
    }
} else {
    n = len(key_sizes);
    L = px(n - 1) + key_sizes[n - 1] / 2 + 6;
    W = 26; H = key_depth + 2;
    difference() {
        linear_extrude(H) rr(L, W);
        for (i = [0 : n - 1]) {
            translate([px(i), 17, 2])
                rotate(30) cylinder(d = (key_sizes[i] + 0.35) / cos(30), h = H);
            // size labels engraved on the top
            translate([px(i), 6, H - 0.8])
                linear_extrude(1) text(str(key_sizes[i]), size = 3.6, halign = "center", $fn = 16);
        }
    }
}
