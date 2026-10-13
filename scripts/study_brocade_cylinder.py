"""Actual cloth-only cylinder UV/material study on a separate G1 scene copy.

Wait for a real approved experiment texture; no placeholder image is generated.
The original UV and source-face IDs are preserved. The color path is a single
image texture and Principled shader, compatible with standard GLB export.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path, EXPORT_STUDIES

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(ROOT/'scripts'))
from lion_material_tools import find_basecolor_image, image_pixels, sample_uv_colors, color_classes


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def source_buffers(body):
    mesh = body.data
    source_uv = mesh.uv_layers[0]
    uv = np.empty(len(mesh.loops)*2, np.float32)
    source_uv.data.foreach_get('uv', uv)
    indices = np.empty(len(mesh.polygons), np.int32)
    attribute = mesh.attributes.get('source_face_index')
    if not attribute or attribute.domain != 'FACE' or attribute.data_type != 'INT' or len(attribute.data) != len(mesh.polygons):
        raise ValueError('Actual FACE-domain source provenance is required')
    attribute.data.foreach_get('value', indices)
    return {'uvName': source_uv.name, 'uvSha256': hashlib.sha256(uv.tobytes()).hexdigest(),
            'sourceFaceSha256': hashlib.sha256(indices.tobytes()).hexdigest(),
            'faceCount': len(indices), 'uvLoopCount': len(uv)//2}


def micro_weave_normal(path, size=2048, threads=128, tile_m=.20):
    """A real tangent-space PNG from periodic synthetic interlaced height data.

    It is procedural textile response, not a photometric recovered normal map.
    """
    path = Path(path)
    if path.exists():
        image = bpy.data.images.load(str(path), check_existing=False)
        if list(image.size) != [size, size]:
            raise ValueError('Existing micro-weave normal has unexpected dimensions')
        image.colorspace_settings.name = 'Non-Color'
        image.pack()
        return image
    yy, xx = np.mgrid[:size, :size].astype(np.float32)
    u, v = xx/size, yy/size
    a, b = 2*math.pi*threads*u, 2*math.pi*threads*v
    # Alternate raised warp/weft segments; N is even so the field is periodic.
    height = .000022*(np.cos(a)*(.5+.5*np.cos(b/2)) + np.cos(b)*(.5-.5*np.cos(a/2)))
    du = (np.roll(height, -1, axis=1)-np.roll(height, 1, axis=1))*size/(2*tile_m)
    dv = (np.roll(height, -1, axis=0)-np.roll(height, 1, axis=0))*size/(2*tile_m)
    normals = np.stack((-du, -dv, np.ones_like(du)), axis=-1)
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    rgba = np.ones((size, size, 4), np.float32)
    rgba[..., :3] = normals*.5+.5
    image = bpy.data.images.new('Procedural_128_Thread_Tangent_Normal_2048', width=size, height=size, alpha=True)
    image.colorspace_settings.name = 'Non-Color'
    image.pixels.foreach_set(rgba.ravel())
    image.update()
    path.parent.mkdir(parents=True, exist_ok=True)
    image.filepath_raw = str(path)
    image.file_format = 'PNG'
    image.save()
    # Independently pack the actual PNG to avoid stale generated/copied bytes.
    persisted = bpy.data.images.load(str(path), check_existing=False)
    persisted.colorspace_settings.name = 'Non-Color'
    persisted.pack()
    return persisted


def apply_cylindrical_brocade(body, texture_path, tile_m=.20, normal_strength=.18, face_mask=None):
    """Callable for root integration; changes only explicitly selected faces.

    Returns real selection/provenance facts. Cylinder center and radii describe
    a design-space approximation, not measured garment construction.
    face_mask may be a Boolean vector with one entry per polygon, for separately
    audited cloth patches misclassified into Trim. Original UV/provenance stay.
    """
    texture_path = Path(texture_path).resolve(strict=True)
    if not .20 <= tile_m <= .30:
        raise ValueError('This study limits physical tile size to 0.20-0.30m')
    before = source_buffers(body)
    mesh = body.data
    if not all(len(p.vertices) == 3 for p in mesh.polygons):
        raise ValueError('Cloth selection expects actual source triangles')
    positions = np.empty(len(mesh.vertices)*3, np.float32)
    mesh.vertices.foreach_get('co', positions)
    positions = positions.reshape(-1, 3)
    matrix = np.asarray(body.matrix_world, np.float64)
    world = positions@matrix[:3, :3].T+matrix[:3, 3]
    loop_vertices = np.empty(len(mesh.loops), np.int32)
    mesh.loops.foreach_get('vertex_index', loop_vertices)
    loops = world[loop_vertices].reshape(-1, 3, 3)
    centers = loops.mean(axis=1)
    if face_mask is None:
        original_uv = np.empty(len(mesh.loops)*2, np.float32)
        mesh.uv_layers[0].data.foreach_get('uv', original_uv)
        original_uv = original_uv.reshape(-1, 3, 2)
        original_material = body.data.materials[0]
        original_image = find_basecolor_image(original_material)
        pixels = image_pixels(original_image)
        colors = sample_uv_colors(pixels, original_uv)
        rgba = np.ones((*colors.shape[:-1], 4), np.float32)
        rgba[..., :3] = colors
        white = color_classes(rgba)['white'].mean(axis=1)
        # Main Red_Trim is a separate mesh. Printed red on the source Body atlas
        # is part of the cloth and must remain selected to avoid old triangles.
        garment = (centers[:, 1] > -.38) & (centers[:, 1] < .79)
        garment &= (centers[:, 2] > .18) & (centers[:, 2] < .78)
        # Gold/cream motifs can satisfy a loose white classifier. Exclude white
        # only at likely fringe boundaries, rather than central cloth.
        white_fringe = (white >= .95) & ((centers[:, 2] < .24) | (centers[:, 1] < -.30))
        garment &= ~white_fringe
        selection_limits = 'Body garment Y[-.38,.79], Z[.18,.78]; near-pure white excluded only at Z<.24 or Y<-.30 fringe boundaries. Printed red and cream/gold central cloth remain included. Actual image review is required at boundaries.'
    else:
        garment = np.asarray(face_mask)
        if garment.dtype != np.bool_ or garment.shape != (len(mesh.polygons),):
            raise ValueError('Explicit face_mask must be a Boolean vector with exactly one entry per polygon')
        garment = garment.copy()
        selection_limits = 'Explicit independently audited Boolean face_mask; no atlas color exclusion or spatial expansion applied by this helper.'
    if np.count_nonzero(garment) < 1000:
        raise ValueError('Too little verified Body cloth selected for a material study')
    radius_x, radius_z, center_z = .29, .21, .45
    equivalent_radius = math.sqrt((radius_x*radius_x+radius_z*radius_z)/2)
    angle = np.arctan2(loops[:, :, 0]/radius_x, (loops[:, :, 2]-center_z)/radius_z)
    crossing = np.ptp(angle, axis=1) > math.pi
    angle[crossing] = np.where(angle[crossing] < 0, angle[crossing]+2*math.pi, angle[crossing])
    cylinder_uv = np.empty((*angle.shape, 2), np.float32)
    cylinder_uv[:, :, 0] = loops[:, :, 1]/tile_m
    cylinder_uv[:, :, 1] = angle*equivalent_radius/tile_m
    uv_name = 'BrocadeCylinder_' + str(tile_m).replace('.', 'p') + 'm'
    if mesh.uv_layers.get(uv_name):
        raise ValueError('Requested study UV already exists; preserve its version')
    layer = mesh.uv_layers.new(name=uv_name)
    layer.data.foreach_set('uv', cylinder_uv.ravel())
    material = bpy.data.materials.new('Brocade_Clear_Tile_Cloth_Study')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Metallic'].default_value = .12
    shader.inputs['Roughness'].default_value = .58
    shader.inputs['Specular IOR Level'].default_value = .22
    shader.inputs['Sheen Weight'].default_value = .18
    links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    image = bpy.data.images.load(str(texture_path), check_existing=False)
    image.colorspace_settings.name = 'sRGB'
    image.pack()
    image_node = nodes.new('ShaderNodeTexImage')
    image_node.image = image
    image_node.extension = 'REPEAT'
    image_node.interpolation = 'Linear'
    uv_node = nodes.new('ShaderNodeUVMap')
    uv_node.uv_map = uv_name
    links.new(uv_node.outputs[0], image_node.inputs['Vector'])
    links.new(image_node.outputs['Color'], shader.inputs['Base Color'])
    normal_path = ROOT/'textures/brocade_new/body_micro_weave_normal_2048.png'
    normal_image = micro_weave_normal(normal_path, tile_m=tile_m)
    normal_texture = nodes.new('ShaderNodeTexImage')
    normal_texture.image = normal_image
    normal_texture.extension = 'REPEAT'
    links.new(uv_node.outputs[0], normal_texture.inputs['Vector'])
    normal_node = nodes.new('ShaderNodeNormalMap')
    normal_node.space = 'TANGENT'
    normal_node.uv_map = uv_name
    normal_node.inputs['Strength'].default_value = normal_strength
    links.new(normal_texture.outputs['Color'], normal_node.inputs['Color'])
    links.new(normal_node.outputs['Normal'], shader.inputs['Normal'])
    material['micro_weave_scope'] = 'Procedural 128-thread interlaced tangent normal PNG; standard exportable texture, not a photometric measurement or recovered original stitch geometry.'
    mesh.materials.append(material)
    material_index = len(mesh.materials)-1
    for polygon, selected in zip(mesh.polygons, garment):
        if selected:
            polygon.material_index = material_index
    after = source_buffers(body)
    if before != after:
        raise RuntimeError('Original UV or source-face provenance unexpectedly changed')
    return {'changedObject': body.name, 'materialName': material.name, 'newUV': uv_name,
            'selectedClothFaceCount': int(np.count_nonzero(garment)),
            'excludedFaceCount': int(np.count_nonzero(~garment)),
            'tileMetersAlongY': tile_m, 'circumferenceEquivalentRadius': equivalent_radius,
            'cylinderCenterZ': center_z, 'texturePath': str(texture_path),
            'textureSha256': digest(texture_path), 'textureDimensions': list(image.size),
            'originalUVAndFaceProvenancePreserved': before == after,
            'originalBuffers': before, 'normalTexture': str(normal_path),
            'normalTextureSha256': digest(normal_path), 'normalDimensions': list(normal_image.size),
            'normalStrength': normal_strength, 'threadsPerTile': 128,
            'selectionLimits': selection_limits,
            'textureSource': 'New supplied tile experiment; not a recovery of the exact original reference motif.'}


def add_camera(name, y, z, scale):
    data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (4, y, z)
    camera.rotation_euler = (Vector((0, y, z))-camera.location).to_track_quat('-Z', 'Y').to_euler()
    data.type = 'ORTHO'
    data.ortho_scale = scale
    return camera


def render(scene, camera, path):
    scene.camera = camera
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--texture', type=Path, required=True)
    parser.add_argument('--variant', default='')
    parser.add_argument('--tile-m', type=float, default=.20)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    suffix = ('_'+args.variant) if args.variant else ''
    if any(character not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for character in args.variant):
        raise ValueError('Invalid variant')
    texture = args.texture.resolve(strict=True)
    master = blend_path('Lion_Final_Master.blend')
    target = STUDIES/('Lion_Brocade_UV_Study'+suffix+'.blend')
    EXPORT_STUDIES.mkdir(parents=True, exist_ok=True)
    glb = EXPORT_STUDIES/('Lion_Brocade_UV_Study'+suffix+'.glb')
    renders = ROOT/('renders/studies/brocade_uv_study'+suffix)
    report_path = ROOT/('docs/brocade_uv_study'+suffix+'.json')
    if any(path.exists() for path in (target, glb, renders, report_path)):
        raise FileExistsError('Study outputs exist; choose a new variant')
    before_master = digest(master)
    bpy.ops.wm.open_mainfile(filepath=str(master))
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 960
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    whole = add_camera('BrocadeStudy_Whole_PositiveX', 0, .52, 2.02)
    close = add_camera('BrocadeStudy_Close_PositiveX', .19, .46, .68)
    renders.mkdir(parents=True)
    for camera, label in ((whole, 'whole_side'), (close, 'cloth_detail')):
        render(scene, camera, renders/('before_'+label+'.png'))
    body = bpy.data.objects['Lion_Body']
    trim = bpy.data.objects['Lion_Body_Red_Trim']
    trim_materials = [material.name for material in trim.data.materials]
    result = apply_cylindrical_brocade(body, texture, args.tile_m)
    result['trimMaterialAssignmentsPreserved'] = trim_materials == [material.name for material in trim.data.materials]
    for camera, label in ((whole, 'whole_side'), (close, 'cloth_detail')):
        render(scene, camera, renders/('after_'+label+'.png'))
    scene.camera = whole
    scene.render.filepath = ''
    bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False)
    # A small actual Body-only GLB is enough to exercise the color texture and
    # both UV maps. Native-only fibers and the rest of the scene are excluded.
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
                              export_materials='EXPORT', export_texcoords=True,
                              export_normals=True, export_cameras=False, export_lights=False)
    after_master = digest(master)
    result.update({'recordedAt': datetime.now(timezone.utc).isoformat(), 'studyBlend': str(target),
                   'bodyOnlyGlb': str(glb), 'renders': str(renders),
                   'protectedMasterShaBefore': before_master, 'protectedMasterShaAfter': after_master,
                   'protectedMasterPreserved': before_master == after_master,
                   'visualAcceptance': 'Pending actual comparison inspection',
                   'glbReimportAcceptance': 'Pending separate real reimport'})
    report_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    if before_master != after_master or not result['trimMaterialAssignmentsPreserved']:
        raise RuntimeError('A protected source or trim changed')
    print(json.dumps({'report': str(report_path), 'study': str(target), 'glb': str(glb)}))


if __name__ == '__main__':
    main()
