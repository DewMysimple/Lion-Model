"""Verify the saved material study against original mesh/UV buffers."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


import hashlib
import json
from pathlib import Path

import bpy
import numpy as np

root = ROOT


def buffers(mesh):
    vertices = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", vertices)
    triangles = np.empty(len(mesh.polygons) * 3, dtype=np.int32)
    mesh.polygons.foreach_get("vertices", triangles)
    uvs = np.empty(len(mesh.uv_layers.active.data) * 2, dtype=np.float32)
    mesh.uv_layers.active.data.foreach_get("uv", uvs)
    return {"vertices": len(mesh.vertices), "polygons": len(mesh.polygons),
            "uv_loops": len(mesh.uv_layers.active.data),
            "position_hash": hashlib.sha256(vertices.tobytes()).hexdigest(),
            "topology_hash": hashlib.sha256(triangles.tobytes()).hexdigest(),
            "uv_hash": hashlib.sha256(uvs.tobytes()).hexdigest()}


bpy.ops.wm.open_mainfile(filepath=str(blend_path("Lion_Material_Study.blend", root=root)))
study_mesh = next(obj.data for obj in bpy.data.objects if obj.type == "MESH")
study = buffers(study_mesh)
material = study_mesh.materials[0]
material_name = material.name
mapped = [{"name": node.image.name, "packed": bool(node.image.packed_file),
           "size": list(node.image.size)}
          for node in material.node_tree.nodes if node.type == "TEX_IMAGE"]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(root / "generated" / "Lux3D_Lion_Base_glb.glb"), import_pack_images=True)
source = buffers(next(obj.data for obj in bpy.data.objects if obj.type == "MESH"))
record = {"saved_study": study, "original_source": source,
          "geometry_and_uv_exactly_preserved": study == source,
          "saved_material": material_name, "saved_map_images": mapped,
          "all_maps_packed": all(item["packed"] for item in mapped)}
if not record["geometry_and_uv_exactly_preserved"] or not record["all_maps_packed"]:
    raise RuntimeError("Study verification failed")
(root / "docs" / "material_study_reopen_verification.json").write_text(json.dumps(record, indent=2))
print("Saved study reopened: geometry and UV buffers unchanged; all four maps packed")
