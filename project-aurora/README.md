# Project Aurora: The Last Child

An original horror game — the FNaF-adjacent shape (an AI host, a facility,
tools an employee left behind) built into its own identity: nobody is
misunderstood, nothing is secretly on your side, and the thing chasing you
runs the whole building on purpose.

## This prototype

Per the project's own build rule — **one room, one mechanic, one
prototype, only then continue** — `room-one.html` is exactly that:

- **Room**: the Orpheon lobby. Front desk, a locked inner door, the
  "Let Our Song Guide You Here" signage, family-entertainment dressing.
- **Mechanic**: D.I.V.A. — the employee tool found behind the desk — makes
  Orpheon's command conduits visible and lets you tap a travelling signal
  and re-aim it at a different endpoint. It's built to counter Aurora's
  defining trait (she coordinates every robot in the building) rather than
  to grapple, scan, or extract like the tools it's deliberately not.
- **Beat**: Aurora's canon first encounter — she walks in, scans Daniel,
  welcomes him, and is gone the moment he looks away, with only a caption
  standing in for the mechanical shuffle that isn't wired to real audio yet.

Open `room-one.html` in a browser (WebGL required) or play it published
as a Claude Artifact. No build step — it's one static file, Three.js
loaded from cdnjs.

**Controls**: WASD move · mouse look (click to lock the pointer) · E
interact · hold right-click to trace with D.I.V.A.

## What's deliberately not here yet

No audio at all — the "mechanical shuffling" is a bracketed caption, not a
sound. No second room. Aurora's behavior in this slice is scripted
(timers and lerps), not a real AI director. All three are exactly the kind
of thing "only then continue" means: prove the room and the mechanic
first, build the next piece once this one is worth building on.
