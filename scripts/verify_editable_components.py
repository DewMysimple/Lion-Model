"""Audit the saved component .blend in a separate Blender process."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import json
from datetime import datetime, timezone
import bmesh
import bpy
from mathutils import Vector

PROJECT = ROOT
collection = bpy.data.collections.get("Lion_Editable_Component_Kit")
if not collection:
    raise RuntimeError("Component collection missing from reopened file")
roots = [bpy.data.objects.get(name) for name in ("Eye_Assembly_L", "Eye_Assembly_R", "Bell_Assembly")]
checks = {
    "source_file_reopened": Path(bpy.data.filepath).is_file(),
    "independent_component_roots_exist": all(roots),
    "eye_rotation_controls_exist": all(bpy.data.objects.get("EyeBall_Rotation_" + side) for side in ("L", "R")),
    "bell_editable_shell_exists": bpy.data.objects.get("Bell_Thin_Brass_Shell") is not None,
}
records = []
depsgraph = bpy.context.evaluated_depsgraph_get()
for obj in collection.objects:
    if obj.type != "MESH":
        continue
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    topology = bmesh.new()
    try:
        topology.from_mesh(mesh)
        closed = all(edge.is_manifold for edge in topology.edges)
        volume = topology.calc_volume(signed=True) if closed else None
        records.append({
            "name": obj.name,
            "parent": obj.parent.name if obj.parent else None,
            "basePolygons": len(obj.data.polygons),
            "evaluatedPolygons": len(mesh.polygons),
            "evaluatedClosed": closed,
            "evaluatedSignedVolume": volume,
            "materialNames": [slot.material.name if slot.material else None for slot in obj.material_slots],
            "boundsWorld": [list(obj.matrix_world @ Vector(corner)) for corner in obj.bound_box],
        })
    finally:
        topology.free()
        evaluated.to_mesh_clear()
checks["all_components_have_materials"] = all(record["materialNames"] and all(record["materialNames"]) for record in records)
checks["evaluated_components_closed"] = all(record["evaluatedClosed"] for record in records)
checks["closed_component_normals_outward"] = all(record["evaluatedSignedVolume"] is not None and record["evaluatedSignedVolume"] > 0 for record in records)
external_images = [image.filepath for image in bpy.data.images if image.source == "FILE" and not image.packed_file]
checks["no_unpacked_external_file_images"] = not external_images
data = {
    "checkedAt": datetime.now(timezone.utc).isoformat(),
    "sourceBlend": bpy.data.filepath,
    "checks": checks,
    "meshRecords": records,
    "scope": "Saved local eye/bell component kit only; not final lion acceptance.",
    "visualReview": "Rendered component study was inspected; earlier parenting placement defect was corrected. Eye frames remain a normalized component study requiring brow fitting and head integration.",
}
report = PROJECT / "docs" / "editable_components_reopen_check.json"
report.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(json.dumps({"checks": checks, "report": str(report)}))
if not all(checks.values()):
    raise RuntimeError("Reopened component audit failed; inspect the report")
