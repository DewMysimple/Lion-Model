"""Correct fitted cap occlusion and tassel grooming after actual draft review."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys, math, json
import bpy
from mathutils import Vector
sys.path.insert(0,str(ROOT/'scripts'))
import refine_lion_master as pipeline
from fiber_tools import add_fibers

bpy.ops.wm.open_mainfile(filepath=str(pipeline.MASTER))
cap=bpy.data.objects['Pivot_Forehead_Metal']
cap.location+=Vector((0,-.042,.016))
cap['review_adjustment']='Moved forward after actual draft showed the generated forehead dome occluding the added metal'
col=bpy.data.collections['Fitted_Metal_And_Tassels']
records=[]
for side in ('L','R'):
    emitter=bpy.data.objects['Lion_Tassel_Collar_'+side]
    for ob in list(bpy.data.objects):
        if ob.type=='CURVE' and ob.get('fiber_emitter')==emitter.name:
            bpy.data.objects.remove(ob,do_unlink=True)
    c=emitter.matrix_world.translation.copy()
    verts=[tuple(c)]
    for j in range(64):
        a=math.tau*j/64;verts.append(tuple(c+Vector((.012*math.cos(a),.012*math.sin(a),0))))
    # Clockwise face winding gives downward (-Z) strand roots.
    faces=[(0,(j+1)%64+1,j+1) for j in range(64)]
    mesh=bpy.data.meshes.new('Tassel_Downward_RootDisk_'+side)
    mesh.from_pydata(verts,[],faces);mesh.update()
    emitter.data=mesh
    emitter.matrix_world.identity()
    # Reset to identity world, since disk vertices are authored in world space.
    bpy.context.view_layer.update()
    emitter.matrix_world.identity()
    mesh.materials.append(bpy.data.materials['Metal_Aged_Copper'])
    result=add_fibers(emitter,count=1800,length=(.092,.125),radius=(.00014,.00022),
        direction=(0,0,-1),direction_strength=.50,droop=.04,angular_spread=.045,
        bend=.055,clump=.16,seed=4210+(side=='R'),point_count=(3,4),resolution=2,
        material=bpy.data.materials['Fiber_Red_Scarlet'],collection=col,
        name='Lion_Tassel_'+side+'_RedFiber')
    records.append(result.stats)
report=json.loads(pipeline.REPORT.read_text())
report['fitting_review_corrected_at']=pipeline.now()
report['tassel_final_stats']=records
report['native_strands']=sum(len(o.data.splines) for o in bpy.data.objects if o.type=='CURVE' and 'fiber_emitter' in o)
pipeline.save_json(pipeline.REPORT,report)
bpy.ops.wm.save_as_mainfile(filepath=str(pipeline.MASTER),compress=True)
pipeline.render_view('draft3_head',(0,-.52,.72),(-.4,-1,.25),.96,1100,850,32)
pipeline.render_view('draft3_front',(0,-.30,.49),(0,-1,.04),1.58,1200,900,32)
