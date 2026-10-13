"""Render original and refined atlases with identical geometry and lighting."""

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
from inspect_generated_asset import bounds, viewpoints, digest
from lion_material_tools import (prepare_lion_material, apply_lion_material,
                                 extract_zip_sources, image_pixels, preserve_atlas)


def main():
    source = ROOT / "generated" / "Lux3D_Lion_Base_glb.glb"
    textures = ROOT / "textures" / "generated"
    renders = ROOT / "renders" / "studies" / "material_study"
    renders.mkdir(parents=True, exist_ok=True)
    before = digest(source)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source), import_pack_images=True)
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    original = meshes[0].data.materials[0]
    original.use_fake_user = True
    source_links = [{"from_node": link.from_node.name, "from_socket": link.from_socket.name,
                     "to_node": link.to_node.name, "to_socket": link.to_socket.name}
                    for link in original.node_tree.links]
    bundle = prepare_lion_material(original, textures)
    auxiliary = []
    for node in original.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image != bundle["basecolor_image"]:
            path = preserve_atlas(node.image, textures, "original_metallicroughness_atlas")
            auxiliary.append({"source_image": node.image.name, "path": str(path),
                              "verified_source_channels": "G=roughness, B=metallic; verified material node links"})
    raw = extract_zip_sources(ROOT / "generated" / "Lux3D_Lion_Base_zip.zip", textures / "original_zip")
    scene = bpy.context.scene
    cameras = viewpoints(scene, bounds(meshes))
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("Material_Study_World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.12, 0.12, 0.12, 1)
    scene.world = world
    record = {"source_sha256_before": before, "source_material_links": source_links,
              "original_zip_files": raw, "auxiliary_source_maps": auxiliary,
              "material": bundle["report"], "renders": []}
    wanted = [camera for camera in cameras if camera.name in ("front_minus_y", "left_minus_x")]
    for stage in ("original", "refined"):
        if stage == "refined":
            apply_lion_material(meshes, bundle)
        for camera in wanted:
            scene.camera = camera
            path = renders / (stage + "_" + camera.name + ".png")
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            record["renders"].append(str(path))
    scene.camera = wanted[1]
    blend = blend_path("Lion_Material_Study.blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), check_existing=False)
    # Reopen derived color from disk to verify the persisted gamma and row order.
    disk = bpy.data.images.load(bundle["texture_paths"]["basecolor"], check_existing=False)
    expected = image_pixels(bundle["adjusted_basecolor_image"])
    actual = image_pixels(disk)
    record["saved_color_roundtrip_max_encoded_error"] = float(np.abs(expected[..., :3] - actual[..., :3]).max())
    record["saved_color_roundtrip_mean_encoded_error"] = float(np.abs(expected[..., :3] - actual[..., :3]).mean())
    record["source_sha256_after"] = digest(source)
    record["source_preserved"] = before == record["source_sha256_after"]
    record["blend"] = str(blend)
    path = ROOT / "docs" / "material_study.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print("Material study complete: %s" % path)


if __name__ == "__main__":
    main()
