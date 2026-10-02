// Desk-edge / shelf-edge glasses holder. Clamps over a tabletop; a cradle holds glasses by the bridge/temples.
// Print on its SIDE (profile flat on the bed), no supports. PETG recommended.
desk_t = 25;     // tabletop/shelf thickness it clamps onto (adjust!)
w      = 32;     // width (print height)
t      = 4;      // wall
clamp_d = 38;    // how far the clamp reaches over the desk
arm    = 52;     // cradle arm length out from the desk edge
$fn = 64;

module profile() {
    // outer clamp "C": back wall, top, bottom (lower jaw longer)
    translate([0, 0]) square([t, desk_t + 2 * t]);                        // back wall at desk edge
    translate([0, desk_t + t]) square([clamp_d, t]);                      // top jaw (on desk surface)
    translate([0, 0]) square([clamp_d - 6, t]);                          // bottom jaw (under desk), shorter
    // grip bump on the lower jaw
    translate([clamp_d - 16, t]) polygon([[0, 0], [8, 0], [4, 1.2]]);
    // cradle arm projecting out from the bottom of the back wall (away from desk)
    hull() { translate([0, 0]) square([0.01, t]); translate([-arm, 0]) circle(d = t); }
    // upturned cradle: two prongs forming a V that holds the glasses bridge
    hull() { translate([-arm, 0]) circle(d = t); translate([-arm, 26]) circle(d = t); }
    hull() { translate([-arm + 18, 0]) circle(d = t); translate([-arm + 18, 14]) circle(d = t); }
    // gusset under the arm for strength
    polygon([[0, t], [-14, t], [0, 18]]);
}

linear_extrude(height = w) offset(delta = 0.01) profile();
