"""Conservative editable partitions of the actual Lux3D lion, with UV provenance.

Coordinates use a design height of 1 m, front -Y, up +Z, anatomical L=+X.
The source GLB is read-only. Spatial cuts are not rig-ready anatomical topology.
"""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

PROJECT = ROOT
G1_SOURCE_SHA256 = '10868714d52a4a4dbea9511ea4986738fdac4b39ba19ad858393f13b7255c3d4'
PALETTE = {
    'Body':(.18,.47,.83,1), 'Head':(.92,.36,.09,1), 'Jaw':(.70,.10,.13,1),
    'Beard':(.97,.86,.38,1), 'Tail':(.66,.27,.84,1),
    'Ear_L':(.32,.90,.75,1), 'Ear_R':(.09,.60,.50,1), 'Crown':(.87,.52,.82,1),
    'Foreleg_L':(.19,.78,.31,1), 'Foreleg_R':(.08,.44,.15,1),
    'Hindleg_L':(.19,.84,.92,1), 'Hindleg_R':(.08,.45,.62,1),
    'Forepaw_L':(.78,.97,.20,1), 'Forepaw_R':(.45,.63,.06,1),
    'Hindpaw_L':(.88,.92,.97,1), 'Hindpaw_R':(.45,.53,.64,1),
}
PIVOTS = {
    'Body':(0,0,.38), 'Head':(0,-.285,.565), 'Jaw':(0,-.45,.515),
    'Beard':(0,-.685,.435), 'Tail':(0,.565,.610),
    'Ear_L':(.285,-.405,.800), 'Ear_R':(-.285,-.405,.800),
    'Crown':(0,-.445,.895),
    'Foreleg_L':(.270,-.355,.410), 'Foreleg_R':(-.270,-.355,.410),
    'Hindleg_L':(.265,.475,.400), 'Hindleg_R':(-.265,.475,.400),
    'Forepaw_L':(.292,-.420,.075), 'Forepaw_R':(-.292,-.420,.075),
    'Hindpaw_L':(.283,.515,.070), 'Hindpaw_R':(-.283,.515,.070),
}
PARENTS = {'Body':None, 'Head':'Body', 'Jaw':'Head', 'Beard':'Jaw', 'Tail':'Body',
           'Ear_L':'Head', 'Ear_R':'Head', 'Crown':'Head',
           'Foreleg_L':'Body', 'Foreleg_R':'Body', 'Hindleg_L':'Body', 'Hindleg_R':'Body',
           'Forepaw_L':'Foreleg_L', 'Forepaw_R':'Foreleg_R',
           'Hindpaw_L':'Hindleg_L', 'Hindpaw_R':'Hindleg_R'}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def box(points):
    points=np.asarray(points)
    return {'min':points.min(axis=0).tolist(),'max':points.max(axis=0).tolist(),
            'dimensions':np.ptp(points,axis=0).tolist()}

def mesh_stats(mesh):
    import bmesh
    bm=bmesh.new();bm.from_mesh(mesh)
    result={'vertices':len(bm.verts),'edges':len(bm.edges),'triangles':len(bm.faces),
            'boundary_edges':sum(e.is_boundary for e in bm.edges),
            'overconnected_edges':sum(len(e.link_faces)>2 for e in bm.edges),
            'inconsistent_winding_edges':sum(e.is_manifold and not e.is_contiguous for e in bm.edges)}
    bm.free();return result

def canonical_positions(obj):
    points=np.array([obj.matrix_world@v.co for v in obj.data.vertices],dtype=np.float64)
    minimum=points.min(axis=0); maximum=points.max(axis=0)
    scale=1/(maximum[2]-minimum[2]);points[:,2]-=minimum[2];points*=scale
    return points,{'scale':scale,'original_z_min':float(minimum[2]),
                   'original_bbox':{'min':minimum.tolist(),'max':maximum.tolist()},
                   'canonical_bbox':box(points),'design_height_m':1.0,
                   'measurement_status':'Design normalization, not a measurement of the reference object.',
                   'front':'-Y','up':'+Z','anatomical_left':'+X','anatomical_right':'-X'}

