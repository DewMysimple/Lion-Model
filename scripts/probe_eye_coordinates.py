
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import bpy,json,sys,numpy as np
from pathlib import Path
R = ROOT
sys.path.insert(0,str(R/'scripts'))
from organize_lion_parts import canonical_positions,box
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(R/'generated/Lux3D_Lion_Base_glb.glb'))
o=next(o for o in bpy.data.objects if o.type=='MESH');m=o.data;p,_=canonical_positions(o)
f=np.array([v.vertices[:] for v in m.polygons]);c=p[f].mean(axis=1)
uv=np.empty(len(m.loops)*2,np.float32);m.uv_layers[0].data.foreach_get('uv',uv);uv=uv.reshape(-1,3,2).mean(axis=1)%1
im=bpy.data.images['Image_0'];w,h=im.size;px=np.empty(w*h*4,np.float32);im.pixels.foreach_get(px);px=px.reshape(h,w,4)
rgb=px[(uv[:,1]*h).astype(int),(uv[:,0]*w).astype(int),:3]
report={}
for name,sgn in [('L',1),('R',-1)]:
    mask=(c[:,0]*sgn>.075)&(c[:,0]*sgn<.24)&(c[:,2]>.585)&(c[:,2]<.755)&(c[:,1]<-.25)
    cc=c[mask];rr=rgb[mask];order=np.argsort(rr.max(axis=1));narrow=cc[order[:200]]
    report[name]={'samples':len(cc),'lowest_colours':rr[order[:10]].tolist(),'lowest_coords':cc[order[:10]].tolist(),'lowest200bbox':box(narrow),'centroid':np.median(narrow,axis=0).tolist(),'blackcounts':int(sum(rr.max(axis=1)<.1))}
report['image']={'min':px[:,:,:3].min(axis=(0,1)).tolist(),'max':px[:,:,:3].max(axis=(0,1)).tolist(),'size':[w,h]}
(R/'docs/lion_eye_probe.json').write_text(json.dumps(report,indent=2));print(report)
