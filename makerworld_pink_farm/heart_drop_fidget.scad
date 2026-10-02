// Heart Drop: print-in-place spiral gravity fidget
// ------------------------------------------------
// A heart-shaped nut is printed already threaded onto a twisted shaft. Flip
// the toy and the heart spins its way down the spiral; flip it again and it
// spins back. One piece, no supports, about 45 minutes on an A1 mini.
//
// Why it prints in place:
//  * the nut prints on the bed around the shaft's flared foot, with a 45-degree
//    cone recess underneath it, so nothing floats
//  * the shaft twists slowly enough that its flanks stay under ~40 degrees
//  * the end caps are 45-degree cones, so they stop the nut at both ends
//
// All parameters work in the OpenSCAD Customizer and in the MakerWorld
// Parametric Model Maker.

/* [Fidget] */
// Shape of the spinning nut
nut_shape = "heart"; // [heart, round, star]
// How far the nut travels in mm
travel = 60; // [30:5:100]
// Turns the nut makes over the full travel
turns = 1.5; // [0.75:0.25:2.5]
// Lobes on the shaft profile
lobes = 3; // [2:1:5]
// Small heart engraved on the top cap
cap_heart = true;

/* [Print-in-place tuning] */
// Gap between nut and shaft. Raise to 0.55-0.6 if the nut comes out stuck
clearance = 0.5; // [0.35:0.05:0.7]

/* [Hidden] */
$fn = 72;
c     = clearance;
r0    = 6.5;                   // mean shaft radius
a     = 1.5;                   // lobe amplitude
nut_h = 14;
z_top = nut_h + travel;        // twisted section ends here (cap starts)
rate  = 360 * turns / travel;  // twist, degrees per mm
Rf    = r0 + a + c + 1.2;      // bottom flare radius
r_in  = r0 - a - 0.5;          // inside every lobe valley
Rcap  = 12;
foot  = 0.3;                   // elephant-foot relief on the first layer

// ---------- helpers ----------

module shaft_profile(grow = 0) {
    offset(r = grow)
        polygon([for (i = [0 : 119]) let(t = i * 3, r = r0 + a * cos(lobes * t)) [r * cos(t), r * sin(t)]]);
}

// The twisted shaft (or, with grow > 0, the matching hole in the nut).
// Both use identical extrusion settings so the helix lines up exactly.
module twisted(grow = 0) {
    linear_extrude(z_top, twist = -rate * z_top, slices = ceil(z_top / 0.4))
        shaft_profile(grow);
}

// Foot cone in (r, z): flat flare that narrows at 45 degrees into the shaft
module foot_profile() {
    polygon([[0, 0], [Rf - foot, 0], [Rf, foot], [Rf, 0.8], [r_in, 0.8 + Rf - r_in], [0, 0.8 + Rf - r_in]]);
}

// Same idea as rounded_slab in the axolotl: round the top edge of an extrusion
module rounded_slab(h, r) {
    steps = ceil(r / 0.3);
    linear_extrude(foot) offset(delta = -foot) children();
    translate([0, 0, foot]) linear_extrude(h - r - foot + 0.01) children();
    for (i = [0 : steps - 1]) {
        z0 = h - r + r * i / steps;
        z1 = h - r + r * (i + 1) / steps;
        ins = r - sqrt(max(0, r * r - pow(z1 - (h - r), 2)));
        translate([0, 0, z0]) linear_extrude(z1 - z0 + 0.01) offset(r = -ins) children();
    }
}

module heart_2d(s) {
    // s = overall width; hole sits a little below the visual centre
    k = s / 38;
    for (m = [0, 1]) mirror([m, 0])
        hull() { translate([7.5 * k, 6 * k]) circle(10.5 * k); translate([0, -16 * k]) circle(1.5 * k); }
}

module star_2d(s) {
    offset(r = 2) offset(delta = -2)
        polygon([for (i = [0 : 9]) let(t = 90 + i * 36, r = (i % 2 == 0) ? s / 2 : s * 0.3) [r * cos(t), r * sin(t)]]);
}

module nut_outline() {
    if (nut_shape == "heart") heart_2d(38);
    else if (nut_shape == "star") star_2d(40);
    else {
        // round nut with grippy scallops
        difference() {
            circle(16, $fn = 96);
            for (i = [0 : 11]) rotate(i * 30) translate([16.8, 0]) circle(2.2, $fn = 24);
        }
    }
}

// ---------- parts ----------

module shaft() {
    union() {
        rotate_extrude() foot_profile();
        twisted();
        // top stop: 45-degree cone, short collar, then a soft dome
        translate([0, 0, z_top - 0.01]) {
            cylinder(r1 = r_in, r2 = Rcap, h = Rcap - r_in);
            translate([0, 0, Rcap - r_in]) cylinder(r = Rcap, h = 2);
            translate([0, 0, Rcap - r_in + 2]) difference() {
                scale([1, 1, 0.45]) sphere(Rcap);
                translate([0, 0, -Rcap]) cube(2 * Rcap, center = true);
                if (cap_heart)
                    translate([0, 0, Rcap * 0.45 - 0.8]) linear_extrude(2) heart_2d(11);
            }
        }
    }
}

module nut() {
    difference() {
        rounded_slab(nut_h, 2) nut_outline();
        twisted(c);
        // recess around the flared foot, opened up at the first layers
        rotate_extrude() intersection() {
            translate([0, -2]) square([50, 50]);
            union() {
                offset(r = c) foot_profile();
                translate([0, -1]) square([Rf + c + 0.45, 1.45]);
            }
        }
    }
}

color("#F6B8C8") { shaft(); nut(); }
