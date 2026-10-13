
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import bpy,json,collections
from pathlib import Path
R = ROOT
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'generated/Lux3D_Lion_Base_glb.glb'))
o=next(o for o in bpy.data.objects if o.type=='MESH');m=o.data
posmap={};groups=[]
for v in m.vertices:
    k=tuple(v.co);groups.append(posmap.setdefault(k,len(posmap)))
edgefaces=collections.Counter();deg=[]
for p in m.polygons:
    g=[groups[i] for i in p.vertices]
    if len(set(g))<3:deg.append(p.index)
    for a,b in zip(g,g[1:]+g[:1]):
        if a!=b:edgefaces[tuple(sorted((a,b)))]+=1
badgroups=set()
for (a,b),cnt in edgefaces.items():
    if cnt>2:badgroups.update((a,b))
for f in deg:badgroups.update(groups[i] for i in m.polygons[f].vertices)
mapping={};vmap=[]
for i,g in enumerate(groups):vmap.append(mapping.setdefault(('original',i) if g in badgroups else ('weld',g),len(mapping)))
newedgecounts=collections.Counter()
for p in m.polygons:
    ids=[vmap[i] for i in p.vertices]
    for a,b in zip(ids,ids[1:]+ids[:1]):newedgecounts[tuple(sorted((a,b)))]+=1
report={'original_verts':len(m.vertices),'canonical_groups':len(posmap),'protected_groups':len(badgroups),'protected_vertices':sum(g in badgroups for g in groups),'safe_weld_vertices':len(mapping),'safe_weld_boundary':sum(c==1 for c in newedgecounts.values()),'safe_weld_overconnected':sum(c>2 for c in newedgecounts.values()),'degenerate_canonical_faces':len(deg),'canonical_overconnected_edges':sum(c>2 for c in edgefaces.values())}
(R/'docs/lion_safe_weld_probe.json').write_text(json.dumps(report,indent=2));print(report)
