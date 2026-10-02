// Flexi Axolotl: print-in-place articulated toy, single colour
// ------------------------------------------------------------
// Chibi-proportioned axolotl that prints flat, in one piece, with no supports.
// Snap it off the plate and every body joint wiggles. Built for a Bambu Lab
// A1 mini (180 x 180 mm bed) and tuned for PLA with a 0.4 mm nozzle at 0.2 mm
// layers.
//
// How the joints work: every joint is a vertical "bicone" knuckle (a pin with a
// 45-degree bulge in the middle) sitting in a matching socket in the piece in
// front of it. The bottom of the socket is a closed ring, so the knuckle can't
// be pulled out sideways. The bulge stops it lifting out. The neck that joins
// the knuckle to its own body only exists in the upper half, so it passes over
// that closed ring. Every surface is either vertical or at 45 degrees, so the
// model needs no supports.
//
// All parameters below work in the OpenSCAD Customizer and in the MakerWorld
// Parametric Model Maker.

/* [Body] */
// Number of body segments between head and tail
segments = 3; // [2:1:4]
// Thickness of the toy (Z height) in mm
body_height = 12; // [10:0.5:14]
// How domed the body is (sideways curve radius in mm, bigger = rounder)
body_dome = 9; // [5:0.5:10]
// Rounding of the head's edge in mm
head_round = 6; // [4:0.5:7]

/* [Face] */
// Engraved smile
smile = true;
// Small heart engraved on the tail (ignored when a tail name is set)
tail_heart = true;
// Optional name engraved on the tail (keep it short: about 6 characters)
tail_name = "";
// Font for the tail name
name_font = "Liberation Sans:style=Bold";

/* [Print-in-place tuning] */
// Gap between moving parts. Raise to 0.45-0.5 if the joints come out fused
clearance = 0.4; // [0.3:0.05:0.6]
// Max bend per joint, in degrees (bigger = wider gaps between segments)
max_bend = 16; // [10:1:22]

/* [Hidden] */
$fn = 64;
H     = body_height;
c     = clearance;
P     = 20;                 // joint-to-joint pitch
kr0   = 3.6;                // knuckle radius at top and bottom
kr1   = 5.6;                // knuckle radius at the bulge
kb    = kr1 - kr0;          // bulge, built at 45 degrees
kz1   = (H - 2*kb) * 0.225; // height where the bulge starts
wall  = 2.0;                // socket wall
Rs    = kr1 + c + wall;     // socket ring outer radius
gap   = 0.6;                // gap between neighbouring bodies
Rcut  = Rs + gap;           // concave cut on the rear piece
neck_w = 4.0;
neck_z = H / 2;             // the neck lives above this height
gv    = max(c + 0.2, 0.6);  // vertical gap under the neck
foot  = 0.3;                // elephant-foot relief on the first layer
soft  = 2.0;                // corner rounding on every piece outline

// rear pieces keep everything within this angle (from -X) of a joint
keep_ang = 90 - max_bend - 4;

function jx(i) = -i * P;    // x of joint i (joint 0 joins the head)
tail_x0 = jx(segments);     // tail joint
tail_len = 38;

// ---------- helpers ----------

// Extrude a 2D shape to height h with an elliptical top edge: it curves in by
// r sideways over the top rv of height (rv defaults to r). A large r turns the
// whole top into a dome. The first layer is pulled in slightly to fight
// elephant's foot.
module rounded_slab(h, r, rv = -1) {
    v = rv < 0 ? r : rv;
    steps = ceil(v / 0.35);
    linear_extrude(foot) offset(delta = -foot) children();
    translate([0, 0, foot]) linear_extrude(h - v - foot + 0.01) children();
    for (i = [0 : steps - 1]) {
        z0 = h - v + v * i / steps;
        z1 = h - v + v * (i + 1) / steps;
        t = (z1 - (h - v)) / v;
        ins = r * (1 - sqrt(max(0, 1 - t * t)));
        translate([0, 0, z0]) linear_extrude(z1 - z0 + 0.01)
            offset(r = -ins) children();
    }
}

// Round every convex corner of a 2D shape
module soften(r = soft) { offset(r = r) offset(r = -r) children(); }

