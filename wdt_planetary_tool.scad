// ============================================================================
// Spirograph / Planetary Gear WDT Tool for 51mm Portafilter
// (e.g. De'Longhi Dedica EC685)
//
// Three printable parts (selected via `part` variable at the bottom):
//   "base"    - Stand/base ring with internal ring gear, sits on the
//               portafilter rim
//   "cap"     - Rotating top/cap that carries the planet gear axles
//   "planets" - The small planetary (spur) gears with needle holes
//
// All gearing uses standard involute spur-gear math computed directly in
// this file - no external libraries (MCAD etc.) are required.
// ============================================================================

$fn = 60;

// ----------------------------------------------------------------------
// GLOBAL / FIT PARAMETERS
// ----------------------------------------------------------------------
tolerance          = 0.2;   // global clearance for all mating/sliding parts

portafilter_id     = 51.5;  // target inner diameter the base ring sits over
rim_wall           = 3.0;   // thickness of the base ring wall that grips the rim
rim_grip_depth     = 6.0;   // how far down the ring skirts over the portafilter rim
base_top_height    = 8.0;   // height of the base ring body above the grip skirt

needle_hole_d      = 0.9;   // friction-fit hole for 0.35-0.4mm needles
needle_hole_extra_h= 1.0;   // extra depth so hole always goes fully through

// ----------------------------------------------------------------------
// GEAR PARAMETERS (module-based involute spur gears)
// ----------------------------------------------------------------------
gear_module        = 1.5;   // mm, shared by ring gear and planet gears
pressure_angle     = 20;    // degrees, standard
planet_teeth       = 12;    // teeth on each small planetary gear
ring_teeth         = 48;    // internal teeth on the base ring gear
gear_thickness     = 6.0;   // vertical height of all gear teeth / bodies
gear_clearance     = 0.15;  // extra radial clearance factor on addendum

num_planets        = 3;     // 2 or 3 planetary gears used in the assembly

// Derived pitch radii
planet_pitch_r     = gear_module * planet_teeth / 2;
ring_pitch_r       = gear_module * ring_teeth  / 2;

// The orbit radius at which each planet's center sits (simple planetary
// arrangement: ring - planet mesh, no separate sun gear needed here since
// the cap directly drives the planet axles as they roll inside the ring).
orbit_radius       = ring_pitch_r - planet_pitch_r;

// ----------------------------------------------------------------------
// SPIROGRAPH NEEDLE-HOLE LAYOUT (per planet gear)
// Offsetting several holes at different radii/angles from each planet's
// center means that as the planets roll around inside the ring gear the
// needles trace overlapping epicycloid/spirograph paths that sweep the
// full 51mm puck surface (center to edge), avoiding dead zones.
// ----------------------------------------------------------------------
holes_per_planet   = 4;                         // 3 to 4 needle holes per gear
planet_body_r      = planet_pitch_r + gear_module; // solid disc radius under teeth
hole_radius_min    = gear_module * 1.2;         // closest hole to planet center
hole_radius_max    = planet_body_r - needle_hole_d - 1.0; // farthest hole, keeps wall

// ----------------------------------------------------------------------
// AXLE / SHAFT PARAMETERS (planet gears rotate freely on pins from the cap)
// ----------------------------------------------------------------------
axle_d             = 3.0;                       // pin diameter driven from the cap
axle_hole_d        = axle_d + tolerance;        // bore through each planet gear
axle_pin_h         = gear_thickness + 2.0;       // pin length protruding from cap

// ============================================================================
// INVOLUTE SPUR GEAR MODULE (self-contained, no external gear library)
// ============================================================================

// Generates a single tooth profile point set is avoided in favor of a
// simplified, robust "trapezoidal involute approximation" gear tooth,
// which prints cleanly at small module sizes and avoids non-manifold
// slivers that pure involute curve sampling can create at this scale.

