// Table Corner Protector — soft, rounded cap for sharp table corners.
// Protects toddlers' heads and shins. Print in TPU for a soft bumper
// (PLA/PETG still rounds the corner but is hard). Print 4.
// Slip it on; a dab of double-sided tape or silicone keeps it put.

/* [Table] */
// Table top thickness (mm) + ~0.5 for TPU, +1 for rigid plastic
table_t = 19;           // [5:0.5:60]

/* [Protector] */
// How far it covers along each edge (mm)
reach = 25;             // [12:1:60]
// Padding thickness (mm)
pad = 5;                // [2:0.5:15]

/* [Hidden] */
$fn = 48;
R = pad + 2;

difference() {
    // rounded on the outer corner, cut square where it ends along the edges
    intersection() {
        hull()
            for (x = [-pad + R, reach + R], y = [-pad + R, reach + R],
                 z = [-pad + R, table_t + pad - R])
                translate([x, y, z]) sphere(r = R);
        translate([-pad - 1, -pad - 1, -pad - 1])
            cube([reach + pad + 1, reach + pad + 1, table_t + 2 * pad + 2]);
    }
    // the table
    cube([reach + 10, reach + 10, table_t]);
}