def conservative_weld(positions, faces):
    # glTF splits positions at UV/normal seams. The source has *exact* coincident
    # positions: 1e-10 through 1e-6 probes give identical candidate groups.
    # Protect every vertex group around an overconnected candidate edge. This
    # avoids exposing overlapping generated surfaces as new non-manifold joins.
    lookup={};groups=[]
    for p in positions:
        key=tuple(p);groups.append(lookup.setdefault(key,len(lookup)))
    counts=Counter()
    for face in faces:
        g=[groups[i] for i in face]
        for a,b in zip(g,g[1:]+g[:1]):
            if a!=b:counts[tuple(sorted((a,b)))]+=1
    protected=set();degenerate=[]
    for (a,b),n in counts.items():
        if n>2:protected.update((a,b))
    for index,face in enumerate(faces):
        g=[groups[i] for i in face]
        if len(set(g))<3:protected.update(g);degenerate.append(index)
    welded_lookup={};remap=[];newpositions=[]
    for index,g in enumerate(groups):
        key=('protected',index) if g in protected else ('coincident',g)
        if key not in welded_lookup:
            welded_lookup[key]=len(newpositions);newpositions.append(positions[index])
        remap.append(welded_lookup[key])
    newfaces=np.array([[remap[i] for i in f] for f in faces],dtype=np.int32)
    return np.array(newpositions),newfaces,{
        'method':'Exact coincident-position seam welding, with protected vertex groups at candidate edges with >2 incident faces; no remesh.',
        'candidate_tolerance_probe':'Historical G1 probes 1e-10 through 1e-6 had identical point grouping. This execution uses exact coincident positions only; no approximation is inferred for a new source.',
        'actual_position_tolerance':0.0,'source_vertices':len(positions),
        'coincident_position_groups':len(lookup),'protected_position_groups':len(protected),
        'protected_source_vertices':sum(g in protected for g in groups),
        'welded_vertices':len(newpositions),'removed_duplicate_vertices':len(positions)-len(newpositions),
        'candidate_overconnected_edges':sum(n>2 for n in counts.values()),
        'candidate_degenerate_faces':len(degenerate),'faces_removed':0,
        'max_position_displacement_design_units':0.0,
        'source_overlap_note':'Protected seams intentionally remain around ambiguous overlapping generated surfaces. This is not a watertight or print-ready repair.'}

def labels_for(centroids):
    result=[]
    for x,y,z in centroids:
        side='L' if x>=0 else 'R'
        # Priority isolates hanging beard/tail before torso and head classifiers.
        if abs(x)<.195 and y<-.590 and .140<z<.460:
            label='Beard'
        elif abs(x)<.220 and ((y>.575 and z>.265) or (y>.535 and z>.570)):
            label='Tail'
        elif abs(x)<.100 and -.580<y<-.335 and z>.882:
            label='Crown'
        elif -.460<y<-.245 and ((abs(x)-.266)/.106)**2+((z-.854)/.112)**2<1.12:
            label='Ear_'+side
        elif y<-.480 and .425<z<.565:
            label='Jaw'
        elif (y<-.235 and z>.550) or (y<-.400 and z>.405):
            label='Head'
        elif z<.083 and y<-.180:
            label='Forepaw_'+side
        elif z<.083 and y>.245:
            label='Hindpaw_'+side
        elif y<-.200 and z<.420 and abs(x)>.155:
            label='Foreleg_'+side
        elif y>.285 and z<.430 and abs(x)>.145:
            label='Hindleg_'+side
        else:
            label='Body'
        result.append(label)
    return np.array(result)

