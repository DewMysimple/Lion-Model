"""Build real, reusable eye and bell geometry for later lion assembly.

Run with Blender 5.0 in background. This is a component kit, not the final lion.
All dimensions are normalized design dimensions pending fitting to the base.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import json
import math
from datetime import datetime, timezone
import bpy
from mathutils import Vector

PROJECT = ROOT
OUT = PROJECT / "blender" / "components"
RENDERS = PROJECT / "renders" / "studies" / "components"
OUT.mkdir(parents=True, exist_ok=True)
RENDERS.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

asset_collection = bpy.data.collections.new("Lion_Editable_Component_Kit")
bpy.context.scene.collection.children.link(asset_collection)
studio_collection = bpy.data.collections.new("Component_Preview_Studio")
bpy.context.scene.collection.children.link(studio_collection)


def move_to(obj, collection):
    for previous in list(obj.users_collection):
        previous.objects.unlink(obj)
    collection.objects.link(obj)


def parent_keep(obj, parent):
    bpy.context.view_layer.update()
    matrix = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = matrix
    bpy.context.view_layer.update()


def root(name, location):
    obj = bpy.data.objects.new(name, None)
    asset_collection.objects.link(obj)
    obj.location = location
    obj.empty_display_size = 0.12
    bpy.context.view_layer.update()
    return obj


def material(name, color, roughness, metallic=0, texture=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    if texture:
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 330
        noise.inputs["Detail"].default_value = 2
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.10
        bump.inputs["Distance"].default_value = 0.002
        mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        mat.node_tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


gold = material("Brass_Warm_Polished", (0.65, 0.37, 0.095), 0.23, 1, True)
copper = material("Copper_Red_Eye_Ring", (0.38, 0.075, 0.024), 0.25, 0.8, True)
black = material("Black_Lacquer", (0.009, 0.009, 0.012), 0.14)
eye_black = material("Black_Polished_Eye", (0.006, 0.004, 0.003), 0.065)
white = material("Ivory_White_Painted_Rim", (0.82, 0.78, 0.68), 0.29)
red = material("Red_Painted_Edge", (0.5, 0.011, 0.019), 0.36)
velour = material("Red_Velour_Growth_Base", (0.33, 0.003, 0.011), 0.73, texture=True)


def mesh_object(name, verts, faces, mat, parent=None):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    # Both radial constructions traverse the inward winding by default.
    mesh.from_pydata(verts, [], [tuple(reversed(face)) for face in faces])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    asset_collection.objects.link(obj)
    mesh.materials.append(mat)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    if parent:
        parent_keep(obj, parent)
    return obj


def oval_ring(name, center, radius, tube, mat, parent, aspect=(1, 1), count=128, sections=16):
    # Finite-thickness ring in the XZ plane, facing negative Y.
    cx, cy, cz = center
    verts = []
    faces = []
    for i in range(count):
        angle = math.tau * i / count
        sx, sz = math.cos(angle), math.sin(angle)
        for j in range(sections):
            phi = math.tau * j / sections
            radial = radius + tube * math.cos(phi)
            verts.append((cx + radial * sx * aspect[0],
                          cy + tube * math.sin(phi),
                          cz + radial * sz * aspect[1]))
    for i in range(count):
        for j in range(sections):
            faces.append((i * sections + j,
                          ((i + 1) % count) * sections + j,
                          ((i + 1) % count) * sections + (j + 1) % sections,
                          i * sections + (j + 1) % sections))
    return mesh_object(name, verts, faces, mat, parent)


def sphere(name, center, radius, mat, parent, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    move_to(obj, asset_collection)
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    parent_keep(obj, parent)
    return obj


def create_eye(side, cx):
    assembly = root("Eye_Assembly_" + side, (cx, 0, 1.72))
    assembly["purpose"] = "Independent reference-inspired layered craft eye; fitting and brows pending"
    assembly["reference_status"] = "Component study, not full-head acceptance"
    rings = [
        ("Outer_Red_Growth_Base", 0.68, 0.09, 0.04, velour),
        ("Outer_White_Painted_Rim", 0.584, 0.044, -0.04, white),
        ("Black_Outer_Eye_Outline", 0.536, 0.025, -0.075, black),
        ("Red_Inner_Eye_Outline", 0.504, 0.017, -0.095, red),
        ("White_Inner_Painted_Rim", 0.462, 0.029, -0.11, white),
        ("Black_Inner_Eye_Socket", 0.421, 0.025, -0.14, black),
    ]
    for name, radius, tube, depth, mat in rings:
        oval_ring(name + "_" + side, (cx, depth, 1.72), radius, tube, mat, assembly,
                  aspect=(0.90, 1.08))
    # The eyeball can rotate independently of all painted and growth-base rings.
    pivot = root("EyeBall_Rotation_" + side, (cx, -0.15, 1.72))
    parent_keep(pivot, assembly)
    pivot["control"] = "Rotate this empty to move the eye without moving the socket"
    ball_cx = cx + (0.07 if cx < 0 else -0.07)
    sphere("EyeBall_" + side, (ball_cx, -0.15, 1.72), 0.39, eye_black, pivot)
    oval_ring("Outer_Brass_Iris_" + side, (ball_cx, -0.412, 1.72), 0.278, 0.028, gold, pivot)
    oval_ring("Copper_Iris_" + side, (ball_cx, -0.449, 1.72), 0.239, 0.02, copper, pivot)
    oval_ring("Inner_Brass_Iris_" + side, (ball_cx, -0.468, 1.72), 0.210, 0.015, gold, pivot)
    sphere("Glossy_Black_Pupil_" + side, (ball_cx, -0.435, 1.72), 0.208, eye_black, pivot,
           scale=(1, 0.58, 1))
    return assembly


def create_bell():
    assembly = root("Bell_Assembly", (0, 0, 0.57))
    assembly["purpose"] = "Editable brass bell with actual bottom aperture, slits and suspension loop"
    radius = 0.29
    segments = 96
    rings = 38
    verts = []
    faces = []
    for i in range(rings + 1):
        angle = 0.035 + (math.pi - 0.3 - 0.035) * i / rings
        for j in range(segments):
            theta = math.tau * j / segments
            verts.append((radius * math.sin(angle) * math.cos(theta),
                          radius * math.sin(angle) * math.sin(theta),
                          0.57 + radius * math.cos(angle)))
    for i in range(rings):
        for j in range(segments):
            # Two real lower slits; their open boundaries get wall thickness.
            slit = i >= int(rings * 0.66) and j in (23, 24, 71, 72)
            if not slit:
                faces.append((i * segments + j,
                              i * segments + (j + 1) % segments,
                              (i + 1) * segments + (j + 1) % segments,
                              (i + 1) * segments + j))
    bell = mesh_object("Bell_Thin_Brass_Shell", verts, faces, gold, assembly)
    solid = bell.modifiers.new("Editable_Shell_Thickness", "SOLIDIFY")
    solid.thickness = 0.012
    bevel = bell.modifiers.new("Soft_Aperture_Edges", "BEVEL")
    bevel.width = 0.003
    bevel.segments = 2
    sphere("Bell_Internal_Clapper", (0, 0, 0.38), 0.06, copper, assembly)
    # A real loop penetrates the bell's top and can attach to the final ankle band.
    oval_ring("Bell_Suspension_Loop", (0, 0, 0.92), 0.088, 0.023, gold, assembly,
              aspect=(0.75, 1), count=64, sections=12)
    return assembly


eyes = [create_eye("L", -1.02), create_eye("R", 1.02)]
bell = create_bell()

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == "OPTIX"
scene.cycles.device = "GPU"
scene.render.resolution_x = 1400
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.world.color = (0.28, 0.28, 0.28)
scene.view_settings.view_transform = "AgX"

bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0.2))
floor = bpy.context.object
floor.name = "Studio_Ground"
move_to(floor, studio_collection)
floor.data.materials.append(material("Studio_Grey", (0.30, 0.31, 0.33), 0.8))


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


for name, loc, energy, size in [
    ("Key_Softbox", (-3.5, -4.2, 6), 500, 4),
    ("Fill_Softbox", (3, -2, 4), 350, 3),
    ("Back_Softbox", (0, 2.5, 5), 550, 3),
]:
    light_data = bpy.data.lights.new(name, "AREA")
    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    studio_collection.objects.link(light)
    light.location = loc
    aim(light, (0, 0, 1.2))

camera_data = bpy.data.cameras.new("Component_Study_Camera")
camera = bpy.data.objects.new("Component_Study_Camera", camera_data)
studio_collection.objects.link(camera)
camera.location = (1.8, -9, 4.1)
aim(camera, (0, 0, 1.35))
camera_data.type = "ORTHO"
camera_data.ortho_scale = 4.25
scene.camera = camera

blend_path = OUT / "Lion_Editable_Components.blend"
render_path = RENDERS / "eye_and_bell_study.png"
scene.render.filepath = str(render_path)
bpy.ops.object.select_all(action="DESELECT")
for component in asset_collection.objects:
    component.select_set(True)
export_dir = PROJECT / "exports" / "components"
export_dir.mkdir(parents=True, exist_ok=True)
glb_path = export_dir / "Lion_Editable_Components.glb"
bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", use_selection=True,
                         export_materials="EXPORT", export_animations=False, export_extras=True)
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
record = {
    "createdAt": datetime.now(timezone.utc).isoformat(),
    "status": "component-kit-saved-render-pending",
    "blend": str(blend_path),
    "componentGlb": str(glb_path),
    "blenderVersion": bpy.app.version_string,
    "assetMeshCount": sum(obj.type == "MESH" for obj in asset_collection.objects),
    "rawPolygonCount": sum(len(obj.data.polygons) for obj in asset_collection.objects if obj.type == "MESH"),
    "rootObjects": [obj.name for obj in eyes] + [bell.name],
    "limits": ["Not a complete lion model.", "Components require fitting to the generated base.",
               "Painted ring geometry and lacquer/brass materials are real; brows and hair are not included.",
               "No rigging or animation acceptance is claimed.",
               "The GLB keeps geometry and standard material factors; native procedural micro-bump is not baked.",
               "Bell slit and clapper construction is a functional inference, not directly measured from the reference.",
               "No external image texture dependencies are used."],
}
report_path = PROJECT / "docs" / "editable_components.json"
report_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
bpy.ops.render.render(write_still=True)
record["status"] = "component-kit-saved-render-created-awaiting-visual-review"
record["render"] = str(render_path)
record["renderDimensions"] = [scene.render.resolution_x, scene.render.resolution_y]
record["renderDevice"] = "OPTIX"
report_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps({"status": record["status"], "blend": str(blend_path), "render": str(render_path)}))
