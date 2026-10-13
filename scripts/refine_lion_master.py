"""Local refinement/export/render utilities for the Lux3D lion project.

Run in Blender 5: --background --python this.py -- build|export|render
Native curves stay editable in the master. Export uses a separate sparse mesh
copy; the original GLB, original UVs and source geometry are preserved.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
from datetime import datetime
import sys, json, math, hashlib, time
import bpy
import numpy as np
from mathutils import Vector, Matrix

sys.path.insert(0, str(ROOT / 'scripts'))
from lion_material_tools import prepare_lion_material, apply_lion_material
from fiber_tools import add_fibers

MASTER = blend_path('Lion_Final_Master.blend')
REPORT = ROOT / 'docs/final_refinement.json'
MODE = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'build'
for sub in ('blender', 'blender/checkpoints', 'blender/studies', 'exports', 'renders/final', 'docs'):
    (ROOT / sub).mkdir(parents=True, exist_ok=True)

def now():
    return datetime.now().astimezone().isoformat()

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2), encoding='utf-8')

def link(obj, collection):
    for old in list(obj.users_collection): old.objects.unlink(obj)
    collection.objects.link(obj)

def parent_keep(obj, parent):
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted_safe()
    obj.matrix_world = world

def material(name, color, roughness=.5, metal=0, coat=0, sheen=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Coat Weight'].default_value = coat
    bsdf.inputs['Coat Roughness'].default_value = .085
    bsdf.inputs['Sheen Weight'].default_value = sheen
    bsdf.inputs['Sheen Roughness'].default_value = .55
    return mat

def sphere(name, position, radius, scale, mat, collection, parent):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=position)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for p in ob.data.polygons: p.use_smooth = True
    ob.data.materials.append(mat)
    link(ob, collection)
    parent_keep(ob, parent)
    return ob

def ring(name, center, radius, thickness, mat, collection, parent, rotation=(math.pi/2,0,0)):
    bpy.ops.mesh.primitive_torus_add(major_segments=96, minor_segments=12,
        location=center, rotation=rotation, major_radius=radius, minor_radius=thickness)
    ob=bpy.context.object
    ob.name=name
    for p in ob.data.polygons: p.use_smooth=True
    ob.data.materials.append(mat)
    link(ob,collection); parent_keep(ob,parent)
    return ob

def eyes(collection):
    head = bpy.data.objects['Pivot_Head']
    black = material('Eye_Obsidian_Gloss', (.004,.003,.002), .11, coat=.75)
    copper = material('Eye_Copper_Iris', (.46,.14,.025), .23, .82)
    brass = material('Eye_Gold_Fillet', (.68,.37,.075), .20, .88)
    objs=[]
    for side,x,y in [('L',.137,-.589),('R',-.137,-.593)]:
        center=Vector((x,y,.676))
        control=bpy.data.objects.new('Pivot_Eye_'+side,None)
        collection.objects.link(control)
        control.location=center
        control.empty_display_type='SPHERE'; control.empty_display_size=.047
        parent_keep(control,head)
        control['purpose']='Independent eyeball rotation about its own fitted center'
        globe=sphere('Lion_EyeBall_'+side,center,.043,(1,.78,1),black,collection,control)
        objs.append(globe)
        objs.append(ring('Lion_Iris_Copper_'+side,(x,y-.033,.676),.027,.003,copper,collection,control))
        objs.append(ring('Lion_Iris_InnerGold_'+side,(x,y-.035,.676),.022,.001,brass,collection,control))
        objs.append(sphere('Lion_Pupil_'+side,(x,y-.035,.676),.0205,(1,.23,1),black,collection,control))
    return objs

def setup_studio():
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1
    scene.render.engine='CYCLES'
    scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.cycles.adaptive_threshold=.035
    scene.cycles.max_bounces=8
    scene.cycles.transparent_max_bounces=8
    prefs=bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type='OPTIX'; prefs.get_devices()
        for d in prefs.devices: d.use=(d.type=='OPTIX')
        scene.cycles.device='GPU'
    except Exception: scene.cycles.device='CPU'
    scene.view_settings.view_transform='AgX'
    scene.view_settings.exposure=0
    scene.world.use_nodes=True
    scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.16,.17,.19,1)
    scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.4
    studio=bpy.data.collections.new('Studio_Render_Only')
    scene.collection.children.link(studio)
    floor=material('Studio_Grey',(.19,.20,.22),.86)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.004))
    ob=bpy.context.object; ob.name='Studio_Floor'; ob.data.materials.append(floor); link(ob,studio)
    for name,loc,power,size,color in [
        ('Key',(-2.2,-3.2,3.1),350,2.5,(1,.94,.87)),
        ('Fill',(2.8,-1.5,1.8),220,2.7,(.88,.94,1)),
        ('Rim',(.5,2.1,2.8),420,2.4,(1,.94,.88))]:
        light=bpy.data.lights.new('Studio_'+name,'AREA');light.energy=power;light.shape='DISK';light.size=size;light.color=color
        ob=bpy.data.objects.new(light.name,light);studio.objects.link(ob);ob.location=loc
        ob.rotation_euler=(Vector((0,0,.55))-ob.location).to_track_quat('-Z','Y').to_euler()
    camdata=bpy.data.cameras.new('Presentation_Camera');camdata.type='ORTHO';camdata.lens=55
    cam=bpy.data.objects.new('Presentation_Camera',camdata);studio.objects.link(cam);scene.camera=cam
    scene.render.image_settings.file_format='PNG'
    scene.render.film_transparent=False
    return scene

def set_camera(target, direction, scale, width=1400, height=1000):
    scene=bpy.context.scene;cam=scene.camera
    target=Vector(target);cam.location=target+Vector(direction).normalized()*4
    up='X' if abs(Vector(direction).normalized().z)>.98 else 'Y'
    # Camera local Y supplies screen-up except vertical top views.
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z',up).to_euler()
    cam.data.ortho_scale=scale
    cam.data.clip_start=.001;cam.data.clip_end=250
    scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100
    bpy.context.view_layer.update()

def render_view(name,target,direction,scale,width=1400,height=1000,samples=None):
    set_camera(target,direction,scale,width,height)
    if samples: bpy.context.scene.cycles.samples=samples
    output_dir=ROOT/('renders/studies/final_revisions' if name.startswith(('draft','revision')) else 'renders/final')
    output_dir.mkdir(parents=True,exist_ok=True)
    bpy.context.scene.render.filepath=str(output_dir/ (name+'.png'))
    print('RENDER_START',name,now(),flush=True)
    bpy.ops.render.render(write_still=True)
    print('RENDER_DONE',name,flush=True)

def build():
    source=blend_path('Lion_Detailed_Parts.blend')
    if not source.exists(): source=blend_path('Lion_Parts_Working.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    for ob in list(bpy.data.objects):
        if ob.type in {'CAMERA','LIGHT'} or not (ob.name.startswith('Lion_') or ob.name.startswith('Pivot_')):
            bpy.data.objects.remove(ob,do_unlink=True)
    parts=[ob for ob in bpy.data.objects if ob.type=='MESH' and ob.name.startswith('Lion_')]
    geometry_triangles=sum(len(ob.data.polygons) for ob in parts)
    assert geometry_triangles==286200, geometry_triangles
    original_material=parts[0].data.materials[0]
    bundle=prepare_lion_material(original_material,ROOT/'textures/generated')
    apply_lion_material(parts,bundle)
    features=bpy.data.collections.new('Head_Detailed_Eyes');bpy.context.scene.collection.children.link(features)
    eyes(features)
    hairs=bpy.data.collections.new('Native_Editable_Fibers');bpy.context.scene.collection.children.link(hairs)
    red=material('Fiber_Red_Scarlet',(.42,.009,.013),.52,sheen=.42)
    white=material('Fiber_Warm_Ivory',(.79,.77,.72),.63,sheen=.34)
    pixels=bundle['pixels'];h,w=pixels.shape[:2]
    def color(uv):
        if uv is None:return (0,0,0)
        return pixels[min(h-1,int((uv[1]%1)*h)),min(w-1,int((uv[0]%1)*w)),:3]
    def red_uv(uv,soft=False):
        r,g,b=color(uv)
        return r>.31 and g/max(r,1e-5)<(.76 if soft else .67) and b/max(r,1e-5)<.64 and r-g>.10
    def white_uv(uv,soft=False):
        rgb=color(uv);hi=max(rgb);lo=min(rgb)
        return lo>(.43 if soft else .53) and (hi-lo)/max(hi,1e-5)<.25
    def filter_for(kind):
        def tri(t):
            corners=t['uv_corners'];uv=tuple(sum(q[k] for q in corners)/3 for k in range(2)) if corners else None
            return red_uv(uv,True) if kind=='red' else white_uv(uv,True)
        return tri, lambda s: red_uv(s['uv']) if kind=='red' else white_uv(s['uv'])
    red_counts={'Head':28000,'Body':46000,'Body_Red_Trim':46000,'Brow_L':12000,'Brow_R':12000,
        'Ear_L':6000,'Ear_R':6000,'Crown':1400,'Jaw':7000,'Nose':2200,'Tail':4000,
        'Foreleg_L':4000,'Foreleg_R':4000,'Hindleg_L':4000,'Hindleg_R':4000,
        'Forepaw_L':1200,'Forepaw_R':1200,'Hindpaw_L':1200,'Hindpaw_R':1200}
    if any(ob.name=='Lion_Body_Red_Trim' for ob in parts):red_counts['Body']=3000
    if any(ob.name.startswith('Lion_Brow_') for ob in parts):red_counts['Head']=10000
    fiber_stats=[]
    for i,ob in enumerate(sorted(parts,key=lambda o:o.name)):
        key=ob.name.removeprefix('Lion_')
        count=red_counts.get(key,0)
        if count:
            tr,sa=filter_for('red')
            print('FIBER_START',ob.name,'red',count,now(),flush=True)
            result=add_fibers(ob,count=count,length=(.008,.025) if 'Brow' not in key else (.015,.032),
                radius=(.00013,.00022),direction=(0,-.06,-1),direction_strength=.25,
                droop=.22,angular_spread=.30,bend=.13,clump=.12,seed=730+i,
                point_count=(3,4),resolution=2,max_splines_per_object=20000,
                triangle_filter=tr,sample_filter=sa,material=red,collection=hairs,name=ob.name+'_RedFiber')
            fiber_stats.append({'part':ob.name,'type':'red',**result.stats})
            print('FIBER_DONE',ob.name,result.stats['actual'],flush=True)
        whites=16000 if key=='Beard' else 20000 if key=='Tail' else 2600 if 'paw' in key else 1500 if 'Ear' in key else 0
        if whites:
            tr,sa=filter_for('white')
            long=key in ('Beard','Tail')
            def length(sample,rng, long=long,key=key):
                lo,hi=((.032,.12) if key=='Tail' else (.028,.065)) if long else (.006,.020)
                return min(rng.uniform(lo,hi),max(.007,sample['position'].z*.65))
            print('FIBER_START',ob.name,'white',whites,now(),flush=True)
            result=add_fibers(ob,count=whites,length=length,radius=(.00012,.00020),
                direction=(0,.16 if key=='Tail' else -.10,-1),direction_strength=.86 if long else .35,
                droop=.45 if long else .18,angular_spread=.20,bend=.15,clump=.22,
                seed=1730+i,point_count=(3,5),resolution=2,
                triangle_filter=tr,sample_filter=sa,material=white,collection=hairs,name=ob.name+'_WhiteFiber')
            fiber_stats.append({'part':ob.name,'type':'white',**result.stats})
            print('FIBER_DONE',ob.name,result.stats['actual'],flush=True)
        save_json(ROOT/'docs/fiber_build_progress.json',fiber_stats)
    scene=setup_studio()
    set_camera((0,-.02,.48),(-2,-3,1.25),1.96)
    for image in bpy.data.images:
        if image.source=='FILE' and image.has_data and not image.packed_file:image.pack()
    scene['asset_origin']='Approved Lux3D task 4054240, locally refined; no subsequent generation'
    scene['design_scale']='1m height normalization; reference dimensions are unknown'
    scene['web_fiber_note']='Export copy uses one in five strands and lower curve tessellation'
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),compress=True)
    report={'executed_at':now(),'blender_version':bpy.app.version_string,'input_blend':str(source),
        'master':str(MASTER),'source_glb_sha256':digest(ROOT/'generated/Lux3D_Lion_Base_glb.glb'),
        'source_triangles_preserved':geometry_triangles,'source_part_meshes':[o.name for o in parts],
        'fiber_stats':fiber_stats,'native_strands':sum(f['actual'] for f in fiber_stats),
        'eye_fit':'Visually estimated from dark eye UV islands; original painted frames remain.',
        'limitations':['Generated 2048px motif atlas retains blurred details and baked lighting.',
            'Part cuts and source overlaps remain; this is not a watertight or skinned production rig.',
            'Fibers are static sampled curves parented to their emitter; regenerate after mesh deformation.',
            'Eye globes are added fitted editable features, not a reconstruction of an actual internal mechanism.']}
    save_json(REPORT,report)
    render_view('draft_hero',(0,-.02,.48),(-2,-3,1.25),1.96,1100,850,24)
    render_view('draft_front',(0,-.28,.5),(0,-1,.05),1.25,1000,1000,24)

def export():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    draco='--draco' in sys.argv
    started=now()
    for decorative in [o for o in bpy.data.objects if o.type=='CURVE' and o.get('decorative_curve_export')]:
        proxy=decorative.copy();proxy.data=decorative.data.copy()
        proxy.name=decorative.name+'_WebMesh'
        bpy.context.scene.collection.objects.link(proxy)
        bpy.ops.object.select_all(action='DESELECT');proxy.select_set(True)
        bpy.context.view_layer.objects.active=proxy
        bpy.ops.object.convert(target='MESH')
        decorative.hide_render=True;decorative.hide_viewport=True
    natives=[o for o in bpy.data.objects if o.type=='CURVE' and 'fiber_emitter' in o]
    proxies=bpy.data.collections.new('Web_Fiber_Proxy');bpy.context.scene.collection.children.link(proxies)
    proxy_records=[]
    for ob in natives:
        data=bpy.data.curves.new(ob.name+'_WebGeometry','CURVE');data.dimensions='3D'
        data.resolution_u=1;data.render_resolution_u=1;data.bevel_depth=ob.data.bevel_depth
        data.bevel_resolution=0;data.use_fill_caps=True
        for mat in ob.data.materials:data.materials.append(mat)
        stride=3 if 'tassel' in ob.name.lower() else 5 if 'white' in ob.name.lower() else 10
        for index in range(0,len(ob.data.splines),stride):
            src=ob.data.splines[index];s=data.splines.new('BEZIER');s.bezier_points.add(len(src.bezier_points)-1)
            for a,b in zip(s.bezier_points,src.bezier_points):
                a.co=b.co;a.radius=b.radius;a.handle_left=b.handle_left;a.handle_right=b.handle_right
                a.handle_left_type='FREE';a.handle_right_type='FREE'
        proxy=bpy.data.objects.new(ob.name+'_WebMesh',data);proxies.objects.link(proxy)
        proxy.matrix_world=ob.matrix_world.copy()
        if ob.parent:parent_keep(proxy,ob.parent)
        bpy.ops.object.select_all(action='DESELECT');proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
        strands=len(data.splines)
        bpy.ops.object.convert(target='MESH')
        proxy=bpy.context.object;proxy['web_proxy_of']=ob.name;proxy['web_strands']=strands
        proxy['export_note']='Sparse native strands with stride '+str(stride)+'; four-sided tubes, one segment per Bezier interval'
        proxy_records.append({'name':proxy.name,'strands':strands,'polygons':len(proxy.data.polygons),'native_stride':stride})
        ob.hide_render=True;ob.hide_viewport=True
    bpy.ops.object.select_all(action='DESELECT')
    export_objects=[]
    for ob in bpy.data.objects:
        if ob.type=='EMPTY' and (ob.name.startswith('Pivot_') or ob.name=='Lion_Root') or ob.type=='MESH' and ob.name.startswith('Lion_'):
            ob.select_set(True);export_objects.append(ob)
    bpy.context.view_layer.objects.active=next(o for o in export_objects if o.type=='MESH')
    output=ROOT/('exports/scene_draco.glb' if draco else 'exports/scene.glb')
    print('EXPORT_START',started,len(export_objects),flush=True)
    compression=dict(export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=7,
        export_draco_position_quantization=20,export_draco_normal_quantization=12,
        export_draco_texcoord_quantization=16) if draco else {}
    bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',use_selection=True,
        export_extras=True,export_animations=False,export_yup=True,export_texcoords=True,
        export_normals=True,export_materials='EXPORT',export_cameras=False,export_lights=False,**compression)
    save_json(ROOT/('docs/final_export_draco.json' if draco else 'docs/final_export.json'),{'export_started_at':started,'export_completed_at':now(),
        'tool':'Blender 5 glTF exporter','path':str(output),'bytes':output.stat().st_size,
        'sha256':digest(output),'source_sha256':digest(ROOT/'generated/Lux3D_Lion_Base_glb.glb'),
        'export_objects':[o.name for o in export_objects],'fiber_proxies':proxy_records,
        'proxy_strands':sum(r['strands'] for r in proxy_records),
        'native_master_unchanged':True,'compression':compression,
        'sources':json.loads((ROOT/'docs/quality_revision_assembly.json').read_text(encoding='utf-8'))['source_assets'],
        'limitations':['Sampled mesh fibers for portable GLB size: red stride10, white stride5, tassel stride3.',
          'Body brocade uses embedded basecolor and a procedural tangent normal texture; other native-only bump nodes are omitted.',
          'Transform hierarchy is exported; no skinned dance animation was created.']})
    # A derived proxy scene is an ignored rebuildable cache, separate from the master.
    CACHE.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(CACHE/('Lion_Draco_Export_Proxy.blend' if draco else 'Lion_Export_Proxy.blend')),compress=True)
    print('EXPORT_DONE',str(output),digest(output),flush=True)

def render():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    views=[
        ('hero',(0,-.02,.48),(-2,-3,1.25),1.96),
        ('front',(0,-.30,.49),(0,-1,.04),1.58),
        ('left',(0,0,.49),(1,0,.08),1.88),
        ('right',(0,0,.49),(-1,0,.08),1.88),
        ('back',(0,.24,.49),(0,1,.04),1.58),
        ('top',(0,0,.5),(0,0,1),1.92),
        ('head',(0,-.52,.72),(-.4,-1,.25),.96),
        ('eye',(-.1415,-.670,.657),(-.10,-1,.03),.20),
        ('mouth',(0,-.70,.42),(0,-1,-.02),.60),
        ('crown',(0,-.45,.945),(-.25,-1,.35),.38),
        ('body_trim',(.25,.12,.49),(1,-.16,.22),.78),
        ('brocade',(.30,.18,.50),(1,-.04,.15),.32),
        ('paw',(.28,-.41,.075),(1,-1,.65),.40),
        ('tail',(0,.75,.52),(1,1,.15),.78),
    ]
    records=[]
    for name,target,direction,scale in views:
        render_view(name,target,direction,scale,1600 if name=='hero' else 1400,1100 if name=='hero' else 1000,64 if name in ('eye','brocade') else 48 if name=='hero' else 32)
        path=ROOT/'renders/final'/(name+'.png')
        records.append({'name':name,'file':str(path),'bytes':path.stat().st_size,'rendered_at':now()})
        save_json(ROOT/'docs/final_render_views.json',records)
    # Geometry-only evidence derived from the finished mesh; hair is hidden.
    native=[o for o in bpy.data.objects if o.type=='CURVE']
    for o in native:o.hide_render=True
    bpy.context.view_layer.material_override=material('QA_Clay',(.46,.46,.46),.75)
    for name,target,direction,scale in views[1:6]:
        render_view('clay_'+name,target,direction,scale,900,700,24)
    bpy.context.view_layer.material_override=None
    print('RENDER_ALL_DONE',now(),flush=True)

if __name__=='__main__':
    if MODE=='build':build()
    elif MODE=='export':export()
    elif MODE=='render':render()
    else:raise ValueError(MODE)
