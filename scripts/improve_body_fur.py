"""Build a dense body-fur study on an independent copy. No cloud calls.

The source mesh and UVs remain editable. Scarlet velvet replaces baked bright
patches on the isolated red trim; real tapered splines supply the fine detail.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys, json, math
import bpy
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(ROOT/'scripts'))
import refine_lion_master as pipeline
from fiber_tools import add_fibers

BODY_KEYS=('Body_Red_Trim','Body','Tail','Foreleg_L','Foreleg_R','Hindleg_L','Hindleg_R',
           'Forepaw_L','Forepaw_R','Hindpaw_L','Hindpaw_R')

def apply_body_quality():
    image=bpy.data.images.get('lion_basecolor_refined.png')
    if image is None:
        image=bpy.data.images.load(str(ROOT/'textures/generated/lion_basecolor_refined.png'),check_existing=True)
    w,h=image.size
    pixels=np.array(image.pixels[:],dtype=np.float32).reshape(h,w,4)
    def rgb(uv):
        if uv is None:return np.zeros(3)
        return pixels[min(h-1,int((uv[1]%1)*h)),min(w-1,int((uv[0]%1)*w)),:3]
    def red_uv(uv):
        r,g,b=rgb(uv)
        return r>.30 and g/max(r,1e-5)<.72 and b/max(r,1e-5)<.70 and r-g>.09
    def white_uv(uv):
        c=rgb(uv);return min(c)>.48 and (max(c)-min(c))/max(max(c),1e-5)<.25
    def tri_uv(t):
        return tuple(sum(q[k] for q in t['uv_corners'])/3 for k in range(2)) if t['uv_corners'] else None
    base=pipeline.material('Velvet_Scarlet_Uniform_Base',(.31,.0045,.009),.88,sheen=.28)
    base.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.16
    red=bpy.data.materials.get('Fiber_Red_Scarlet')
    bs=red.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(.31,.0045,.009,1)
    bs.inputs['Roughness'].default_value=.82
    bs.inputs['Specular IOR Level'].default_value=.16
    bs.inputs['Sheen Weight'].default_value=.24
    white=bpy.data.materials['Fiber_Warm_Ivory']
    bs=white.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(.76,.74,.69,1)
    bs.inputs['Roughness'].default_value=.72
    bs.inputs['Specular IOR Level'].default_value=.20
    stats=[];assignments={}
    col=bpy.data.collections.new('Dense_Body_Editable_Fibers')
    bpy.context.scene.collection.children.link(col)
    for i,key in enumerate(BODY_KEYS):
        ob=bpy.data.objects.get('Lion_'+key)
        if ob is None:continue
        for o in list(bpy.data.objects):
            if o.type=='CURVE' and o.get('fiber_emitter')==ob.name:
                bpy.data.objects.remove(o,do_unlink=True)
        # The Body atlas includes printed red cloth. Painting its RGB-selected
        # triangles velvet caused visible islands in the first actual study.
        # Its garment material is rebuilt separately; only isolated trim and
        # limb/tail fur receive the scarlet base here.
        if key=='Body':
            for p in ob.data.polygons:p.material_index=0
            assignments[ob.name]=0
            continue
        ob.data.materials.append(base);slot=len(ob.data.materials)-1
        uv=ob.data.uv_layers.active
        assigned=0
        for poly in ob.data.polygons:
            u=tuple(sum(uv.data[j].uv[k] for j in poly.loop_indices)/len(poly.loop_indices) for k in range(2))
            if key=='Body_Red_Trim' or red_uv(u):
                poly.material_index=slot;assigned+=1
        assignments[ob.name]=assigned
        counts={'Body_Red_Trim':320000,'Body':10000,'Tail':32000,
                'Foreleg_L':28000,'Foreleg_R':28000,'Hindleg_L':28000,'Hindleg_R':28000,
                'Forepaw_L':4500,'Forepaw_R':4500,'Hindpaw_L':4500,'Hindpaw_R':4500}
        all_red=key=='Body_Red_Trim'
        print('DENSE_FIBER_START',ob.name,counts[key],flush=True)
        result=add_fibers(ob,count=counts[key],length=(.008,.020),radius=(.000095,.00016),
            direction=(0,.13,-1),direction_strength=.45,droop=.20,angular_spread=.22,
            bend=.20,clump=.18,clump_count=4500,clump_radius=.014,
            seed=8600+i,point_count=3,resolution=2,max_splines_per_object=20000,
            triangle_filter=None if all_red else lambda t:red_uv(tri_uv(t)),
            sample_filter=None if all_red else lambda s:red_uv(s['uv']),
            material=red,collection=col,name=ob.name+'_DenseRedFiber')
        stats.append({'part':ob.name,'type':'red',**result.stats})
        if key=='Tail' or 'paw' in key:
            long=key=='Tail';count=65000 if long else 7000
            def length(sample,rng):
                a,b=(.028,.095) if long else (.009,.023)
                return min(rng.uniform(a,b),max(.008,sample['position'].z*.60))
            result=add_fibers(ob,count=count,length=length,radius=(.00009,.00015),
                direction=(0,.45 if long else 0,-1),direction_strength=.79 if long else .40,
                droop=.40 if long else .22,angular_spread=.27,bend=.24,clump=.30,
                clump_count=850 if long else 200,clump_radius=.035 if long else .010,
                seed=9700+i,point_count=(3,4),resolution=2,
                triangle_filter=lambda t:white_uv(tri_uv(t)),sample_filter=lambda s:white_uv(s['uv']),
                material=white,collection=col,name=ob.name+'_DenseWhiteFiber')
            stats.append({'part':ob.name,'type':'white',**result.stats})
        pipeline.save_json(ROOT/'docs/body_dense_fur_progress.json',stats)
    return {'executed_at':pipeline.now(),'fiber_stats':stats,'scarlet_base_faces':assignments,
            'body_strands':sum(s['actual'] for s in stats),
            'limitations':['Static emitter parenting; regeneration is needed after vertex deformation.',
                           'Scarlet base intentionally removes source baked lighting on red trim.']}

def study_render(name):
    pipeline.set_camera((.25,.16,.47),(1,-.12,.24),.77,1200,950)
    scene=bpy.context.scene;scene.cycles.samples=48
    scene.render.filepath=str(ROOT/'renders/studies/body_dense_fur_study'/ (name+'.png'))
    bpy.ops.render.render(write_still=True)

if __name__=='__main__':
    (ROOT/'renders/studies/body_dense_fur_study').mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend_path('Lion_G1_Refined_Stage.blend')))
    study_render('before_body_trim')
    report=apply_body_quality()
    pipeline.save_json(ROOT/'docs/body_dense_fur_study.json',report)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path('Lion_Body_Quality_Stage.blend')),compress=True)
    study_render('after_body_trim')
    pipeline.set_camera((0,0,.49),(1,0,.08),1.88,1400,1000)
    bpy.context.scene.render.filepath=str(ROOT/'renders/studies/body_dense_fur_study/after_whole_side.png')
    bpy.ops.render.render(write_still=True)
    print('BODY_QUALITY_STUDY_DONE',report['body_strands'],flush=True)
