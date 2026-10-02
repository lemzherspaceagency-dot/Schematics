// Pastel Pumpkin: jack-o'-lantern shade or candy jar, with a carved lid
// ---------------------------------------------------------------------
// Two parts on one plate (pumpkin + lid with the stem), no supports.
//  * "lantern": open bottom. Set it over a battery LED tea light. Never use a
//    real flame: PLA softens at around 60 C.
//  * "jar": closed bottom, for candy or desk bits.
//  * "solid": one-piece decoration with the face engraved, no lid.
//
// Why it prints without supports:
//  * the flat bottom is cut where the ribs are still steep (under 45 degrees)
//  * the inside is computed so its ceiling never overhangs more than 45
//    degrees. The lid opening is a cone that widens upwards, cut like a real
//    carved pumpkin, so the lid sits in it and can't fall through
//  * every face hole has a pointed or small round top, so there are no flat
//    bridges inside the holes
//
// Fits the A1 mini at the default size. All parameters work in the OpenSCAD
// Customizer and in the MakerWorld Parametric Model Maker.

/* [Shape] */
// What to make
style = "lantern"; // [lantern, jar, solid]
// Overall diameter in mm
diameter = 90; // [50:5:120]
// Body height in mm (without the stem)
height = 60; // [40:2:120]
// Number of ribs
ribs = 10; // [6:1:16]
// Rib fullness (lower = deeper grooves between ribs)
rib_fullness = 0.7; // [0.5:0.01:0.85]

/* [Face] */
// Face style
face = "hearts"; // [hearts, classic, kawaii, none]
// Face size, relative to the pumpkin
face_scale = 1.0; // [0.6:0.05:1.3]

/* [Walls and lid] */
// Wall thickness in mm
wall = 1.8; // [1.2:0.2:4]
// Lid opening radius at its narrowest point, as a fraction of the diameter
lid_size = 0.12; // [0.08:0.01:0.16]
// Gap between lid and pumpkin in mm
lid_gap = 0.3; // [0.2:0.05:0.6]

/* [Stem] */
stem_height = 20; // [6:1:35]
// Twist of the stem in degrees
stem_twist = 90; // [0:5:180]
// How much the stem curls sideways
stem_curl = 0.4; // [0:0.05:0.45]

/* [Hidden] */
$fn = 72;
R   = diameter / 2;
N   = ribs;
d   = 0.42 * R;                      // rib centre offset from the axis
lr  = R - d;                         // rib radial semi-axis
lw  = rib_fullness * 2 * PI * R / N; // rib sideways semi-axis
cut = 0.7;                           // bottom cut, as a fraction of hz
hz  = height / (1 + cut);            // rib vertical semi-axis
z0  = -cut * hz;                     // flat bottom (rib-centre coordinates)
zc  = hz * sqrt(1 - pow(d / lr, 2)); // height of the dip under the stem
f   = face_scale * diameter / 100;   // face scale factor
total_h = hz - z0;
has_lid = style != "solid";
r_lid = lid_size * diameter;         // lid opening radius at z_lid
z_lid = zc - 3;                      // bottom of the lid plug (3 mm under the dip)
floor_t = 1.6;                       // jar floor

// Lid opening: a cone widening upwards at 45 degrees
function cone_r(z) = r_lid + (z - z_lid);

// ---------- shape maths ----------

// Radius of the outside surface along the groove between two ribs, at height
// z. Returns 0 where neighbouring ribs no longer overlap.
function groove_r(z) =
    let(s2 = 1 - pow(z / hz, 2))
    s2 <= 0 ? 0 :
    let(s = sqrt(s2), A = lr * s, B = lw * s,
        ca = cos(180 / N), sa = sin(180 / N),
        qa = ca * ca / (A * A) + sa * sa / (B * B),
        qb = -2 * d * ca / (A * A),
        qc = d * d / (A * A) - 1,
        disc = qb * qb - 4 * qa * qc)
    disc < 0 ? 0 : (-qb + sqrt(disc)) / (2 * qa);

// Largest hollow radius at height z that still leaves `t` of material in every
// direction (checks the outside surface within +/- t above and below)
function hollow_lim(z, t) =
    min([for (k = [-6 : 6])
        let(dz = t * k / 6, zz = z + dz)
        if (zz >= z0) groove_r(zz) - sqrt(max(0, t * t - dz * dz))]);

dz = 0.5;
M  = floor((hz - z0) / dz) + 2;
function zi(i) = z0 + i * dz;

// Inside profile, worked out from the top down. Where the lid cone is wider it
// takes over, otherwise the wall is allowed to lean in by at most 45 degrees
// per step.
function raw_profile(t) = [for (i = [0 : M]) max(0, hollow_lim(zi(i), t))];
function lipschitz(raw, i, above) =
    i < 0 ? [] :
    let(v = min(raw[i], above + dz),
        open = has_lid ? max(v, cone_r(zi(i))) : v)
    concat(lipschitz(raw, i - 1, open), [open]);

module hollow_solid(t) {
    prof = lipschitz(raw_profile(t), M, has_lid ? cone_r(zi(M)) : 0);
    rotate_extrude($fn = 96)
        polygon(concat([[0, z0 - 1], [prof[0], z0 - 1]],
                       [for (i = [0 : M]) [prof[i], zi(i)]],
                       [[prof[M], zi(M) + 20], [0, zi(M) + 20]]));
}

// ---------- body ----------

module rib() {
    translate([d, 0, 0]) scale([lr, lw, hz]) sphere(1, $fn = 64);
}

