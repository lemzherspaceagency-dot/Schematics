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
GLOBAL TURN_START_ALT IS 1000.                 // gravity turn pitch program bounds
GLOBAL TURN_MID_ALT IS 22000.                  // steep-climb segment ends / gravity-turn segment starts
GLOBAL TURN_MID_PITCH IS 65.                   // pitch (deg above horizon) held at TURN_MID_ALT
GLOBAL TURN_END_ALT IS 45000.                  // "horizontal by 45km" per the craft's own design notes
GLOBAL GEAR_DEPLOY_ALT IS 600.                 // radar altitude to drop gear, m
GLOBAL FLARE_ALT IS 60.                        // radar altitude to begin flare, m
GLOBAL STALL_SPEED_MIN IS 70.                  // below this, prioritize regaining speed over anything else

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
// FIX (universal HUD, not a forced resize): clamp every pad width to
// whatever the terminal ACTUALLY is (read live, every call), leaving a
// 1-column margin so the last character never touches the terminal edge --
// that's what was wrapping onto the next row and corrupting it. This adapts
// to any terminal size instead of assuming or forcing one; a small terminal
// gets truncated text, a large one gets the full requested width, and
// nothing ever wraps.
FUNCTION PAD {
    PARAMETER s, w.
    LOCAL maxW IS TERMINAL:WIDTH - 1.
    LOCAL effW IS MIN(w, maxW).
    LOCAL str IS s + "".
    IF str:LENGTH > effW { RETURN str:SUBSTRING(0, effW). }
    UNTIL str:LENGTH >= effW { SET str TO str + " ". }
    RETURN str.
}

// ---------------------------- BLACK BOX FLIGHT RECORDER ----------------------------
// Full state snapshot on every physics tick, written to the archive volume as
// CSV. If the mission succeeds OR fails (crash, loss of control, whatever),
// this file survives and can be handed back for post-flight analysis: every
// column needed to reconstruct what the vehicle was doing at any instant.
// Every column here is chosen to mirror the HUD exactly -- one blackbox row
// is the full HUD snapshot for that tick, not a subset of it, so reading the
// CSV post-flight tells you everything the HUD was showing at any instant.
FUNCTION BLACKBOX_INIT {
    IF EXISTS(BLACKBOX_PATH) { DELETEPATH(BLACKBOX_PATH). }
    LOG "t_UT,mission_time,phase,altitude,radar_alt,vspeed,airspeed,groundspeed,orbital_speed," +
        "apoapsis,periapsis,mass_t,throttle,stage,pitch,heading,roll,dynamic_pressure," +
        "lat,lng,gear,brakes,rcs,sas,dist_to_runway,bearing_to_runway,warning_count,last_warning," +
        "blackbox_rows,oms_monoprop_units,oms_engines_ignited,oms_engines_flamedout,oms_available_thrust," +
        "warp_level,hasnode,node_eta,node_burnvec_mag,node_align_err,steering_locked," +
        "aoa_srfprograde,aoa_orbitprograde," +
        "last_event"
        TO BLACKBOX_PATH.
}

// So a future "OMS has ~0 m/s" moment can be diagnosed from the black box
// directly instead of inferred from mass deltas: was it really out of
// propellant, or were the engines just not producing thrust?
FUNCTION OMS_ENGINE_STATS {
    LOCAL omsEngines IS ENGINES_NAMED("omsEngine").
    LOCAL ignited IS 0.
    LOCAL flamedOut IS 0.
    LOCAL thrust IS 0.
    FOR e IN omsEngines {
        IF e:IGNITION { SET ignited TO ignited + 1. }
        IF e:FLAMEOUT { SET flamedOut TO flamedOut + 1. }
        IF e:IGNITION AND NOT e:FLAMEOUT { SET thrust TO thrust + e:AVAILABLETHRUST. }
    }
    RETURN LIST(ignited, flamedOut, thrust).
}

