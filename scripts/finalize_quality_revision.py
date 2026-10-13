"""Apply audited cloth recovery, regenerate trim fur, and add native limits.

Limits apply to rigid transform controls in Blender. They are not a skin rig,
and GLB viewers do not execute Blender constraints.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys,json,math
import bpy
sys.path.insert(0,str(ROOT/'scripts'))
import refine_lion_master as pipeline
from recover_trim_cloth import load_recovery_mask,apply_trim_cloth_recovery
from fiber_tools import add_fibers

def add_limits():
    specs={'Pivot_Head':((-12,12),(-12,12),(-25,25)),
           'Pivot_Jaw':((-20,8),(-3,3),(-3,3)),
           'Pivot_Tail':((-15,15),(-20,20),(-20,20)),
           'Pivot_Eye_L':((-18,18),(-18,18),(-5,5)),
           'Pivot_Eye_R':((-18,18),(-18,18),(-5,5)),
           'Pivot_Ear_L':((-12,12),(-18,18),(-12,12)),
           'Pivot_Ear_R':((-12,12),(-18,18),(-12,12))}
    for name,axes in specs.items():
        ob=bpy.data.objects[name]
        constraint=ob.constraints.get('Local_Design_Rotation_Limits') or ob.constraints.new('LIMIT_ROTATION')
        constraint.name='Local_Design_Rotation_Limits';constraint.owner_space='LOCAL'
        for axis,(lo,hi) in zip('xyz',axes):
            setattr(constraint,'use_limit_'+axis,True)
            setattr(constraint,'min_'+axis,math.radians(lo));setattr(constraint,'max_'+axis,math.radians(hi))
        ob['rotation_limits_degrees']=json.dumps(axes)
        ob['limit_scope']='Native Blender rigid transform controls; GLB includes metadata only, not executable constraints'
    return specs

def finalize():
    bpy.ops.wm.open_mainfile(filepath=str(pipeline.MASTER))
    trim=bpy.data.objects['Lion_Body_Red_Trim']
    mask=load_recovery_mask(trim,ROOT)
    recovery=apply_trim_cloth_recovery(trim,mask,ROOT)['report']
    for ob in list(bpy.data.objects):
        if ob.type=='CURVE' and ob.get('fiber_emitter')==trim.name:
            bpy.data.objects.remove(ob,do_unlink=True)
    col=bpy.data.collections.new('Audited_Body_Trim_Fibers');bpy.context.scene.collection.children.link(col)
    result=add_fibers(trim,density=240000,length=(.008,.020),radius=(.000095,.00016),
        direction=(0,.13,-1),direction_strength=.45,droop=.20,angular_spread=.22,
        bend=.20,clump=.18,clump_count=4500,clump_radius=.014,
        seed=22917,point_count=3,resolution=2,max_splines_per_object=20000,
        triangle_filter=lambda t:not mask[t['polygon_index']],
        material=bpy.data.materials['Fiber_Red_Scarlet'],collection=col,name='Lion_Body_Red_Trim_AuditedRedFiber')
    limits=add_limits()
    report=json.loads(pipeline.REPORT.read_text(encoding='utf-8'))
    report['audited_trim_recovery']={'executed_at':pipeline.now(),'selected_cloth_faces':int(mask.sum()),
        'retained_fur_faces':int((~mask).sum()),'cloth_material':recovery,'fibers_regenerated':result.stats}
    report['rotation_limits_degrees']=limits
    report['rotation_limits_scope']='Native rigid pivots with local rotation constraints; no skin deformation or authored dance animation'
    report['native_strands']=sum(len(o.data.splines) for o in bpy.data.objects if o.type=='CURVE' and 'fiber_emitter' in o)
    for img in bpy.data.images:
        if img.has_data and not img.packed_file:img.pack()
    pipeline.save_json(pipeline.REPORT,report)
    pipeline.save_json(ROOT/'docs/quality_revision_assembly.json',report)
    bpy.ops.wm.save_as_mainfile(filepath=str(pipeline.MASTER),compress=True)
    pipeline.render_view('revision3_brocade',(.3,.16,.49),(1,-.1,.2),.67,1300,1000,48)
    pipeline.render_view('revision3_hero',(0,-.02,.49),(-2,-3,1.25),1.96,1400,1000,48)
    print('QUALITY_REVISION_FINALIZED',report['native_strands'],flush=True)

if __name__=='__main__':finalize()
