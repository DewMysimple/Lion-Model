"""Reopen actual head study and check geometry, UV0, provenance and protections."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys, json, hashlib
import bpy
import numpy as np
sys.path.insert(0,str(ROOT/'scripts'))
from lion_material_tools import find_basecolor_image,image_pixels

def snapshot():
    meshes={}
    for obj in bpy.data.objects:
        if obj.type!='MESH':continue
        mesh=obj.data
        h=hashlib.sha256()
        h.update(np.asarray(obj.matrix_world,dtype=np.float64).tobytes())
        for data,prop,width,dtype in ((mesh.vertices,'co',3,np.float32),
                                     (mesh.loops,'vertex_index',1,np.int32),
                                     (mesh.corner_normals,'vector',3,np.float32)):
            values=np.empty(len(data)*width,dtype)
            data.foreach_get(prop,values);h.update(values.tobytes())
        if mesh.uv_layers:
            uv=np.empty(len(mesh.loops)*2,np.float32)
            mesh.uv_layers[0].data.foreach_get('uv',uv);h.update(uv.tobytes())
        for key in ('source_face_index','source_asset_id'):
            attr=mesh.attributes.get(key)
            if attr:
                values=np.empty(len(attr.data),np.int32)
                attr.data.foreach_get('value',values);h.update(values.tobytes())
        meshes[obj.name]={'digest':h.hexdigest(),'faces':len(mesh.polygons),
                          'materials':[p.material_index for p in mesh.polygons]}
    curves={obj.name:len(obj.data.splines) for obj in bpy.data.objects if obj.type=='CURVE'}
    head=bpy.data.objects['Lion_Head']
    atlas=find_basecolor_image(head.data.materials[0])
    atlas_digest=hashlib.sha256(image_pixels(atlas).tobytes()).hexdigest()
    return meshes,curves,atlas_digest

def main():
    source=blend_path('Lion_Head_Cloth_Input_Copy.blend')
    target=blend_path('Lion_Head_Forehead_Brocade_Study.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    original,curves_before,atlas_before=snapshot()
    bpy.ops.wm.open_mainfile(filepath=str(target))
    actual,curves_after,atlas_after=snapshot()
    mask=np.load(ROOT/'docs/head_forehead_brocade_mask.npy')
    head=bpy.data.objects['Lion_Head']
    attribute=np.empty(len(head.data.polygons),np.bool_)
    head.data.attributes['forehead_brocade_face'].data.foreach_get('value',attribute)
    original_indices=np.asarray(original['Lion_Head']['materials'],np.int32)
    actual_indices=np.asarray(actual['Lion_Head']['materials'],np.int32)
    all_geometry_preserved=(set(original)==set(actual)
        and all(original[name]['digest']==actual[name]['digest'] for name in original))
    unchanged_other_materials=all(original[name]['materials']==actual[name]['materials']
                                  for name in original if name!='Lion_Head')
    results={'study':str(target),'inputCopy':str(source),'reopenedActualFile':True,
             'allModelMeshWorldPositionsTopologyNormalsUV0AndSourceIdsExact':all_geometry_preserved,
             'modelMeshObjectCount':len(original),
             'allOtherPartMaterialIndicesExact':unchanged_other_materials,
             'allUnselectedHeadMaterialIndicesExact':np.array_equal(original_indices[~mask],actual_indices[~mask]),
             'selectedHeadFaceCount':int(mask.sum()),'maskMatchesFaceBooleanAttribute':np.array_equal(mask,attribute),
             'allCurveObjectsAndSplineCountsPreserved':curves_before==curves_after,
             'originalHeadAtlasPixelsExactlyPreserved':atlas_before==atlas_after,
             'originalAtlasPixelSha256':atlas_before}
    if not all(results[key] for key in (
        'allModelMeshWorldPositionsTopologyNormalsUV0AndSourceIdsExact',
        'allOtherPartMaterialIndicesExact','allUnselectedHeadMaterialIndicesExact',
        'maskMatchesFaceBooleanAttribute','allCurveObjectsAndSplineCountsPreserved',
        'originalHeadAtlasPixelsExactlyPreserved')):
        raise RuntimeError('Forehead study changed protected source/model data')
    (ROOT/'docs/head_forehead_brocade_reopen_verification.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results))

if __name__=='__main__':main()
