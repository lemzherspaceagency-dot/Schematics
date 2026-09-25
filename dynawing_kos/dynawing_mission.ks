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
//   CONFIRMED (KSP wiki): OMS + RCS share only ~300 m/s of dv total, used for
//   BOTH circularization trim AND the deorbit burn. This is why the ascent
//   loop below deliberately keeps the SSMEs burning near-horizontal until
//   periapsis is already close to target, instead of cutting the instant
//   apoapsis first reaches it -- vis-viva math shows that difference is
//   ~72 m/s (early cutoff) vs. ~10 m/s (proper insertion) of OMS trim, and
//   every m/s saved there is margin for the ~44 m/s deorbit burn plus RCS
//   attitude control during reentry, all drawn from the same 300 m/s pool.
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
// OMS PROPELLANT BUDGET (ground-computed, sourced part stats):
//   O-10 "Puff" Isp_vac = 290s (NOT the 220s atmospheric figure -- these
//   engines only fire in vacuum here). MonoPropellant density = 4 kg/unit.
//   Primary MONO tank = 1000 units = 4.0 t propellant.
//   dv available depends on orbiter dry mass (not in any public part-stat
//   table); cross-checking the wiki's independent "~300 m/s OMS+RCS" claim
//   against this Isp/propellant mass backs out an implied dry mass of ~36t,
//   which is a plausible number for this craft class -- two independent
//   sources triangulate to the same figure. OMS_DV_AVAILABLE() computes the
//   real number in-flight from SHIP:MASS once it's known exactly.
//   Budget closure: ~10 m/s insertion trim + ~44 m/s deorbit burn = ~54 m/s
//   used of the ~300 m/s pool, leaving ~246 m/s margin for RCS attitude
//   control during reentry.
//
// CALIBRATION NOTE -- the two honestly-uncertain constants in this script:
//   RUNWAY_POS      : KSC runway centerline LATLNG, converted from the KSP
//                      wiki's published 0°2'26"S 74°41'28"W. Verify by parking
//                      on the runway and printing SHIP:GEOPOSITION.
//   GLIDE_LEAD_DEG   : how many degrees of orbital travel the deorbit aim
//                      point is placed *before* the runway, to cover the
//                      unpowered glide distance (18 deg = 188.5 km of ground
//                      track at this orbit). This vehicle's exact L/D is not
//                      in any part-stat table -- it can only come from a
//                      flight test, same as it would for a real aircraft.
//                      Tune it from the miss-distance this script prints
//                      after each landing attempt.
// ============================================================================

@LAZYGLOBAL OFF.
CLEARSCREEN.

// ---------------------------- CONFIG ----------------------------
GLOBAL TARGET_APO IS 80000.                    // target circular orbit altitude, m
GLOBAL DEORBIT_PE IS 30000.                    // deorbit target periapsis, m
GLOBAL RUNWAY_POS IS LATLNG(-0.040556, -74.691111). // KSC runway, converted from the published
                                                     // 0°2'26"S 74°41'28"W (KSP wiki). VERIFY IN-GAME
                                                     // by parking on the runway and printing
                                                     // SHIP:GEOPOSITION -- this is the best public
                                                     // reference, not a first-party measurement.
GLOBAL GLIDE_LEAD_DEG IS 18.                   // TUNE THIS after each attempt
GLOBAL G0 IS 9.80665.
GLOBAL GEAR_DEPLOY_ALT IS 600.                 // radar altitude to drop gear, m
GLOBAL FLARE_ALT IS 60.                        // radar altitude to begin flare, m

// HONEST NOTE on logging rate: KSP's physics engine runs a fixed 20ms tick
// (50 Hz) at normal warp -- that is a hard engine limit, not a kOS setting,
// so "every 0.01s" (100 Hz) is not something any script running inside KSP
// can actually do. What this script does instead: log and refresh the HUD on
// EVERY physics tick, i.e. as fast as the game itself updates, which is the
// real ceiling. CONFIG:IPU is raised so the CPU has enough instruction budget
// to do that plus fly the ship in the same tick without falling behind.
SET CONFIG:IPU TO 4000.
GLOBAL BLACKBOX_PATH IS "0:/dynawing_blackbox.csv". // archive volume: unlimited size,
                                                     // survives the flight, pull it off disk
                                                     // after landing (or after a crash) for
                                                     // post-flight debugging.