def texture_probe(source_mesh,centroids,uvs,source_sha256):
    texture=next((n.image for slot in source_mesh.materials if slot and slot.use_nodes
                  for n in slot.node_tree.nodes if n.type=='TEX_IMAGE' and n.image
                  and n.image.colorspace_settings.name=='sRGB'),None)
    if texture is None:return {'status':'albedo_texture_not_found'}
    width,height=texture.size
    pixels=np.empty(width*height*4,dtype=np.float32);texture.pixels.foreach_get(pixels)
    pixels=pixels.reshape(height,width,4)
    miduv=uvs.reshape(-1,3,2).mean(axis=1)%1
    rgb=pixels[np.minimum((miduv[:,1]*height).astype(int),height-1),
               np.minimum((miduv[:,0]*width).astype(int),width-1),:3]
    result={'method':'Actual face-centroid albedo lookup, filtered to the frontal eye neighbourhood. Sphere suggestions remain estimates, not separated source eyeballs.',
            'texture':texture.name,'albedo_size':[width,height],'eyes':{}}
    for side,sgn in [('L',1),('R',-1)]:
        mask=((centroids[:,0]*sgn>.095)&(centroids[:,0]*sgn<.195)&
              (centroids[:,1]<-.585)&(centroids[:,1]>-.655)&
              (centroids[:,2]>.635)&(centroids[:,2]<.720)&
              (rgb.max(axis=1)<.180)&(np.ptp(rgb,axis=1)<.055))
        points=centroids[mask]
        if len(points)<3:
            result['eyes'][side]={'status':'insufficient_dark_samples','sample_count':len(points)};continue
        # Front-facing pigment clusters may include edges around painted rings;
        # publish the measured neighbourhood rather than pretend it is an iris fit.
        surface=np.median(points,axis=0)
        # Review against true eye-white islands identified in the independent
        # full-coincidence topology probe. The R dark pigment samples sit on the
        # inner edge and cannot determine the complete globe's center by themselves.
        calibrated=source_sha256==G1_SOURCE_SHA256
        recommended=(np.array([.137*sgn,-.580 if side=='L' else -.584,.676]) if calibrated
                     else surface+np.array([0,.033,0]))
        white_min=([.0725110471,-.5972769260,.6016610265] if side=='L'
                   else [-.2037143856,-.5961393118,.6019121408])
        white_max=([.2023552805,-.4776398540,.7435881495] if side=='L'
                   else [-.0717842057,-.4782715440,.7437270880])
        result['eyes'][side]={'status':('estimated_from_dark_albedo_faces_and_eye_white_island_bounds' if calibrated
                                      else 'estimated_dark_albedo_surface_only_uncalibrated_for_new_source'),'sample_faces':len(points),
            'dark_surface_median':surface.tolist(),'dark_surface_bbox':box(points),
            'eye_white_island_bbox_probe':({'min':white_min,'max':white_max,
                'evidence':'docs/lion_geometry_probe.json; actual coincident-position component bounds, not an anatomical eyeball guarantee'}
                 if calibrated else None),
            'placement_calibrated_against_g1_source':calibrated,
            'recommended_sphere_center':recommended.tolist(),
            'recommended_sphere_radius':.052,'recommended_pupil_radius':.020,
            'placement_note':('Symmetry-constrained visual estimate for an overlay. Head shell and original painted eye frames are retained. Preview the suggested sphere against the actual eye opening and adjust depth; +Y moves into the face.'
                              if calibrated else 'Uncalibrated new-source pigment sample; inspect actual head orientation, eye neighbourhood and globe radius before using this placement. No G1 white-island coordinates are attributed to this source.')}
    return result

def make_empty(name,collection,parent,local_location):
    obj=bpy.data.objects.new(name,None);collection.objects.link(obj)
    obj.empty_display_type='PLAIN_AXES';obj.empty_display_size=.035
    obj.parent=parent;obj.location=local_location
    return obj