// Chain of hulled circles: pts = [[x, y, r], ...]
module blob_chain(pts) {
    for (i = [0 : len(pts) - 2])
        hull() {
            translate([pts[i][0], pts[i][1]]) circle(pts[i][2]);
            translate([pts[i+1][0], pts[i+1][1]]) circle(pts[i+1][2]);
        }
}

// Area the neck sweeps through when the joint bends +/- max_bend, plus clearance
module neck_slot_2d() {
    offset(r = c) for (t = [-max_bend : 2 : max_bend])
        rotate(t) translate([-(Rs + 1), -neck_w / 2]) square([Rs + 1, neck_w]);
}

// Knuckle profile in (r, z) for rotate_extrude
module knuckle_profile() {
    polygon([[0, 0], [kr0 - foot, 0], [kr0, foot], [kr0, kz1], [kr1, kz1 + kb],
             [kr1, H - kz1 - kb], [kr0, H - kz1], [kr0, H], [0, H]]);
}

// Socket cavity = knuckle grown by the clearance, open at top and bottom
module cavity_profile() {
    intersection() {
        translate([0, -2]) square([20, H + 4]);
        union() {
            offset(r = c) knuckle_profile();
            translate([0, -1]) square([kr0 + c, H + 2]);
            // extra relief on the first layers
            polygon([[0, -1], [kr0 + c + 0.45, -1], [kr0 + c + 0.45, 0], [kr0 + c, 0.45], [0, 0.45]]);
        }
    }
}

// Cut that turns a front piece's rear end into a socket
module socket_cut(a) {
    translate([a, 0, 0]) {
        rotate_extrude() cavity_profile();
        translate([0, 0, neck_z - gv]) linear_extrude(H) neck_slot_2d();
    }
}

// Knuckle plus neck that a rear piece pushes into the socket in front of it
module knuckle_and_neck(b) {
    intersection() {
        translate([b, 0, 0]) {
            rotate_extrude() knuckle_profile();
            translate([-(Rcut + 1.5), -neck_w/2, neck_z]) cube([Rcut + 1.5, neck_w, H - neck_z]);
        }
        body_solid();
    }
}

// Region a front piece may occupy around its rear joint
module front_clip(a) {
    union() {
        translate([a + 0.3, -150]) square([400, 300]);
        translate([a, 0]) circle(Rs);
    }
}

// Region a rear piece must stay out of around its front joint, so it can swing
// +/- max_bend without touching the piece in front
module rear_keepout(b) {
    L = 400;
    translate([b, 0]) {
        circle(Rcut);
        polygon([[0, 0], [-L * cos(keep_ang), L * sin(keep_ang)], [L, L],
                 [L, -L], [-L * cos(keep_ang), -L * sin(keep_ang)]]);
    }
}

// ---------- 2D outlines ----------

// Big, broad, round head
module head_2d() {
    hull() {
        circle(Rs);
        translate([19, 0]) scale([17 / 21, 1]) circle(21, $fn = 96);
    }
}

// One gill: a short, fat teardrop that is widest at its rounded tip
module gill_2d(base, ang, len, tip_r = 4) {
    dir = [-sin(ang), cos(ang)];
    hull() { translate(base) circle(2.4); translate(base + len * dir) circle(tip_r); }
}

// Three gills per side, fanned out like a little crown
module gills_2d() {
    for (m = [0, 1]) mirror([0, m]) {
        gill_2d([18, 17.5], -35, 10);
        gill_2d([12.5, 17.5], 5, 11, 4.2);
        gill_2d([9, 14.5], 38, 8, 3.6);
    }
}

function seg_w(k) = 12.5 - 0.7 * (k - 1);   // half-width of segment k

// The whole animal as one smooth outline (head, body, tail). It is turned into
// one puffy solid first and then sliced into pieces, so the finished toy reads
// as a single body with thin cut lines.
module silhouette_2d() {
    b = tail_x0;
    offset(r = -3) offset(r = 3) union() {   // fillet where head meets body
        head_2d();
        blob_chain(concat(
            [[4, 0, 10.5]],
            [for (k = [1 : segments]) [jx(k) + P / 2, 0, seg_w(k)]],
            [[b, 0, seg_w(segments) - 1.2], [b - 13, 0, 9.5], [b - 27, 0, 6.2], [b - tail_len, 0, 2.6]]));
    }
}

