"""Actual front-plane brocade study on a stable independent head scene copy.

Reference-inspired design synthesis is explicitly identified. This changes
material assignments and adds UV1 only; original atlas, UV0 and source IDs stay.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import hashlib
import json
import sys

import bpy
import numpy as np

sys.path.insert(0,str(ROOT/'scripts'))
from lion_material_tools import image_pixels, find_basecolor_image, sample_uv_colors
from study_brocade_cylinder import micro_weave_normal, source_buffers
import refine_lion_master as pipeline


def mesh_arrays(head):
    mesh=head.data
    if any(len(p.vertices)!=3 for p in mesh.polygons):
        raise ValueError('Original triangular source geometry is required')
    positions=np.empty(len(mesh.vertices)*3,np.float32)
    mesh.vertices.foreach_get('co',positions)
    positions=positions.reshape(-1,3)
    indices=np.empty(len(mesh.polygons)*3,np.int32)
    mesh.polygons.foreach_get('vertices',indices)
    indices=indices.reshape(-1,3)
    matrix=np.asarray(head.matrix_world,np.float64)
    world=positions@matrix[:3,:3].T+matrix[:3,3]
    corners=world[indices]
    centers=corners.mean(axis=1)
    normals=np.empty(len(mesh.loops)*3,np.float32)
    mesh.corner_normals.foreach_get('vector',normals)
    normals=normals.reshape(-1,3,3).mean(axis=1)@np.linalg.inv(matrix[:3,:3])
    normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-8)
    uv=np.empty(len(mesh.loops)*2,np.float32)
    mesh.uv_layers[0].data.foreach_get('uv',uv)
    return corners,centers,normals,uv.reshape(-1,3,2)


def select_forehead_cloth(head,root=ROOT):
    """A conservative source-face window, with geometric and original-UV guards."""
    if head.name!='Lion_Head':
        raise ValueError('This study is restricted to actual Lion_Head, not brows/eyes/other parts')
    root=Path(root)
    corners,centers,normals,uv=mesh_arrays(head)
    image=find_basecolor_image(head.data.materials[0])
    if image is None:
        raise ValueError('The actual original head atlas must remain in material slot zero')
    pixels=image_pixels(image)
    bary=np.array([[1/3,1/3,1/3],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]],np.float32)
    sampled=sample_uv_colors(pixels,np.einsum('nc,fcx->fnx',bary,uv))
    r,g,b=np.moveaxis(sampled,-1,0)
    neutral_white=((np.minimum(np.minimum(r,g),b)>.58)
                   & ((np.maximum(np.maximum(r,g),b)-np.minimum(np.minimum(r,g),b))
                      /np.maximum(np.maximum(np.maximum(r,g),b),1e-6)<.105))
    red=(r>.28)&(g/np.maximum(r,1e-6)<.68)&(b/np.maximum(r,1e-6)<.65)&(r-g>.11)
    x,y,z=centers.T
    region=(np.abs(x)<.105)&(z>.705)&(z<.915)&(y<-.56)&(normals[:,1]<-.35)
    landmarks=json.loads((root/'docs/head_candidate_parts_report_v3.json').read_text(encoding='utf-8'))
    badge=np.asarray(landmarks['feature_estimates_fitted_world']['forehead_medallion']['surface_center_area_weighted'])
    # Protect the original decorative ring and fitted cap, not only the cap's
    # exposed .035m brass disk. Every corner must be outside the guard disk.
    badge_corner_distance=np.sqrt((corners[:,:,0]-badge[0])**2+(corners[:,:,2]-badge[2])**2)
    metal_badge=badge_corner_distance.min(axis=1)<.057
    # The upper forehead contains pale cream/gold printed motifs. Near-neutral
    # atlas pixels are not fur by themselves; protect white only at the lower
    # side edges adjoining the eye-frame region, not across the cloth field.
    white_fur=(neutral_white.mean(axis=1)>=.75)&(np.abs(x)>.065)&(z<.790)
    raised_red_eye_rim=(np.abs(x)>.055)&(z<.743)&(y<-.643)&(red.mean(axis=1)>=.5)
    mask=region&~metal_badge&~white_fur&~raised_red_eye_rim
    report={'sourceObject':head.name,'sourceAsset':head.get('source_asset','unknown'),
            'originalAtlasImageName':image.name,'originalAtlasSize':list(image.size),
            'allHeadSourceFaces':len(mask),'frontWindowFaces':int(region.sum()),
            'selectedForeheadClothFaces':int(mask.sum()),
            'excludedBadgeFacesInWindow':int((region&metal_badge).sum()),
            'excludedNeutralWhiteFacesInWindow':int((region&white_fur).sum()),
            'excludedRaisedRedEyeRimFacesInWindow':int((region&raised_red_eye_rim).sum()),
            'badgeMeasuredCenterWorld':badge.tolist(),'badgeGuardRadiusMeters':.057,
            'window':'|world X|<.105, world Z[.705,.915], world Y<-.56, normal Y<-.35; actual Lion_Head only',
            'limitations':['Conservative source-triangle appearance window; not a recovered stitch layout.',
                           'Atlas color protects near-neutral white only in the lower side-edge geometry adjoining the eye frame, and the geometrically constrained lower red eye rim; pale printed motifs in the upper cloth remain selected.',
                           'No side/back shell expansion; a new-versus-old motif boundary may be visible at the window edge.',
                           'Source circular metal/decorative region is protected by measured location, not exact anatomy.']}
    if mask.sum()<20:
        raise ValueError('Too few actual forehead faces selected for a useful study')
    return mask,corners,report


def apply_forehead_brocade(head=None,root=ROOT,texture_path=None,tile_m=.20,normal_strength=.18):
    """Return face_mask + report; apply one ImageTex/Principled front-plane material."""
    root=Path(root)
    if head is None:head=bpy.data.objects['Lion_Head']
    if not .18<=tile_m<=.25:raise ValueError('Audited physical tile range is .18-.25m')
    if texture_path is None:texture_path=root/'textures/brocade_new/brocade_reference_synthesis.png'
    texture_path=Path(texture_path).resolve(strict=True)
    before=source_buffers(head)
    mask,corners,report=select_forehead_cloth(head,root)
    mesh=head.data
    uv_name='ForeheadPlane_XZ_'+str(tile_m).replace('.','p')+'m'
    if mesh.uv_layers.get(uv_name):raise ValueError('Forehead study UV already exists; do not overwrite')
    planar_uv=np.empty((len(mesh.polygons),3,2),np.float32)
    planar_uv[:,:,0]=.5+corners[:,:,0]/tile_m
    planar_uv[:,:,1]=.5+(corners[:,:,2]-.83)/tile_m
    layer=mesh.uv_layers.new(name=uv_name)
    layer.data.foreach_set('uv',planar_uv.ravel())
    material=bpy.data.materials.new('Forehead_ReferenceInspired_Brocade_Study')
    material.use_nodes=True
    nodes,links=material.node_tree.nodes,material.node_tree.links
    nodes.clear()
    output=nodes.new('ShaderNodeOutputMaterial')
    shader=nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Metallic'].default_value=.12
    shader.inputs['Roughness'].default_value=.58
    shader.inputs['Specular IOR Level'].default_value=.22
    shader.inputs['Sheen Weight'].default_value=.18
    links.new(shader.outputs['BSDF'],output.inputs['Surface'])
    image=bpy.data.images.load(str(texture_path),check_existing=False)
    image.colorspace_settings.name='sRGB';image.pack()
    texture=nodes.new('ShaderNodeTexImage');texture.image=image
    texture.extension='REPEAT';texture.interpolation='Linear'
    mapping=nodes.new('ShaderNodeUVMap');mapping.uv_map=uv_name
    links.new(mapping.outputs[0],texture.inputs['Vector'])
    links.new(texture.outputs['Color'],shader.inputs['Base Color'])
    normal_path=root/'textures/brocade_new/body_micro_weave_normal_2048.png'
    normal_image=micro_weave_normal(normal_path,tile_m=tile_m)
    normal_texture=nodes.new('ShaderNodeTexImage');normal_texture.image=normal_image
    normal_texture.extension='REPEAT'
    links.new(mapping.outputs[0],normal_texture.inputs['Vector'])
    normal=nodes.new('ShaderNodeNormalMap');normal.space='TANGENT';normal.uv_map=uv_name
    normal.inputs['Strength'].default_value=normal_strength
    links.new(normal_texture.outputs['Color'],normal.inputs['Color'])
    links.new(normal.outputs['Normal'],shader.inputs['Normal'])
    material['texture_provenance']='Imagegen synthesized reference-inspired design; not the exact recovered original pattern.'
    mesh.materials.append(material);slot=len(mesh.materials)-1
    for polygon,selected in zip(mesh.polygons,mask):
        if selected:polygon.material_index=slot
    attribute=mesh.attributes.new('forehead_brocade_face','BOOLEAN','FACE')
    attribute.data.foreach_set('value',mask)
    after=source_buffers(head)
    if before!=after:raise RuntimeError('Original atlas UV0/source face provenance changed')
    report.update({'material':material.name,'newUV':uv_name,'tileMetersWorldXZ':tile_m,
                   'planeOffsetCenterXZ':[0,.83],'normalStrength':normal_strength,
                   'normalPath':str(normal_path),'normalSize':list(normal_image.size),
                   'texturePath':str(texture_path),'textureSize':list(image.size),
                   'textureSha256':hashlib.sha256(texture_path.read_bytes()).hexdigest(),
                   'textureProvenance':'New synthesized reference-inspired brocade; original source atlas is preserved.',
                   'originalUV0AndFaceIdsPreserved':before==after,'sourceBuffers':before})
    return {'face_mask':mask,'report':report}


def main():
    source=blend_path('Lion_Head_Cloth_Input_Copy.blend')
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.view_layer.update()
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    directory=ROOT/'renders/studies/head_forehead_brocade'
    directory.mkdir(parents=True,exist_ok=True)
    pipeline.set_camera((0,-.61,.78),(-.15,-1,.1),.66,1100,900)
    scene.render.filepath=str(directory/'before_forehead.png')
    bpy.ops.render.render(write_still=True)
    result=apply_forehead_brocade()
    np.save(ROOT/'docs/head_forehead_brocade_mask.npy',result['face_mask'])
    scene.render.filepath=str(directory/'after_forehead.png')
    bpy.ops.render.render(write_still=True)
    output=blend_path('Lion_Head_Forehead_Brocade_Study.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False,compress=True)
    report=result['report']
    report.update({'inputStableCopy':str(source),'inputCopySha256':source_hash,
                   'inputCopyPreserved':hashlib.sha256(source.read_bytes()).hexdigest()==source_hash,
                   'masterWrittenByUtility':False,'studyBlend':str(output),
                   'comparisonImages':str(directory),'visualAcceptance':'Pending actual comparison inspection'})
    (ROOT/'docs/head_forehead_brocade_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('HEAD_FOREHEAD_STUDY_DONE',report['selectedForeheadClothFaces'],flush=True)


if __name__=='__main__':main()
