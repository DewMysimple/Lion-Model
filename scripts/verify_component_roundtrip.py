"""Validate the local component GLB against its saved Blender import (no scene edits saved)."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

import bpy


project = ROOT
source = project / "exports/components/Lion_Editable_Components.glb"
inspection = project / "docs/component_roundtrip_check"
raw = source.read_bytes()
json_length, chunk_type = struct.unpack_from("<II", raw, 12)
assert chunk_type == 0x4E4F534A, "GLB first chunk must be JSON."
gltf = json.loads(raw[20:20 + json_length].decode("utf-8"))
parents = {child: parent for parent, node in enumerate(gltf["nodes"])
           for child in node.get("children", [])}
checks = []
for index, node in enumerate(gltf["nodes"]):
    obj = bpy.data.objects.get(node["name"])
    expected_parent = gltf["nodes"][parents[index]]["name"] if index in parents else None
    expected_type = "MESH" if "mesh" in node else "EMPTY"
    expected_materials, expected_triangles = [], None
    if "mesh" in node:
        primitives = gltf["meshes"][node["mesh"]]["primitives"]
        expected_materials = list(dict.fromkeys(gltf["materials"][item["material"]]["name"]
                                               for item in primitives if "material" in item))
        assert all(item.get("mode", 4) == 4 for item in primitives), "Only triangle primitives are checked."
        expected_triangles = sum(gltf["accessors"][item["indices"]]["count"] // 3 for item in primitives)
    actual_materials = [slot.material.name for slot in obj.material_slots if slot.material] if obj else []
    actual_triangles = None
    if obj and obj.type == "MESH":
        obj.data.calc_loop_triangles()
        actual_triangles = len(obj.data.loop_triangles)
    checks.append({"node": node["name"], "expected_parent": expected_parent,
                   "actual_parent": obj.parent.name if obj and obj.parent else None,
                   "expected_type": expected_type, "actual_type": obj.type if obj else None,
                   "expected_materials": expected_materials, "actual_materials": actual_materials,
                   "expected_triangles": expected_triangles, "actual_triangles": actual_triangles,
                   "passed": bool(obj) and obj.type == expected_type
                       and (obj.parent.name if obj.parent else None) == expected_parent
                       and actual_materials == expected_materials and actual_triangles == expected_triangles})
materials = []
for material in gltf["materials"]:
    actual = bpy.data.materials.get(material["name"])
    shader = next((node for node in actual.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    pbr = material.get("pbrMetallicRoughness", {})
    expected = {"base_color": pbr.get("baseColorFactor", [1, 1, 1, 1]),
                "metallic": pbr.get("metallicFactor", 1), "roughness": pbr.get("roughnessFactor", 1)}
    observed = {"base_color": list(shader.inputs["Base Color"].default_value),
                "metallic": shader.inputs["Metallic"].default_value,
                "roughness": shader.inputs["Roughness"].default_value}
    passed = all(abs(a - b) < 1e-6 for a, b in zip(expected["base_color"], observed["base_color"]))
    passed = passed and all(abs(expected[key] - observed[key]) < 1e-6 for key in ("metallic", "roughness"))
    materials.append({"name": material["name"], "source_pbr": expected, "imported_pbr": observed, "passed": passed})
pngs = []
for path in sorted((inspection / "renders").glob("*.png")):
    image = bpy.data.images.load(str(path), check_existing=False)
    pngs.append({"file": str(path), "dimensions": list(image.size), "passed": list(image.size) == [384, 384]})
    bpy.data.images.remove(image)
report = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
          "scope": "Local eye/ring/bell component GLB only; not cloud generation or full-lion acceptance. "
                   "Checks compare node hierarchy, mesh triangles/material slots and standard PBR factors; "
                   "native procedural micro-bump is not present in this GLB.",
          "source_sha256": hashlib.sha256(raw).hexdigest(), "objects": checks, "materials": materials,
          "render_images": pngs,
          "passed": all(item["passed"] for item in checks + materials + pngs) and len(pngs) == 6}
(inspection / "roundtrip_verification.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
assert report["passed"], "Component roundtrip checks failed; inspect roundtrip_verification.json."
print("Component roundtrip passed: %d nodes, %d materials, %d PNGs." % (len(checks), len(materials), len(pngs)))
