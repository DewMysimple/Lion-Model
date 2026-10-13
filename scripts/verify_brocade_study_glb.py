"""Actual standalone reimport and structural checks for the brocade study GLB."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path, EXPORT_STUDIES

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import struct
import sys
from collections import defaultdict
import bpy
from mathutils import Vector



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.variant):
        raise ValueError('Invalid variant')
    suffix = '_'+args.variant
    path = EXPORT_STUDIES/('Lion_Brocade_UV_Study'+suffix+'.glb')
    report_path = ROOT/('docs/brocade_uv_study'+suffix+'_reimport.json')
    if report_path.exists():
        raise FileExistsError('Preserve the prior actual evidence report')
    raw = path.read_bytes()
    magic, version, total = struct.unpack_from('<III', raw)
    json_len, json_type = struct.unpack_from('<II', raw, 12)
    if (magic, version, total, json_type) != (0x46546C67, 2, len(raw), 0x4E4F534A):
        raise RuntimeError('Unexpected actual GLB container')
    content = json.loads(raw[20:20+json_len])
    materials = content['materials']
    material_index = next(i for i,m in enumerate(materials) if m['name'].startswith('Brocade_Clear_Tile_Cloth_Study'))
    newmat = materials[material_index]
    if newmat['pbrMetallicRoughness']['baseColorTexture'].get('texCoord', 0) != 1:
        raise RuntimeError('Actual GLB color texture does not reference UV1')
    if newmat['normalTexture'].get('texCoord', 0) != 1:
        raise RuntimeError('Actual GLB normal texture does not reference UV1')
    if abs(newmat['normalTexture'].get('scale', 1)-.18) > 1e-6:
        raise RuntimeError('Actual GLB normal strength differs')
    if any('uri' in item for item in content.get('images', [])+content.get('buffers', [])):
        raise RuntimeError('Actual GLB has an external core texture/buffer dependency')
    cloth_primitives = [p for m in content['meshes'] for p in m['primitives'] if p.get('material') == material_index]
    if not cloth_primitives or any('TEXCOORD_1' not in p['attributes'] for p in cloth_primitives):
        raise RuntimeError('Actual cloth primitives omit UV1')
    source = json.loads((ROOT/('docs/brocade_uv_study'+suffix+'.json')).read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=source['studyBlend'])
    original_mesh = bpy.data.objects['Lion_Body'].data
    source_attribute=original_mesh.attributes['source_face_index']
    groups=defaultdict(list)
    for polygon in original_mesh.polygons:
        groups[tuple(sorted(polygon.vertices))].append(int(source_attribute.data[polygon.index].value))
    duplicates=[{'sourceFaceIds':ids,'sameNativeVertexSet':list(vertices)} for vertices,ids in groups.items() if len(ids)>1]
    expected_omissions=sum(len(group['sourceFaceIds'])-1 for group in duplicates)
    validated_copy=original_mesh.copy()
    actual_validation_changed=validated_copy.validate(verbose=False,clean_customdata=False)
    expected_face_count=len(validated_copy.polygons)
    if len(original_mesh.polygons)-expected_face_count != expected_omissions:
        raise RuntimeError('Validated native copy has changes beyond exact duplicate triangles')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path), import_pack_images=True)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    native = next(m for m in bpy.data.materials if m.name.startswith('Brocade_Clear_Tile_Cloth_Study'))
    nodes = native.node_tree.nodes
    texture_images = [{
        'image': n.image.name, 'dimensions': list(n.image.size),
        'colorSpace': n.image.colorspace_settings.name, 'packed': bool(n.image.packed_file)
    } for n in nodes if n.type == 'TEX_IMAGE' and n.image]
    dimensions = {tuple(t['dimensions']) for t in texture_images}
    if (1254,1254) not in dimensions or (2048,2048) not in dimensions:
        raise RuntimeError('Reimported actual color/normal texture dimensions differ')
    if not any(n.type == 'NORMAL_MAP' and abs(n.inputs['Strength'].default_value-.18)<1e-6 for n in nodes):
        raise RuntimeError('Reimported shader has no expected NormalMap strength')
    face_count = sum(len(o.data.polygons) for o in meshes)
    if face_count != expected_face_count:
        raise RuntimeError('Actual reimport triangle count differs from independently validated native copy')
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = 960, 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.world = bpy.data.worlds.new('Brocade_Reimport_Studio_World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.085,.10,.13,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .5
    for name, location, energy, size in (
        ('Key',(2,-2,3),600,3),('Fill',(3,2,1.5),250,3),('Rim',(-1,.8,2),400,2)):
        data = bpy.data.lights.new(name,'AREA'); data.energy=energy; data.shape='DISK'; data.size=size
        obj = bpy.data.objects.new(name,data); scene.collection.objects.link(obj)
        obj.location=location; obj.rotation_euler=(Vector((0,.15,.45))-obj.location).to_track_quat('-Z','Y').to_euler()
    camera_data = bpy.data.cameras.new('Brocade_Reimport_Close_PositiveX')
    camera_data.type='ORTHO'; camera_data.ortho_scale=.68
    camera=bpy.data.objects.new('Brocade_Reimport_Close_PositiveX',camera_data)
    scene.collection.objects.link(camera); camera.location=(4,.19,.46)
    camera.rotation_euler=(Vector((0,.19,.46))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=camera
    render_path=ROOT/('renders/studies/brocade_uv_study'+suffix+'/reimport_cloth_detail.png')
    scene.render.filepath=str(render_path)
    bpy.ops.render.render(write_still=True)
    result = {
        'recordedAt':datetime.now(timezone.utc).isoformat(), 'scope':'Actual Body-only exported GLB, independently reimported into factory-empty Blender scene; different studio illumination than native study.',
        'artifact':str(path), 'sha256':hashlib.sha256(raw).hexdigest(),
        'standardGlbCoreImagesAndBuffersEmbedded':True,
        'baseColorTexCoord':1,'normalTexCoord':1,'normalScale':newmat['normalTexture']['scale'],
        'actualImportedImages':texture_images,'actualImportedTriangleCount':face_count,
        'originalSourceTriangleCount':source['originalBuffers']['faceCount'],
        'nativeSourceFaceIdsPreserved':source['originalUVAndFaceProvenancePreserved'],
        'glbTriangleCountPreserved':face_count==source['originalBuffers']['faceCount'],
        'expectedValidatedCopyTriangleCount':expected_face_count,
        'actualReimportCountMatchesValidatedNativeCopy':True,
        'validatedNativeCopyChanged':actual_validation_changed,
        'exactSourceDuplicateTrianglesRemovedByExporter':expected_omissions,
        'sourceDuplicateGroups':duplicates,
        'actualImportedMeshes':[{'name':o.name,'uvLayers':[u.name for u in o.data.uv_layers]} for o in meshes],
        'render':str(render_path),'glbStructuralAndReimportChecks':'passed',
        'visualAcceptance':'Pending actual rendered-image review',
        'limits':'Synthesized motif differs from the exact reference. Native Body geometry and provenance are preserved. Standard GLB export removes exact source duplicate triangles; source face IDs are not standard GLB attributes.'
    }
    report_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(report_path),'render':str(render_path),'checks':'passed'}))


if __name__=='__main__':
    main()
