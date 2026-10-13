"""Assemble the improved body and separately generated head, without cloud calls.

Uses real source-face provenance for two Lux3D assets. The earlier complete
G1 stage is retained as a separate file; replaced head faces are not retained
inside the finished scene to manufacture conservation checks.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys, json, math
import bpy
from mathutils import Vector,Matrix
sys.path.insert(0,str(ROOT/'scripts'))
import refine_lion_master as pipeline
from fiber_tools import add_fibers
from study_brocade_cylinder import apply_cylindrical_brocade

def descendants(root):
    return [root]+[o for c in root.children for o in descendants(c)]

def disk(name,center,radius,parent,collection):
    verts=[tuple(center)]+[tuple(Vector(center)+Vector((radius*math.cos(i*math.tau/64),radius*math.sin(i*math.tau/64),0))) for i in range(64)]
    mesh=bpy.data.meshes.new(name+'_Mesh')
    mesh.from_pydata(verts,[],[(0,(i+1)%64+1,i+1) for i in range(64)]);mesh.update()
    ob=bpy.data.objects.new(name,mesh);collection.objects.link(ob)
    ob.matrix_world=Matrix.Identity(4);pipeline.parent_keep(ob,parent)
    return ob

def empty(name,pos,parent,col):
    ob=bpy.data.objects.new(name,None);col.objects.link(ob);ob.location=pos
    ob.empty_display_type='SPHERE';ob.empty_display_size=.025
    pipeline.parent_keep(ob,parent);return ob

def add_head_features():
    landmarks=json.loads((ROOT/'docs/head_candidate_parts_report_v3.json').read_text(encoding='utf-8'))['feature_estimates_fitted_world']
    col=bpy.data.collections.new('New_Head_Fitted_Features');bpy.context.scene.collection.children.link(col)
    head=bpy.data.objects['Pivot_Head'];jaw=bpy.data.objects['Pivot_Jaw']
    black=pipeline.material('New_Eye_Black_Glass',(.0025,.0025,.002),.11,coat=.4)
    brass=pipeline.material('New_Head_Brass',(.57,.30,.052),.25,.88)
    copper=pipeline.material('New_Iris_Copper',(.26,.075,.015),.24,.75)
    ivory=pipeline.material('Teeth_Ivory_Enamel',(.83,.82,.76),.38)
    ivory.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.26
    for side in ('L','R'):
        lm=landmarks['eyes'][side];normal=Vector(lm['mean_face_normal']).normalized()
        center=Vector(lm['surface_center_area_weighted'])-normal*.024
        control=empty('Pivot_Eye_'+side,center,head,col)
        globe=pipeline.sphere('Lion_EyeBall_'+side,center,.043,(1,1,.65),black,col,control)
        globe.rotation_euler=normal.to_track_quat('Z','Y').to_euler()
        iris_center=center+normal*.029
        rotation=normal.to_track_quat('Z','Y').to_euler()
        pipeline.ring('Lion_Iris_Copper_'+side,iris_center,.023,.0018,copper,col,control,rotation)
        pipeline.ring('Lion_Iris_InnerGold_'+side,iris_center+normal*.001,.0195,.00065,brass,col,control,rotation)
        pupil=pipeline.sphere('Lion_Pupil_'+side,iris_center+normal*.001,.0188,(1,1,.16),black,col,control)
        pupil.rotation_euler=rotation
        lm=landmarks['side_medallions'][side];normal=Vector(lm['mean_face_normal']).normalized()
        surface=Vector(lm['surface_center_area_weighted'])
        center=surface+normal*.017
        control=empty('Pivot_SideMedallion_'+side,center,head,col)
        cap=pipeline.sphere('Lion_SideMedallion_Convex_'+side,center,.047,(1,1,.22),brass,col,control)
        cap.rotation_euler=normal.to_track_quat('Z','Y').to_euler()
        pipeline.ring('Lion_SideMedallion_Rim_'+side,center+normal*.006,.047,.0018,brass,col,control,cap.rotation_euler)
        lm=landmarks['cheek_bells'][side];normal=Vector(lm['mean_face_normal']).normalized()
        center=Vector(lm['surface_center_area_weighted'])+normal*.028
        # Use the already tested local shell constructor, not a painted ball.
        from add_fitted_details import bell
        control=bell('CheekBell_'+side,center,.023,head,col,brass,copper)
        root=Vector((center.x,center.y-.013,center.z-.029))
        tassel=empty('Pivot_Tassel_'+side,root,head,col)
        emitter=disk('Lion_Tassel_Collar_'+side,root,.0105,tassel,col)
        emitter.data.materials.append(brass)
        add_fibers(emitter,count=3600,length=(.087,.116),radius=(.00010,.00017),
            direction=(0,0,-1),direction_strength=.5,droop=.025,angular_spread=.045,
            bend=.06,clump=.18,clump_radius=.020,seed=19100+(side=='R'),
            point_count=3,resolution=2,collection=col,material=bpy.data.materials['Fiber_Red_Scarlet'],
            name='Lion_Tassel_'+side+'_FineFiber')
    lm=landmarks['forehead_medallion'];n=Vector(lm['mean_face_normal']).normalized()
    center=Vector(lm['surface_center_area_weighted'])+n*.040
    control=empty('Pivot_Forehead_Metal',center,head,col)
    cap=pipeline.sphere('Lion_Forehead_Convex_Brass',center,.035,(1,1,.20),brass,col,control)
    cap.rotation_euler=n.to_track_quat('Z','Y').to_euler()
    pipeline.ring('Lion_Forehead_Brass_Rim',center+n*.007,.035,.0018,brass,col,control,cap.rotation_euler)
    # Distinct bevelled teeth follow a curved lower row. Placement is estimated
    # from the measured generated tooth band, then checked in actual renders.
    for i in range(11):
        x=(i-5)*.032;fraction=x/.17
        center=(x,-.714+.070*fraction*fraction,.414+.018*fraction*fraction)
        bpy.ops.mesh.primitive_cube_add(size=1,location=center)
        ob=bpy.context.object;ob.name='Lion_Tooth_%02d'%i
        ob.dimensions=(.0275,.018,.032);ob.rotation_euler.z=-fraction*.22
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        bevel=ob.modifiers.new('Soft enamel edge','BEVEL');bevel.width=.002;bevel.segments=3
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        for p in ob.data.polygons:p.use_smooth=True
        ob.data.materials.append(ivory);pipeline.link(ob,col);pipeline.parent_keep(ob,jaw)
    return {'landmark_report':'docs/head_candidate_parts_report_v3.json',
            'fitted_details':'Independent eye globes, ivory tooth objects, brass caps, slit bell shells and hanging curve tassels',
            'fit_scope':'Measured surface windows with visually estimated overlay depth; original features remain behind overlays.'}

def assemble():
    bpy.ops.wm.open_mainfile(filepath=str(blend_path('Lion_Body_Quality_Stage.blend')))
    old=bpy.data.objects['Pivot_Head']
    for ob in reversed(descendants(old)):bpy.data.objects.remove(ob,do_unlink=True)
    body=bpy.data.objects['Lion_Body']
    for p in body.data.polygons:p.material_index=0
    for ob in list(bpy.data.objects):
        if ob.type=='CURVE' and ob.get('fiber_emitter')==body.name:bpy.data.objects.remove(ob,do_unlink=True)
    for ob in bpy.data.objects:
        if ob.type=='MESH' and ob.data.attributes.get('source_face_index'):
            ob['source_asset']='g1_full_lion_4054240'
            attr=ob.data.attributes.get('source_asset_id') or ob.data.attributes.new('source_asset_id','INT','FACE')
            for d in attr.data:d.value=0
    with bpy.data.libraries.load(str(blend_path('Lion_Head_Quality_Stage_v2.blend')),link=False) as (src,dst):
        part_keys=('Head','Jaw','Beard','Ear_L','Ear_R','Brow_L','Brow_R','Nose','Crown')
        picked=[n for n in src.objects if any(n=='Lion_'+k or n.startswith('Lion_'+k+'_HighDetail') for k in part_keys)]
        for k in part_keys:
            base='Pivot_'+k
            # v2 contains unlinked old control names from target bounds reads;
            # its actual head controls received .001. v3 fixes only naming.
            picked.append(base+'.001' if base+'.001' in src.objects else base)
        dst.objects=picked
    imported=[]
    for ob in dst.objects:
        if ob is not None:
            bpy.context.scene.collection.objects.link(ob);imported.append(ob)
    # v3 only corrected the empty naming; v2 has identical mesh/UV/source IDs.
    for ob in imported:
        if ob.type=='EMPTY' and ob.name.startswith('Pivot_'):
            base=ob.name.split('.')[0]
            if bpy.data.objects.get(base) and bpy.data.objects.get(base) is not ob:
                unused=bpy.data.objects[base]
                if not unused.children and not unused.users_collection:bpy.data.objects.remove(unused)
            ob.name=base;ob['source_asset']='head_highdetail_4055287'
    pipeline.parent_keep(bpy.data.objects['Pivot_Head'],bpy.data.objects['Pivot_Body'])
    cloth=apply_cylindrical_brocade(body,ROOT/'textures/brocade_new/brocade_reference_synthesis.png',tile_m=.20)
    details=add_head_features()
    for mat in bpy.data.materials:
        if mat.name.startswith(('Fiber_Red_Scarlet','Velvet_Scarlet_Uniform','Head_Scarlet_Velvet')):
            bs=mat.node_tree.nodes.get('Principled BSDF')
            bs.inputs['Base Color'].default_value=(.21,.0027,.006,1)
            bs.inputs['Specular IOR Level'].default_value=.14
            bs.inputs['Sheen Weight'].default_value=.22
            if bs.inputs.get('Sheen Tint'):bs.inputs['Sheen Tint'].default_value=(.30,.006,.012,1)
    for img in bpy.data.images:
        if img.has_data and not img.packed_file:img.pack()
    scene=bpy.context.scene
    scene['asset_origin']='Lux3D G1 whole lion 4054240 body + isolated G1 head 4055287; locally rebuilt fur, brocade and fitted details'
    scene['web_fiber_note']='Separate sparse strand export copy; native editable splines remain in the master'
    scene.view_settings.exposure=-.30
    report={'executed_at':pipeline.now(),'source_assets':[
        {'source_asset':'g1_full_lion_4054240','path':str(ROOT/'generated/Lux3D_Lion_Base_glb.glb'),'sha256':pipeline.digest(ROOT/'generated/Lux3D_Lion_Base_glb.glb'),'retained_faces':242792,'removed_head_faces':43408},
        {'source_asset':'head_highdetail_4055287','path':str(ROOT/'generated/candidates/head_highdetail/Lion_head_highdetail_glb.glb'),'sha256':pipeline.digest(ROOT/'generated/candidates/head_highdetail/Lion_head_highdetail_glb.glb'),'retained_faces':285606}],
        'source_triangles':sum(len(o.data.polygons) for o in bpy.data.objects if o.type=='MESH' and o.data.attributes.get('source_face_index')),
        'native_strands':sum(len(o.data.splines) for o in bpy.data.objects if o.type=='CURVE' and 'fiber_emitter' in o),
        'cloth':cloth,'head_features':details,'master':str(pipeline.MASTER),
        'limitations':['Generated topology and overlapping surfaces remain; not a watertight print or a fully skinned dance rig.',
                       'Brocade tile is reference-guided synthesis, not recovery of exact hidden motifs.',
                       'Sparse GLB strand proxy differs from the dense editable native curves.']}
    pipeline.save_json(ROOT/'docs/quality_revision_assembly.json',report)
    pipeline.save_json(pipeline.REPORT,report)
    bpy.ops.wm.save_as_mainfile(filepath=str(pipeline.MASTER),compress=True)
    pipeline.render_view('revision_hero',(0,-.02,.49),(-2,-3,1.25),1.96,1400,1000,48)
    pipeline.render_view('revision_head',(0,-.53,.69),(-.3,-1,.2),.93,1300,1000,48)
    pipeline.render_view('revision_brocade',(.3,.16,.49),(1,-.10,.2),.67,1300,1000,48)
    print('QUALITY_REVISION_ASSEMBLED',report['source_triangles'],report['native_strands'],flush=True)

if __name__=='__main__':assemble()
