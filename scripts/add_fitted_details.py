"""Add editable metal fittings at inspected mesh locations, and correct fibers.

Local artistic fitting only; the source mesh and original textures are retained.
The placement report distinguishes observed surface positions from inferred
shell construction. No external services are contacted.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys, json, math
import bpy
from mathutils import Vector
sys.path.insert(0,str(ROOT/'scripts'))
import refine_lion_master as pipeline
from fiber_tools import add_fibers

def control(name,location,parent,collection):
    ob=bpy.data.objects.new('Pivot_'+name,None);collection.objects.link(ob)
    ob.location=location;ob.empty_display_type='SPHERE';ob.empty_display_size=.027
    pipeline.parent_keep(ob,parent)
    return ob

def orient(ob,normal,axis='-Y'):
    world=ob.matrix_world.copy()
    ob.rotation_euler=Vector(normal).to_track_quat(axis,'Z' if axis=='-Y' else 'Y').to_euler()
    bpy.context.view_layer.update()

def bell(name,center,radius,parent,collection,gold,copper):
    c=Vector(center);ctrl=control(name,c,parent,collection)
    verts=[];faces=[];segments=64;rings=24
    for i in range(rings+1):
        polar=.045+(math.pi-.25-.045)*i/rings
        for j in range(segments):
            az=math.tau*j/segments
            verts.append(c+Vector((radius*math.sin(polar)*math.cos(az),
                radius*math.sin(polar)*math.sin(az),radius*math.cos(polar))))
    for i in range(rings):
        for j in range(segments):
            if i>=int(rings*.63) and j in (15,16,47,48):continue
            faces.append((i*segments+j,(i+1)*segments+j,
                (i+1)*segments+(j+1)%segments,i*segments+(j+1)%segments))
    mesh=bpy.data.meshes.new('Lion_'+name+'_Shell_Geometry');mesh.from_pydata(verts,[],faces);mesh.update()
    ob=bpy.data.objects.new('Lion_'+name+'_Shell',mesh);collection.objects.link(ob)
    mesh.materials.append(gold)
    for p in mesh.polygons:p.use_smooth=True
    pipeline.parent_keep(ob,ctrl)
    solid=ob.modifiers.new('Shell_Thickness','SOLIDIFY');solid.thickness=radius*.045
    bevel=ob.modifiers.new('Soft_Slit_Edges','BEVEL');bevel.width=radius*.011;bevel.segments=2
    pipeline.sphere('Lion_'+name+'_Clapper',c+Vector((0,0,-radius*.48)),radius*.16,(1,1,1),copper,collection,ctrl)
    pipeline.ring('Lion_'+name+'_Loop',c+Vector((0,0,radius*1.13)),radius*.25,radius*.055,gold,collection,ctrl)
    return ctrl

def main():
    bpy.ops.wm.open_mainfile(filepath=str(pipeline.MASTER))
    if bpy.data.collections.get('Fitted_Metal_And_Tassels'):
        raise RuntimeError('Fitted details already exist; this one-time refinement must not be duplicated')
    col=bpy.data.collections.new('Fitted_Metal_And_Tassels');bpy.context.scene.collection.children.link(col)
    gold=pipeline.material('Metal_Polished_Brass',(.64,.35,.066),.21,.92,coat=.12)
    copper=pipeline.material('Metal_Aged_Copper',(.32,.095,.023),.30,.87)
    head=bpy.data.objects['Pivot_Head'];tail=bpy.data.objects['Pivot_Tail']
    normal=Vector((0,-.77,.64)).normalized()
    center=Vector((0,-.697,.798))+normal*.003
    ctrl=control('Forehead_Metal',center,head,col)
    cap=pipeline.sphere('Lion_Forehead_Convex_Brass',center,.044,(1,.22,.86),gold,col,ctrl)
    orient(cap,normal)
    rim=pipeline.ring('Lion_Forehead_Brass_Rim',center,.046,.0022,copper,col,ctrl,rotation=(0,0,0))
    orient(rim,normal,'Z')
    # Tiny bead edging follows the same sloping forehead plane.
    rotation=normal.to_track_quat('Z','Y').to_matrix()
    for i in range(32):
        a=math.tau*i/32;point=center+rotation@Vector((.048*math.cos(a),.048*math.sin(a),.001))
        pipeline.sphere('Lion_Forehead_Bead_%02d'%i,point,.0016,(1,1,1),gold,col,ctrl)
    for side,x,n,z in [('L',.3242,(.966,-.080,.244),.6739),('R',-.3264,(-.985,-.096,.146),.6669)]:
        n=Vector(n).normalized();center=Vector((x,-.3996,z))+n*.003
        ctrl=control('SideMedallion_'+side,center,head,col)
        rim=pipeline.ring('Lion_SideMedallion_Rim_'+side,center,.041,.0022,gold,col,ctrl,rotation=(0,0,0))
        orient(rim,n,'Z')
        center=Vector((.331 if side=='L' else -.331,-.456,.570))
        bellctrl=bell('CheekBell_'+side,center,.024,head,col,gold,copper)
        tasselctrl=control('Tassel_'+side,center+Vector((0,0,-.034)),head,col)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.007,location=tasselctrl.matrix_world.translation)
        emitter=bpy.context.object;emitter.name='Lion_Tassel_Collar_'+side
        pipeline.link(emitter,col);pipeline.parent_keep(emitter,tasselctrl);emitter.data.materials.append(copper)
        red=bpy.data.materials['Fiber_Red_Scarlet']
        result=add_fibers(emitter,count=1300,length=(.070,.112),radius=(.00012,.00018),
            direction=(0,0,-1),direction_strength=.97,droop=.09,angular_spread=.10,
            bend=.055,clump=.22,seed=4200+(side=='R'),point_count=(3,4),resolution=2,
            material=red,collection=col,name='Lion_Tassel_'+side+'_RedFiber')
        for o in result.objects:o['fitting_note']='Added suspended cords at an estimated attachment; source tassel remains behind'
    for side,x in [('L',.1141),('R',-.11617)]:
        bell('TailBell_'+side,(x,.673,.5937),.035,tail,col,gold,copper)
    # Reduce pale specular response on scarlet fibers under studio illumination.
    bsdf=bpy.data.materials['Fiber_Red_Scarlet'].node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(.32,.004,.008,1)
    bsdf.inputs['Roughness'].default_value=.72
    bsdf.inputs['Specular IOR Level'].default_value=.17
    bsdf.inputs['Sheen Weight'].default_value=.16
    palette=ROOT/'scripts/scarlet_palette.py'
    if palette.exists():
        import scarlet_palette
        scarlet_palette.refine_master_palette(ROOT)
    else:print('PALETTE_PENDING: metal fitting saved; palette will be applied separately',flush=True)
    bpy.context.scene.view_settings.look='AgX - Medium High Contrast'
    bpy.context.scene.view_settings.exposure=-.15
    bpy.context.scene['metal_fitting_note']='Observed source surface positions; added inferred shells, loops, clappers and tassel cords. Original generated fittings remain behind.'
    for image in bpy.data.images:
        if image.source=='FILE' and image.has_data and not image.packed_file:image.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(pipeline.MASTER),compress=True)
    report=json.loads(pipeline.REPORT.read_text())
    report['fitted_details_updated_at']=pipeline.now()
    report['fitted_detail_objects']=[o.name for o in col.objects]
    report['native_strands']=sum(len(o.data.splines) for o in bpy.data.objects if o.type=='CURVE' and 'fiber_emitter' in o)
    report['limitations'].append('Metal and tassel additions are fitted overlays; original generated details remain behind them.')
    pipeline.save_json(pipeline.REPORT,report)
    pipeline.render_view('draft2_hero',(0,-.02,.48),(-2,-3,1.25),1.96,1200,900,32)
    pipeline.render_view('draft2_front',(0,-.30,.49),(0,-1,.04),1.58,1200,900,32)

if __name__=='__main__':main()
