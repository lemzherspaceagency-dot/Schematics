// Original print-in-place "spinning spider" wand. Print upright as modeled, NO supports:
// the spider stands on its own leg tips, hub floats 0.4 mm around the pin. After printing, snap the hub free by spinning it.
// Hold the wand tip-down: the spider hangs on the pin and spins freely.
leg_n   = 8;
hub_r   = 7;       // leg start radius at hub bottom
knee_r  = 30;      // knee radius on the bed
tip_r   = 44;
leg_d   = 3.6;
zk      = 3.0;     // knee height above bed (leg lies near bed at the tip)
zh      = zk + (knee_r - hub_r);   // 45-degree legs: hub bottom height
hub_h   = 9;
dome_h  = 3.5;
pin_d   = 6;  hole_d = 6.8;  gap = 0.4;
head_d  = 13;
handle_d = 12; handle_top = 150;
$fn = 48;

module leg() {
    hull() { translate([hub_r, 0, zh]) sphere(d = leg_d); translate([knee_r, 0, zk]) sphere(d = leg_d); }
    hull() { translate([knee_r, 0, zk]) sphere(d = leg_d); translate([tip_r, 0, leg_d / 2]) sphere(d = leg_d); }
}

module spider() {
    difference() {
        union() {
            // hub: 45-degree chamfered underside, domed top (body)
            translate([0, 0, zh]) cylinder(r1 = hub_r, r2 = hub_r + 4, h = 4);
            translate([0, 0, zh + 4]) cylinder(r = hub_r + 4, h = hub_h - 4 - 0.01);
            translate([0, 0, zh + hub_h - 0.01]) cylinder(r1 = hub_r + 4, r2 = hub_r - 1, h = dome_h);
            for (i = [0 : leg_n - 1]) rotate(i * 360 / leg_n) leg();
        }
        translate([0, 0, zh - 1]) cylinder(d = hole_d, h = hub_h + 10);
        // two eyes
        for (s = [-1, 1]) translate([s * 3, hub_r + 3, zh + hub_h]) sphere(d = 2.6);
    }
}

module wand() {
    // foot cone (45-degree), pin, head cone, handle
    cylinder(d1 = 12, d2 = pin_d, h = 3);
    cylinder(d = pin_d, h = zh + hub_h + dome_h + gap + 1);
    translate([0, 0, zh + hub_h + dome_h + gap]) cylinder(d1 = pin_d, d2 = head_d, h = (head_d - pin_d) / 2);
    translate([0, 0, zh + hub_h + dome_h + gap + (head_d - pin_d) / 2 - 0.01]) cylinder(d = head_d, h = 2);
    top0 = zh + hub_h + dome_h + gap + (head_d - pin_d) / 2 + 2;
    translate([0, 0, top0 - 0.01]) cylinder(d1 = head_d, d2 = handle_d, h = 1.5);
    translate([0, 0, top0 + 1.5 - 0.02]) cylinder(d = handle_d, h = handle_top - top0 - 1.5);
    // grip rings
    for (z = [top0 + 20 : 12 : handle_top - 18]) translate([0, 0, z]) cylinder(d = handle_d + 2.4, h = 2.4);
    // tip finial
    translate([0, 0, handle_top - 0.02]) cylinder(d1 = handle_d, d2 = 3, h = 14);
}

spider();
wand();
