
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import bpy,bmesh,json
from pathlib import Path
R = ROOT
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'generated/Lux3D_Lion_Base_glb.glb'))
o=next(o for o in bpy.data.objects if o.type=='MESH')
low=min(v.co.z for v in o.data.vertices);scale=1/(max(v.co.z for v in o.data.vertices)-low)
for v in o.data.vertices:v.co=((v.co.x*scale,v.co.y*scale,(v.co.z-low)*scale))
results=[]
for eps in [0,1e-10,1e-9,1e-8,5e-8,1e-7,1e-6]:
    bm=bmesh.new();bm.from_mesh(o.data)
    if eps:bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=eps)
    item={'eps':eps,'vertices':len(bm.verts),'faces':len(bm.faces),'boundaries':sum(e.is_boundary for e in bm.edges),'overconnected_edges':sum(len(e.link_faces)>2 for e in bm.edges),'inconsistent':sum(e.is_manifold and not e.is_contiguous for e in bm.edges)}
    results.append(item);bm.free()
(R/'docs/lion_seam_tolerance_probe.json').write_text(json.dumps(results,indent=2))
print(results)
