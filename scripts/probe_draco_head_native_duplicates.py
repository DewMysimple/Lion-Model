"""Read-only find actual native source faces for unmatched decoded UV corners."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import bpy,json,sys,numpy as np,importlib.util
from pathlib import Path
from mathutils.kdtree import KDTree
spec=importlib.util.spec_from_file_location('draco_qa',ROOT/'scripts/verify_draco_lion.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
doc,buf,storage=q.load_glb(ROOT/'exports/scene_draco.glb');node=next(n for n in doc['nodes'] if n.get('name')=='Lion_Head')
prim=doc['meshes'][node['mesh']]['primitives'][0];dll,_=q.decoder_library();attrs,indices=q.decode_primitive(dll,doc,buf,prim)
probe=json.loads((ROOT/'docs/draco_head_attribute_correspondence_probe.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(blend_path('Lion_Final_Master.blend')))
obj=bpy.data.objects['Lion_Head'];m=obj.data
p=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',p);p=p.reshape(-1,3)
# GLTF native mesh local coords are exported with X,Y,Z -> X,Z,-Y.
p=p[:,[0,2,1]]*np.array([1,1,-1])
tree=KDTree(len(p))
for i,v in enumerate(p):tree.insert(v,i)
tree.balance();vertex_to_faces={}
for poly in m.polygons:
    for vi in poly.vertices:vertex_to_faces.setdefault(vi,[]).append(poly.index)
ids=np.empty(len(m.polygons),np.int32);m.attributes['source_face_index'].data.foreach_get('value',ids)
uvs=[]
for u in m.uv_layers:
    a=np.empty(len(u.data)*2,np.float32);u.data.foreach_get('uv',a);uvs.append(a.reshape(-1,2))
rows=[]
for bad in probe[0]['initial_unmatched_uv']:
    candidates=tree.find_range(bad['decoded_position'],bad['position_budget_radius'])
    matches=[]
    for _,vi,dist in candidates:
        for fi in vertex_to_faces[vi]:
            poly=m.polygons[fi]
            for li in poly.loop_indices:
                if m.loops[li].vertex_index!=vi:continue
                native_uv=np.concatenate([np.array([u[li,0],1-u[li,1]]) for u in uvs[:2]])
                diff=float(np.abs(native_uv-np.asarray(bad['decoded_uvs'])).max())
                if diff<3e-5:
                    matches.append({'native_face_index':fi,'source_face_index':int(ids[fi]),'native_vertex_index':vi,
                        'native_polygon_vertex_indices':list(poly.vertices),'native_uvs':native_uv.tolist(),'max_uv_diff':diff,'material_index':poly.material_index,
                        'native_corner_normal':list(m.corner_normals[li].vector),
                        'decoded_normal':attrs['NORMAL'][bad['decoded_index']].tolist(),
                        'normal_angle_degrees':float(np.degrees(np.arccos(np.clip(np.asarray(m.corner_normals[li].vector)[[0,2,1]]*np.array([1,1,-1])@attrs['NORMAL'][bad['decoded_index']]/np.linalg.norm(attrs['NORMAL'][bad['decoded_index']]),-1,1)))),
                        'actual_decoded_triangles_with_vertex':indices.reshape(-1,3)[np.any(indices.reshape(-1,3)==bad['decoded_index'],axis=1)].tolist()})
    rows.append({'decoded_index':bad['decoded_index'],'native_corner_matches':matches})
out=ROOT/'docs/draco_native_duplicate_attribute_probe.json';out.write_text(json.dumps(rows,indent=2),encoding='utf8')
print(json.dumps({'path':str(out),'matches_per_corner':[len(r['native_corner_matches']) for r in rows]}),flush=True)