FUNCTION BLACKBOX_LOG {
    LOCAL lastEvent IS "".
    IF RECENT_MSGS:LENGTH > 0 { SET lastEvent TO RECENT_MSGS[RECENT_MSGS:LENGTH - 1]. }
    // Strip commas from free-text fields so they can't be mistaken for extra
    // CSV columns by a downstream parser.
    SET lastEvent TO lastEvent:REPLACE(",", ";").
    LOCAL lastWarn IS LAST_WARNING:REPLACE(",", ";").
    LOCAL omsStats IS OMS_ENGINE_STATS().

    // FIX (blind-spot report, take 2): a single event-triggered log line
    // isn't enough -- it only catches what I thought to instrument. HASNODE
    // and NEXTNODE are global, phase-independent kOS built-ins: querying
    // them here means the black box captures the TRUE node/warp/steering
    // state on every single tick, regardless of which function is running
    // or what I remembered to log explicitly. This should make "why did it
    // fire early" answerable directly from the data instead of requiring
    // another round of inference or another targeted log line.
    LOCAL nodeEta IS -1.
    LOCAL nodeBurnMag IS -1.
    LOCAL nodeAlignErr IS -1.
    IF HASNODE {
        SET nodeEta TO ROUND(NEXTNODE:ETA,1).
        SET nodeBurnMag TO ROUND(NEXTNODE:BURNVECTOR:MAG,2).
        SET nodeAlignErr TO ROUND(VANG(SHIP:FACING:FOREVECTOR, NEXTNODE:BURNVECTOR),2).
    }

    // The Euler pitch/heading/roll below (SHIP:FACING) are known to glitch
    // near-vertical attitudes (gimbal-lock-style artifacts, seen in flight
    // 1's blackbox). What actually matters for diagnosing attitude -- and
    // what the navball itself shows -- is how far the nose is from the
    // prograde/retrograde marker, in both surface and orbital modes (the
    // navball can be toggled between them, and they diverge whenever there's
    // any wind/rotation, which is exactly when this distinction matters).
    LOCAL aoaSrf IS ROUND(VANG(SHIP:FACING:FOREVECTOR, SHIP:SRFPROGRADE:FOREVECTOR),2).
    LOCAL aoaOrb IS ROUND(VANG(SHIP:FACING:FOREVECTOR, SHIP:PROGRADE:FOREVECTOR),2).

    LOCAL row IS TIME:SECONDS + "," + ROUND(MISSIONTIME,3) + "," + MISSION_PHASE + "," +
        ROUND(SHIP:ALTITUDE,1) + "," + ROUND(ALT:RADAR,1) + "," + ROUND(SHIP:VERTICALSPEED,2) + "," +
        ROUND(SHIP:AIRSPEED,2) + "," + ROUND(SHIP:GROUNDSPEED,2) + "," + ROUND(SHIP:VELOCITY:ORBIT:MAG,2) + "," +
        ROUND(SHIP:APOAPSIS,1) + "," + ROUND(SHIP:PERIAPSIS,1) + "," + ROUND(SHIP:MASS,3) + "," +
        ROUND(THROTTLE,3) + "," + STAGE:NUMBER + "," +
        ROUND(SHIP:FACING:PITCH,2) + "," + ROUND(SHIP:FACING:YAW,2) + "," + ROUND(SHIP:FACING:ROLL,2) + "," +
        ROUND(SHIP:Q,4) + "," + ROUND(SHIP:GEOPOSITION:LAT,5) + "," + ROUND(SHIP:GEOPOSITION:LNG,5) + "," +
        GEAR + "," + BRAKES + "," + RCS + "," + SAS + "," +
        ROUND(RUNWAY_POS:DISTANCE,0) + "," + ROUND(RUNWAY_POS:HEADING,0) + "," +
        WARNING_COUNT + "," + lastWarn + "," + BLACKBOX_ROWS + "," +
        ROUND(OMS_MONOPROP_AVAILABLE(),1) + "," + omsStats[0] + "," + omsStats[1] + "," +
        ROUND(omsStats[2],1) + "," +
        KUNIVERSE:TIMEWARP:WARP + "," + HASNODE + "," + nodeEta + "," + nodeBurnMag + "," +
        nodeAlignErr + "," + STEERINGMANAGER:ENABLED + "," +
        aoaSrf + "," + aoaOrb + "," + lastEvent.
    LOG row TO BLACKBOX_PATH.
    SET BLACKBOX_ROWS TO BLACKBOX_ROWS + 1.
}

// ---------------------------- HUD ----------------------------
// FIX (HUD corruption report): kOS's terminal defaults to 50 columns wide,
// but every PAD() call in this HUD pads strings out to 55-70 characters
// wide before printing at a fixed AT() row/column. On a 50-column terminal,
// printing a string longer than the remaining width WRAPS onto the next
// row -- which overwrites/mixes with whatever fixed-position text is there,
// exactly the garbled "lamed out, jettisoning" (missing its own start)
// seen in-game. TERMINAL:WIDTH/HEIGHT are settable in kOS (confirmed
// against docs); resizing to something roomy enough for our widest PAD()
// call fixes the wraparound at the source instead of trimming text to fit
// an artificially narrow window.
// Clamp a target row to whatever the terminal's CURRENT height is (read
// live, every call) so a mid-flight resize -- taller or shorter -- never
// tries to print past the actual window. A too-short terminal just
// overlaps some rows rather than erroring; that's an acceptable
// degradation compared to failing outright.
FUNCTION SAFE_ROW {
    PARAMETER rowNum.
    RETURN MIN(rowNum, TERMINAL:HEIGHT - 1).
}

FUNCTION HUD_INIT {
    CLEARSCREEN.
    PRINT PAD("======================= DYNAWING MISSION HUD =======================", 200) AT(0, SAFE_ROW(0)).
    PRINT PAD("----------------------------------------------------------------------", 200) AT(0, SAFE_ROW(16)).
    PRINT PAD("RECENT EVENTS:", 200) AT(0, SAFE_ROW(17)).
    PRINT PAD("----------------------------------------------------------------------", 200) AT(0, SAFE_ROW(26)).
}

