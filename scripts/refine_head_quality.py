"""Locally refine the separately generated, fitted head. No cloud calls.

Color-classed physical response and real Bezier fibers improve appearance; no
claim is made that color classes recover original hidden materials or anatomy.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys, json
import bpy
import numpy as np
sys.path.insert(0,str(ROOT/'scripts'))
import refine_lion_master as pipeline
from lion_material_tools import prepare_lion_material,apply_lion_material,image_pixels,find_basecolor_image
from fiber_tools import add_fibers

HEAD_KEYS=('Head','Jaw','Beard','Ear_L','Ear_R','Brow_L','Brow_R','Nose','Crown')

def refine_head_quality():
    parts=[bpy.data.objects['Lion_'+k] for k in HEAD_KEYS if bpy.data.objects.get('Lion_'+k)]
    original=parts[0].data.materials[0]
    bundle=prepare_lion_material(original,ROOT/'textures/highdetail_head',weave=False)
    bundle['material'].name='HighDetail_Head_Atlas_PBR'
    pixels=bundle['pixels'];h,w=pixels.shape[:2]
    def rgb(uv):
        if uv is None:return np.zeros(3)
        return pixels[min(h-1,int((uv[1]%1)*h)),min(w-1,int((uv[0]%1)*w)),:3]
    def red_uv(uv):
        r,g,b=rgb(uv)
        return r>.28 and g/max(r,1e-5)<.77 and b/max(r,1e-5)<.75 and r-g>.08
    def white_uv(uv):
        c=rgb(uv);return min(c)>.46 and (max(c)-min(c))/max(max(c),1e-5)<.24
    def tri_uv(t):
        return tuple(sum(q[k] for q in t['uv_corners'])/3 for k in range(2)) if t['uv_corners'] else None
    redbase=pipeline.material('Head_Scarlet_Velvet_Base',(.31,.0045,.009),.88,sheen=.24)
    redbase.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.16
    whitebase=pipeline.material('Head_Ivory_Fringe_Base',(.74,.72,.68),.86,sheen=.23)
    whitebase.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.18
    red=bpy.data.materials.get('Fiber_Red_Scarlet') or pipeline.material('Fiber_Red_Scarlet',(.31,.0045,.009),.82,sheen=.24)
    white=bpy.data.materials.get('Fiber_Warm_Ivory') or pipeline.material('Fiber_Warm_Ivory',(.76,.74,.69),.72,sheen=.25)
    apply_lion_material(parts,bundle)
    col=bpy.data.collections.new('HighDetail_Head_Editable_Fibers')
    bpy.context.scene.collection.children.link(col)
    records=[];assignments={}
    red_counts={'Head':90000,'Jaw':32000,'Beard':0,'Ear_L':32000,'Ear_R':32000,
                'Brow_L':48000,'Brow_R':48000,'Nose':15000,'Crown':7000}
    for i,ob in enumerate(parts):
        key=ob.name.removeprefix('Lion_')
        ob.data.materials.append(redbase);redslot=len(ob.data.materials)-1
        ob.data.materials.append(whitebase);whiteslot=len(ob.data.materials)-1
        uv=ob.data.uv_layers[0]
        redfaces=whitefaces=0
        for poly in ob.data.polygons:
            u=tuple(sum(uv.data[j].uv[k] for j in poly.loop_indices)/len(poly.loop_indices) for k in range(2))
            if key.startswith('Brow') or red_uv(u):
                poly.material_index=redslot;redfaces+=1
            elif key=='Beard' or white_uv(u):
                poly.material_index=whiteslot;whitefaces+=1
        assignments[ob.name]={'scarlet_faces':redfaces,'ivory_faces':whitefaces}
        count=red_counts.get(key,0)
        if count:
            all_red=key.startswith('Brow')
            print('HEAD_FIBER_START',ob.name,'red',count,flush=True)
            result=add_fibers(ob,count=count,length=(.009,.022),radius=(.00009,.00015),
                direction=(0,-.1,-1),direction_strength=.43,droop=.20,angular_spread=.24,
                bend=.22,clump=.20,clump_count=1500,clump_radius=.012,
                seed=11800+i,point_count=3,resolution=2,
                triangle_filter=None if all_red else lambda t:red_uv(tri_uv(t)),
                sample_filter=None if all_red else lambda s:red_uv(s['uv']),
                material=red,collection=col,name=ob.name+'_HighDetailRedFiber')
            records.append({'part':ob.name,'type':'red',**result.stats})
        whites=90000 if key=='Beard' else 45000 if key=='Head' else 6000 if key.startswith('Ear') else 0
        if whites:
            def white_tri(t):
                uv=tri_uv(t)
                if key=='Beard':return True
                c=t['center']
                return white_uv(uv) and (key!='Head' or c.y>-.59 or c.z<.55 or c.z>.86)
            def white_sample(s):
                if key=='Beard':return True
                c=s['position']
                return white_uv(s['uv']) and (key!='Head' or c.y>-.59 or c.z<.55 or c.z>.86)
            long=key in ('Beard','Head')
            def length(s,rng):
                a,b=(.016,.060) if key=='Beard' else (.018,.055) if key=='Head' else (.005,.015)
                # Guides have varied lengths to avoid a single even curtain.
                return min(rng.uniform(a,b)*(1+.22*np.sin(s['position'].x*105)),max(.006,s['position'].z*.35))
            print('HEAD_FIBER_START',ob.name,'white',whites,flush=True)
            result=add_fibers(ob,count=whites,length=length,radius=(.00008,.00014),
                direction=(0,-.14,-1),direction_strength=.85 if long else .4,
                droop=.42 if long else .18,angular_spread=.29,bend=.26,
                clump=.32,clump_count=450,clump_radius=.025,
                seed=12800+i,point_count=(3,4),resolution=2,
                triangle_filter=white_tri,sample_filter=white_sample,
                material=white,collection=col,name=ob.name+'_HighDetailWhiteFiber')
            records.append({'part':ob.name,'type':'white',**result.stats})
        pipeline.save_json(ROOT/'docs/head_quality_progress.json',records)
    return {'executed_at':pipeline.now(),'material_assignments':assignments,'fiber_stats':records,
            'head_strands':sum(r['actual'] for r in records),
            'source_head_glb_sha256':pipeline.digest(ROOT/'generated/candidates/head_highdetail/Lion_head_highdetail_glb.glb'),
            'limitations':['Native curve grooming is a synthetic local reconstruction, not recovered original hair.',
                           'Generated cloth patterns on the head remain approximate.',
                           'Color-based material boundaries require visual review.']}

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if len(args)!=2:raise ValueError('Use -- input.blend output.blend')
    bpy.ops.wm.open_mainfile(filepath=str(resolve_project_path(args[0])))
    report=refine_head_quality()
    pipeline.save_json(ROOT/'docs/head_quality_study.json',report)
    for img in bpy.data.images:
        if img.has_data and not img.packed_file:img.pack()
    output=resolve_project_path(args[1]);output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    print('HEAD_QUALITY_DONE',report['head_strands'],flush=True)
