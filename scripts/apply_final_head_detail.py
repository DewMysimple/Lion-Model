"""Apply the reviewed forehead cloth and editable fine metal ornament.

The floral wire and beads are local design synthesis, not hidden reference
recovery. Every geometry addition remains independently editable.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys,math,json
import bpy
from mathutils import Vector
sys.path.insert(0,str(ROOT/'scripts'))
import refine_lion_master as pipeline
from study_head_forehead_brocade import apply_forehead_brocade

def ornaments():
    col=bpy.data.collections.new('Fine_Metal_Ornament');bpy.context.scene.collection.children.link(col)
    gold=bpy.data.materials['New_Head_Brass']
    copper=bpy.data.materials['New_Iris_Copper']
    added=[]
    for key,radius,depth in [('Forehead',.035,.20),('SideMedallion_Convex_L',.047,.22),('SideMedallion_Convex_R',.047,.22)]:
        name='Lion_Forehead_Convex_Brass' if key=='Forehead' else 'Lion_'+key
        ob=bpy.data.objects[name];parent=ob.parent
        center=ob.matrix_world.translation.copy()
        basis=ob.matrix_world.to_3x3().normalized()
        u,v,n=(basis@Vector(a) for a in ((1,0,0),(0,1,0),(0,0,1)))
        for i in range(32):
            t=i*math.tau/32;rho=radius*.97
            position=center+(u*math.cos(t)+v*math.sin(t))*rho+n*(radius*depth*.20)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=.0010,location=position)
            bead=bpy.context.object;bead.name='Lion_'+key+'_Bead_%02d'%i
            for p in bead.data.polygons:p.use_smooth=True
            bead.data.materials.append(gold);pipeline.link(bead,col);pipeline.parent_keep(bead,parent)
            added.append(bead.name)
        curve=bpy.data.curves.new('Lion_'+key+'_FloralWire_Geometry','CURVE')
        curve.dimensions='3D';curve.bevel_depth=.00032;curve.bevel_resolution=2
        spline=curve.splines.new('POLY');spline.points.add(159);spline.use_cyclic_u=True
        for i,p in enumerate(spline.points):
            t=i*math.tau/160;rho=radius*(.47+.10*math.cos(5*t))
            z=radius*depth*math.sqrt(1-(rho/radius)**2)+.00026
            position=center+(u*math.cos(t)+v*math.sin(t))*rho+n*z
            p.co=(*position,1)
        wire=bpy.data.objects.new('Lion_'+key+'_FloralWire',curve);col.objects.link(wire)
        curve.materials.append(copper);pipeline.parent_keep(wire,parent)
        # This decorative curve is not a hair proxy; export converts a COPY.
        wire['decorative_curve_export']=True
        added.append(wire.name)
    return added

if __name__=='__main__':
    bpy.ops.wm.open_mainfile(filepath=str(pipeline.MASTER))
    cloth=apply_forehead_brocade(root=ROOT)['report']
    added=ornaments()
    report=json.loads(pipeline.REPORT.read_text(encoding='utf-8'))
    report['final_head_detail']={'executed_at':pipeline.now(),'forehead_cloth':cloth,
        'metal_ornament_objects':added,'ornament_scope':'Local floral wire and bead design synthesis; no claim of exact reference engraving.'}
    report['native_strands']=sum(len(o.data.splines) for o in bpy.data.objects if o.type=='CURVE' and 'fiber_emitter' in o)
    for img in bpy.data.images:
        if img.has_data and not img.packed_file:img.pack()
    pipeline.save_json(pipeline.REPORT,report)
    pipeline.save_json(ROOT/'docs/quality_revision_assembly.json',report)
    bpy.ops.wm.save_as_mainfile(filepath=str(pipeline.MASTER),compress=True)
    print('FINAL_HEAD_DETAIL_SAVED',report['native_strands'],flush=True)
