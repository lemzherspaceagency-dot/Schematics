// Cord Winder — wrap earbuds, charging cables or extension leads
// so they don't tangle. Tuck the plug into the slit at one end.
// Print flat (as rendered). Print two or three at different lengths.

/* [Size] */
// Overall length (mm)
length = 70;            // [40:1:200]
// Width of the end tabs (mm)
width = 34;             // [20:1:80]
// Width of the middle where the cable wraps (mm)
waist = 16;             // [8:1:60]
// Thickness (mm)
thickness = 3;          // [2:0.5:6]
// Width of the slit that holds the cable end (mm)
slit = 2.2;             // [1:0.1:5]

/* [Hidden] */
$fn = 48;
tab = 12;   // height of each end tab

module shape() {
    offset(r = 2) offset(delta = -2)
    difference() {
        union() {
            translate([-width / 2, 0]) square([width, tab]);
            translate([-width / 2, length - tab]) square([width, tab]);
            translate([-waist / 2, 0]) square([waist, length]);
        }
        // slit + keyhole to lock the cable end
        translate([width / 2 - 8, tab / 2 - slit / 2]) square([10, slit]);
        translate([width / 2 - 8, tab / 2]) circle(d = slit * 1.8);
    }
}

linear_extrude(thickness) shape();
