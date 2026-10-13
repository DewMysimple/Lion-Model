"""Correct overbroad per-face appearance classes found in actual head renders.

Restore continuous atlas materials on printed head/body regions. Keep the
unambiguous isolated velvet brows and trim, ivory beard and real fitted parts.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys,json
import bpy
import numpy as np
sys.path.insert(0,str(ROOT/'scripts'))
import refine_lion_master as pipeline
from lion_material_tools import image_pixels,find_basecolor_image
from fiber_tools import add_fibers

def correct_material_boundaries():
    changed=[]
    for key in ('Head','Nose','Crown','Ear_L','Ear_R','Foreleg_L','Foreleg_R','Hindleg_L','Hindleg_R',
                'Forepaw_L','Forepaw_R','Hindpaw_L','Hindpaw_R','Tail'):
        ob=bpy.data.objects['Lion_'+key]
        for p in ob.data.polygons:p.material_index=0
        changed.append(ob.name)
    head=bpy.data.objects['Lion_Head'];original=find_basecolor_image(head.data.materials[0])
    pixels=image_pixels(original);h,w=pixels.shape[:2]
    def rgb(uv):
        if uv is None:return np.zeros(3)
        return pixels[min(h-1,int((uv[1]%1)*h)),min(w-1,int((uv[0]%1)*w)),:3]
    def red_region(s):
        c=s['position'] if 'position' in s else s['center'];r,g,b=rgb(s.get('uv'))
        # Only raised front lip and eye rims; printed forehead/back shell is
        # deliberately excluded even when its pattern contains red pixels.
        geometry=(c.y<-.698 and .47<c.z<.585 and abs(c.x)<.24) or (c.y<-.643 and .60<c.z<.72 and .07<abs(c.x)<.225)
        return geometry and r>.28 and g/max(r,1e-5)<.73 and b/max(r,1e-5)<.7
    def white_region(s):
        c=s['position'] if 'position' in s else s['center'];v=rgb(s.get('uv'))
        # Side/back white fringe, avoiding smooth eye frames and forehead art.
        geometry=c.y>-.60 and .26<c.z<.63 and abs(c.x)>.22
        return geometry and min(v)>.46 and (max(v)-min(v))/max(max(v),1e-5)<.25
    def tri_uv(t):
        t=dict(t);t['uv']=tuple(sum(q[k] for q in t['uv_corners'])/3 for k in range(2))
        return t
    for ob in list(bpy.data.objects):
        if ob.type=='CURVE' and ob.get('fiber_emitter') in ('Lion_Head','Lion_Crown','Lion_Nose'):
            bpy.data.objects.remove(ob,do_unlink=True)
    col=bpy.data.collections.new('Corrected_Head_Fringe_Groom');bpy.context.scene.collection.children.link(col)
    records=[]
    for kind,count,region,mat in [('red',42000,red_region,bpy.data.materials['Fiber_Red_Scarlet']),
                                  ('white',120000,white_region,bpy.data.materials['Fiber_Warm_Ivory'])]:
        result=add_fibers(head,count=count,length=(.009,.021) if kind=='red' else (.018,.066),
            radius=(.000085,.00015),direction=(0,-.08,-1),direction_strength=.44 if kind=='red' else .84,
            droop=.22 if kind=='red' else .38,angular_spread=.24,bend=.23,clump=.26,
            clump_count=700,clump_radius=.021,seed=20900+(kind=='white'),point_count=(3,4),resolution=2,
            triangle_filter=lambda t:region(tri_uv(t)),sample_filter=region,
            collection=col,material=mat,name='Lion_Head_Corrected'+kind.capitalize()+'Fiber')
        records.append({'part':head.name,'type':kind,**result.stats})
    # Keep a continuous red UV response rather than a mosaic of face-constant
    # white/red replacements on printed surfaces. No source image is altered.
    report=json.loads(pipeline.REPORT.read_text(encoding='utf-8'))
    report['material_boundary_correction']={'executed_at':pipeline.now(),'restored_atlas_objects':changed,
        'head_groom':records,'reason':'Actual head render showed printed cloth and baked highlight triangles wrongly classified as pure red/white materials.'}
    report['native_strands']=sum(len(o.data.splines) for o in bpy.data.objects if o.type=='CURVE' and 'fiber_emitter' in o)
    pipeline.save_json(pipeline.REPORT,report)
    pipeline.save_json(ROOT/'docs/quality_revision_assembly.json',report)
    return report

if __name__=='__main__':
    bpy.ops.wm.open_mainfile(filepath=str(pipeline.MASTER))
    report=correct_material_boundaries()
    bpy.ops.wm.save_as_mainfile(filepath=str(pipeline.MASTER),compress=True)
    pipeline.render_view('revision2_head',(0,-.53,.69),(-.3,-1,.2),.93,1300,1000,48)
    pipeline.render_view('revision2_hero',(0,-.02,.49),(-2,-3,1.25),1.96,1400,1000,48)
    print('MATERIAL_BOUNDARIES_CORRECTED',report['native_strands'],flush=True)
