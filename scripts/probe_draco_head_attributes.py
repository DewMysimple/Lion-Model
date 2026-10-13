"""Read-only diagnose rare Draco seam-candidate correspondence failures."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import importlib.util,json,sys
from pathlib import Path
import numpy as np
from mathutils.kdtree import KDTree
spec=importlib.util.spec_from_file_location('draco_qa',ROOT/'scripts/verify_draco_lion.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
rd,rb,rs=q.load_glb(ROOT/'exports/scene.glb');dd,db,ds=q.load_glb(ROOT/'exports/scene_draco.glb')
dll,_=q.decoder_library();reports=[]
for meshname in ('Lion_Head',):
    node=next(n for n in dd['nodes'] if n.get('name')==meshname);mi=node['mesh']
    for pi,(dp,rp) in enumerate(zip(dd['meshes'][mi]['primitives'],rd['meshes'][mi]['primitives'])):
        da,indices=q.decode_primitive(dll,dd,db,dp)
        ra={k:q.accessor(rd,rb,v) for k,v in rp['attributes'].items()}
        p=ra['POSITION'];tree=KDTree(len(p))
        for i,v in enumerate(p):tree.insert(v,i)
        tree.balance();names=sorted(k for k in ra if k.startswith('TEXCOORD_'))
        uvr=np.concatenate([ra[k] for k in names],axis=1);uvd=np.concatenate([da[k] for k in names],axis=1)
        budget=[]
        for name in names:
            u=ra[name];span=float(np.ptp(u,axis=0).max())
            budget.extend([.5*span/(2**16-1)+4*np.finfo(np.float32).eps*max(float(np.abs(u).max()),span,np.finfo(np.float32).tiny)]*2)
        budget=np.asarray(budget);span=float(np.ptp(p,axis=0).max());step=span/(2**20-1)
        r0=(np.sqrt(3)*.5*step+4*np.finfo(np.float32).eps*max(float(np.abs(p).max()),span))*1.0001
        bad=[];normal_bad=[]
        for i,v in enumerate(da['POSITION']):
            c=tree.find_range(v,r0)
            if not c:continue
            ids=np.asarray([x[1] for x in c]);diff=np.abs(uvr[ids].astype(float)-uvd[i]);passed=np.all(diff<=budget,axis=1)
            if not passed.any():
                larger=tree.find_range(v,step*16)
                ids2=np.asarray([x[1] for x in larger]);diff2=np.abs(uvr[ids2].astype(float)-uvd[i]);passed2=np.all(diff2<=budget,axis=1)
                matches=[]
                for ci in ids2[passed2]:
                    n=ra['NORMAL'][ci].astype(float);nd=da['NORMAL'][i].astype(float)
                    angle=float(np.degrees(np.arccos(np.clip(n@nd/(np.linalg.norm(n)*np.linalg.norm(nd)),-1,1))))
                    matches.append({'original_vertex_index':int(ci),'distance_float64':float(np.linalg.norm(p[ci].astype(float)-v)),'normal_angle':angle,'original_position':p[ci].tolist(),'original_uvs':uvr[ci].tolist()})
                bad.append({'decoded_index':i,'decoded_position':v.tolist(),'decoded_uvs':uvd[i].tolist(),'position_budget_radius':r0,'step':step,
                            'original_nearest_position_and_uvs':[{'index':int(ci),'position':p[ci].tolist(),'uvs':uvr[ci].tolist(),'dist':float(np.linalg.norm(p[ci].astype(float)-v))} for ci in ids],
                            'compatible_uv_matches_in_16_steps':matches})
            else:
                ns=ra['NORMAL'][ids[passed]].astype(float);nd=da['NORMAL'][i].astype(float)
                angles=np.degrees(np.arccos(np.clip((ns@nd)/(np.linalg.norm(ns,axis=1)*np.linalg.norm(nd)),-1,1)))
                if angles.min()>.092:normal_bad.append({'decoded_index':i,'angle':float(angles.min())})
        reports.append({'name':meshname,'primitive':pi,'initial_unmatched_uv':bad,'normal_bad_with_matching_uv':normal_bad})
path=ROOT/'docs/draco_head_attribute_correspondence_probe.json';path.write_text(json.dumps(reports,indent=2),encoding='utf8')
print(json.dumps({'probe':str(path),'unmatched':[len(r['initial_unmatched_uv']) for r in reports],'normal_bad':[len(r['normal_bad_with_matching_uv']) for r in reports]}),flush=True)
