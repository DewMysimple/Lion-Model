"""Reopen detailed partitions and compare per-source-face geometry/UV/normals."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(ROOT / "scripts"))
from separate_lion_details import snapshot, mesh_buffers


def objects():
    return [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("Lion_")]


bpy.ops.wm.open_mainfile(filepath=str(blend_path("Lion_Parts_Working.blend")))
before = snapshot(objects())
bpy.ops.wm.open_mainfile(filepath=str(blend_path("Lion_Detailed_Parts.blend")))
after = snapshot(objects())
if len(after) != 286200 or set(before) != set(after):
    raise RuntimeError("Source triangle provenance failed after reopen")
max_position_delta = 0
uv_exact = True
for source_id in before:
    a_positions, a_uvs, _ = before[source_id]
    b_positions, b_uvs, _ = after[source_id]
    max_position_delta = max(max_position_delta, float(np.abs(a_positions - b_positions).max()))
    uv_exact &= np.array_equal(a_uvs, b_uvs)
normal_attribute_exact = True
for obj in objects():
    attribute = obj.data.attributes.get("source_corner_normal")
    if attribute is None:
        continue
    buffer = mesh_buffers(obj.data)
    vectors = np.empty(len(obj.data.loops) * 3, dtype=np.float32)
    attribute.data.foreach_get("vector", vectors)
    vectors = vectors.reshape(-1, 3, 3)
    for index, source_id in enumerate(buffer["source_ids"]):
        normal_attribute_exact &= np.array_equal(vectors[index], before[int(source_id)][2])
record = {"saved_source_faces": len(after), "each_original_face_present_once": True,
          "uv_values_exact_after_reopen": uv_exact,
          "max_world_position_delta_after_reopen_m": max_position_delta,
          "source_corner_normal_attributes_exact_after_reopen": normal_attribute_exact,
          "native_normal_note": "Native Blender custom-normal re-encoding error is recorded separately in detail_parts_report.json"}
if not uv_exact or max_position_delta != 0 or not normal_attribute_exact:
    raise RuntimeError("Saved detailed parts geometry/UV/vector preservation failed")
(ROOT / "docs" / "detail_parts_reopen_verification.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print("Detailed parts reopened: 286200 source faces once; world positions, UVs and source normal attributes unchanged")