def make_diagnostics(scene,objects,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    collection=bpy.data.collections.new('Part_Diagnostic_Viewpoints');scene.collection.children.link(collection)
    scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=scene.render.resolution_y=512
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT'
    scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
    scene.display.shading.show_shadows=True;scene.display.shading.background_type='WORLD'
    scene.world=bpy.data.worlds.new('Parts_Diagnostic_World');scene.world.color=(.055,.055,.055)
    scene.view_settings.view_transform='Standard'
    target=Vector((0,0,.5));files=[]
    for name,axis in {'front_minus_y':(0,-1,0),'left_minus_x':(-1,0,0),
                      'back_plus_y':(0,1,0),'top_plus_z':(0,0,1)}.items():
        data=bpy.data.cameras.new('Parts_'+name);data.type='ORTHO';data.ortho_scale=1.82
        camera=bpy.data.objects.new(data.name,data);collection.objects.link(camera)
        camera.location=target+Vector(axis)*4
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.camera=camera;path=outdir/(name+'.png');scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True);files.append(str(path))
    collection.hide_viewport=True
    scene.render.engine='BLENDER_EEVEE'
    return files

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=PROJECT)
    parser.add_argument('--revision',default='initial')
    parser.add_argument('--input',type=Path,help='Explicit new source GLB; original sources are never modified.')
    parser.add_argument('--output-blend',type=Path,help='Use a new path when organizing G2 to preserve the G1 working files.')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--diagnostics-dir',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root=args.project.resolve();src=(args.input or root/'generated/Lux3D_Lion_Base_glb.glb').resolve()
    sha=digest(src)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src),import_pack_images=True)
    imported_meshes=[o for o in bpy.data.objects if o.type=='MESH']
    if len(imported_meshes)!=1:
        raise ValueError('Expected one source mesh; a multi-mesh source requires explicit UV/material-preserving consolidation before this partition workflow.')
    source=imported_meshes[0];mesh=source.data
    original_stats=mesh_stats(mesh)
    pos,normalization=canonical_positions(source)
    faces=np.array([p.vertices[:] for p in mesh.polygons],dtype=np.int32)
    if faces.shape[1]!=3:raise ValueError('Source is expected to be a triangulated mesh.')
    centroids=pos[faces].mean(axis=1)
    uv_layers={}
    for layer in mesh.uv_layers:
        arr=np.empty(len(mesh.loops)*2,dtype=np.float32);layer.data.foreach_get('uv',arr)
        uv_layers[layer.name]=arr.reshape(-1,2)
    materials=list(mesh.materials)
    mats=np.array([p.material_index for p in mesh.polygons],dtype=np.int32)
    splitnormals=np.array([n.vector[:] for n in mesh.corner_normals],dtype=np.float32)
    normalmatrix=np.array(source.matrix_world.to_3x3().inverted_safe().transposed(),dtype=np.float64)
    splitnormals=splitnormals@normalmatrix.T
    splitnormals/=np.maximum(np.linalg.norm(splitnormals,axis=1)[:,None],1e-20)
    eye_probe=texture_probe(mesh,centroids,next(iter(uv_layers.values())),sha)
    wpos,wfaces,weld_report=conservative_weld(pos,faces)
    repaired=bpy.data.meshes.new('Lion_SeamRepair_Audit')
    repaired.from_pydata(wpos.tolist(),[],wfaces.tolist());repaired.update()
    weld_report['topology_before']=original_stats;weld_report['topology_after']=mesh_stats(repaired)
    if weld_report['topology_after']['overconnected_edges']>original_stats['overconnected_edges']:
        raise RuntimeError('Conservative weld unexpectedly introduced overconnected edges.')
    bpy.data.meshes.remove(repaired)
    labels=labels_for(centroids)
    source_face_area=np.linalg.norm(np.cross(pos[faces[:,1]]-pos[faces[:,0]],pos[faces[:,2]]-pos[faces[:,0]]),axis=1)*.5
    parts_collection=bpy.data.collections.new('Lion_Editable_Parts');bpy.context.scene.collection.children.link(parts_collection)
    root_obj=make_empty('Lion_Root',parts_collection,None,(0,0,0))
    root_obj['source_sha256']=sha;root_obj['design_height_m']=1.;root_obj['semantic_front']='-Y';root_obj['anatomical_left']='+X'
    pivots={}
    for name,pivot in PIVOTS.items():
        parent_name=PARENTS[name];parent=pivots[parent_name] if parent_name else root_obj
        parent_position=np.array(PIVOTS[parent_name]) if parent_name else np.zeros(3)
        pivots[name]=make_empty('Pivot_'+name,parts_collection,parent,np.array(pivot)-parent_position)
        pivots[name]['pivot_status']='Estimated functional pivot from visual inspection, not an anatomical joint fit.'
    part_report=[];objects=[];uv_preserved=True;normal_preserved=True
    for label in PALETTE:
        selected=np.flatnonzero(labels==label)
        if not len(selected):continue
        chosen_faces=wfaces[selected]
        chosen_vertices=np.unique(chosen_faces)
        vertexmap=np.full(len(wpos),-1,dtype=np.int32);vertexmap[chosen_vertices]=np.arange(len(chosen_vertices))
        localpoints=wpos[chosen_vertices]-np.array(PIVOTS[label])
        sub=bpy.data.meshes.new('Lion_'+label+'_Mesh')
        sub.from_pydata(localpoints.tolist(),[],vertexmap[chosen_faces].tolist());sub.update()
        for material in materials:sub.materials.append(material)
        sub.polygons.foreach_set('material_index',mats[selected]);sub.polygons.foreach_set('use_smooth',np.ones(len(selected),dtype=bool))
        loops=(selected[:,None]*3+np.arange(3)[None,:]).reshape(-1)
        for layer_name,uv in uv_layers.items():
            newlayer=sub.uv_layers.new(name=layer_name);newlayer.data.foreach_set('uv',uv[loops].reshape(-1))
            actual=np.empty(len(loops)*2,dtype=np.float32);newlayer.data.foreach_get('uv',actual)
            uv_preserved=uv_preserved and np.array_equal(actual,uv[loops].reshape(-1))
        if hasattr(sub,'normals_split_custom_set'):
            sub.normals_split_custom_set(splitnormals[loops].tolist())
        else:normal_preserved=False
        attribute=sub.attributes.new(name='source_face_index',type='INT',domain='FACE')
        attribute.data.foreach_set('value',selected)
        obj=bpy.data.objects.new('Lion_'+label,sub);parts_collection.objects.link(obj)
        obj.parent=pivots[label];obj.color=PALETTE[label];obj['source_sha256']=sha
        obj['part_selection_method']='Source-triangle centroid spatial partition; UV, surface positions and source-face IDs preserved.'
        obj['rigging_status']='Uncapped cuts; source intersections and remaining seams need retopology for deformation.'
        stats=mesh_stats(sub)
        stats.update({'name':obj.name,'class':label,'canonical_bbox':box(wpos[chosen_vertices]),'pivot_canonical':list(PIVOTS[label]),
                     'parent_pivot':obj.parent.name,'parent_group':PARENTS[label] or 'Lion_Root',
                     'source_face_count':len(selected),'source_surface_area_design_units2':float(source_face_area[selected].sum()),
                     'palette_rgba':list(PALETTE[label]),'uv_layers':list(uv_layers),
                     'source_face_min':int(selected.min()),'source_face_max':int(selected.max())})
        part_report.append(stats);objects.append(obj)
    # Each source face appears once; no surface is recreated, omitted, or duplicated.
    if sum(p['triangles'] for p in part_report)!=len(faces):raise RuntimeError('Source face conservation failed.')
    if not uv_preserved:raise RuntimeError('Partition UV loop values changed.')
    bpy.data.objects.remove(source,do_unlink=True)
    if mesh.users==0:bpy.data.meshes.remove(mesh)
    cuts=defaultdict(lambda:{'edges':0,'length_design_units':0.})
    edge_labels=defaultdict(set)
    for face, label in zip(wfaces,labels):
        for a,b in zip(face,np.roll(face,-1)):edge_labels[tuple(sorted((int(a),int(b))))].add(label)
    for (a,b),names in edge_labels.items():
        if len(names)>1:
            key=' | '.join(sorted(names));cuts[key]['edges']+=1
            cuts[key]['length_design_units']+=float(np.linalg.norm(wpos[a]-wpos[b]))
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    bpy.context.view_layer.update()
    diagnostic_dir=(args.diagnostics_dir or root/'docs/lion_parts_diagnostics').resolve()
    paths=make_diagnostics(scene,objects,diagnostic_dir)
    blend=(args.output_blend or blend_path('Lion_Parts_Working.blend', root=root)).resolve();blend.parent.mkdir(parents=True,exist_ok=True)
    scene.camera=bpy.data.objects.get('Parts_front_minus_y')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active=objects[0];objects[0].select_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend),check_existing=False)
    report={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'revision':args.revision,
            'blender_version':bpy.app.version_string,'source':{'path':str(src),'sha256_before':sha,'sha256_after':digest(src),'preserved':sha==digest(src)},
            'working_blend':str(blend),'normalization':normalization,'seam_repair':weld_report,
            'part_count':len(objects),'parts':part_report,'split_cut_edges_by_part_pair':dict(cuts),
            'face_conservation':{'source_triangles':len(faces),'partitioned_triangles':sum(p['triangles'] for p in part_report),'all_source_faces_present_exactly_once':True},
            'uv_loop_values_exactly_preserved':bool(uv_preserved),'source_corner_normals_applied':bool(normal_preserved),
            'eye_estimates':eye_probe,'diagnostic_render_files':paths,'diagnostics_review_status':'pending_actual_visual_inspection',
            'spatial_classifier_calibration':{'source_sha256':G1_SOURCE_SHA256,'matches_current_source':sha==G1_SOURCE_SHA256,
                'new_source_requirement':'Reinspect actual front, body proportions and new diagnostics before accepting or reusing G1 spatial thresholds.'},
            'limitations':['Spatial region boundaries create open cuts and are not a complete deformation topology.',
                           'Source mesh intersections, duplicated surfaces, one original overconnected edge, and protected UV seams remain.',
                           'Main eye shell and painted frames remain in Head; no eye-frame holes were cut.',
                           'All pivots are visual estimates for editing; no completed rig, deformation test, or animation claim.',
                           'Crown, ears and jaw are conservative spatial regions and retain their UV textures; they are not asserted to have watertight attachment loops.',
                           'No synthetic primitive lion replacement, cloud submission, paid API call, source edit, remesh, or UV unwrap occurred.']}
    report_path=(args.report or root/'docs/lion_parts_report.json').resolve();report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'blend':str(blend),'report':str(report_path),'parts':len(objects),'source_triangles':len(faces),'uv_preserved':bool(uv_preserved),'weld':weld_report},ensure_ascii=False))

if __name__=='__main__':main()
