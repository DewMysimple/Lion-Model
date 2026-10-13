"""Reopen the editable lion and compare every source triangle, UV and world point."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import hashlib,json,sys
import bpy,numpy as np
R = ROOT
sys.path.insert(0,str(R/'scripts'))
from organize_lion_parts import canonical_positions,box,PIVOTS,PARENTS
sourcepath=R/'generated/Lux3D_Lion_Base_glb.glb'
source_sha_before=hashlib.sha256(sourcepath.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(blend_path('Lion_Parts_Working.blend', root=R)))
parts=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('Lion_')]
reopened={o.name:o for o in parts}
source_objects=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(sourcepath),import_pack_images=True)
src=next(o for o in bpy.data.objects if o not in source_objects and o.type=='MESH');m=src.data
positions,normalization=canonical_positions(src)
faces=np.array([p.vertices[:] for p in m.polygons],dtype=np.int32)
uv=np.empty(len(m.loops)*2,np.float32);m.uv_layers[0].data.foreach_get('uv',uv);uv=uv.reshape(-1,3,2)
coverage=np.zeros(len(faces),np.int32)
max_geometry_delta=0.;max_uv_delta=0.;bounds=[];hierarchy=[]
for obj in parts:
    ids=np.empty(len(obj.data.polygons),np.int32);obj.data.attributes['source_face_index'].data.foreach_get('value',ids)
    coverage[ids]+=1
    outfaces=np.array([p.vertices[:] for p in obj.data.polygons],np.int32)
    outpoints=np.array([obj.matrix_world@v.co for v in obj.data.vertices])
    delta=np.max(np.abs(outpoints[outfaces]-positions[faces[ids]]))
    max_geometry_delta=max(max_geometry_delta,float(delta))
    outuv=np.empty(len(obj.data.loops)*2,np.float32);obj.data.uv_layers[0].data.foreach_get('uv',outuv);outuv=outuv.reshape(-1,3,2)
    max_uv_delta=max(max_uv_delta,float(np.max(np.abs(outuv-uv[ids]))))
    if obj.parent.name!='Pivot_'+obj.name[5:]:raise RuntimeError('Unexpected mesh parent '+obj.name)
    bounds.append(outpoints)
    hierarchy.append({'name':obj.name,'parent':obj.parent.name,'parent_world_position':list(obj.parent.matrix_world.translation),
                      'world_bbox':box(outpoints),'triangles':len(ids),'point_delta':float(delta)})
all_covered=bool(np.all(coverage==1));uv_unchanged=max_uv_delta==0;geometry_unchanged=max_geometry_delta<2e-7
source_sha_after=hashlib.sha256(sourcepath.read_bytes()).hexdigest()
result={'status':'pass' if all_covered and uv_unchanged and geometry_unchanged and source_sha_after==source_sha_before else 'fail',
        'reopened_blend':str(blend_path('Lion_Parts_Working.blend', root=R)),'parts':len(parts),'triangles':int(coverage.sum()),
        'all_source_faces_once':all_covered,'max_world_position_difference_design_units':max_geometry_delta,
        'geometry_within_float32_roundoff':geometry_unchanged,'max_uv_loop_difference':max_uv_delta,
        'uv_loops_exact':uv_unchanged,'world_bbox':box(np.concatenate(bounds)),
        'source_sha256_before':source_sha_before,'source_sha256_after':source_sha_after,
        'source_preserved':source_sha_before==source_sha_after,'hierarchy':hierarchy,
        'scope':'Every reopened partition triangle is checked against the actual original GLB, including UV loops and normalized world vertex positions. This does not validate deformation or full modeling completion.'}
(R/'docs/lion_parts_reopen_verification.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k!='hierarchy'}))
if result['status']!='pass':raise RuntimeError('Part verification failed')