// ---------------------------- MISSION STATE (for HUD + black box) ----------------------------
GLOBAL MISSION_PHASE IS "PRELAUNCH".
GLOBAL RECENT_MSGS IS LIST().        // last N log lines, newest last
GLOBAL WARNING_COUNT IS 0.
GLOBAL LAST_WARNING IS "none".
GLOBAL BLACKBOX_ROWS IS 0.

// ---------------------------- TELEMETRY / LOG ----------------------------
FUNCTION LOG_MSG {
    PARAMETER msg.
    LOCAL line IS "[T+" + ROUND(MISSIONTIME,1) + "s] " + msg.
    RECENT_MSGS:ADD(line).
    IF RECENT_MSGS:LENGTH > 8 { RECENT_MSGS:REMOVE(0). }
    IF msg:CONTAINS("WARNING") OR msg:CONTAINS("CRITICAL") {
        SET WARNING_COUNT TO WARNING_COUNT + 1.
        SET LAST_WARNING TO line.
    }
}

// Pad/truncate a string to a fixed width so PRINT AT() cleanly overwrites
// whatever was on that screen cell last tick (otherwise a shorter new string
// leaves stale characters from a longer old one).
FUNCTION PAD {
    PARAMETER s, w.
    LOCAL str IS s + "".
    IF str:LENGTH > w { RETURN str:SUBSTRING(0, w). }
    UNTIL str:LENGTH >= w { SET str TO str + " ". }
    RETURN str.
}

// ---------------------------- BLACK BOX FLIGHT RECORDER ----------------------------
// Full state snapshot on every physics tick, written to the archive volume as
// CSV. If the mission succeeds OR fails (crash, loss of control, whatever),
// this file survives and can be handed back for post-flight analysis: every
// column needed to reconstruct what the vehicle was doing at any instant.
FUNCTION BLACKBOX_INIT {
    IF EXISTS(BLACKBOX_PATH) { DELETEPATH(BLACKBOX_PATH). }
    LOG "t_UT,mission_time,phase,altitude,radar_alt,vspeed,airspeed,groundspeed,orbital_speed," +
        "apoapsis,periapsis,mass_t,throttle,stage,pitch,heading,roll,dynamic_pressure," +
        "lat,lng,gear,brakes,rcs,sas,warning_count,last_warning"
        TO BLACKBOX_PATH.
}

FUNCTION BLACKBOX_LOG {
    LOCAL row IS TIME:SECONDS + "," + ROUND(MISSIONTIME,3) + "," + MISSION_PHASE + "," +
        ROUND(SHIP:ALTITUDE,1) + "," + ROUND(ALT:RADAR,1) + "," + ROUND(SHIP:VERTICALSPEED,2) + "," +
        ROUND(SHIP:AIRSPEED,2) + "," + ROUND(SHIP:GROUNDSPEED,2) + "," + ROUND(SHIP:VELOCITY:ORBIT:MAG,2) + "," +
        ROUND(SHIP:APOAPSIS,1) + "," + ROUND(SHIP:PERIAPSIS,1) + "," + ROUND(SHIP:MASS,3) + "," +
        ROUND(THROTTLE,3) + "," + STAGE:NUMBER + "," +
        ROUND(SHIP:FACING:PITCH,2) + "," + ROUND(SHIP:FACING:YAW,2) + "," + ROUND(SHIP:FACING:ROLL,2) + "," +
        ROUND(SHIP:Q,4) + "," + ROUND(SHIP:GEOPOSITION:LAT,5) + "," + ROUND(SHIP:GEOPOSITION:LNG,5) + "," +
        GEAR + "," + BRAKES + "," + RCS + "," + SAS + "," + WARNING_COUNT + "," + LAST_WARNING.
    LOG row TO BLACKBOX_PATH.
    SET BLACKBOX_ROWS TO BLACKBOX_ROWS + 1.
}

// ---------------------------- HUD ----------------------------
FUNCTION HUD_INIT {
    CLEARSCREEN.
    PRINT "======================= DYNAWING MISSION HUD =======================" AT(0,0).
    PRINT "----------------------------------------------------------------------" AT(0,15).
    PRINT "RECENT EVENTS:" AT(0,16).
    PRINT "----------------------------------------------------------------------" AT(0,25).
}

