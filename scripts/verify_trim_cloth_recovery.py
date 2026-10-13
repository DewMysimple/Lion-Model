"""Reopen the actual study to verify source geometry, UV0 and face assignments."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import hashlib, json, sys
import bpy
import numpy as np
sys.path.insert(0,str(ROOT/'scripts'))
from recover_trim_cloth import load_recovery_mask

def arrays(mesh):
    result={}
    for key,data,prop,width,dtype in (
        ('vertices',mesh.vertices,'co',3,np.float32),
        ('faces',mesh.polygons,'vertices',3,np.int32),
        ('uv0',mesh.uv_layers[0].data,'uv',2,np.float32),
        ('normals',mesh.corner_normals,'vector',3,np.float32),
        ('sourceIds',mesh.attributes['source_face_index'].data,'value',1,np.int32),
        ('sourceNormals',mesh.attributes['source_corner_normal'].data,'vector',3,np.float32),
    ):
        values=np.empty(len(data)*width,dtype)
        data.foreach_get(prop,values)
        result[key]=values
    result['materialIndices']=np.array([p.material_index for p in mesh.polygons],np.int32)
    return result

def main():
    source=blend_path('Lion_Body_Quality_Stage.blend')
    target=blend_path('Lion_Trim_Cloth_Recovery_Study.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    before={name:arrays(bpy.data.objects[name].data) for name in ('Lion_Body','Lion_Body_Red_Trim')}
    curves_before={o.name:len(o.data.splines) for o in bpy.data.objects if o.type=='CURVE'}
    bpy.ops.wm.open_mainfile(filepath=str(target))
    preserved={}
    for name,original in before.items():
        actual=arrays(bpy.data.objects[name].data)
        preserved[name]={key:np.array_equal(value,actual[key]) for key,value in original.items() if key!='materialIndices'}
    trim=bpy.data.objects['Lion_Body_Red_Trim']
    mask=load_recovery_mask(trim,ROOT)
    assignment=np.array([p.material_index for p in trim.data.polygons],np.int32)
    bool_attribute=np.empty(len(mask),np.bool_)
    trim.data.attributes['recovered_brocade_face'].data.foreach_get('value',bool_attribute)
    selected_slots=set(assignment[mask].tolist())
    selected_materials=[trim.data.materials[i].name for i in sorted(selected_slots)]
    unselected_preserved=np.array_equal(assignment[~mask],before['Lion_Body_Red_Trim']['materialIndices'][~mask])
    curves_after={o.name:len(o.data.splines) for o in bpy.data.objects if o.type=='CURVE'}
    all_ids=[]
    for obj in bpy.data.objects:
        if obj.type=='MESH' and obj.data.attributes.get('source_face_index'):
            ids=np.empty(len(obj.data.polygons),np.int32)
            obj.data.attributes['source_face_index'].data.foreach_get('value',ids)
            all_ids.append(ids)
    all_ids=np.concatenate(all_ids)
    result={'study':str(target),'source':str(source),'reopenedActualFile':True,
            'exactSourceBuffersPreserved':preserved,
            'maskFaceAttributeMatchesSavedNpy':np.array_equal(mask,bool_attribute),
            'recoveredFaceCount':int(mask.sum()),'selectedMaterialNames':selected_materials,
            'allUnselectedTrimMaterialIndicesPreserved':unselected_preserved,
            'curveObjectAndSplineCountsPreserved':curves_before==curves_after,
            'originalTriangleCount':len(all_ids),'uniqueOriginalSourceFaceIds':len(np.unique(all_ids)),
            'original286200FacesPresentOnce':len(all_ids)==286200 and len(np.unique(all_ids))==286200}
    (ROOT/'docs/trim_cloth_recovery_reopen_verification.json').write_text(json.dumps(result,indent=2))
    if (not all(all(item.values()) for item in preserved.values()) or not unselected_preserved
        or not result['maskFaceAttributeMatchesSavedNpy'] or not result['curveObjectAndSplineCountsPreserved']
        or not result['original286200FacesPresentOnce']):
        raise RuntimeError('Reopened source conservation check failed')
    print(json.dumps(result))

if __name__=='__main__':main()
