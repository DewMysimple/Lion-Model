"""Read-only mesh probes for the real Lux3D lion. No source modification."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import bpy, bmesh, json
from pathlib import Path
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'generated/Lux3D_Lion_Base_glb.glb'), import_pack_images=True)
obj = next(o for o in bpy.data.objects if o.type == 'MESH')
for v in obj.data.vertices:
    v.co = obj.matrix_world @ v.co
low = min(v.co.z for v in obj.data.vertices)
scale = 1/(max(v.co.z for v in obj.data.vertices)-low)
for v in obj.data.vertices:
    v.co = Vector((v.co.x*scale, v.co.y*scale, (v.co.z-low)*scale))
obj.matrix_world.identity()
bm=bmesh.new(); bm.from_mesh(obj.data)
before=len(bm.verts)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
components=[]; unseen=set(bm.verts)
while unseen:
    seed=unseen.pop(); stack=[seed]; vs=[seed]
    while stack:
        cur=stack.pop()
        for e in cur.link_edges:
            v=e.other_vert(cur)
            if v in unseen:
                unseen.remove(v); stack.append(v); vs.append(v)
    fs=set(f for v in vs for f in v.link_faces)
    lo=[min(v.co[i] for v in vs) for i in range(3)]
    hi=[max(v.co[i] for v in vs) for i in range(3)]
    components.append({'verts':len(vs),'faces':len(fs),'min':lo,'max':hi})
components.sort(key=lambda x:x['faces'],reverse=True)
out={'before_vertices':before,'after_vertices':len(bm.verts),'faces':len(bm.faces),
     'boundary':sum(e.is_boundary for e in bm.edges),'nonmanifold':sum(not e.is_manifold for e in bm.edges),
     'components':components}
(ROOT/'docs/lion_geometry_probe.json').write_text(json.dumps(out,indent=2),encoding='utf8')
bm.to_mesh(obj.data); bm.free()
obj.data.update()
for p in obj.data.polygons:p.use_smooth=True
mat=bpy.data.materials.new('ProbeCoord');mat.use_nodes=True
nt=mat.node_tree;nt.nodes.clear()
outnode=nt.nodes.new('ShaderNodeOutputMaterial');em=nt.nodes.new('ShaderNodeEmission')
geo=nt.nodes.new('ShaderNodeNewGeometry');sep=nt.nodes.new('ShaderNodeSeparateXYZ')
nt.links.new(geo.outputs['Position'],sep.inputs[0])
math=nt.nodes.new('ShaderNodeMath'); math.operation='MULTIPLY'; math.inputs[1].default_value=10
nt.links.new(sep.outputs['Z'],math.inputs[0])
frac=nt.nodes.new('ShaderNodeMath');frac.operation='PINGPONG';frac.inputs[1].default_value=1
nt.links.new(math.outputs[0],frac.inputs[0])
ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(0.05,.1,.7,1);ramp.color_ramp.elements[1].color=(1,.25,.05,1)
nt.links.new(frac.outputs[0],ramp.inputs[0]);nt.links.new(ramp.outputs[0],em.inputs['Color']);nt.links.new(em.outputs[0],outnode.inputs['Surface'])
original=obj.data.materials[0]
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=scene.render.resolution_y=768
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard';scene.world=bpy.data.worlds.new('ProbeWorld');scene.world.color=(.02,.02,.02)
target=Vector((0,0,.5))
for n, axis in {'front':(0,-1,0),'left':(-1,0,0),'back':(0,1,0),'top':(0,0,1)}.items():
    cd=bpy.data.cameras.new(n);cd.type='ORTHO';cd.ortho_scale=1.9
    cam=bpy.data.objects.new(n,cd);scene.collection.objects.link(cam);cam.location=target+Vector(axis)*5;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.camera=cam
    scene.render.filepath=str(ROOT/f'docs/generated_base_inspection/probe_{n}.png')
    obj.data.materials[0]=mat;bpy.ops.render.render(write_still=True)
obj.data.materials[0]=original
print(json.dumps({k:v for k,v in out.items() if k!='components'}));print('components',len(components),components[:8])
