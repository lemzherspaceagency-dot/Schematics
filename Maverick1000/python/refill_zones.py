#!/usr/bin/env python3
"""
Refills all copper zones on the real board using KiCad's real ZONE_FILLER
engine and saves the result. Earlier project history noted ZONE_FILLER.Fill()
"reliably segfaulting" in this headless environment -- re-tested this pass:
the actual issue was calling Fill() with a plain list() of the zones vector
(a SWIG typemap mismatch, not a crash). Calling Fill(board.Zones()) directly
with the native vector type works correctly and does not segfault.

Usage: python3 refill_zones.py
"""
import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board)
    ok = filler.Fill(board.Zones())
    print(f"Zone fill ok: {ok}  ({len(board.Zones())} zones)")
    board.Save(PCB_PATH)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
