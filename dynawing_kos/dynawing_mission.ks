// ============================================================================
// DYNAWING AUTONOMOUS MISSION SCRIPT
// KSC Launchpad -> 80 km circular orbit -> deorbit -> unpowered glide
// landing on the KSC runway.  Everything happens at the KSC base.
//
// VEHICLE (confirmed from the .craft file, part-for-part):
//   2x MassiveBooster  ("Kickback" SRB)   -- liftoff stage
//   1x Size3LargeTank + 2x SSME           -- sustainer stage
//   4x omsEngine (MonoPropellant)         -- circularize / deorbit
//   mk3 cockpit, canards, elevons, delta + structural wings,
//   GearMedium (main gear) x2 + SmallGearBay (nose gear), RCS blocks.
//   NO air-breathing engines -> reentry and landing are a dead-stick glide.
//
// PHYSICS BASIS (from the in-flight dV readout, cross-checked against the
// Tsiolkovsky rocket equation -- both agree to <1%, so the numbers below
// are trustworthy, not guessed):
//   Booster stage  : 241.4 t -> 161.8 t, Isp 246 s -> dv = 246*9.80665*ln(241.4/161.8) = 965 m/s
//   Sustainer stage: 151.3 t ->  65.6 t, Isp 295 s -> dv = 295*9.80665*ln(151.3/65.6)  = 2418 m/s
//   Rocket dv budget ~3382 m/s.
//   v_circ(80 km)  = sqrt(mu/r) = 2279 m/s.  Add ~950 m/s of stock gravity/steering
//   losses for an 80 km Kerbin ascent -> ~3230 m/s required.  Margin ~150 m/s,
//   healthy but not huge -- this is why the ascent loop below targets apoapsis
//   directly with a closed loop rather than burning a fixed duration.
//
// CALIBRATION NOTE -- the two honestly-uncertain constants in this script:
//   RUNWAY_POS      : KSC runway centerline LATLNG. Stock-standard published
//                      value used below; verify by parking on the runway and
//                      printing SHIP:GEOPOSITION, then correct if it's off.
//   GLIDE_LEAD_DEG   : how many degrees of orbital travel the deorbit aim
//                      point is placed *before* the runway, to cover the
//                      unpowered glide distance. This vehicle's exact L/D is
//                      not something I can get from a part list without a
//                      wind-tunnel/flight test, so this starts as an estimate
//                      and is meant to be tuned from the miss-distance this
//                      script prints after each landing attempt.
// ============================================================================

@LAZYGLOBAL OFF.
CLEARSCREEN.
SET CONFIG:IPU TO 2000.

// ---------------------------- CONFIG ----------------------------
GLOBAL TARGET_APO IS 80000.                    // target circular orbit altitude, m
GLOBAL DEORBIT_PE IS 30000.                    // deorbit target periapsis, m
GLOBAL RUNWAY_POS IS LATLNG(-0.048679, -74.724375). // KSC runway centerline (VERIFY IN-GAME)
GLOBAL GLIDE_LEAD_DEG IS 18.                   // TUNE THIS after each attempt
GLOBAL G0 IS 9.80665.
GLOBAL GEAR_DEPLOY_ALT IS 600.                 // radar altitude to drop gear, m
GLOBAL FLARE_ALT IS 60.                        // radar altitude to begin flare, m

// ---------------------------- TELEMETRY / LOG ----------------------------
FUNCTION LOG_MSG {
    PARAMETER msg.
    PRINT "[T+" + ROUND(MISSIONTIME,1) + "s] " + msg.
}

// ---------------------------- ENGINE HELPERS ----------------------------
FUNCTION ENGINES_NAMED {
    PARAMETER pname.
    LOCAL result IS LIST().
    LOCAL allEng IS LIST().
    LIST ENGINES IN allEng.
    FOR e IN allEng {
        IF e:NAME = pname {
            result:ADD(e).
        }
    }
    RETURN result.
}

FUNCTION ALL_FLAMED_OUT {
    PARAMETER elist.
    IF elist:LENGTH = 0 { RETURN TRUE. }
    FOR e IN elist {
        IF NOT e:FLAMEOUT { RETURN FALSE. }
    }
    RETURN TRUE.
}