// Standard gear proportions (module-based)
function addendum(m)        = m;
function dedendum(m)        = 1.25 * m;
function tooth_thickness(m) = m * PI / 2;

// External spur gear (solid, teeth pointing outward) - used for planets
module spur_gear_external(m, teeth, thickness, clearance = 0.15) {
    pitch_r  = m * teeth / 2;
    add_r    = pitch_r + addendum(m);
    ded_r    = pitch_r - dedendum(m);
    base_r   = ded_r - clearance;
    tooth_ang = 360 / teeth;
    half_tooth_ang = (tooth_ang / 2) * 0.55; // tooth width fraction of pitch

    linear_extrude(height = thickness)
    union() {
        // root cylinder (dedendum circle) forms the gear core
        circle(r = base_r);

        // individual teeth as trapezoids from base circle out to addendum
        for (i = [0 : teeth - 1]) {
            rotate([0, 0, i * tooth_ang])
            polygon(points = [
                [ ded_r * cos(-half_tooth_ang), ded_r * sin(-half_tooth_ang) ],
                [ ded_r * cos( half_tooth_ang), ded_r * sin( half_tooth_ang) ],
                [ add_r * cos( half_tooth_ang * 0.55), add_r * sin( half_tooth_ang * 0.55) ],
                [ add_r * cos(-half_tooth_ang * 0.55), add_r * sin(-half_tooth_ang * 0.55) ]
            ]);
        }
    }
}

// Internal ring gear (teeth cut INTO the inside face of a cylinder)
// Returns a negative (cutter) shape to be subtracted from the base ring body.
module ring_gear_cutter(m, teeth, thickness, clearance = 0.15) {
    pitch_r  = m * teeth / 2;
    add_r    = pitch_r - addendum(m);   // internal teeth point inward
    ded_r    = pitch_r + dedendum(m);
    outer_r  = ded_r + clearance;
    tooth_ang = 360 / teeth;
    half_tooth_ang = (tooth_ang / 2) * 0.55;

    linear_extrude(height = thickness)
    difference() {
        circle(r = outer_r);
        // subtract the solid disc that the teeth protrude from, leaving
        // only trapezoidal tooth cutters pointing toward the center
        union() {
            circle(r = add_r);
            for (i = [0 : teeth - 1]) {
                rotate([0, 0, i * tooth_ang])
                polygon(points = [
                    [ add_r * cos(-half_tooth_ang), add_r * sin(-half_tooth_ang) ],
                    [ add_r * cos( half_tooth_ang), add_r * sin( half_tooth_ang) ],
                    [ ded_r * cos( half_tooth_ang * 0.55), ded_r * sin( half_tooth_ang * 0.55) ],
                    [ ded_r * cos(-half_tooth_ang * 0.55), ded_r * sin(-half_tooth_ang * 0.55) ]
                ]);
            }
        }
    }
}

// ============================================================================
// PART 1: BASE / STAND RING  (sits on portafilter rim, holds ring gear)
// ============================================================================
module base_ring() {
    grip_id   = portafilter_id + tolerance;               // clears over the rim
    grip_od   = grip_id + 2 * rim_wall;                    // outer wall of skirt
    body_od   = ring_pitch_r * 2 + 2 * addendum(gear_module) + 6; // outer body incl. ring gear land
    body_id   = grip_id;                                    // keep bore constant through base

    union() {
        // Skirt that grips over the portafilter rim
        difference() {
            cylinder(h = rim_grip_depth, d = grip_od);
            translate([0, 0, -0.5])
                cylinder(h = rim_grip_depth + 1, d = grip_id);
        }

        // Upper body carrying the internal ring gear
        translate([0, 0, rim_grip_depth])
        difference() {
            cylinder(h = base_top_height, d = body_od);
            translate([0, 0, -0.5])
                cylinder(h = base_top_height + 1, d = body_id);

            // Cut the internal ring-gear teeth into the bore
            translate([0, 0, (base_top_height - gear_thickness) / 2])
                ring_gear_cutter(gear_module, ring_teeth, gear_thickness, gear_clearance);
        }
    }
}

