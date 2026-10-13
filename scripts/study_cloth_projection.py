"""Study a conservative +X-side reference photograph projection on real Body.

Only a separate .blend and comparisons are written. The master and reference
images remain untouched. Occluded/opposite surfaces keep their original atlas.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys

import bpy
import numpy as np
from mathutils import Vector



def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def pixel_array(image):
    values = np.empty(len(image.pixels), np.float32)
    image.pixels.foreach_get(values)
    return values.reshape(image.size[1], image.size[0], 4)


def camera(name, position, target, scale):
    data = bpy.data.cameras.new(name)
    result = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(result)
    result.location = position
    result.rotation_euler = (Vector(target)-result.location).to_track_quat('-Z', 'Y').to_euler()
    data.type = 'ORTHO'
    data.ortho_scale = scale
    data.lens = 50
    return result


def add_projection_material(original, photo, mask, uv_name):
    material = original.copy()
    material.name = original.name + '_Conservative_Reference_Cloth_Study'
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
    original_color = shader.inputs['Base Color']
    prior = original_color.links[0].from_socket if original_color.links else None
    uv = nodes.new('ShaderNodeUVMap')
    uv.uv_map = uv_name
    uv.label = 'Real world Y/Z landmark projection, +X side only'
    color = nodes.new('ShaderNodeTexImage')
    color.image = photo
    color.extension = 'CLIP'
    color.interpolation = 'Linear'
    color.label = 'Actual reference pixels; no invented repeating motif'
    alpha = nodes.new('ShaderNodeTexImage')
    alpha.image = mask
    alpha.extension = 'CLIP'
    alpha.interpolation = 'Linear'
    geometry = nodes.new('ShaderNodeNewGeometry')
    normal = nodes.new('ShaderNodeSeparateXYZ')
    links.new(geometry.outputs['Normal'], normal.inputs[0])
    side = nodes.new('ShaderNodeMapRange')
    side.inputs['From Min'].default_value = .35
    side.inputs['From Max'].default_value = .75
    side.clamp = True
    links.new(normal.outputs['X'], side.inputs['Value'])
    factor = nodes.new('ShaderNodeMath')
    factor.operation = 'MULTIPLY'
    links.new(alpha.outputs['Color'], factor.inputs[0])
    links.new(side.outputs['Result'], factor.inputs[1])
    mix = nodes.new('ShaderNodeMixRGB')
    mix.blend_type = 'MIX'
    if prior:
        links.new(prior, mix.inputs[1])
    else:
        mix.inputs[1].default_value = tuple(original_color.default_value)
    links.new(factor.outputs[0], mix.inputs[0])
    links.new(color.outputs['Color'], mix.inputs[2])
    links.new(mix.outputs['Color'], original_color)
    links.new(uv.outputs[0], color.inputs['Vector'])
    links.new(uv.outputs[0], alpha.inputs['Vector'])
    return material


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', default='')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    variant = ('_' + args.variant) if args.variant else ''
    if any(character not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for character in args.variant):
        raise ValueError('Variant must use ASCII letters, digits, underscore or hyphen')
    master = blend_path('Lion_Final_Master.blend')
    reference = ROOT/'references/left.png'
    target = STUDIES/('Lion_Cloth_Projection_Study' + variant + '.blend')
    output = ROOT/('renders/studies/cloth_projection_study' + variant)
    report_path = ROOT/('docs/cloth_projection_study' + variant + '.json')
    if target.exists() or output.exists() or report_path.exists():
        raise FileExistsError('Study output already exists; preserve earlier versions')
    before = {'master': digest(master), 'reference': digest(reference)}
    bpy.ops.wm.open_mainfile(filepath=str(master))
    body = bpy.data.objects.get('Lion_Body')
    trim = bpy.data.objects.get('Lion_Body_Red_Trim')
    if not body or body.type != 'MESH':
        raise ValueError('Actual Lion_Body mesh not found')
    if not trim:
        raise ValueError('Separate actual Lion_Body_Red_Trim not found')
    trim_original = [material.name if material else None for material in trim.data.materials]
    materials_before = list(body.data.materials)
    output.mkdir(parents=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 960
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    full = camera('ClothStudy_Full_PositiveX', (4, 0, .52), (0, 0, .52), 2.02)
    detail = camera('ClothStudy_Detail_PositiveX', (4, .19, .46), (0, .19, .46), .68)
    renders = []
    for cam, name in ((full, 'whole_side'), (detail, 'cloth_detail')):
        scene.camera = cam
        path = output/('before_' + name + '.png')
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        renders.append(str(path))

    photo = bpy.data.images.load(str(reference), check_existing=False)
    pixels = pixel_array(photo)
    r, g, b = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    # Conservative cloth seeds distinguish yellow brocade and dark green motifs
    # from neutral backdrop and saturated red fibers. A small local expansion
    # retains adjacent embroidered reds/blacks; broad furry bands stay excluded.
    colored = (np.max(pixels[..., :3], axis=-1)-np.min(pixels[..., :3], axis=-1)) > .045
    gold = (r > g*.88) & (g > b*1.12) & (g > .16) & colored
    green = (g > r*1.12) & (g > b*.94) & (g > .065) & colored
    seed = gold | green
    expanded = seed.copy()
    for unused in range(3):
        p = np.pad(expanded, 1)
        expanded = np.logical_or.reduce([p[dy:dy+expanded.shape[0], dx:dx+expanded.shape[1]] for dy in range(3) for dx in range(3)])
    pure_red = (r > g*1.85) & (r > b*1.7) & (g < .24)
    mask_pixels = expanded.astype(np.float32) * np.where(pure_red & ~seed, .08, 1).astype(np.float32)
    # Smooth only the inclusion mask, retaining reference image sharpness.
    p = np.pad(mask_pixels, 1)
    mask_pixels = sum(p[dy:dy+mask_pixels.shape[0], dx:dx+mask_pixels.shape[1]] for dy in range(3) for dx in range(3))/9
    height, width = mask_pixels.shape
    # Restrict to photographed Body, using reference-pixel shoulder/tail bounds.
    yy, xx = np.mgrid[:height, :width]
    ytop = height-1-yy
    def smoothstep(values):
        values = np.clip(values, 0, 1)
        return values*values*(3-2*values)
    region = smoothstep((xx-340)/35) * smoothstep((790-xx)/30)
    region *= smoothstep((ytop-160)/30) * smoothstep((510-ytop)/30)
    mask_pixels *= region
    rgba = np.ones_like(pixels)
    rgba[..., :3] = mask_pixels[..., None]
    mask = bpy.data.images.new('Reference_Cloth_Visible_Only_Mask', width=width, height=height, alpha=True)
    mask.colorspace_settings.name = 'Non-Color'
    mask.pixels.foreach_set(rgba.ravel())
    mask.update()
    # Landmarks are explicit estimated correspondences, not an automatic bbox fit:
    # Independent master probes estimated these correspondences:
    # Y-.19506/Z.57397->(365.6,247.8), Y.35084/Z.60957->(657.7,227.5),
    # Y.28972/Z.23737->(625.0,439.7). Perspective remains approximate.
    uv_name = 'ReferenceClothWorldYZ_PositiveX'
    layer = body.data.uv_layers.new(name=uv_name)
    vertices = np.empty(len(body.data.vertices)*3, np.float32)
    body.data.vertices.foreach_get('co', vertices)
    vertices = vertices.reshape(-1, 3)
    matrix = np.asarray(body.matrix_world, dtype=np.float64)
    world = vertices@matrix[:3, :3].T+matrix[:3, 3]
    indices = np.empty(len(body.data.loops), np.int32)
    body.data.loops.foreach_get('vertex_index', indices)
    coordinates = np.empty((len(indices), 2), np.float32)
    coordinates[:, 0] = (470+535*world[indices, 1])/width
    coordinates[:, 1] = 1-(575-570*world[indices, 2])/height
    layer.data.foreach_set('uv', coordinates.ravel())
    for index, material in enumerate(materials_before):
        if material:
            body.data.materials[index] = add_projection_material(material, photo, mask, uv_name)
    photo.pack()
    mask.pack()
    body['cloth_reference_projection_scope'] = 'Prototype: actual +X reference pixels on visible Body only; opposite side and excluded pixels preserve original UV atlas.'
    body['cloth_projection_landmarks'] = 'estimated shoulder Y-.19506/Z.57397->px365.6/247.8, rear Y.35084/Z.60957->px657.7/227.5, belly Y.28972/Z.23737->px625/439.7'
    for cam, name in ((full, 'whole_side'), (detail, 'cloth_detail')):
        scene.camera = cam
        path = output/('after_' + name + '.png')
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        renders.append(str(path))
    scene.camera = full
    scene.render.filepath = ''
    bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False)
    after = {'master': digest(master), 'reference': digest(reference)}
    trim_after = [material.name if material else None for material in trim.data.materials]
    report = {
        'recordedAt': datetime.now(timezone.utc).isoformat(),
        'studyBlend': str(target), 'reference': str(reference), 'renders': renders,
        'changedObject': body.name, 'unchangedTrim': trim.name,
        'trimMaterialAssignmentsPreserved': trim_original == trim_after,
        'sourceHashesBefore': before, 'sourceHashesAfter': after, 'sourcesPreserved': before == after,
        'referenceMaskNonzeroPixelFraction': float((mask_pixels > .01).mean()),
        'projectionUV': uv_name,
        'mapping': {'pixelX': '470 + 535 * worldY', 'pixelYFromTop': '575 - 570 * worldZ'},
        'landmarkStatus': 'Estimated shoulder, rear and belly correspondences; visual comparison is required.',
        'limitations': ['Only photographed +X-facing cloth is projected.', 'Reference contains baked lighting; this is not measured albedo.', 'Opposite/occluded faces, gray backdrop and strong red-fur pixels fall back to the original atlas.', 'The original low-resolution reference limits achievable detail.', 'No unseen motif or original embroidery stitch geometry is reconstructed.'],
        'visualAcceptance': 'Pending actual image inspection; no improvement is claimed yet.'
    }
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if before != after or trim_original != trim_after:
        raise RuntimeError('Prototype changed a protected source or trim assignment')
    print(json.dumps({'report': str(report_path), 'blend': str(target), 'sourcesPreserved': before == after}))


if __name__ == '__main__':
    main()