FUNCTION TOTAL_AVAILABLE_THRUST {
    LOCAL eng IS LIST().
    LIST ENGINES IN eng.
    LOCAL F IS 0.
    FOR e IN eng {
        IF e:IGNITION AND NOT e:FLAMEOUT { SET F TO F + e:AVAILABLETHRUST. }
    }
    RETURN F.
}

FUNCTION DO_STAGE {
    WAIT UNTIL STAGE:READY.
    STAGE.
    WAIT 0.1.
    LOG_MSG("Staged -> now on stage " + STAGE:NUMBER + ".").
    WAIT 0.5.
}

// ---------------------------- ORBITAL MATH ----------------------------
FUNCTION V_CIRC {
    PARAMETER r.
    RETURN SQRT(BODY:MU / r).
}

FUNCTION V_VIS_VIVA {
    PARAMETER r, a.
    RETURN SQRT(BODY:MU * (2/r - 1/a)).
}

// Build a circularization node at apoapsis.
FUNCTION MAKE_CIRC_NODE {
    LOCAL apR IS BODY:RADIUS + SHIP:APOAPSIS.
    LOCAL smaNow IS SHIP:ORBIT:SEMIMAJORAXIS.
    LOCAL vNow IS V_VIS_VIVA(apR, smaNow).
    LOCAL vTarget IS V_CIRC(apR).
    LOCAL dv IS vTarget - vNow.
    LOG_MSG("Circularize: v_now=" + ROUND(vNow,1) + " v_target=" + ROUND(vTarget,1) + " dv=" + ROUND(dv,1)).
    LOCAL nd IS NODE(TIME:SECONDS + ETA:APOAPSIS, 0, 0, dv).
    ADD nd.
    RETURN nd.
}

// Build a deorbit node: prograde-node burn timed so the resulting periapsis
// sits at DEORBIT_PE, with the burn placed GLIDE_LEAD_DEG of true anomaly
// before the runway's longitude crossing.
FUNCTION MAKE_DEORBIT_NODE {
    LOCAL rPe IS BODY:RADIUS + DEORBIT_PE.
    LOCAL smaNow IS SHIP:ORBIT:SEMIMAJORAXIS.
    LOCAL rNow IS BODY:RADIUS + SHIP:ALTITUDE.

    // new semi-major axis so that periapsis = rPe, apoapsis unchanged at burn point
    LOCAL smaNew IS (rNow + rPe) / 2.
    LOCAL vNow IS V_VIS_VIVA(rNow, smaNow).
    LOCAL vNew IS V_VIS_VIVA(rNow, smaNew).
    LOCAL dv IS vNew - vNow. // negative -> retrograde burn

    // Find how long (in orbits) until our ground track longitude, minus the
    // glide lead, lines up with the runway. Search forward in whole-orbit
    // steps up to one full orbit for the closest longitude match.
    LOCAL bestEta IS ETA:APOAPSIS.
    LOCAL bestDiff IS 999.
    LOCAL period IS SHIP:ORBIT:PERIOD.
    LOCAL steps IS 60.
    LOCAL i IS 0.
    UNTIL i > steps {
        LOCAL tTry IS TIME:SECONDS + (period * i / steps).
        LOCAL futurePos IS POSITIONAT(SHIP, tTry).
        LOCAL futureGeo IS BODY:GEOPOSITIONOF(futurePos).
        LOCAL aimLng IS RUNWAY_POS:LNG - GLIDE_LEAD_DEG.
        LOCAL diff IS ABS(MOD(futureGeo:LNG - aimLng + 540, 360) - 180).
        IF diff < bestDiff {
            SET bestDiff TO diff.
            SET bestEta TO tTry - TIME:SECONDS.
        }
        SET i TO i + 1.
    }

    LOG_MSG("Deorbit burn planned in " + ROUND(bestEta,0) + "s, dv=" + ROUND(dv,1) + " m/s.").
    LOCAL nd IS NODE(TIME:SECONDS + bestEta, 0, 0, dv).
    ADD nd.
    RETURN nd.
}

