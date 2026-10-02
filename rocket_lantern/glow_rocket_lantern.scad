// =====================================================================
//  GLOW ROCKET LANTERN  -  single colour (milky/translucent), print-in-place
//  Bambu Lab A1 mini, 0.4 nozzle, 0.2 layer. NO supports, NO colour swaps.
//  A rotating print-in-place shutter sleeve opens / closes the portholes.
//  Sits over a 38 mm LED tealight. Total height ~128 mm.
// =====================================================================

// ---------- parameters ----------
R_c      = 22;     // core outer radius (bore fits a 38 mm tealight)
wall_c   = 1.2;    // core wall (3 perimeters -> glows nicely)
gap      = 0.30;   // radial clearance sleeve <-> core
vg       = 0.40;   // vertical clearance (2 layers @0.2)
ws       = 1.2;    // sleeve wall
sleeve_h = 50;     // sleeve height
bell_h   = 8;      // engine bell height (45 deg)
nose_len = 66;     // ogive length (tip half-angle ~41 deg)
n_holes  = 6;      // portholes (core and sleeve)
hole_r   = 7.5;    // teardrop radius (45 deg roof, no supports)
sleeve_rot = 30;   // 30 = shutter CLOSED as printed, 0 = open
fin_w    = 14;     // fin span beyond the bell ledge
fin_h    = 26;     // fin height (edge angle < 45 deg)
fin_t    = 3;
n_fins   = 3;
$fn = 120;

// ---------- derived ----------
R_so = R_c + gap + ws;        // sleeve outer radius
R_N  = R_so + 1.5;            // nose base radius (retains sleeve)
R_L  = R_so + 2;              // bell ledge radius
r_b  = R_c - wall_c;          // bore radius
z_sl = bell_h + vg;           // sleeve bottom
z_st = z_sl + sleeve_h;       // sleeve top
z_s0 = z_st + vg;             // nose shoulder starts
z_s1 = z_s0 + (R_N - R_c);    // shoulder ends / ogive base (45 deg)
zmid = z_sl + sleeve_h/2;

function rho(r, L) = (r*r + L*L) / (2*r);
function oy(x, r, L) = sqrt(max(0, pow(rho(r,L),2) - pow(L-x,2))) + r - rho(r,L);

// solid outline of core+nose above the bell (r,z)
module solid2d(steps = 50) {
    polygon(concat(
        [[0, bell_h], [R_c, bell_h], [R_c, z_s0], [R_N, z_s1]],
        [for (i = [1:steps]) let(x = nose_len - nose_len*i/steps)
            [oy(x, R_N, nose_len), z_s1 + nose_len*i/steps]],
        [[0, z_s1 + nose_len]]));
}

module core2d() {
    difference() {
        union() {
            solid2d();
            // engine bell: flat ledge, 45 deg flare down to the bed
            polygon([[r_b, 0], [R_L + bell_h, 0], [R_L, bell_h], [r_b, bell_h]]);
        }
        union() {   // constant-wall cavity, 45 deg roof, open at the bottom
            offset(delta = -wall_c) solid2d();
            square([r_b, bell_h + wall_c + 1]);
        }
    }
}

module sleeve2d() { translate([R_c + gap, z_sl]) square([ws, sleeve_h]); }

// teardrop hole cutter: tip up at 45 deg, extruded radially from x0 to x1
module hole(x0, x1, ang) {
    rotate([0, 0, ang]) translate([x0, 0, zmid]) rotate([90, 0, 90])
        linear_extrude(x1 - x0)
            hull() { circle(r = hole_r, $fn = 48); translate([0, hole_r*sqrt(2)]) square(0.01, center = true); }
}

module core() {
    difference() {
        rotate_extrude() core2d();
        for (i = [0:n_holes-1]) hole(r_b - 1, R_c + 0.1, i*360/n_holes);
    }
}

module sleeve() {
    rotate([0, 0, sleeve_rot]) difference() {
        rotate_extrude() sleeve2d();
        for (i = [0:n_holes-1]) hole(R_c + gap - 0.1, R_so + 0.1, i*360/n_holes);
    }
}

module fins() {
    x0 = R_so + 1.3;    // hug the sleeve, never touch it
    for (i = [0:n_fins-1]) rotate([0, 0, i*360/n_fins + 30])
        rotate([90, 0, 0]) translate([0, 0, -fin_t/2]) linear_extrude(fin_t)
            polygon([[x0, 0], [R_L + fin_w, 0], [x0, fin_h]]);
}

core(); sleeve(); fins();
