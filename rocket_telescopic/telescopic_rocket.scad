// =====================================================================
//  TELESCOPIC ROCKET  -  print-in-place, no supports, single printer
//  Target: Bambu Lab A1 mini (180x180x180), 0.4 nozzle, 0.2 layer
//  Collapsed print height ~83 mm  ->  extends to ~170 mm
//  Rocket Revolution Master Challenge (MakerWorld)
// =====================================================================

// ---------- main parameters ----------
H        = 60;    // height of every telescopic tube (mm)
R_o      = 15;    // outer radius of outermost tube (mm)
wall     = 1.6;   // tube wall (4 x 0.4 perimeters)
gap      = 0.30;  // clearance between moving parts (radial)
lip      = 1.2;   // flange / lip protrusion (3 x 0.4 lines)
guide    = 8;     // flange height = lip height (stability when extended)
stages   = 3;     // number of telescopic tubes (2..3 tested)
nose_len = 23;    // ogive nose length (tip half-angle ~42 deg < 45)
bell_h   = 6;     // engine bell height (orange zone)
fin_w    = 16;    // fin span beyond tube
fin_h    = 27;    // fin height (>= fin_w+1 keeps edge < 45 deg)
fin_t    = 2.4;   // fin thickness
n_fins   = 3;
port_z   = 34;    // porthole centre height (blue band 28..40)
port_r   = 5.5;   // porthole boss radius at the wall
n_ports  = 3;

// ---------- build-plate layout ----------
plate_nx = 1;     // rockets along X  (A1 mini: 3x3 = 172 mm fits at pitch 60)
plate_ny = 1;     // rockets along Y
pitch    = 60;

$fn = 96;

// ---------- derived ----------
function R(k)  = R_o - k * (wall + gap + lip);       // outer radius, tube k
function Ri(k) = R(k) - wall;                         // inner radius, tube k
last = stages - 1;

// tangent ogive, x measured from the tip (x=0 tip, x=L base)
function ogive_rho(r, L) = (r*r + L*L) / (2*r);
function ogive_y(x, r, L) = let(p = ogive_rho(r, L))
    sqrt(max(0, p*p - (L-x)*(L-x))) + r - p;

module nose2d(r, L, steps = 40) {
    rb = r - wall;
    pts = concat(
        [[rb, 0], [r, 0]],
        [for (i = [1:steps]) let(x = L - L*i/steps) [ogive_y(x, r, L), L*i/steps]],
        [[0, L], [0, rb]]
    );
    polygon(pts);
}

// 2D profile (r,z) of telescopic tube k
module tube2d(k) {
    r = R(k); ri = Ri(k);
    union() {
        translate([ri, 0]) square([wall, H]);                         // wall
        if (k > 0)                                                    // bottom flange (on bed, no overhang)
            translate([r, 0]) square([lip, guide]);
        if (k < last)                                                 // top lip, 45 deg underside
            polygon([[ri, H-guide], [ri-lip, H-guide+lip],
                     [ri-lip, H],   [ri, H]]);
        if (k == 0)                                                   // engine bell (orange), 45 deg
            polygon([[r-0.01, 0], [r+bell_h, 0], [r-0.01, bell_h]]);
        if (k == last)                                                // nose cone with 45 deg inner roof
            translate([0, H]) nose2d(r, nose_len);
    }
}

module tube(k) { rotate_extrude() tube2d(k); }

// fins: base on the bed, outer edge leans in at < 45 deg
module fins() {
    for (i = [0:n_fins-1]) rotate([0, 0, i*360/n_fins])
        rotate([90, 0, 0]) translate([0, 0, -fin_t/2])
            linear_extrude(fin_t)
                polygon([[R_o-1, 0], [R_o+fin_w, 0], [R_o-1, fin_h]]);
}

// portholes: truncated cones, 45 deg chamfer
module portholes() {
    for (i = [0:n_ports-1]) rotate([0, 0, i*360/n_ports + 60])
        translate([R_o-0.8, 0, port_z]) rotate([0, 90, 0])
            cylinder(r1 = port_r, r2 = port_r - 1.0, h = 1.8);
}

module rocket() {
    for (k = [0:last]) tube(k);
    fins();
    portholes();
}

// ---------- output ----------
for (i = [0:plate_nx-1], j = [0:plate_ny-1])
    translate([(i-(plate_nx-1)/2)*pitch, (j-(plate_ny-1)/2)*pitch, 0]) rocket();
