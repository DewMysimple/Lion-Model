"""Read actual source-face features at unchanged orthographic study pixels."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys, json
import bpy
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(ROOT/'scripts'))
bpy.ops.wm.open_mainfile(filepath=str(blend_path('Lion_Trim_Cloth_Recovery_Study.blend')))
f=np.load(ROOT/'docs/trim_geometry_features.npz')
mask=np.load(ROOT/'docs/trim_cloth_recovery_mask.npy')
graph=bpy.context.evaluated_depsgraph_get()
pixels=[(450,505),(515,470),(485,518),(460,275),(520,330),(640,400),
        (470,425),(480,380),(335,190),(500,455),(755,520),(808,428),
        (420,465),(475,480),(442,480),(385,435),(375,450),(535,508),
        (350,91),(337,97),(345,111)]
results=[]
for x,y in pixels:
    world_y=.19+(x-480)/960*.68
    world_z=.46+(320-y)/960*.68
    origin=Vector((4,world_y,world_z));direction=Vector((-1,0,0))
    nearest=None
    for ob in (bpy.data.objects['Lion_Body_Red_Trim'],bpy.data.objects['Lion_Body']):
        inv=ob.matrix_world.inverted()
        hit,loc,normal,index=ob.ray_cast(inv@origin,inv.to_3x3()@direction,depsgraph=graph)
        if hit:
            world=ob.matrix_world@loc
            distance=(world-origin).length
            if nearest is None or distance<nearest[0]:
                nearest=(distance,world,normal,index,ob)
    hit=nearest is not None
    if hit: _,loc,normal,index,ob=nearest
    else: loc,normal,index,ob=None,None,-1,None
    item={'pixel':[x,y],'hit':hit,'object':ob.name if ob else None,'face':int(index)}
    if hit and ob.name=='Lion_Body_Red_Trim':
        item['recovered']=bool(mask[index])
        item.update({key: f[key][index].tolist() for key in f.files})
    results.append(item)
(ROOT/'docs/trim_recovery_ray_probes.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results))