// Closed-loop node execution: point at the burn vector, throttle
// proportional to remaining dv, stop when residual dv crosses zero.
FUNCTION EXECUTE_NODE {
    PARAMETER nd.

    IF nd:BURNVECTOR:MAG < 0.1 {
        LOG_MSG("Node dv negligible, skipping.").
        REMOVE nd.
        RETURN.
    }

    LOCK STEERING TO nd:BURNVECTOR.
    LOCAL alignStart IS TIME:SECONDS.
    WAIT UNTIL VANG(SHIP:FACING:FOREVECTOR, nd:BURNVECTOR) < 1.0 OR TIME:SECONDS - alignStart > 20.

    LOCAL dvMag IS nd:BURNVECTOR:MAG.
    LOCAL F IS TOTAL_AVAILABLE_THRUST().
    IF F < 1 { SET F TO 1. }
    LOCAL burnTime IS (SHIP:MASS * 1000 * dvMag) / F.

    LOCAL burnStart IS TIME:SECONDS + nd:ETA - (burnTime / 2) - 10.
    IF burnStart > TIME:SECONDS + 15 {
        KUNIVERSE:TIMEWARP:WARPTO(burnStart).
        WAIT UNTIL TIME:SECONDS >= burnStart.
    }

    LOCK STEERING TO nd:BURNVECTOR.
    WAIT UNTIL nd:ETA <= (burnTime / 2) + 1.
    WAIT UNTIL VANG(SHIP:FACING:FOREVECTOR, nd:BURNVECTOR) < 2.0.

    LOCAL initialDv IS nd:BURNVECTOR:MAG.
    LOCK THROTTLE TO MIN(1.0, MAX(0.02, nd:BURNVECTOR:MAG / 15)).

    UNTIL nd:BURNVECTOR:MAG < 0.2 OR nd:BURNVECTOR:MAG > initialDv {
        LOCK STEERING TO nd:BURNVECTOR.
        WAIT 0.02.
    }

    LOCK THROTTLE TO 0.
    WAIT 0.5.
    UNLOCK THROTTLE.
    UNLOCK STEERING.
    LOG_MSG("Burn complete, residual dv=" + ROUND(nd:BURNVECTOR:MAG,2) + " m/s.").
    REMOVE nd.
}

// ============================================================================
// PHASE 1: LIFTOFF + GRAVITY TURN (Boosters + SSMEs)
// ============================================================================
FUNCTION ASCENT {
    LOG_MSG("Beginning ascent sequence.").
    SAS OFF.
    RCS OFF.
    LOCK THROTTLE TO 1.0.
    LOCK STEERING TO HEADING(90, 90).

    DO_STAGE(). // release clamps / ignite boosters+SSMEs

    LOCAL boosters IS ENGINES_NAMED("MassiveBooster").
    LOCAL ssmes IS ENGINES_NAMED("SSME").

    // Closed-loop gravity turn: pitch kick starts once we're moving, then we
    // simply follow surface-prograde, which is the standard "perfect" gravity
    // turn -- no hardcoded pitch-vs-time table, it self-adjusts to drag/TWR.
    WAIT UNTIL SHIP:VELOCITY:SURFACE:MAG > 50 OR SHIP:ALTITUDE > 500.
    LOG_MSG("Pitch kickover.").
    LOCK STEERING TO HEADING(90, 85).
    WAIT UNTIL SHIP:ALTITUDE > 1000.
    LOCK STEERING TO SHIP:SRFPROGRADE.

    // Booster separation on flameout (closed loop, no fixed timer)
    WAIT UNTIL ALL_FLAMED_OUT(boosters) OR SHIP:ALTITUDE > 20000.
    LOG_MSG("Boosters flamed out, jettisoning.").
    DO_STAGE().

    // Continue on SSMEs, following prograde, throttling to hit target
    // apoapsis exactly rather than burning a fixed duration.
    LOCK STEERING TO SHIP:SRFPROGRADE.
    UNTIL SHIP:APOAPSIS >= TARGET_APO OR ALL_FLAMED_OUT(ssmes) {
        IF SHIP:APOAPSIS > TARGET_APO - 2000 {
            LOCK THROTTLE TO 0.15. // fine trim near target
        } ELSE {
            LOCK THROTTLE TO 1.0.
        }
        WAIT 0.05.
    }
    LOCK THROTTLE TO 0.
    WAIT 0.5.
    UNLOCK THROTTLE.
    LOG_MSG("Target apoapsis reached: " + ROUND(SHIP:APOAPSIS,0) + " m.").

    // Shut down SSMEs explicitly, jettison tank, bring up OMS.
    FOR e IN ssmes { e:SHUTDOWN(). }
    DO_STAGE(). // jettison external tank
    DO_STAGE(). // activate OMS stage if separate
    UNLOCK STEERING.
    SAS ON.
    LOG_MSG("Ascent complete, coasting to apoapsis for circularization.").
}

