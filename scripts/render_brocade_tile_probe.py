"""Render the actual texture repeated 3x3 under flat emission, without editing it."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


from pathlib import Path
import bpy

texture_path = ROOT / "textures" / "brocade_new" / "brocade_reference_synthesis.png"
bpy.ops.wm.read_factory_settings(use_empty=True)
image = bpy.data.images.load(str(texture_path), check_existing=False)
image.colorspace_settings.name = "sRGB"
image.pack()
material = bpy.data.materials.new("Brocade_Repeat_Probe_Emission")
material.use_nodes = True
nodes, links = material.node_tree.nodes, material.node_tree.links
nodes.clear()
texture = nodes.new("ShaderNodeTexImage")
texture.image = image
texture.extension = "REPEAT"
emission = nodes.new("ShaderNodeEmission")
output = nodes.new("ShaderNodeOutputMaterial")
links.new(texture.outputs["Color"], emission.inputs["Color"])
links.new(emission.outputs[0], output.inputs["Surface"])
bpy.ops.mesh.primitive_plane_add(size=3)
plane = bpy.context.object
plane.name = "Brocade_Three_By_Three_Repeat_Card"
plane.data.materials.append(material)
for loop in plane.data.uv_layers.active.data:
    loop.uv *= 3
camera_data = bpy.data.cameras.new("Repeat_Camera")
camera_data.type = "ORTHO"
camera_data.ortho_scale = 3
camera = bpy.data.objects.new("Repeat_Camera", camera_data)
bpy.context.scene.collection.objects.link(camera)
camera.location = (0, 0, 3)
scene = bpy.context.scene
scene.camera = camera
scene.render.engine = "CYCLES"
scene.cycles.samples = 1
scene.view_settings.view_transform = "Standard"
scene.render.resolution_x = scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(ROOT / "textures" / "brocade_new" / "brocade_three_by_three_repeat.png")
bpy.ops.render.render(write_still=True)
STUDIES.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(STUDIES / "Brocade_Tile_Probe.blend"), check_existing=False)
print("Actual texture 3x3 repeat rendered; seams at x/y=320 and 640")
