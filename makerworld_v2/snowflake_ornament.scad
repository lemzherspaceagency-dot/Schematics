// Parametric snowflake ornaments. Flat, ~15-25 min each, no supports. Export a variant with:
//   openscad -D variant=3 -o snowflake_3.stl snowflake_ornament.scad
variant = 1;      // 1..6
R       = 45;     // arm length (mm) -> ~90 mm across
w       = 2.4;    // line width
th      = 2.4;    // thickness
$fn = 32;

// each variant: [ [position along arm, branch length, branch angle], ... ] plus center style
V = [
  [[[0.45,14,60],[0.70,10,60]], 0],
  [[[0.35,18,45],[0.60,14,45],[0.82,8,45]], 1],
  [[[0.55,22,60]], 0],
  [[[0.30,12,60],[0.55,16,60],[0.80,10,60]], 1],
  [[[0.50,20,40],[0.75,12,40]], 0],
  [[[0.40,26,90],[0.70,14,90]], 1],
];

module seg(a, b) { hull() { translate(a) circle(d = w); translate(b) circle(d = w); } }

module arm(br) {
    seg([0, 0], [R, 0]);
    for (b = br) {
        p = b[0] * R;
        for (s = [-1, 1])
            seg([p, 0], [p + b[1] * cos(b[2]) , s * b[1] * sin(b[2])]);
    }
}

module flake(v) {
    union() {
        for (i = [0 : 5]) rotate(i * 60) arm(v[0]);
        if (v[1] == 1) difference() { circle(d = 18); circle(d = 18 - 2 * w); }
        else circle(d = 10);
        // hang loop
        translate([R + 2, 0]) difference() { circle(d = 8); circle(d = 3.4); }
    }
}

linear_extrude(height = th) flake(V[variant - 1]);