// Area belonging to piece i: 0 = head, 1..segments = body, segments+1 = tail
module region_2d(i) {
    if (i == 0) front_clip(0);
    else if (i <= segments) difference() { front_clip(jx(i)); rear_keepout(jx(i - 1)); }
    else difference() { translate([-400, -150]) square([400 + tail_x0 + 50, 300]); rear_keepout(tail_x0); }
}

module piece_outline(i) { soften(1.5) intersection() { silhouette_2d(); region_2d(i); } }

module body_solid() { rounded_slab(H, body_dome, H - 4) silhouette_2d(); }
module head_solid() { rounded_slab(H, head_round, head_round) silhouette_2d(); }

// Puffy slice of the body for piece i
module piece_body(i) {
    intersection() {
        if (i == 0) head_solid(); else body_solid();
        translate([0, 0, -1]) linear_extrude(H + 2) piece_outline(i);
    }
}

// Stubby little leg with three round toes, reaching out and slightly back
module leg_2d(x, w) {
    base = [x + 1, w - 3];
    foot_p = [x - 2, w + 4];
    hull() { translate(base) circle(3.8); translate(foot_p) circle(3.2); }
    for (t = [-35, 10, 55]) translate(foot_p + 3 * [sin(t), cos(t)]) circle(1.9);
}

module legs_2d(k) {
    m = jx(k) + P / 2;
    soften(1) intersection() {
        for (s = [0, 1]) mirror([0, s]) leg_2d(m, seg_w(k));
        region_2d(k);
    }
}

module heart_2d(s) {
    for (m = [0, 1]) mirror([m, 0])
        hull() { translate([s * 0.25, s * 0.18]) circle(s * 0.28); translate([0, -s * 0.5]) circle(0.3); }
}

// ---------- 3D pieces ----------

module head() {
    ex = 24; ey = 11.5;
    difference() {
        union() {
            piece_body(0);
            rounded_slab(H * 0.62, 2) soften(1) intersection() { gills_2d(); region_2d(0); }
        }
        socket_cut(0);
        // big round eyes, recessed
        for (s = [-1, 1]) translate([ex, s * ey, H - 1.2]) cylinder(r = 4, h = 3);
        if (smile) translate([0, 0, H - 0.8]) linear_extrude(2) smile_2d();
    }
    // sparkle highlight in each eye
    for (s = [-1, 1]) translate([ex + 1.4, s * ey + 1.3, H - 1.3]) cylinder(r = 1.2, h = 1.3);
}

module smile_2d() {
    // wide, dopey axolotl smile near the front of the head
    for (t = [-32 : 4 : 28])
        hull() {
            translate([18 + 12 * cos(t), 12 * sin(t)]) circle(0.6, $fn = 16);
            translate([18 + 12 * cos(t + 4), 12 * sin(t + 4)]) circle(0.6, $fn = 16);
        }
}

module segment(k) {
    difference() {
        union() {
            piece_body(k);
            if (k == 1 || k == segments) rounded_slab(H * 0.6, 2) legs_2d(k);
        }
        socket_cut(jx(k));
    }
    knuckle_and_neck(jx(k - 1));
}

module tail() {
    b = tail_x0;
    difference() {
        piece_body(segments + 1);
        // engrave the name or heart 0.8 mm deep, following the curved surface
        intersection() {
            difference() { body_solid(); translate([0, 0, -0.8]) body_solid(); }
            translate([b - 18, 0, 0]) linear_extrude(H + 1)
                if (tail_name != "")
                    resize([min(16, 3.6 * len(tail_name)), 0], auto = [true, true])
                        text(tail_name, size = 5, font = name_font, halign = "center", valign = "center");
                else if (tail_heart)
                    rotate(-90) heart_2d(7);
        }
    }
    knuckle_and_neck(b);
}

module axolotl() {
    head();
    for (k = [1 : segments]) segment(k);
    tail();
}

// Centre the model on the plate
x_front = 36;
x_back = tail_x0 - tail_len - 2.8;
color("#F6B8C8") translate([-(x_front + x_back) / 2, 0, 0]) axolotl();
