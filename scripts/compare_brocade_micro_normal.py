"""Actual micro-normal strengths on the saved separate study; no blend changes."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
from datetime import datetime, timezone
import json
import sys
import bpy
sys.path.insert(0,str(ROOT/'scripts'))
from study_brocade_cylinder import add_camera, render

bpy.ops.wm.open_mainfile(filepath=str(blend_path('Lion_Brocade_UV_Study_clear_v2.blend')))
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=960
scene.render.resolution_y=640
scene.render.resolution_percentage=100
camera=add_camera('MicroNormalMacro',.10,.39,.06)
material=bpy.data.materials['Brocade_Clear_Tile_Cloth_Study']
normal=next(node for node in material.node_tree.nodes if node.type=='NORMAL_MAP')
out=ROOT/'renders/studies/brocade_uv_study_clear_v2'
evidence=[]
for strength in (0,.18,.25):
    normal.inputs['Strength'].default_value=strength
    path=out/('micro_normal_strength_'+str(strength).replace('.','p')+'.png')
    if path.exists():
        raise FileExistsError('Preserve existing real render evidence')
    render(scene,camera,path)
    evidence.append({'strength':strength,'path':str(path)})
normal.inputs['Strength'].default_value=.18
(ROOT/'docs/brocade_micro_normal_comparison.json').write_text(json.dumps({
    'recordedAt':datetime.now(timezone.utc).isoformat(),'tileMeters':.20,
    'macroHorizontalWidthMeters':.06,'threadsPerTile':128,
    'geometryAndBlendSaved':False,'normalSource':'Real exported periodic synthetic tangent normal PNG, not photometric',
    'evidence':evidence,'visualAcceptance':'Pending actual rendered-image inspection'
},indent=2),encoding='utf-8')
print(json.dumps({'actualStrengths':[0,.18,.25],'renderWidthMeters':.06,'output':str(out)}))
