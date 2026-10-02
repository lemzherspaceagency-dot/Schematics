// Print-flat spring bag / cable-bundle clip, one piece, no supports. Lay profile on bed (as modeled).
// Best in PETG or TPU-95A. Spine thickness controls spring force.
L   = 70;   // clip length
H   = 14;   // jaw width (print height)
jaw = 3.2;  // jaw thickness
spine = 1.6;
gap = 1.0;  // closed gap between jaws
$fn = 64;

module profile() {
    // lower jaw
    translate([0, 0]) square([L, jaw]);
    // upper jaw (closed with a small gap)
    translate([0, jaw + gap]) square([L, jaw]);
    // curved spine joining jaws at the left end
    r = (2 * jaw + gap) / 2 + spine;
    translate([0, jaw + gap / 2 + 0]) difference() {
        circle(r = r);
        circle(r = r - spine);
        translate([0, -r]) square([r + 1, 2 * r]);
    }
    // grip teeth on the lower jaw
    for (x = [L * 0.45 : 4 : L - 6])
        translate([x, jaw]) polygon([[0, -0.2], [2, -0.2], [1, 0.8]]);
    // thumb pad on the upper jaw
    translate([L * 0.5, 2 * jaw + gap]) square([L * 0.5, 2]);
}

linear_extrude(height = H) offset(delta = 0.01) profile();