module body() {
    intersection() {
        union() {
            for (i = [0 : N - 1]) rotate(-90 + i * 360 / N) rib();
            // fill the pinhole the ribs leave at the very centre
            translate([0, 0, z0]) cylinder(r = d * 0.5, h = zc - z0 - 1);
        }
        translate([-R - 1, -R - 1, z0]) cube([2 * R + 2, 2 * R + 2, hz - z0 + 1]);
    }
}

// Twisted stem that curls to one side and tapers, rising out of the dip.
// The curl gets steepest at the tip, where it reaches at most 45 degrees.
module stem() {
    sr = 0.09 * diameter;
    n = 24;
    h = stem_height + 4;
    function at(t) = [stem_curl * h * t * t, 0, h * t];
    module slice(t)
        translate(at(t)) rotate(stem_twist * t) linear_extrude(0.01)
            scale(1 - 0.4 * t) offset(r = sr * 0.25) offset(delta = -sr * 0.25)
                circle(sr, $fn = 6);
    translate([0, 0, zc - 4])
        for (i = [0 : n - 1]) hull() { slice(i / n); slice((i + 1) / n); }
}

// Solid cone used to split off the lid (g = extra clearance)
module lid_cone(g = 0) {
    rotate_extrude($fn = 96)
        polygon([[0, z_lid], [r_lid - g, z_lid], [r_lid - g + 200, z_lid + 200], [0, z_lid + 200]]);
}

// ---------- faces (drawn flat: x across, y up from the bottom) ----------

module teardrop(r) {
    hull() { circle(r); translate([0, r * sqrt(2)]) square(0.01, center = true); }
}

module tri_up(w, h) { polygon([[-w / 2, 0], [w / 2, 0], [0, h]]); }

// Heart with pointed lobe tops (no flat overhangs)
module heart(s) {
    for (m = [0, 1]) mirror([m, 0])
        hull() { translate([s * 0.24, 0]) teardrop(s * 0.27); translate([0, -s * 0.62]) circle(0.4); }
}

// Grin with a zigzag top edge: every top-edge slope is at least 45 degrees
module zigzag_mouth(w, depth, teeth) {
    n = teeth * 2;
    function by(x) = 4 * f - depth * (1 - pow(2 * x / w, 2));             // bottom curve
    function ty(x) = 4 * f - depth * 0.3 * (1 - pow(2 * x / w, 2));       // top curve
    tooth_h = 1.15 * w / n;    // steeper than 45 degrees
    top = [for (i = [0 : n])
        let(x = -w / 2 + w * i / n, tooth = (i % 2 == 1) ? tooth_h : 0)
        [x, max(ty(x) - tooth, by(x) + 2.5 * f)]];
    bottom = [for (i = [24 : -1 : 0]) let(x = -w / 2 + w * i / 24) [x, by(x)]];
    polygon(concat(top, bottom));
}

// Thin arc stroke, used for the cat mouth
module arc_stroke(r, a0, a1, w) {
    for (a = [a0 : 10 : a1 - 10])
        hull() {
            translate(r * [cos(a), sin(a)]) circle(w / 2, $fn = 16);
            translate(r * [cos(a + 10), sin(a + 10)]) circle(w / 2, $fn = 16);
        }
}

module face_2d() {
    eye_y   = 0.60 * total_h;
    nose_y  = 0.45 * total_h;
    mouth_y = 0.30 * total_h;
    if (face == "classic") {
        for (s = [-1, 1]) translate([s * 18 * f, eye_y]) tri_up(21 * f, 18 * f);
        translate([0, nose_y]) tri_up(10 * f, 9 * f);
        translate([0, mouth_y]) zigzag_mouth(60 * f, 20 * f, 4);
    } else if (face == "hearts") {
        for (s = [-1, 1]) translate([s * 18 * f, eye_y + 8 * f]) heart(22 * f);
        translate([0, mouth_y]) zigzag_mouth(54 * f, 17 * f, 3);
    } else if (face == "kawaii") {
        // round eyes are small enough to print without support
        for (s = [-1, 1]) translate([s * 17 * f, eye_y + 2 * f]) circle(6.5 * f);
        // little "w" cat mouth
        translate([0, mouth_y + 9 * f])
            for (s = [-1, 1]) translate([s * 4 * f, 0]) arc_stroke(4 * f, 180, 360, 2.6 * f);
    }
}

// Face holes pushed straight through the front wall
module face_cut() {
    if (face != "none")
        translate([0, 0, z0]) rotate([90, 0, 0]) linear_extrude(R + 10) face_2d();
}

// ---------- parts ----------

module pumpkin_base() {
    difference() {
        union() {
            body();
            if (!has_lid) stem();
        }
        if (style == "solid") {
            // engrave the face 2.5 mm deep
            difference() { face_cut(); hollow_solid(2.5); }
        } else {
            difference() {
                hollow_solid(wall);
                if (style == "jar") translate([-R, -R, z0 - 2]) cube([2 * R, 2 * R, 2 + floor_t]);
            }
            lid_cone();
            face_cut();
        }
    }
}

module lid() {
    intersection() {
        union() { body(); stem(); }
        lid_cone(lid_gap);
    }
}

// Plate layout: pumpkin at the origin, lid (flat side down) beside it
color("#F6B8C8") {
    translate([0, 0, -z0]) pumpkin_base();
    if (has_lid) {
        off = (R + cone_r(hz) + 6) / sqrt(2);
        translate([off, off, -z_lid]) lid();
    }
}
