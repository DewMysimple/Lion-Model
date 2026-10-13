"""Compare a generated buffer and a reloaded PNG in actual emission rendering."""

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
from lion_material_tools import create_png

bpy.ops.wm.read_factory_settings(use_empty=True)
out = ROOT / "docs" / "texture_color_probe"
out.mkdir(parents=True, exist_ok=True)
rgba = np.ones((2, 2, 4), dtype=np.float32)
rgba[..., :3] = (.659, .218, .190)
generated = create_png("Generated_RGB_Probe", rgba, out / "saved_probe.png", "sRGB")
reloaded = bpy.data.images.load(str(out / "saved_probe.png"), check_existing=False)
reloaded.colorspace_settings.name = "sRGB"
for index, image in enumerate((generated, reloaded)):
    material = bpy.data.materials.new("Probe_%d" % index)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs[0], output.inputs["Surface"])
    bpy.ops.mesh.primitive_plane_add(size=.9, location=(-.55 + index * 1.10, 0, 0))
    bpy.context.object.data.materials.append(material)
camera_data = bpy.data.cameras.new("Probe_Camera")
camera_data.type = "ORTHO"
camera_data.ortho_scale = 2.2
camera = bpy.data.objects.new("Probe_Camera", camera_data)
bpy.context.scene.collection.objects.link(camera)
camera.location = (0, 0, 3)
scene = bpy.context.scene
scene.camera = camera
scene.render.engine = "CYCLES"
scene.cycles.samples = 1
scene.view_settings.view_transform = "Standard"
scene.render.resolution_x = 440
scene.render.resolution_y = 220
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(out / "generated_left_file_right.png")
bpy.ops.render.render(write_still=True)
report = {"input_encoded_rgb": [.659, .218, .190],
          "generated_source": generated.source, "generated_is_float": generated.is_float,
          "reloaded_source": reloaded.source, "reloaded_is_float": reloaded.is_float,
          "render": scene.render.filepath}
(out / "texture_source_probe.json").write_text(json.dumps(report, indent=2))
print(report)
