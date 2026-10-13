"""Actual Blender test on copied eye-ring components, never the final lion."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys
import bpy
from mathutils import Vector

PROJECT = ROOT
sys.path.insert(0, str(PROJECT / 'scripts'))
from fiber_tools import create_fibers

source = Path(bpy.data.filepath)
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
emitters = [bpy.data.objects['Outer_Red_Growth_Base_' + side] for side in ('L', 'R')]
original_meshes = {obj.name: (len(obj.data.vertices), len(obj.data.polygons)) for obj in emitters}
collection = bpy.data.collections.new('Component_Red_Velvet_Fiber_Test')
bpy.context.scene.collection.children.link(collection)
mat = bpy.data.materials.new('Component_Test_Crimson_Fine_Fibers')
mat.use_nodes = True
shader = mat.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value = (0.43, 0.006, 0.018, 1)
shader.inputs['Roughness'].default_value = 0.68
shader.inputs['Sheen Weight'].default_value = 0.25
shader.inputs['Sheen Roughness'].default_value = 0.62

results = create_fibers(emitters, count=16000, length=(0.012, 0.03),
    radius=(0.00012, 0.0002), direction=(0, 0, -1), direction_strength=0.36,
    droop=0.2, angular_spread=0.40, bend=0.22, clump=0.22,
    clump_count=160, clump_radius=0.05, point_count=(3, 6),
    seed=173, triangle_filter=lambda tri: tri['normal'].y < -0.05,
    collection=collection, material=mat, resolution=3, max_splines_per_object=16000)

checks = dict(source_mesh_counts_preserved=all(
    (len(obj.data.vertices), len(obj.data.polygons)) == original_meshes[obj.name] for obj in emitters))
fiber_objects = [obj for result in results for obj in result.objects]
checks['all_native_3d_curve_objects'] = all(obj.type == 'CURVE' and obj.data.dimensions == '3D'
                                           for obj in fiber_objects)
checks['per_emitter_parent_preserved'] = all(obj.parent == result.emitter
                                            for result in results for obj in result.objects)
checks['all_strands_editable_bezier_3_to_6_points'] = all(
    spline.type == 'BEZIER' and 3 <= len(spline.bezier_points) <= 6
    for obj in fiber_objects for spline in obj.data.splines)
checks['all_tips_finer_than_roots'] = all(spline.bezier_points[-1].radius < spline.bezier_points[0].radius
    for obj in fiber_objects for spline in obj.data.splines)
checks['requested_count_created'] = sum(len(obj.data.splines) for obj in fiber_objects) == 32000
checks['lengths_and_radii_vary'] = all(
    result.stats['length_requested_range'][1] > result.stats['length_requested_range'][0]
    and result.stats['radius_root_range'][1] > result.stats['radius_root_range'][0]
    for result in results)

# Check a real emitter transform moves its child fibers by the same delta, then
# restore it before saving. This does not claim mesh deformation binding.
emitter = emitters[0]
child = results[0].objects[0]
bpy.context.view_layer.update()
before = child.matrix_world.translation.copy()
original_location = emitter.location.copy()
emitter.location.x += 0.1
bpy.context.view_layer.update()
after = child.matrix_world.translation.copy()
checks['emitter_transform_moves_fibers'] = abs((after - before).x - 0.1) < 1e-6
emitter.location = original_location
bpy.context.view_layer.update()

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.cycles.device = 'GPU'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == 'OPTIX'
camera = scene.camera
camera.location = (-0.93, -3.6, 1.9)
camera.rotation_euler = (Vector((-1.02, 0, 1.72)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 1.88
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
out_blend = PROJECT / 'blender' / 'components' / 'Lion_Fiber_Component_Test.blend'
out_render = PROJECT / 'renders' / 'studies' / 'components' / 'red_velvet_fiber_test.png'
scene.render.filepath = str(out_render)
scene['fiber_test_scope'] = 'Eye-ring component sample only, not full-lion fur completion.'
scene['fiber_test_source'] = str(source)
scene['fiber_strand_count'] = 32000
if not all(checks.values()):
    raise RuntimeError('Fiber checks failed: ' + json.dumps(checks))
bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
bpy.ops.render.render(write_still=True)
checks['original_file_hash_unchanged'] = hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
report = dict(checked_at_utc=datetime.now(timezone.utc).isoformat(), blender=bpy.app.version_string,
              source_blend=str(source), source_sha256=source_hash, blend=str(out_blend),
              render=str(out_render), render_dimensions=[512, 512],
              actual_curve_objects=len(fiber_objects), actual_strands=32000,
              checks=checks, results=[result.stats for result in results],
              scope='Native editable fibers on two eye-ring red bases; not a complete lion.',
              limitations=['Static surface sampling: regeneration or binding required after mesh deformation.',
                  'GLB export requires curve conversion on an export copy; original native curves stay editable.',
                  'Component scale is a fitting study; model surface masks/density need adjustment after fitting.',
                  'This 512px render checks actual curve geometry but cannot prove full-lion fur fidelity.',
                  'length describes initial growth vector; bending/droop changes arc length.'])
report_path = PROJECT / 'docs' / 'fiber_component_test.json'
report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'report': str(report_path), 'curve_objects': len(fiber_objects),
                  'strands': 32000, 'checks': checks}))
