// Print-in-place herringbone planetary-gear fidget spinner. Print all parts at once as laid out, no supports.
// Spin the center knob: the three planets and the outer ring turn with it. ~1.5 h on an A1 mini.
m   = 1.5;      // gear module
Zs  = 12;       // sun teeth
Zp  = 12;       // planet teeth
Zr  = Zs + 2 * Zp;  // ring teeth (36)
h   = 8;        // gear thickness
tw  = 14;       // helix twist per half (deg at pitch radius scale, see below)
beta = 22;      // helix angle (deg)
clr = 0.15;     // clearance per side (total gap 0.3 mm)
knob_d = 20; knob_h = 8;
ring_wall = 7;
alpha = 20;     // pressure angle
$fn = 64;

function inv(a) = tan(a) - a * PI / 180;   // involute function (a in degrees, returns radians)
function tooth_half(rp, rb, r) = 90 / (2 * rp / m) + (inv(alpha) - inv(acos(rb / r))) * 180 / PI;

module gear2d(Z) {
    rp = m * Z / 2; rb = rp * cos(alpha); ra = rp + m; rr = rp - 1.25 * m;
    rs = max(rb, rr + 0.01);
    n = 8;
    rs_list = [for (i = [0 : n]) rs + (ra - rs) * i / n];
    right = [for (r = rs_list) let (a = tooth_half(rp, rb, r)) [r * cos(-a), r * sin(-a)]];
    left  = [for (i = [n : -1 : 0]) let (r = rs_list[i], a = tooth_half(rp, rb, r)) [r * cos(a), r * sin(a)]];
    root_a = tooth_half(rp, rb, rs);
    tooth = concat([[rr - 0.2, 0 - 0]], [[(rr - 0.2) * cos(-root_a), (rr - 0.2) * sin(-root_a)]], right, left, [[(rr - 0.2) * cos(root_a), (rr - 0.2) * sin(root_a)]]);
    union() {
        circle(r = rr);
        for (i = [0 : Z - 1]) rotate(i * 360 / Z) polygon(tooth);
    }
}

// herringbone: lower half twists one way, upper half mirrors it
function twist_for(Z) = 360 * (h / 2) * tan(beta) / (PI * m * Z);

module herringbone(Z, sign = 1, grow = 0) {
    t = sign * twist_for(Z);
    for (up = [0, 1]) {
        translate([0, 0, up ? h : 0]) mirror([0, 0, up ? 1 : 0])
            linear_extrude(height = h / 2 + (up ? 0 : 0.001), twist = -t, slices = 24, convexity = 6)
                offset(delta = grow) gear2d(Z);
    }
}

R_orbit = m * (Zs + Zp) / 2;

// SUN (+ knob on top)
module sun() {
    herringbone(Zs, 1, -clr);
    translate([0, 0, h - 0.01]) cylinder(d = knob_d, h = knob_h + 0.01);
}
// PLANETS
module planet(i) {
    phi = i * 120;
    translate([R_orbit * cos(phi), R_orbit * sin(phi), 0]) rotate(180 / Zp) herringbone(Zp, -1, -clr);
}
// RING
module ring() {
    ro = m * Zr / 2 + m + ring_wall;
    difference() {
        cylinder(r = ro, h = h);
        translate([0, 0, -0.01]) scale([1, 1, 1]) herringbone_cut();
        // knurl for grip
        for (a = [0 : 15 : 359]) rotate(a) translate([ro, 0, -1]) cylinder(d = 3, h = h + 2, $fn = 16);
    }
}
module herringbone_cut() { herringbone(Zr, -1, clr); }

// parts printed in their meshed (assembled) positions - it is a print-in-place mechanism
sun();
for (i = [0 : 2]) planet(i);
ring();