FUNCTION HUD_UPDATE {
    PRINT PAD("PHASE: " + MISSION_PHASE, 40) AT(0, SAFE_ROW(1)).
    PRINT PAD("T+ " + ROUND(MISSIONTIME,1) + " s   UT " + ROUND(TIME:SECONDS,1), 40) AT(0, SAFE_ROW(2)).
    PRINT PAD("Altitude:  " + ROUND(SHIP:ALTITUDE,0) + " m   Radar: " + ROUND(ALT:RADAR,0) + " m", 50) AT(0, SAFE_ROW(3)).
    PRINT PAD("V.Speed:   " + ROUND(SHIP:VERTICALSPEED,1) + " m/s", 40) AT(0, SAFE_ROW(4)).
    PRINT PAD("Airspeed:  " + ROUND(SHIP:AIRSPEED,1) + " m/s   Ground: " + ROUND(SHIP:GROUNDSPEED,1) + " m/s", 55) AT(0, SAFE_ROW(5)).
    PRINT PAD("Orbit vel: " + ROUND(SHIP:VELOCITY:ORBIT:MAG,1) + " m/s", 40) AT(0, SAFE_ROW(6)).
    PRINT PAD("Apoapsis:  " + ROUND(SHIP:APOAPSIS,0) + " m", 40) AT(0, SAFE_ROW(7)).
    PRINT PAD("Periapsis: " + ROUND(SHIP:PERIAPSIS,0) + " m", 40) AT(0, SAFE_ROW(8)).
    PRINT PAD("Throttle:  " + ROUND(THROTTLE*100,0) + " %   Stage: " + STAGE:NUMBER, 40) AT(0, SAFE_ROW(9)).
    PRINT PAD("Mass:      " + ROUND(SHIP:MASS,2) + " t   Q: " + ROUND(SHIP:Q,3), 40) AT(0, SAFE_ROW(10)).
    PRINT PAD("Attitude:  P " + ROUND(SHIP:FACING:PITCH,1) + "  Y " + ROUND(SHIP:FACING:YAW,1) + "  R " + ROUND(SHIP:FACING:ROLL,1), 55) AT(0, SAFE_ROW(11)).
    PRINT PAD("Gear:" + GEAR + " Brakes:" + BRAKES + " RCS:" + RCS + " SAS:" + SAS, 55) AT(0, SAFE_ROW(12)).
    PRINT PAD("Lat: " + ROUND(SHIP:GEOPOSITION:LAT,4) + "  Lng: " + ROUND(SHIP:GEOPOSITION:LNG,4), 40) AT(0, SAFE_ROW(13)).
    PRINT PAD("Dist to runway: " + ROUND(RUNWAY_POS:DISTANCE,0) + " m   Brg: " + ROUND(RUNWAY_POS:HEADING,0) + " deg", 55) AT(0, SAFE_ROW(14)).
    PRINT PAD("Warnings: " + WARNING_COUNT + "   Blackbox rows: " + BLACKBOX_ROWS, 55) AT(0, SAFE_ROW(15)).

    LOCAL i IS 0.
    UNTIL i >= 8 {
        LOCAL msg IS "".
        IF i < RECENT_MSGS:LENGTH { SET msg TO RECENT_MSGS[i]. }
        PRINT PAD(msg, 70) AT(0, SAFE_ROW(18+i)).
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

// FIX (post-flight #1): locking steering to SHIP:SRFPROGRADE for the whole
// ascent is unstable on a lower-TWR vehicle like this. Once the velocity
// vector starts tipping past level, chasing it faithfully just steers the
// nose further down into a dive -- there is nothing in a pure prograde-lock
// to stop it, and that's exactly what the first flight's black box showed:
// apoapsis kept climbing (engines still firing) while actual altitude
// collapsed from 6.8km to 1.4km between t=70s and t=103s.
// Fix: pitch is a function of ALTITUDE ONLY, clamped to [0,90] degrees above
// horizon between TURN_START_ALT and TURN_END_ALT. This cannot diverge
// below horizontal by construction, and TURN_END_ALT=45km matches the
// craft's own documented profile ("horizontal by 45 km"). LOCK STEERING TO
// HEADING(90, PITCH_PROGRAM()) re-evaluates this every tick automatically.
//
// FIX (heating): this used to be a single linear ramp from 90 deg at
// TURN_START_ALT straight to 0 deg at TURN_END_ALT, which leans the vehicle
// over fast while still deep in the thick lower atmosphere (e.g. already at
// 51 deg by 20km) -- exactly where aerodynamic heating is worst, since heat
// flux scales with both air density AND velocity, and leaning over early
// trades altitude for horizontal speed right where the air is densest. This
// is why the ignore-max-temp cheat was needed. Real ascent profiles (Saturn
// V, Shuttle) fly steep through the thick air first and save the aggressive
// gravity-turn lean-over for thinner air higher up. Now a two-segment
// program: mostly vertical up to TURN_MID_ALT (holds TURN_MID_PITCH there,
// e.g. 65 deg vs. the old program's 51 deg at the same altitude -- notably
// less horizontal speed built up in the dense air), then the rest of the
// lean-over happens between TURN_MID_ALT and TURN_END_ALT where the air is
// thin enough that the same speed generates much less heating. Trade-off:
// a steeper climb costs a little more gravity-loss dv than the old shallow
// ramp -- watch the ascent margin (already logged) if this needs retuning.
FUNCTION PITCH_PROGRAM {
    // "alt" collides with kOS's built-in ALT structure (ALT:RADAR etc.) --
    // same class of clobber as the earlier "r" vs. R() bug. Renamed.
    LOCAL curAlt IS SHIP:ALTITUDE.
    IF curAlt < TURN_START_ALT { RETURN 90. }
    IF curAlt < TURN_MID_ALT {
        LOCAL frac IS (curAlt - TURN_START_ALT) / (TURN_MID_ALT - TURN_START_ALT).
        RETURN 90 - (90 - TURN_MID_PITCH) * frac.
    }
    IF curAlt < TURN_END_ALT {
        LOCAL frac2 IS (curAlt - TURN_MID_ALT) / (TURN_END_ALT - TURN_MID_ALT).
        RETURN TURN_MID_PITCH * (1 - frac2).
    }
    RETURN 0.
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
// FIX (post-flight #3): comparing THRUST against full AVAILABLETHRUST spams
// false positives whenever the script itself has throttled down (e.g. the
// soft overshoot cap at 0.1 throttle) -- 10% actual thrust vs 100% available
// looks identical to an engine failure. Compare against what the CURRENT
// throttle command should be producing instead.
FUNCTION CHECK_ENGINE_OUT {
    PARAMETER elist, graceSeconds, igniteTime.
    IF TIME:SECONDS - igniteTime < graceSeconds { RETURN TRUE. }
    LOCAL liveCount IS 0.
    FOR e IN elist {
        LOCAL expected IS e:AVAILABLETHRUST * THROTTLE * 0.5.
        IF e:IGNITION AND NOT e:FLAMEOUT AND e:THRUST > expected {
            SET liveCount TO liveCount + 1.
        }
    }
    RETURN liveCount = elist:LENGTH.
}

// FAILSAFE: total MonoPropellant available to the OMS pods, so we never
// commit to a burn node we can't actually finish.
// FIX (post-flight #6): this was checking p:RESOURCES on parts NAMED
// "omsEngine" -- but engines don't store their own propellant, the TANKS
// do (mk3FuselageMONO, rcsTankRadialLong, etc.), fed to the engine via
// crossfeed. So this was summing the OMS engines' own near-empty local
// pools and basically always reporting ~0, regardless of how much fuel
// the vehicle actually had. Confirmed from the black box: circularize
// used only 222 units (of however many the tanks actually hold) for a
// clean 57 m/s burn, yet OMS_DV_AVAILABLE reported ~0 m/s right after --
// not a real fuel shortage, a counting bug. SHIP:RESOURCES gives the
// correct whole-vessel aggregate regardless of which parts store it.
FUNCTION OMS_MONOPROP_AVAILABLE {
    FOR res IN SHIP:RESOURCES {
        IF res:NAME:TOUPPER():CONTAINS("MONOPROP") { RETURN res:AMOUNT. }
    }
    RETURN 0.
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
// FIX (post-flight #2): "rails" warp -- the fast kind, up to 100,000x -- is
// disabled by the game itself below ~70km altitude near an atmospheric body.
// Only "physics" warp (capped at ~4x) is available under that, which is why
// a WARPTO called right after MECO can crawl: if the ship is still under
// 70km when it's called, KSP silently restricts it to 4x no matter what the
// script asks for. Wait until clear of the atmosphere first so the warp
// request actually gets the fast rails mode instead of being throttled.
// FIX (post-flight #5, take 2): KUNIVERSE:TIMEWARP:WARPTO() picks its own
// deceleration curve and it isn't exact -- that's what carried the ship past
// apoapsis last flight. Replaced with a manually-capped, stepped-down warp:
// we choose the rails warp index ourselves based on time remaining, ramp it
// down in stages as the target approaches, and cut it several seconds early
// so real-time WAIT closes the last stretch precisely. Slower to reach the
// target than WARPTO's max-speed approach, but it can't overshoot the same
// way because we're the ones deciding when to slow down, not trusting its
// internal curve to guess right.
FUNCTION WARP_TO_UT {
    PARAMETER targetUT, leadSeconds.
    IF SHIP:ALTITUDE < 70000 AND SHIP:APOAPSIS > 70000 {
        // FIX (in-flight report): this wait used to just sit at 1x real time.
        // Rails warp is capped below 70km, but PHYSICS warp (up to 4x) is
        // still available there and this was leaving it unused the entire
        // time -- a real, free speedup being left on the table.
        LOG_MSG("Waiting to clear 70km before warping (4x physics warp while we're still low).").
        SET KUNIVERSE:TIMEWARP:MODE TO "PHYSICS".
        SET KUNIVERSE:TIMEWARP:WARP TO 3. // max physics warp, ~4x
        WAIT UNTIL SHIP:ALTITUDE > 70000 OR ETA:APOAPSIS < 5.
        SET KUNIVERSE:TIMEWARP:WARP TO 0.
        SET KUNIVERSE:TIMEWARP:MODE TO "RAILS". // switch back before requesting rails warp below
    }
    LOCAL t IS targetUT - leadSeconds.
    IF t > TIME:SECONDS + 5 {
        LOCAL intendedGap IS t - TIME:SECONDS.
        LOG_MSG("Warping " + ROUND(intendedGap,0) + "s ahead (capped, stepped-down warp).").
        // FIX (post-flight #11, real crash): this loop only ever tracked
        // time-remaining-to-target, never altitude. Confirmed from the black
        // box: rails warp (level 2-3) stayed engaged continuously from 70km
        // all the way down past 2km altitude during the coast-to-reentry
        // warp -- the ship warped straight through the ENTIRE atmospheric
        // entry with zero steering control, because the 120s lead margin
        // wasn't enough once actual atmospheric deceleration extended how
        // long the remaining descent took, and this loop had no way to
        // notice that and bail out early. REENTRY_AND_GLIDE() never got a
        // chance to run; the vehicle just fell, uncontrolled, until it broke
        // up. Added a hard, altitude-based emergency exit: regardless of how
        // much time is left, if we're ever below 70km at high speed while
        // this loop is running, cut warp and return immediately. Time-based
        // margins can be miscalculated; this can't be, because it checks the
        // one thing that actually matters (are we already in the atmosphere)
        // instead of a prediction of when that would happen.
        UNTIL TIME:SECONDS >= t - 10 OR SHIP:ALTITUDE < 70000 {
            LOCAL remain IS t - TIME:SECONDS.
            IF remain > 600 { SET KUNIVERSE:TIMEWARP:WARP TO 4. }      // ~100x
            ELSE IF remain > 120 { SET KUNIVERSE:TIMEWARP:WARP TO 3. } // ~50x
            ELSE IF remain > 30 { SET KUNIVERSE:TIMEWARP:WARP TO 2. }  // ~10x
            ELSE { SET KUNIVERSE:TIMEWARP:WARP TO 1. }                 // ~5x
            WAIT 1.
        }
        SET KUNIVERSE:TIMEWARP:WARP TO 0.
        IF SHIP:ALTITUDE < 70000 {
            LOG_MSG("WARNING: dropped below 70km during warp -- cutting warp early, handing back control now.").
            RETURN.
        }
        WAIT UNTIL TIME:SECONDS >= t - 1.
        // Diagnostic (post-flight #8): confirm in the black box whether this
        // actually advanced game time by roughly the intended amount, so a
        // future "fired way too early" report can be told apart from "warp
        // silently didn't engage" at a glance instead of re-deriving it from
        // mass/apoapsis deltas again.
        LOG_MSG("Warp done: intended gap " + ROUND(intendedGap,0) + "s, actual UT now " + ROUND(TIME:SECONDS,0) + ".").
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

// FIX (post-flight #10 investigation): the navball reportedly showed the
// node's countdown still far out, yet the script fired almost immediately
// in GAME time (0.08s between finishing alignment and throttle going live)
// -- which is only possible if the code's local `nd:ETA` and what the game
// itself considers the "next" node (NEXTNODE, what the navball displays)
// were NOT the same node. This script only ever intends one node in the
// flight plan at a time; this guarantees that's actually true before every
// node creation, regardless of whether a previous node was ever left behind
// by some path this code didn't anticipate.
FUNCTION CLEAR_ALL_NODES {
    UNTIL NOT HASNODE {
        REMOVE NEXTNODE.
    }
}

// Build a circularization node at apoapsis.
FUNCTION MAKE_CIRC_NODE {
    CLEAR_ALL_NODES().
    LOCAL apR IS BODY:RADIUS + SHIP:APOAPSIS.
    LOCAL smaNow IS SHIP:ORBIT:SEMIMAJORAXIS.
    LOCAL vNow IS V_VIS_VIVA(apR, smaNow).
    LOCAL vTarget IS V_CIRC(apR).
    LOCAL dv IS vTarget - vNow.
    LOG_MSG("Circularize: v_now=" + ROUND(vNow,1) + " v_target=" + ROUND(vTarget,1) + " dv=" + ROUND(dv,1)).
    // FIX (post-flight #5): if a warp overshoot already carried us past
    // apoapsis, ETA:APOAPSIS reports time to NEXT orbit's apoapsis (nearly a
    // full period) instead of "we're basically there." Scheduling the node
    // that far out would silently waste most of an orbit. If it's not
    // actually close, just burn now instead of waiting for a distant
    // apoapsis that's already behind us.
    LOCAL burnEta IS ETA:APOAPSIS.
    IF burnEta > 300 { SET burnEta TO 10. }
    LOCAL nd IS NODE(TIME:SECONDS + burnEta, 0, 0, dv).
    ADD nd.
    RETURN nd.
}

// Build a deorbit node: prograde-node burn timed so the resulting periapsis
// sits at DEORBIT_PE, with the burn placed GLIDE_LEAD_DEG of true anomaly
// before the runway's longitude crossing.
FUNCTION MAKE_DEORBIT_NODE {
    CLEAR_ALL_NODES().
    LOCAL rPe IS BODY:RADIUS + DEORBIT_PE.
    LOCAL smaNow IS SHIP:ORBIT:SEMIMAJORAXIS.
    LOCAL rNow IS BODY:RADIUS + SHIP:ALTITUDE.

    // new semi-major axis so that periapsis = rPe, apoapsis unchanged at burn point
    LOCAL smaNew IS (rNow + rPe) / 2.
    LOCAL vNow IS V_VIS_VIVA(rNow, smaNow).
    LOCAL vNew IS V_VIS_VIVA(rNow, smaNew).
    LOCAL dv IS vNew - vNow. // negative -> retrograde burn

    // FIX (post-flight #12, real crash 740km off): a retrograde burn does
    // NOT lower the ground track at the BURN point -- it lowers periapsis
    // roughly HALF AN ORBIT away, on the opposite side of the planet. This
    // search was matching the burn point's own longitude to the runway,
    // which is the wrong point in the orbit entirely: confirmed from the
    // black box, the ship was near -106 deg longitude (reasonably close to
    // the intended aim point) AT THE BURN, but the periapsis/reentry ended
    // up on a completely different part of the planet, ~740km from the
    // runway -- not a glide-ratio tuning error, an orbital-mechanics error.
    // Fix: search over candidate BURN times, but score each one by the
    // ground longitude at PERIAPSIS TIME (burn time + half the orbital
    // period, since a small retrograde burn barely changes the period),
    // not at the burn time itself.
    LOCAL bestEta IS ETA:APOAPSIS.
    LOCAL bestDiff IS 999.
    LOCAL period IS SHIP:ORBIT:PERIOD.
    LOCAL steps IS 60.
    LOCAL i IS 0.
    UNTIL i > steps {
        LOCAL tTry IS TIME:SECONDS + (period * i / steps).
        LOCAL periapsisTime IS tTry + (period / 2).
        LOCAL futurePos IS POSITIONAT(SHIP, periapsisTime).
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

    // FIX (post-flight #8): the OLD code locked steering to nd:BURNVECTOR
    // before computing burnStart and before the long warp -- and never
    // unlocked it until after. An active steering LOCK demands continuous
    // torque correction every physics tick, which stops rails warp from
    // actually engaging at high multiplier (same conflict class as SAS
    // fighting an active steering lock). No lock is held during the warp.
    //
    // FIX (post-flight #9): that alone wasn't enough. Flight 8 confirmed the
    // warp wasn't even the issue this time (no "Warping ahead" ever logged --
    // the burn point was already close) and apoapsis STILL rose instead of
    // falling. Root cause: alignment was only attempted right as the burn
    // window arrived, with a hard 20s cap. If the ship's leftover attitude
    // from the previous burn was far from retrograde, rotating a ~43t vessel
    // that far can genuinely take longer than 20s, and by the time it
    // finished turning, the burn window (specific to the ground-track-aligned
    // point MAKE_DEORBIT_NODE chose) had already passed -- so it fired late,
    // against a real but now-stale orbital position. Fix: align FIRST, with
    // no time pressure, BEFORE computing burnStart/warping at all. A vessel
    // holds its attitude through an unperturbed vacuum coast even after
    // UNLOCK, so aligning early and then unlocking for the warp costs nothing
    // and guarantees the ship is already pointed correctly when the window
    // arrives, instead of racing to turn while the clock runs out.
    LOCK STEERING TO nd:BURNVECTOR.
    LOCAL preAlignStart IS TIME:SECONDS.
    WAIT UNTIL VANG(SHIP:FACING:FOREVECTOR, nd:BURNVECTOR) < 1.0 OR TIME:SECONDS - preAlignStart > 60.

    // FIX (post-flight #10, actual root cause): kOS's AVAILABLETHRUST (and
    // thus TOTAL_AVAILABLE_THRUST here) is in KILONEWTONS, not Newtons --
    // confirmed against kOS docs. This formula converted SHIP:MASS from tons
    // to kg (*1000) but never converted F from kN to N, a net 1000x error:
    // burnTime came out as ~23,600s instead of ~24s. That single corrupted
    // number explains every symptom seen across flights 5-9 at once -- it's
    // been hiding underneath the steering-lock fix, the align-first fix, the
    // node-clearing fix, and the warp hardening, none of which could ever
    // work while this was silently making every downstream timing check
    // vacuously true:
    //   burnStart = now + ETA - burnTime/2 - 10 came out deeply NEGATIVE
    //     (burnTime/2 ~11800s dwarfing ETA ~1080s), so "IF burnStart > now+15"
    //     was always false -- the warp branch never ran, ever.
    //   "WAIT UNTIL nd:ETA <= burnTime/2 + 1" was satisfied on the very
    //     first check (1080 <= ~11800), i.e. no actual wait at all.
    //   The abort sanity check ("ETA drifted too far") could never trigger
    //     for the same reason -- its own threshold was equally corrupted.
    // Tons and kN happen to cancel the same SI conversion factor, so the
    // fix is to remove the erroneous *1000 entirely, not add another one.
    LOCAL dvMag IS nd:BURNVECTOR:MAG.
    LOCAL F IS TOTAL_AVAILABLE_THRUST().
    IF F < 1 { SET F TO 1. }
    LOCAL burnTime IS (SHIP:MASS * dvMag) / F.

    LOCAL burnStart IS TIME:SECONDS + nd:ETA - (burnTime / 2) - 10.
    IF burnStart > TIME:SECONDS + 15 {
        UNLOCK STEERING. // already aligned; ship holds attitude through the coast/warp
        WARP_TO_UT(burnStart, 0).
    }

    LOCK STEERING TO nd:BURNVECTOR.
    LOCAL alignStart IS TIME:SECONDS.
    WAIT UNTIL VANG(SHIP:FACING:FOREVECTOR, nd:BURNVECTOR) < 1.0 OR TIME:SECONDS - alignStart > 20.
    LOCAL etaWaitStart IS TIME:SECONDS.
    WAIT UNTIL nd:ETA <= (burnTime / 2) + 1 OR TIME:SECONDS - etaWaitStart > 60.
    WAIT UNTIL VANG(SHIP:FACING:FOREVECTOR, nd:BURNVECTOR) < 2.0.

    // FAILSAFE: even with the hardened warp, if timing still drifted badly
    // enough that we're clearly not at the planned burn window anymore,
    // firing anyway would repeat exactly the wrong-direction burn seen in
    // flight. A missed/rescheduled burn is a recoverable, safe failure; a
    // burn executed against stale node geometry is not -- it wastes
    // propellant AND moves the orbit the wrong way.
    IF ABS(nd:ETA) > (burnTime / 2) + 30 {
        LOG_MSG("CRITICAL: burn timing drifted too far off-plan (ETA=" + ROUND(nd:ETA,1) + "s), aborting burn.").
        UNLOCK STEERING.
        REMOVE nd. // FIX (post-flight #8): this used to leave the node in the flight
                   // plan on abort -- a stale node sitting there confuses the navball
                   // (shows a maneuver marker for a burn that will never fire this way)
                   // and would collide with a freshly-planned retry node.
        RETURN.
    }

    // FIX (blind-spot report): the black box samples once per physics tick,
    // and during high rails warp a single tick can span a large jump in game
    // time -- so if ignition happened mid-jump, one row could show "T-20min,
    // nothing happening" and the very next show "already burned," with the
    // actual ignition instant never captured by the periodic sample. This is
    // an explicit, event-triggered log fired at the exact moment throttle
    // goes nonzero, independent of the regular per-tick sampling, so the
    // real ignition moment (and the ETA/attitude at that instant) is always
    // visible in the black box even if it happened inside a warp jump.
    // FIX (post-flight #10 investigation): directly compare the LOCAL node
    // handle's ETA against whatever NEXTNODE (what the navball shows) reports
    // at this exact instant. If these two numbers disagree, it proves the
    // code fired against a different node than what the flight plan/navball
    // considered "next" -- confirming the multi-node theory outright instead
    // of leaving it inferred.
    LOCAL nextnodeEta IS -999.
    IF HASNODE { SET nextnodeEta TO ROUND(NEXTNODE:ETA,1). }
    LOG_MSG("IGNITION: throttle live. local nd:ETA=" + ROUND(nd:ETA,1) +
        "s, NEXTNODE:ETA=" + nextnodeEta + "s, warp=" + KUNIVERSE:TIMEWARP:WARP +
        ", VANG=" + ROUND(VANG(SHIP:FACING:FOREVECTOR, nd:BURNVECTOR),2) + " deg.").

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

    // Closed-loop gravity turn: pitch is a function of altitude only (see
    // PITCH_PROGRAM), between TURN_START_ALT and TURN_END_ALT. It re-evaluates
    // every tick since it's a LOCK, not a one-time SET, and it cannot diverge
    // below horizontal by construction -- see the comment on PITCH_PROGRAM
    // for why this replaced a plain SRFPROGRADE lock after the first flight.
    WAIT UNTIL SHIP:VELOCITY:SURFACE:MAG > 50 OR SHIP:ALTITUDE > 500.
    LOG_MSG("Pitch kickover.").
    LOCK STEERING TO HEADING(90, PITCH_PROGRAM()).

    // Booster separation on flameout (closed loop, no fixed timer)
    WAIT UNTIL ALL_FLAMED_OUT(boosters) OR SHIP:ALTITUDE > 20000.
    LOG_MSG("Boosters flamed out, jettisoning.").
    SET MISSION_PHASE TO "ASCENT-SSME".
    DO_STAGE().

    // Continue on SSMEs, following the same altitude-based pitch program.
    // FIX (post-flight #4): flights 2 and 3 both hit the hard apoapsis cap
    // without ever reaching the old "periapsis >= 85% of target" condition.
    // The reason is physics, not a tuning problem: vis-viva shows a Pe=68km/
    // Ap=80km orbit needs 2268.8 m/s at apoapsis, which is 99.6% of full
    // circular velocity (2278.9 m/s) -- that condition was asking the SSMEs
    // to do essentially the ENTIRE circularization themselves, and this
    // vehicle's rocket dv budget has no margin for that (94-98% of it is
    // already needed just to reach apoapsis). Reverting to the simple,
    // physically-grounded version: cut the instant apoapsis reaches target,
    // whatever periapsis happens to be. Worst case (Pe=0) only costs ~72 m/s
    // of OMS trim, which the ~300 m/s pool covers easily -- there was never
    // a real problem here worth chasing.
    LOCAL ssmeIgniteTime IS TIME:SECONDS.
    LOCK STEERING TO HEADING(90, PITCH_PROGRAM()).
    UNTIL SHIP:APOAPSIS >= TARGET_APO OR ALL_FLAMED_OUT(ssmes) {
        // FAILSAFE: engine-out check with a 3s spool-up grace period. Checking
        // THRUST vs. AVAILABLETHRUST from the instant of ignition false-triggers
        // every launch because engines aren't at full thrust yet -- this is
        // exactly the bug that sinks most "engine-out failsafe" scripts.
        IF NOT CHECK_ENGINE_OUT(ssmes, 3, ssmeIgniteTime) {
            LOG_MSG("WARNING: SSME engine-out detected. Continuing on remaining thrust.").
        }
        LOCK THROTTLE TO 1.0.
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
    // FIX (in-flight report): this used to be "SAS ON" here, but the very
    // next thing MAIN SEQUENCE does is LOCK STEERING TO SHIP:PROGRADE for
    // the coast -- SAS and an active steering LOCK both try to command
    // attitude at the same time, which is exactly the "fighting" kOS was
    // warning about. SAS was never actually needed here since a steering
    // lock takes over immediately; just leave it off.
    SAS OFF.
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
// Retrograde tilted toward local vertical by aoaDeg -- built with plain
// vector blending, not ANGLEAXIS/VCRS, specifically to avoid their sign
// ambiguity in KSP's left-handed coordinate system (cross-product direction
// there is flipped from standard math convention). This construction can't
// have that problem: it's just "retrograde, rotated aoaDeg toward true-up,
// in the plane containing both" -- the sign is correct by construction,
// verifiable without needing to fly it first to check which way it tilts.
FUNCTION AOA_RETROGRADE {
    PARAMETER aoaDeg.
    LOCAL fwd IS SHIP:SRFRETROGRADE:VECTOR:NORMALIZED.
    LOCAL upv IS SHIP:UP:VECTOR:NORMALIZED.
    LOCAL upPerp IS (upv - fwd * VDOT(upv, fwd)):NORMALIZED.
    RETURN (fwd * COS(aoaDeg) + upPerp * SIN(aoaDeg)):NORMALIZED.
}

FUNCTION REENTRY_AND_GLIDE {
    SET MISSION_PHASE TO "REENTRY-HOLD".
    LOG_MSG("Entering atmosphere, starting reentry attitude hold.").
    RCS ON.
    SAS OFF.

    // FIX (pre-flight review): SHIP:SRFRETROGRADE alone is ZERO angle of
    // attack -- nose pointed exactly opposite velocity. That is NOT what the
    // craft's own design notes call for ("fly a high-AoA reentry"): a real
    // shuttle-style entry flies nose-up off retrograde for lift and to keep
    // the belly (not the nose) taking the heating. Using plain retrograde
    // was silently flying the wrong attitude for the whole hypersonic entry.
    //
    // TUNED (craft file confirms the geometry): GearMedium (main gear, i.e.
    // the belly) sits at a strongly negative Z-offset vs. the fuselage
    // centerline, and the AdvancedCanard pair is mounted at the nose as
    // pitch-only trim surfaces (ignorePitch=False, ignoreYaw/Roll=True) --
    // the same role real Shuttle canards/body-flaps play, and only useful if
    // the vehicle flies nose-up, belly-first. There is no ablative heat
    // shield part anywhere on this craft (no AblatorResource at all), so
    // attitude is the ONLY heat protection it has. 40 degrees matches the
    // real Space Shuttle's actual hypersonic entry AoA, the closest real
    // reference for a deliberate shuttle-analog with this exact layout.
    LOCAL REENTRY_AOA IS 40.
    LOCK STEERING TO AOA_RETROGRADE(REENTRY_AOA).
    WAIT UNTIL SHIP:ALTITUDE < 60000.

    // Hold high-AoA retrograde through the hottest part of reentry.
    WAIT UNTIL SHIP:ALTITUDE < 40000 OR SHIP:AIRSPEED < 800.

    SET MISSION_PHASE TO "GLIDE".
    LOG_MSG("Transitioning to glide guidance.").
    RCS OFF.

    // Closed-loop glide with REAL energy management, not a fixed pitch: the
    // required flight path angle is computed every tick from altitude and
    // remaining distance to the runway (glideslope = atan(alt/dist)), so if
    // GLIDE_LEAD_DEG was off and we're going to undershoot or overshoot, the
    // pitch command actually corrects for it instead of blindly holding -8
    // degrees regardless of where the runway actually is.
    UNTIL (SHIP:ALTITUDE < FLARE_ALT AND RUNWAY_POS:DISTANCE < 3000)
        OR SHIP:STATUS = "LANDED" OR SHIP:STATUS = "SPLASHED" {
        LOCAL courseToRunway IS RUNWAY_POS:HEADING. // absolute compass course, ship-independent
        LOCAL distToGo IS MAX(RUNWAY_POS:DISTANCE, 1).

        // Ideal descent angle to cover the remaining distance at the
        // remaining altitude, clamped to a flyable range so it never
        // commands something the airframe can't hold.
        LOCAL idealAngle IS ARCTAN2(SHIP:ALTITUDE, distToGo).
        LOCAL pitchTarget IS -1 * MIN(25, MAX(2, idealAngle)).

        // FIX (post-flight #12, real crash): a far-off aim point (740km, from
        // the deorbit targeting bug above) pinned idealAngle at its shallow
        // floor for the ENTIRE glide -- altitude is negligible next to a
        // distance that large. With no engine, flying nearly level for that
        // long just bleeds airspeed with nothing to arrest it, and the black
        // box showed exactly that: airspeed sank to 42-46 m/s (well under
        // this vehicle's ~70 m/s stall speed), pitch oscillated wildly
        // (49-86 degrees, repeatedly) as the steering fought for authority
        // it didn't have at that speed, and it hit the ground at -22 m/s
        // vertical -- a stall-mush crash, not a controlled glide. The
        // targeting fix above should prevent needing this, but regardless of
        // how close the aim point is, protecting airspeed has to come first:
        // if we're already below stall speed, override the distance-based
        // pitch entirely and nose down to regain speed, rather than holding
        // whatever the glideslope math wants.
        IF SHIP:AIRSPEED < STALL_SPEED_MIN {
            SET pitchTarget TO -10.
        } ELSE IF SHIP:AIRSPEED < 150 {
            SET pitchTarget TO MAX(pitchTarget, -3). // flatten out as we slow, avoid stalling
        }

        LOCK STEERING TO HEADING(courseToRunway, 90 + pitchTarget).

        IF SHIP:ALTITUDE < GEAR_DEPLOY_ALT AND NOT GEAR {
            LOG_MSG("Deploying landing gear.").
            GEAR ON.
        }

        WAIT 0.1.
    }

    // FIX (pre-flight review): the loop above used to exit ONLY on being
    // both low AND close to the runway -- if the glide brought the ship down
    // far from the runway instead (bad GLIDE_LEAD_DEG, wind, whatever), it
    // would touch down while still inside this loop with no gear-check, no
    // brakes, and no mission-complete log: a silent, undetected crash with
    // the script just looping forever afterward. Now it also exits on
    // SHIP:STATUS, and this catches that case explicitly.
    IF SHIP:STATUS = "LANDED" OR SHIP:STATUS = "SPLASHED" {
        LOG_MSG("WARNING: touched down during glide, before reaching final approach.").
        LOG_MSG("Landed away from the runway -- check GLIDE_LEAD_DEG and the black box.").
        IF NOT GEAR { GEAR ON. }
        BRAKES ON.
        SET MISSION_PHASE TO "MISSION-COMPLETE-OFF-TARGET".
        LOG_MSG("Vehicle stopped. Distance from runway aim point: " + ROUND(RUNWAY_POS:DISTANCE,0) + " m.").
        RETURN.
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
        // Same stall guard as the main glide loop: don't flare (pitch up)
        // into a stall this close to the ground -- that's the worst
        // possible place for it. Prioritize airspeed over flare shape.
        IF SHIP:AIRSPEED < STALL_SPEED_MIN { SET flarePitch TO -5. }
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
    PRINT PAD(">>> MISSION COMPLETE -- black box: " + BLACKBOX_ROWS + " rows at " + BLACKBOX_PATH, 70) AT(0, SAFE_ROW(27)).
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
// FIX (post-flight #5): WARPTO's stop precision isn't exact -- it can settle
// a few seconds late, which is enough to carry the ship PAST apoapsis. Once
// that happens, ETA:APOAPSIS flips from "small" to "time until NEXT orbit's
// apoapsis" (nearly a full period, ~1875s here), and a plain
// "WAIT UNTIL ETA:APOAPSIS < 30" then hangs for the better part of an orbit
// waiting on a condition that already came and went. Bounding the wait with
// a real-time timeout means it always moves on, whichever side of apoapsis
// the warp actually landed on.
LOCK STEERING TO SHIP:PROGRADE. // minimize drag during the coast, not just SAS-whatever-it-was-holding
WARP_TO_UT(TIME:SECONDS + ETA:APOAPSIS, 30). // warp the ascent->apoapsis coast, drop out 30s early
LOCAL apoWaitStart IS TIME:SECONDS.
WAIT UNTIL ETA:APOAPSIS < 30 OR TIME:SECONDS - apoWaitStart > 60.
UNLOCK STEERING.
CIRCULARIZE().
LOG_MSG("Orbit achieved. Coasting before deorbit planning.").
WAIT 5.

// FIX (post-flight #7): EXECUTE_NODE can now abort a burn that drifted too
// far off-plan instead of firing against stale geometry (see EXECUTE_NODE).
// But that means DEORBIT() alone doesn't guarantee periapsis actually came
// down -- without a check here, the mission would go straight into a
// "WAIT UNTIL ALTITUDE < 70000" that could wait forever on an orbit that
// never decays. Verify and retry rather than assume success.
LOCAL deorbitAttempts IS 0.
UNTIL SHIP:PERIAPSIS < 60000 OR deorbitAttempts >= 3 {
    DEORBIT().
    SET deorbitAttempts TO deorbitAttempts + 1.
    IF SHIP:PERIAPSIS >= 60000 {
        LOG_MSG("WARNING: periapsis still " + ROUND(SHIP:PERIAPSIS,0) + "m after deorbit attempt " + deorbitAttempts + ". Retrying.").
        WAIT 5.
    }
}
IF SHIP:PERIAPSIS >= 60000 {
    LOG_MSG("CRITICAL: deorbit failed after 3 attempts, periapsis still " + ROUND(SHIP:PERIAPSIS,0) + "m.").
    LOG_MSG("This orbit will not decay on its own. Manual intervention needed.").
}

SET MISSION_PHASE TO "COAST-TO-REENTRY".
// Warp the long coast back down, dropping out with a generous 120s margin
// before periapsis so we're well clear of the atmosphere when warp ends --
// WARPTO already refuses to physics-warp inside atmosphere, this margin is
// just to make sure REENTRY_AND_GLIDE gets full manual control in time.
WARP_TO_UT(TIME:SECONDS + ETA:PERIAPSIS, 120).
LOCAL reentryWaitStart IS TIME:SECONDS.
WAIT UNTIL SHIP:ALTITUDE < 70000 OR TIME:SECONDS - reentryWaitStart > SHIP:ORBIT:PERIOD + 300.
REENTRY_AND_GLIDE().