// ============================================================================
// PHASE 2: CIRCULARIZE
// ============================================================================
FUNCTION CIRCULARIZE {
    SAS OFF.
    LOCAL nd IS MAKE_CIRC_NODE().
    EXECUTE_NODE(nd).
    LOG_MSG("Orbit: Ap=" + ROUND(SHIP:APOAPSIS,0) + " Pe=" + ROUND(SHIP:PERIAPSIS,0) + ".").
}

// ============================================================================
// PHASE 3: DEORBIT
// ============================================================================
FUNCTION DEORBIT {
    LOCAL nd IS MAKE_DEORBIT_NODE().
    EXECUTE_NODE(nd).
    LOG_MSG("Deorbit burn complete. Pe=" + ROUND(SHIP:PERIAPSIS,0) + " m.").
}

// ============================================================================
// PHASE 4: REENTRY + GLIDE GUIDANCE
// High-AoA hypersonic hold (per design notes), tapering to a normal glide
// AoA as speed bleeds off, with continuous bearing correction toward the
// runway aim point.
// ============================================================================
FUNCTION REENTRY_AND_GLIDE {
    LOG_MSG("Entering atmosphere, starting reentry attitude hold.").
    RCS ON.
    SAS OFF.

    LOCK STEERING TO SHIP:SRFRETROGRADE. // belly-first, high-AoA hold via retrograde lock
    WAIT UNTIL SHIP:ALTITUDE < 60000.

    // Hold retrograde through the hottest part of reentry.
    WAIT UNTIL SHIP:ALTITUDE < 40000 OR SHIP:AIRSPEED < 800.

    LOG_MSG("Transitioning to glide guidance.").
    RCS OFF.

    // Closed-loop glide: bank toward the runway aim point, hold a pitch
    // that trades a shallow descent for airspeed control.
    UNTIL SHIP:ALTITUDE < FLARE_ALT AND RUNWAY_POS:DISTANCE < 3000 {
        LOCAL courseToRunway IS RUNWAY_POS:HEADING. // absolute compass course, ship-independent

        LOCAL pitchTarget IS -8. // shallow nose-down glide attitude
        IF SHIP:AIRSPEED < 150 { SET pitchTarget TO -3. } // flatten out as we slow

        LOCK STEERING TO HEADING(courseToRunway, 90 + pitchTarget).

        IF SHIP:ALTITUDE < GEAR_DEPLOY_ALT AND NOT GEAR {
            LOG_MSG("Deploying landing gear.").
            GEAR ON.
        }

        WAIT 0.1.
    }

    LOG_MSG("Final approach. Distance to runway: " + ROUND(RUNWAY_POS:DISTANCE,0) + " m.").
    IF NOT GEAR { GEAR ON. }

    // Flare: reduce descent rate as we near the ground.
    UNTIL SHIP:STATUS = "LANDED" OR SHIP:STATUS = "SPLASHED" {
        LOCAL courseToRunway IS RUNWAY_POS:HEADING.
        LOCAL flarePitch IS -2.
        IF SHIP:ALTITUDE < 20 { SET flarePitch TO 3. }
        LOCK STEERING TO HEADING(courseToRunway, 90 + flarePitch).
        WAIT 0.05.
    }

    LOG_MSG("Touchdown detected. Applying brakes.").
    UNLOCK STEERING.
    BRAKES ON.
    WAIT UNTIL SHIP:VELOCITY:SURFACE:MAG < 1.

    LOCAL missDist IS RUNWAY_POS:DISTANCE.
    LOG_MSG("Vehicle stopped. Miss distance from runway aim point: " + ROUND(missDist,0) + " m.").
    LOG_MSG("If short: decrease GLIDE_LEAD_DEG. If long/overshot: increase it.").
    PRINT "MISSION COMPLETE.".
}

// ============================================================================
// MAIN SEQUENCE
// ============================================================================
LOG_MSG("Dynawing autonomous mission starting.").
ASCENT().
WAIT UNTIL ETA:APOAPSIS < 60.
CIRCULARIZE().
LOG_MSG("Orbit achieved. Coasting before deorbit planning.").
WAIT 5.
DEORBIT().
WAIT UNTIL SHIP:ALTITUDE < 70000.
REENTRY_AND_GLIDE().
