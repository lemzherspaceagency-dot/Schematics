// Memory Card & USB Stick Holder — keep SD cards, microSD cards and
// USB sticks upright and easy to find. Print upright (as rendered).

/* [How many] */
sd_count = 6;           // [0:1:20]
microsd_count = 8;      // [0:1:30]
usb_count = 4;          // [0:1:20]

/* [Hidden] */
$fn = 32;
// [slot width, slot thickness, slot depth]
SD    = [24.8, 2.8, 16];
MICRO = [11.6, 1.6, 9];
USB   = [12.8, 5.2, 12];
types = [[SD, sd_count], [MICRO, microsd_count], [USB, usb_count]];
gap = 3;         // material between slots
border = 4;

function col_w(i) = types[i][1] > 0 ? types[i][0][0] + gap : 0;
function col_x(i) = i == 0 ? border : col_x(i - 1) + col_w(i - 1);
function col_len(i) = types[i][1] * (types[i][0][1] + gap) - gap;

L = col_x(len(types)) - gap + border;
W = max([for (i = [0 : len(types) - 1]) col_len(i)]) + 2 * border;
H = max([for (t = types) t[1] > 0 ? t[0][2] : 0]) + 3;
assert(sd_count + microsd_count + usb_count > 0, "need at least one slot");

difference() {
    linear_extrude(H) offset(r = 3) offset(delta = -3) square([L, W]);
    for (i = [0 : len(types) - 1])
        for (j = [0 : 1 : types[i][1] - 1]) {
            s = types[i][0];
            translate([col_x(i), border + j * (s[1] + gap), H - s[2]])
                cube([s[0], s[1], s[2] + 1]);
        }
}
