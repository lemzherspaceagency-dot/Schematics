#!/usr/bin/env python3
"""Download + flatten the official Bambu Studio A1 mini profiles.

Resolves the `inherits` chains of the system presets into three flat JSON
files in ./bambu_profiles, which build_bambu_3mf.py turns into the project
settings of the .3mf. Only needs to run again to pick up newer presets.
"""
import json, os, urllib.parse, urllib.request

BASE = ("https://raw.githubusercontent.com/bambulab/BambuStudio/master/"
        "resources/profiles/BBL/")
PRESETS = {
    "machine": "Bambu Lab A1 mini 0.4 nozzle",
    "process": "0.16mm Optimal @BBL A1M",
    "filament": "Bambu PLA Basic @BBL A1M",
}
META = {"inherits", "instantiation", "setting_id", "type", "from"}


def get(kind, name):
    url = BASE + urllib.parse.quote(f"{kind}/{name}.json")
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def resolve(kind, name):
    d = get(kind, name)
    parent = d.get("inherits")
    out = resolve(kind, parent) if parent else {}
    out.update(d)
    return out


def main():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "bambu_profiles")
    os.makedirs(here, exist_ok=True)
    for kind, name in PRESETS.items():
        d = resolve(kind, name)
        d["name"] = name
        d = {k: v for k, v in d.items() if k not in META or k == "name"}
        with open(os.path.join(here, f"{kind}.json"), "w") as f:
            json.dump(d, f, indent=1, sort_keys=True)
        print(kind, name, len(d), "keys")


if __name__ == "__main__":
    main()