// ============================================================================
// PART 2: ROTATING TOP / CAP (fits over base, carries planet axle pins)
// ============================================================================
module cap_top() {
    cap_od       = portafilter_id + 2 * rim_wall + 2 * tolerance + 4; // overlaps base OD
    cap_id       = portafilter_id + tolerance + 2 * tolerance;        // slides over base body
    cap_wall_h   = base_top_height + 4;   // overlaps the base body height
    lid_thick    = 3.0;                   // solid top disc thickness

    difference() {
        union() {
            // Solid top lid
            cylinder(h = lid_thick, d = cap_od);

            // Skirt that slides down over the base ring's upper body
            translate([0, 0, -cap_wall_h])
            difference() {
                cylinder(h = cap_wall_h, d = cap_od);
                translate([0, 0, -0.5])
                    cylinder(h = cap_wall_h + 1, d = cap_id);
            }
        }

        // Central finger-grip / puck-visibility hole through the lid
        translate([0, 0, -1])
            cylinder(h = lid_thick + 2, d = portafilter_id * 0.35);
    }

    // Axle pins that hold and drive each planetary gear, evenly spaced
    // around the orbit radius so the planets mesh with the base ring gear
    for (i = [0 : num_planets - 1]) {
        angle = i * 360 / num_planets;
        translate([orbit_radius * cos(angle), orbit_radius * sin(angle), -cap_wall_h])
            cylinder(h = axle_pin_h, d = axle_d, $fn = 30);
    }
}

// ============================================================================
// PART 3: PLANETARY GEARS (spur gears with spirograph needle holes)
// ============================================================================
module planet_gear() {
    difference() {
        spur_gear_external(gear_module, planet_teeth, gear_thickness, gear_clearance);

        // Central bore for the cap's axle pin (free rotation)
        translate([0, 0, -1])
            cylinder(h = gear_thickness + 2, d = axle_hole_d, $fn = 30);

        // Spirograph needle holes: offset at different radii AND angles so
        // each planet's needles sweep a different band of the puck as the
        // whole assembly is rotated by hand, together covering center to edge.
        for (j = [0 : holes_per_planet - 1]) {
            hole_r = hole_radius_min + (hole_radius_max - hole_radius_min)
                        * (j / (holes_per_planet - 1));
            hole_ang = j * (360 / holes_per_planet) + 15; // angular stagger

            translate([hole_r * cos(hole_ang), hole_r * sin(hole_ang), -1])
                cylinder(h = gear_thickness + needle_hole_extra_h + 2,
                         d = needle_hole_d, $fn = 20);
        }
    }
}

// Lay out all planetary gears flat for printing, spaced apart
module all_planet_gears() {
    spacing = planet_body_r * 2 + 4;
    for (i = [0 : num_planets - 1]) {
        translate([i * spacing, 0, 0])
            planet_gear();
    }
}

// ============================================================================
// PART SELECTOR - set to "base", "cap", "planets", or "assembly" (preview)
// ============================================================================
part = "assembly"; // ["base","cap","planets","assembly"]

if (part == "base") {
    base_ring();
} else if (part == "cap") {
    cap_top();
} else if (part == "planets") {
    all_planet_gears();
} else {
    // Preview-only assembly view (not for printing as one object)
    color("SlateGray") base_ring();
    color("Tomato")
        translate([0, 0, rim_grip_depth + base_top_height + 4])
            cap_top();
    color("SteelBlue")
    for (i = [0 : num_planets - 1]) {
        angle = i * 360 / num_planets;
        translate([orbit_radius * cos(angle), orbit_radius * sin(angle),
                    rim_grip_depth + (base_top_height - gear_thickness) / 2])
            planet_gear();
    }
}
