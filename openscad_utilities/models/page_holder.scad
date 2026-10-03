// Thumb Page Holder — slip it on your thumb and the wings hold the book
// open with one hand. Great for reading in bed, on the train, at the pool.
// Print flat (as rendered).

/* [Fit] */
// Thumb hole diameter (mm). Measure your thumb at the knuckle + 1 mm.
thumb_d = 22;           // [15:0.5:30]
// Wing span (mm)
span = 90;              // [60:1:140]
// Thickness (mm)
thickness = 5;          // [3:0.5:10]

/* [Hidden] */
$fn = 96;
ring = thumb_d + 7;

module shape() {
    offset(r = 1.5) offset(delta = -1.5)
    difference() {
        union() {
            circle(d = ring);
            // two curved wings, each a lens shape that presses the pages down
            for (s = [-1, 1])
                hull() {
                    translate([s * ring / 4, 0]) circle(d = ring * 0.7);
                    translate([s * (span / 2 - 6), -ring * 0.15]) circle(d = 12);
                }
        }
        circle(d = thumb_d);
    }
}

linear_extrude(thickness) shape();
