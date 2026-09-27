#!/usr/bin/env python3
"""Build a ready-to-print Bambu Studio project for the Bambu Lab A1 mini.

Writes out/spiro51_A1mini.3mf with:
  * printer  : Bambu Lab A1 mini 0.4 nozzle, Textured PEI plate
  * filament : Bambu PLA Basic
  * process  : 0.16mm Optimal @BBL A1M + tweaks for small functional parts
  * 3 plates : 1) base (print first to test the basket fit)
               2) mechanism: planet, lid, knob
               3) stand (optional)
  * per-part overrides (walls, infill, seam, brim) where they matter

The printer/process/filament presets come from the official Bambu Studio
profiles (see fetch_profiles.py; cached in ./bambu_profiles).
"""
import json
import os
import uuid
import zipfile

import numpy as np

import generate as g

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
APP_VERSION = "02.00.00.95"
BED = 180.0
PLATE_STRIDE = BED * 1.2      # Bambu Studio lays plates out with a 20 % gap

# Changes on top of "0.16mm Optimal @BBL A1M" for the whole project
PROCESS_OVERRIDES = {
    "wall_loops": "3",
    "sparse_infill_pattern": "gyroid",
    "sparse_infill_density": "15%",
    "top_shell_layers": "6",
    "bottom_shell_layers": "4",
    "seam_position": "aligned",
    # the base prints upside down on its top rim; the lid skirt has to slide
    # over that edge, so don't let elephant's foot eat the 0.25 mm clearance
    "elefant_foot_compensation": "0.15",
    "enable_support": "0",
    "brim_type": "auto_brim",
}

# Per-part overrides (object level in Bambu Studio)
PART_SETTINGS = {
    "base": {
        # random seam keeps a seam ridge off the ring-gear teeth
        "seam_position": "random",
    },
    "planet": {
        "wall_loops": "4",            # solid teeth + solid tube round needles
        "sparse_infill_density": "25%",
        "seam_position": "random",
    },
    "carrier": {
        "wall_loops": "4",            # snap pin ends up solid = strong
    },
    "knob": {
        "wall_loops": "4",
        "brim_type": "outer_only",    # 25 mm tall on a 13 mm footprint
        "brim_width": "4",
    },
    "stand": {
        "wall_loops": "2",
        "sparse_infill_density": "10%",
    },
}

PLATES = [
    ("1 - Base (print first, test fit in basket)", {"base": (90, 90)}),
    ("2 - Mechanism (planet, lid, knob)",
     {"carrier": (62, 90), "planet": (136, 118), "knob": (136, 52)}),
    ("3 - Stand (optional)", {"stand": (90, 90)}),
]

PART_NAMES = {
    "base": "Spiro51 Base", "planet": "Spiro51 Planet (needles)",
    "carrier": "Spiro51 Lid", "knob": "Spiro51 Knob",
    "stand": "Spiro51 Stand",
}


def load_profiles():
    prof = {}
    for kind in ("machine", "process", "filament"):
        with open(os.path.join(HERE, "bambu_profiles", f"{kind}.json")) as f:
            prof[kind] = json.load(f)
    return prof


def project_settings(prof):
    machine, process, filament = (prof["machine"], prof["process"],
                                  prof["filament"])
    cfg = {}
    for d in (machine, process, filament):
        cfg.update({k: v for k, v in d.items() if k != "name"})
    cfg.update(PROCESS_OVERRIDES)
    cfg.update({
        "name": "project_settings",
        "from": "project",
        "version": APP_VERSION,
        "printer_settings_id": machine["name"],
        "print_settings_id": process["name"],
        "filament_settings_id": [filament["name"]],
        "inherits_group": [process["name"], filament["name"], machine["name"]],
        "different_settings_to_system": [
            ";".join(sorted(PROCESS_OVERRIDES)), "", ""],
        "print_compatible_printers": process.get("compatible_printers", []),
        "curr_bed_type": "Textured PEI Plate",
        "filament_colour": ["#161616"],
        "default_filament_colour": [""],
        "filament_ids": [filament.get("filament_id", "GFA00")],
        "filament_settings_id": [filament["name"]],
    })
    return cfg


def object_model_xml(obj_id, obj_uuid, verts, faces):
    v = "\n".join(f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>'
                  for x, y, z in verts)
    t = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>'
                  for a, b, c in faces)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <resources>
  <object id="{obj_id}" p:UUID="{obj_uuid}" type="model">
   <mesh>
    <vertices>
{v}
    </vertices>
    <triangles>
{t}
    </triangles>
   </mesh>
  </object>
 </resources>
 <build/>
