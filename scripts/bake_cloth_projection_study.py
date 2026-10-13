"""Bake the real projection study's Body base color to its original 4096px UV.

Only a new study .blend, PNG and technical report are written. EMIT baking
avoids baking studio illumination into the already photographed base color.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import argparse
import sys
import bpy
import numpy as np



def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', default='')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if any(character not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for character in args.variant):
        raise ValueError('Variant must use ASCII letters, digits, underscore or hyphen')
    suffix = ('_' + args.variant) if args.variant else ''
    source = blend_path('Lion_Cloth_Projection_Study_v2.blend')
    target = STUDIES/('Lion_Cloth_Projection_Baked_Study' + suffix + '.blend')
    texture = ROOT/('textures/cloth_projection/lion_body_reference_projection_4096' + suffix + '.png')
    report = ROOT/('docs/cloth_projection_bake_study' + suffix + '.json')
    if target.exists() or texture.exists() or report.exists():
        raise FileExistsError('Bake study output exists; preserve the existing version')
    before = sha(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    body = bpy.data.objects['Lion_Body']
    original_uv = next(layer for layer in body.data.uv_layers if layer.name != 'ReferenceClothWorldYZ_PositiveX')
    body.data.uv_layers.active = original_uv
    for layer in body.data.uv_layers:
        layer.active_render = layer == original_uv
    source_atlas = None
    for material in body.data.materials:
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image and ('lion_basecolor_refined' in node.image.name or 'original_basecolor' in node.image.name):
                source_atlas = node.image
                break
    if source_atlas is None:
        # Preserve unrelated UV islands using the actual source atlas from disk.
        source_atlas = bpy.data.images.load(str(ROOT/'textures/generated/lion_basecolor_refined.png'), check_existing=False)
    # A fresh generated image has no stale packed source bytes.
    baked = bpy.data.images.new('Body_Reference_Projection_4096_OriginalUV', width=4096, height=4096, alpha=True)
    baked.colorspace_settings.name = 'sRGB'
    values = np.empty(len(source_atlas.pixels), np.float32)
    source_atlas.pixels.foreach_get(values)
    pixels = values.reshape(source_atlas.size[1], source_atlas.size[0], 4)
    yi = np.minimum((np.arange(4096)*source_atlas.size[1]/4096).astype(int), source_atlas.size[1]-1)
    xi = np.minimum((np.arange(4096)*source_atlas.size[0]/4096).astype(int), source_atlas.size[0]-1)
    baked.pixels.foreach_set(pixels[yi[:, None], xi[None, :], :].ravel())
    baked.update()
    replaced = []
    temporary = []
    for material in body.data.materials:
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        shader = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
        output = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL' and node.is_active_output)
        prior_surface = output.inputs['Surface'].links[0].from_socket
        color = shader.inputs['Base Color']
        color_socket = color.links[0].from_socket if color.links else None
        emission = nodes.new('ShaderNodeEmission')
        if color_socket:
            links.new(color_socket, emission.inputs['Color'])
        else:
            emission.inputs['Color'].default_value = color.default_value
        links.new(emission.outputs[0], output.inputs['Surface'])
        image_node = nodes.new('ShaderNodeTexImage')
        image_node.image = baked
        for node in nodes:
            node.select = False
        image_node.select = True
        nodes.active = image_node
        temporary.append((material, emission, image_node, output, prior_surface, shader))
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 1
    scene.render.bake.use_clear = False
    scene.render.bake.margin = 8
    bpy.ops.object.bake(type='EMIT', use_clear=False, margin=8)
    texture.parent.mkdir(parents=True, exist_ok=True)
    baked.filepath_raw = str(texture)
    baked.file_format = 'PNG'
    baked.save()
    # A copied packed image can retain the original packed bytes on reopen.
    # Load the real newly saved PNG independently and pack that exact file.
    verified_disk_image = bpy.data.images.load(str(texture), check_existing=False)
    if list(verified_disk_image.size) != [4096, 4096]:
        raise RuntimeError('Persisted bake PNG does not have requested dimensions')
    verified_disk_image.name = 'Body_Reference_Projection_4096_Persisted' + suffix
    verified_disk_image.pack()
    for material, emission, image_node, output, prior_surface, shader in temporary:
        links = material.node_tree.links
        links.new(prior_surface, output.inputs['Surface'])
        image_node.image = verified_disk_image
        image_node.label = 'Actual side-photo overlay baked to original UV, 4096px'
        uv = material.node_tree.nodes.new('ShaderNodeUVMap')
        uv.uv_map = original_uv.name
        links.new(uv.outputs[0], image_node.inputs['Vector'])
        links.new(image_node.outputs['Color'], shader.inputs['Base Color'])
        material.node_tree.nodes.remove(emission)
        replaced.append(material.name)
    scene.render.engine = 'BLENDER_EEVEE'
    bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False)
    after = sha(source)
    payload = {'recordedAt': datetime.now(timezone.utc).isoformat(), 'sourceStudy': str(source),
               'sourceShaBefore': before, 'sourceShaAfter': after, 'sourcePreserved': before == after,
               'bakedStudy': str(target), 'texture': str(texture), 'textureSha256': sha(texture),
               'bakedObject': body.name, 'uvMap': original_uv.name, 'resolution': [4096, 4096],
               'bakeType': 'EMIT', 'clear': False, 'marginPixels': 8,
               'materials': replaced,
               'scope': 'Actual existing study colors baked to original Body UV. 4096px preserves sampled reference detail; it does not create missing detail or validate visual parity.'}
    report.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    if before != after:
        raise RuntimeError('Protected study file changed')
    print(json.dumps({'report': str(report), 'texture': str(texture), 'sourcePreserved': True}))


if __name__ == '__main__':
    main()