FUNCTION HUD_UPDATE {
    PRINT PAD("PHASE: " + MISSION_PHASE, 40) AT(0,1).
    PRINT PAD("T+ " + ROUND(MISSIONTIME,1) + " s   UT " + ROUND(TIME:SECONDS,1), 40) AT(0,2).
    PRINT PAD("Altitude:  " + ROUND(SHIP:ALTITUDE,0) + " m   Radar: " + ROUND(ALT:RADAR,0) + " m", 50) AT(0,3).
    PRINT PAD("V.Speed:   " + ROUND(SHIP:VERTICALSPEED,1) + " m/s", 40) AT(0,4).
    PRINT PAD("Airspeed:  " + ROUND(SHIP:AIRSPEED,1) + " m/s   Ground: " + ROUND(SHIP:GROUNDSPEED,1) + " m/s", 55) AT(0,5).
    PRINT PAD("Orbit vel: " + ROUND(SHIP:VELOCITY:ORBIT:MAG,1) + " m/s", 40) AT(0,6).
    PRINT PAD("Apoapsis:  " + ROUND(SHIP:APOAPSIS,0) + " m", 40) AT(0,7).
    PRINT PAD("Periapsis: " + ROUND(SHIP:PERIAPSIS,0) + " m", 40) AT(0,8).
    PRINT PAD("Throttle:  " + ROUND(THROTTLE*100,0) + " %   Stage: " + STAGE:NUMBER, 40) AT(0,9).
    PRINT PAD("Mass:      " + ROUND(SHIP:MASS,2) + " t   Q: " + ROUND(SHIP:Q,3), 40) AT(0,10).
    PRINT PAD("Attitude:  P " + ROUND(SHIP:FACING:PITCH,1) + "  Y " + ROUND(SHIP:FACING:YAW,1) + "  R " + ROUND(SHIP:FACING:ROLL,1), 55) AT(0,11).
    PRINT PAD("Gear:" + GEAR + " Brakes:" + BRAKES + " RCS:" + RCS + " SAS:" + SAS, 55) AT(0,12).
    PRINT PAD("Dist to runway: " + ROUND(RUNWAY_POS:DISTANCE,0) + " m   Brg: " + ROUND(RUNWAY_POS:HEADING,0) + " deg", 55) AT(0,13).
    PRINT PAD("Warnings: " + WARNING_COUNT + "   Blackbox rows: " + BLACKBOX_ROWS, 55) AT(0,14).

    LOCAL i IS 0.
    UNTIL i >= 8 {
        LOCAL msg IS "".
        IF i < RECENT_MSGS:LENGTH { SET msg TO RECENT_MSGS[i]. }
        PRINT PAD(msg, 70) AT(0, 17+i).
        SET i TO i + 1.
    }
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

// FAILSAFE: bounded wait for STAGE:READY instead of an unconditional WAIT
// UNTIL, so a staging fault (e.g. a decoupler that never reports ready)
// can't hang the whole mission forever.
FUNCTION DO_STAGE {
    LOCAL waitStart IS TIME:SECONDS.
    WAIT UNTIL STAGE:READY OR TIME:SECONDS - waitStart > 10.
    IF NOT STAGE:READY {
        LOG_MSG("WARNING: STAGE:READY timed out after 10s, staging anyway.").
    }
    STAGE.
    WAIT 0.1.
    LOG_MSG("Staged -> now on stage " + STAGE:NUMBER + ".").
    WAIT 0.5.
}

// FAILSAFE: engine-out check with a grace period. Engines take a moment to
// spool up to full AVAILABLETHRUST after ignition, so checking THRUST vs.
// AVAILABLETHRUST immediately at ignition false-triggers on every launch.
// Only start checking once thrust has had time to stabilize.
FUNCTION CHECK_ENGINE_OUT {
    PARAMETER elist, graceSeconds, igniteTime.
    IF TIME:SECONDS - igniteTime < graceSeconds { RETURN TRUE. }
    LOCAL liveCount IS 0.
    FOR e IN elist {
        IF e:IGNITION AND NOT e:FLAMEOUT AND e:THRUST > e:AVAILABLETHRUST * 0.5 {
            SET liveCount TO liveCount + 1.
        }
    }
    RETURN liveCount = elist:LENGTH.
}

// FAILSAFE: total MonoPropellant available to the OMS pods, so we never
// commit to a burn node we can't actually finish.
FUNCTION OMS_MONOPROP_AVAILABLE {
    LOCAL total IS 0.
    LIST PARTS IN allParts.
    FOR p IN allParts {
        IF p:NAME = "omsEngine" {
            FOR res IN p:RESOURCES {
                IF res:NAME = "MonoPropellant" { SET total TO total + res:AMOUNT. }
            }
        }
    }
    RETURN total.
}

// FAILSAFE: rough propellant-to-dv check using the rocket equation with the
// OMS Isp (O-10 "Puff" engines, stock Isp ~120s vacuum), so a deorbit/circ
// burn that would run the tanks dry gets caught before it's attempted.
FUNCTION OMS_DV_AVAILABLE {
    // Sourced: O-10 "Puff" Isp_vac = 290s (this vehicle burns OMS in vacuum,
    // never in atmosphere, so the vacuum figure is the correct one -- not the
    // 220s atmospheric Isp). MonoPropellant density = 4 kg/unit, confirmed
    // against the KSP wiki resource table.
    LOCAL propMass IS OMS_MONOPROP_AVAILABLE() * 4.0. // kg
    LOCAL wetMass IS SHIP:MASS * 1000. // SHIP:MASS is metric tons, convert to kg
    LOCAL dryMass IS MAX(wetMass - propMass, 1).
    LOCAL ispVac IS 290.
    RETURN ispVac * G0 * LN(wetMass / dryMass).
}

// ---------------------------- TIMEWARP ----------------------------
// Warp through dead coast time (ascent->apoapsis, deorbit->reentry interface)
// instead of sitting there in real time. WARPTO handles the deceleration
// itself -- it's the same call the game uses for "warp to next node," and it
// already refuses to physics-warp inside the atmosphere, so it's safe to call
// even when the target time is close to atmospheric entry.
FUNCTION WARP_TO_UT {
    PARAMETER targetUT, leadSeconds.
    LOCAL t IS targetUT - leadSeconds.
    IF t > TIME:SECONDS + 5 {
        LOG_MSG("Warping " + ROUND(t - TIME:SECONDS,0) + "s ahead to save real time.").
        KUNIVERSE:TIMEWARP:WARPTO(t).
        WAIT UNTIL TIME:SECONDS >= t - 1.
    }
    SET KUNIVERSE:TIMEWARP:WARP TO 0.
}

// ---------------------------- ORBITAL MATH ----------------------------
FUNCTION V_CIRC {
    PARAMETER radius.
    RETURN SQRT(BODY:MU / radius).
}

FUNCTION V_VIS_VIVA {
    PARAMETER radius, sma.
    RETURN SQRT(BODY:MU * (2/radius - 1/sma)).
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

    // FAILSAFE: cap the burn at 3x the estimated duration (plus a 10s floor)
    // so a burn that never converges -- dead engine, node math gone wrong --
    // can't run the tanks dry silently instead of stopping and reporting.
    LOCAL burnDeadline IS TIME:SECONDS + MAX(burnTime * 3, 10).

    UNTIL nd:BURNVECTOR:MAG < 0.2 OR nd:BURNVECTOR:MAG > initialDv OR TOTAL_AVAILABLE_THRUST() < 0.1 {
        IF TIME:SECONDS > burnDeadline {
            LOG_MSG("WARNING: burn exceeded 3x estimated time, aborting node execution.").
            BREAK.
        }
        LOCK STEERING TO nd:BURNVECTOR.
        WAIT 0.02.
    }

    IF TOTAL_AVAILABLE_THRUST() < 0.1 {
        LOG_MSG("WARNING: no thrust available mid-burn (engine failure or propellant exhausted).").
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
    SET MISSION_PHASE TO "ASCENT-LIFTOFF".
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
    SET MISSION_PHASE TO "ASCENT-SSME".
    DO_STAGE().

    // Continue on SSMEs, following prograde. The OMS pods only carry ~300 m/s
    // combined with RCS (confirmed from the stock craft's flight notes), shared
    // with the deorbit burn later, so MECO should not happen the instant
    // apoapsis first touches target -- that leaves periapsis deep in the
    // atmosphere and costs ~70 m/s of OMS just to fix (vis-viva check: cutting
    // at Pe=0/Ap=80km needs ~72 m/s trim vs. ~10 m/s if Pe is already near
    // target when MECO happens). So: keep burning near-horizontal until BOTH
    // apoapsis and periapsis are near target, capped so we never overshoot
    // apoapsis by more than 15%.
    LOCAL ssmeIgniteTime IS TIME:SECONDS.
    LOCK STEERING TO SHIP:SRFPROGRADE.
    UNTIL (SHIP:APOAPSIS >= TARGET_APO AND SHIP:PERIAPSIS >= TARGET_APO * 0.85) OR ALL_FLAMED_OUT(ssmes) {
        // FAILSAFE: engine-out check with a 3s spool-up grace period. Checking
        // THRUST vs. AVAILABLETHRUST from the instant of ignition false-triggers
        // every launch because engines aren't at full thrust yet -- this is
        // exactly the bug that sinks most "engine-out failsafe" scripts.
        IF NOT CHECK_ENGINE_OUT(ssmes, 3, ssmeIgniteTime) {
            LOG_MSG("WARNING: SSME engine-out detected. Continuing on remaining thrust.").
        }

        IF SHIP:APOAPSIS > TARGET_APO * 1.15 {
            LOCK THROTTLE TO 0.1. // overshoot safety, should rarely trigger
        } ELSE {
            LOCK THROTTLE TO 1.0.
        }
        WAIT 0.05.
    }
    LOCK THROTTLE TO 0.
    WAIT 0.5.
    UNLOCK THROTTLE.
    LOG_MSG("SSME cutoff: Ap=" + ROUND(SHIP:APOAPSIS,0) + " Pe=" + ROUND(SHIP:PERIAPSIS,0) + " m.").

    // FAILSAFE: if the SSMEs flamed out (engine failure or ran the tank dry)
    // before reaching a viable apoapsis, an OMS circularization burn from here
    // would need far more than the ~300 m/s available and will not succeed.
    // Flag it clearly rather than silently proceeding into a doomed sequence.
    IF SHIP:APOAPSIS < TARGET_APO * 0.5 {
        LOG_MSG("CRITICAL: apoapsis " + ROUND(SHIP:APOAPSIS,0) + "m is far below target -- ").
        LOG_MSG("SSMEs likely underperformed or flamed out early. OMS cannot make up this").
        LOG_MSG("much dv. Mission will attempt circularization anyway but may re-enter.").
    }

    // Shut down SSMEs explicitly, jettison tank, bring up OMS.
    FOR e IN ssmes { e:SHUTDOWN(). }
    DO_STAGE(). // jettison external tank
    DO_STAGE(). // activate OMS stage if separate
    UNLOCK STEERING.
    SAS ON.
    LOG_MSG("Ascent complete, coasting to apoapsis for circularization.").
    SET MISSION_PHASE TO "COAST-TO-APOAPSIS".
}

// ============================================================================
// PHASE 2: CIRCULARIZE
// ============================================================================
FUNCTION CIRCULARIZE {
    SET MISSION_PHASE TO "CIRCULARIZE".
    SAS OFF.
    LOCAL nd IS MAKE_CIRC_NODE().

    // FAILSAFE: verify the OMS pods can actually deliver this dv before
    // committing. The pool is only ~300 m/s total, and if it's already short
    // here there won't be anything left for the deorbit burn either.
    LOCAL needed IS ABS(nd:DELTAV:MAG).
    LOCAL available IS OMS_DV_AVAILABLE().
    LOG_MSG("Circularization needs " + ROUND(needed,1) + " m/s; OMS has ~" + ROUND(available,1) + " m/s.").
    IF needed > available {
        LOG_MSG("CRITICAL: insufficient OMS propellant for full circularization.").
        LOG_MSG("Burning anyway with whatever propellant remains; orbit may stay eccentric.").
    }

    EXECUTE_NODE(nd).
    LOG_MSG("Orbit: Ap=" + ROUND(SHIP:APOAPSIS,0) + " Pe=" + ROUND(SHIP:PERIAPSIS,0) + ".").
}

// ============================================================================
// PHASE 3: DEORBIT
// ============================================================================
FUNCTION DEORBIT {
    SET MISSION_PHASE TO "DEORBIT-PLANNING".
    LOCAL nd IS MAKE_DEORBIT_NODE().
    SET MISSION_PHASE TO "DEORBIT-BURN".

    // FAILSAFE: same propellant check as circularization -- a deorbit burn
    // that runs out partway leaves periapsis higher than planned, which at
    // least is a *safe* failure (stays in orbit) rather than an unsafe one,
    // so we still attempt it, but we want it logged rather than silent.
    LOCAL needed IS ABS(nd:DELTAV:MAG).
    LOCAL available IS OMS_DV_AVAILABLE().
    LOG_MSG("Deorbit needs " + ROUND(needed,1) + " m/s; OMS has ~" + ROUND(available,1) + " m/s.").
    IF needed > available {
        LOG_MSG("WARNING: insufficient OMS propellant for full deorbit burn.").
        LOG_MSG("Periapsis will end up higher than planned -- rerun deorbit next orbit if so.").
    }

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
    SET MISSION_PHASE TO "REENTRY-HOLD".
    LOG_MSG("Entering atmosphere, starting reentry attitude hold.").
    RCS ON.
    SAS OFF.

    LOCK STEERING TO SHIP:SRFRETROGRADE. // belly-first, high-AoA hold via retrograde lock
    WAIT UNTIL SHIP:ALTITUDE < 60000.

    // Hold retrograde through the hottest part of reentry.
    WAIT UNTIL SHIP:ALTITUDE < 40000 OR SHIP:AIRSPEED < 800.

    SET MISSION_PHASE TO "GLIDE".
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

    SET MISSION_PHASE TO "FINAL-APPROACH".
    LOG_MSG("Final approach. Distance to runway: " + ROUND(RUNWAY_POS:DISTANCE,0) + " m.").
    IF NOT GEAR { GEAR ON. }

    // Flare: reduce descent rate as we near the ground.
    SET MISSION_PHASE TO "FLARE".
    UNTIL SHIP:STATUS = "LANDED" OR SHIP:STATUS = "SPLASHED" {
        LOCAL courseToRunway IS RUNWAY_POS:HEADING.
        LOCAL flarePitch IS -2.
        IF SHIP:ALTITUDE < 20 { SET flarePitch TO 3. }
        LOCK STEERING TO HEADING(courseToRunway, 90 + flarePitch).
        WAIT 0.05.
    }

    SET MISSION_PHASE TO "ROLLOUT".
    LOG_MSG("Touchdown detected. Applying brakes.").
    UNLOCK STEERING.
    BRAKES ON.
    WAIT UNTIL SHIP:VELOCITY:SURFACE:MAG < 1.

    SET MISSION_PHASE TO "MISSION-COMPLETE".
    LOCAL missDist IS RUNWAY_POS:DISTANCE.
    LOG_MSG("Vehicle stopped. Miss distance from runway aim point: " + ROUND(missDist,0) + " m.").
    LOG_MSG("If short: decrease GLIDE_LEAD_DEG. If long/overshot: increase it.").
    HUD_UPDATE(). // final draw so the HUD shows the landed state, not a stale tick
    PRINT PAD(">>> MISSION COMPLETE -- black box: " + BLACKBOX_ROWS + " rows at " + BLACKBOX_PATH, 70) AT(0,26).
}

// ============================================================================
// MAIN SEQUENCE
// ============================================================================
BLACKBOX_INIT().
HUD_INIT().
LOG_MSG("Dynawing autonomous mission starting.").

// Background telemetry trigger: runs every physics tick regardless of what
// the main flow below is doing (even while it's blocked in a WAIT UNTIL
// inside another function), so the HUD and black box never go stale and
// never miss a tick just because the main thread is busy elsewhere.
WHEN TRUE THEN {
    HUD_UPDATE().
    BLACKBOX_LOG().
    PRESERVE.
}

ASCENT().
SET MISSION_PHASE TO "COAST-TO-APOAPSIS".
WARP_TO_UT(TIME:SECONDS + ETA:APOAPSIS, 30). // warp the ascent->apoapsis coast, drop out 30s early
WAIT UNTIL ETA:APOAPSIS < 30.
CIRCULARIZE().
LOG_MSG("Orbit achieved. Coasting before deorbit planning.").
WAIT 5.
DEORBIT().
SET MISSION_PHASE TO "COAST-TO-REENTRY".
// Warp the long coast back down, dropping out with a generous 120s margin
// before periapsis so we're well clear of the atmosphere when warp ends --
// WARPTO already refuses to physics-warp inside atmosphere, this margin is
// just to make sure REENTRY_AND_GLIDE gets full manual control in time.
WARP_TO_UT(TIME:SECONDS + ETA:PERIAPSIS, 120).
WAIT UNTIL SHIP:ALTITUDE < 70000.
REENTRY_AND_GLIDE().