</model>
'''


def main():
    os.makedirs(OUT, exist_ok=True)
    prof = load_profiles()
    makers = {"base": g.make_base, "planet": g.make_planet,
              "carrier": g.make_carrier, "knob": g.make_knob,
              "stand": g.make_stand}

    files = {}
    res_objs, build_items, obj_cfg, plate_cfg = [], [], [], []
    next_id = 1
    ident = 100
    for p_idx, (plate_name, parts) in enumerate(PLATES):
        col, row = p_idx % 2, p_idx // 2
        ox, oy = col * PLATE_STRIDE, -row * PLATE_STRIDE
        instances = []
        for key, (px, py) in parts.items():
            m = g.print_orientation(key, makers[key]())
            mesh = m.to_mesh()
            verts = np.array(mesh.vert_properties)[:, :3].copy()
            faces = np.array(mesh.tri_verts)
            # centre the mesh in XY, bottom on z = 0
            verts[:, 0] -= (verts[:, 0].min() + verts[:, 0].max()) / 2
            verts[:, 1] -= (verts[:, 1].min() + verts[:, 1].max()) / 2
            verts[:, 2] -= verts[:, 2].min()

            mesh_id, obj_id = next_id, next_id + 1
            next_id += 2
            path = f"3D/Objects/object_{mesh_id}.model"
            files[path] = object_model_xml(mesh_id, str(uuid.uuid4()),
                                           verts, faces)
            res_objs.append(
                f'  <object id="{obj_id}" p:UUID="{uuid.uuid4()}" '
                f'type="model">\n   <components>\n'
                f'    <component p:path="/{path}" objectid="{mesh_id}" '
                f'p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
                f'\n   </components>\n  </object>')
            build_items.append(
                f'  <item objectid="{obj_id}" p:UUID="{uuid.uuid4()}" '
                f'transform="1 0 0 0 1 0 0 0 1 {ox + px:.4f} {oy + py:.4f} 0" '
                f'printable="1"/>')
            name = PART_NAMES[key]
            settings = "".join(
                f'\n    <metadata key="{k}" value="{v}"/>'
                for k, v in PART_SETTINGS.get(key, {}).items())
            obj_cfg.append(f'''  <object id="{obj_id}">
    <metadata key="name" value="{name}"/>
    <metadata key="extruder" value="1"/>{settings}
    <metadata face_count="{len(faces)}"/>
    <part id="{mesh_id}" subtype="normal_part">
      <metadata key="name" value="{name}"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <metadata key="source_object_id" value="0"/>
      <metadata key="source_volume_id" value="0"/>
      <metadata key="source_offset_x" value="0"/>
      <metadata key="source_offset_y" value="0"/>
      <metadata key="source_offset_z" value="0"/>
      <mesh_stat face_count="{len(faces)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>''')
            ident += 1
            instances.append(f'''    <model_instance>
      <metadata key="object_id" value="{obj_id}"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="{ident}"/>
    </model_instance>''')
        n = p_idx + 1
        plate_cfg.append(f'''  <plate>
    <metadata key="plater_id" value="{n}"/>
    <metadata key="plater_name" value="{plate_name}"/>
    <metadata key="locked" value="false"/>
    <metadata key="gcode_file" value=""/>
{chr(10).join(instances)}
  </plate>''')

    main_model = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">
 <metadata name="Application">BambuStudio-{APP_VERSION}</metadata>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <metadata name="Title">Spiro51 - spirograph WDT for DeLonghi Dedica (51 mm)</metadata>
 <metadata name="Designer">Spiro51</metadata>
 <metadata name="Description">Planetary gear WDT tool for 51 mm DeLonghi portafilters. Print plate 1 first and test the fit in your basket. Needles: 12x 0.25 x 40 mm acupuncture needles.</metadata>
 <resources>
{chr(10).join(res_objs)}
 </resources>
 <build>
{chr(10).join(build_items)}
 </build>
</model>
'''
    model_settings = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
                      + "\n".join(obj_cfg) + "\n" + "\n".join(plate_cfg)
                      + "\n</config>\n")
    files["3D/3dmodel.model"] = main_model
    files["Metadata/model_settings.config"] = model_settings
    files["Metadata/project_settings.config"] = json.dumps(
        project_settings(prof), indent=4, sort_keys=True)
    files["[Content_Types].xml"] = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>
'''
    files["_rels/.rels"] = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
'''
    rel_lines = "\n".join(
        f' <Relationship Target="/{p}" Id="rel-{i}" '
        f'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        for i, p in enumerate(sorted(k for k in files
                                     if k.startswith("3D/Objects/")), 1))
    files["3D/_rels/3dmodel.model.rels"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns='
        '"http://schemas.openxmlformats.org/package/2006/relationships">\n'
        + rel_lines + "\n</Relationships>\n")

    path = os.path.join(OUT, "spiro51_A1mini.3mf")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ["[Content_Types].xml", "_rels/.rels"] + sorted(
                k for k in files if k not in ("[Content_Types].xml",
                                              "_rels/.rels")):
            z.writestr(name, files[name])
    print("wrote", path, f"{os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
