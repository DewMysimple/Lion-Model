"""Verify native spline editability after reopening the actual saved test file."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
from datetime import datetime, timezone
import json
import math
import bpy
from mathutils import Vector

PROJECT = ROOT
collection = bpy.data.collections.get('Component_Red_Velvet_Fiber_Test')
objects = list(collection.objects) if collection else []
checks = dict(reopened_saved_fiber_file=Path(bpy.data.filepath).name == 'Lion_Fiber_Component_Test.blend',
              two_separate_emitter_curve_objects=len(objects) == 2,
              native_curve_types_preserved=all(obj.type == 'CURVE' for obj in objects))
strands = sum(len(obj.data.splines) for obj in objects)
checks['actual_32000_strands_persisted'] = strands == 32000
checks['finite_editable_3d_points_persisted'] = all(
    spline.type == 'BEZIER' and 3 <= len(spline.bezier_points) <= 6
    and all(math.isfinite(axis) for point in spline.bezier_points for axis in point.co)
    for obj in objects for spline in obj.data.splines)
checks['parents_and_collection_persisted'] = all(
    obj.parent and obj.parent.name.startswith('Outer_Red_Growth_Base_') and collection in obj.users_collection
    for obj in objects)
checks['taper_persisted'] = all(
    spline.bezier_points[-1].radius < spline.bezier_points[0].radius
    for obj in objects for spline in obj.data.splines)
checks['native_control_point_is_editable'] = False
if objects:
    point = objects[0].data.splines[0].bezier_points[1]
    previous = point.co.copy()
    point.co += Vector((0.001, 0, 0))
    checks['native_control_point_is_editable'] = abs(point.co.x - previous.x - 0.001) < 1e-6
    point.co = previous
report = dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),
    file=bpy.data.filepath, blender=bpy.app.version_string, actual_curve_objects=len(objects),
    actual_strands=strands, checks=checks,
    scope='Reopened native eye-ring fiber sample only. No full-lion fur acceptance is claimed.')
path = PROJECT / 'docs' / 'fiber_component_reopen_check.json'
path.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
if not all(checks.values()):
    raise RuntimeError('Saved editable fiber verification failed')
