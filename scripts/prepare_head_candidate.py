"""Fit and conservatively partition the real, inspected head-only Lux3D source.

This creates a separate candidate; it never writes the whole-lion master.
"""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from organize_lion_parts import conservative_weld, mesh_stats, box

ORIGIN = 'head_highdetail_4055287'
HEAD_CLASSES = ['Head', 'Jaw', 'Beard', 'Ear_L', 'Ear_R', 'Brow_L', 'Brow_R', 'Nose', 'Crown']
OLD_HEAD_NAMES = ['Lion_' + n for n in HEAD_CLASSES]
COLORS = {'Head':(.25,.40,.66,1),'Jaw':(.80,.12,.12,1),'Beard':(.98,.91,.45,1),
          'Ear_L':(.14,.76,.52,1),'Ear_R':(.12,.45,.36,1),
          'Brow_L':(.9,.27,.65,1),'Brow_R':(.62,.12,.47,1),
          'Nose':(.12,.82,.86,1),'Crown':(.8,.48,.12,1)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_glb_json(path):
    raw=path.read_bytes();magic,version,total=struct.unpack_from('<4sII',raw)
    if magic!=b'glTF' or version!=2 or total!=len(raw):
        raise ValueError('Source is not a complete GLB v2')
    length,kind=struct.unpack_from('<II',raw,12)
    if kind!=0x4e4f534a:raise ValueError('GLB has no leading JSON chunk')
    return json.loads(raw[20:20+length])


def read_target_bounds(path):
    # Only the source-part objects are loaded, measured, then removed. No save.
    with bpy.data.libraries.load(str(path),link=False) as (available,requested):
        requested.objects=[n for n in OLD_HEAD_NAMES if n in available.objects]
    objects=[o for o in requested.objects if o and o.type=='MESH']
    if not objects:raise ValueError('Target has no expected real head parts')
    points=np.concatenate([np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices]) for o in objects])
    # Matrices from unlinked library objects do not include newly linked parents:
    # measure after linking the actual pivot hierarchy in a temporary scene.
    names={o.name for o in objects}
    with bpy.data.libraries.load(str(path),link=False) as (available,requested):
        requested.objects=[n for n in available.objects if n.startswith('Pivot_') or n=='Lion_Root']
    controls=[o for o in requested.objects if o]
    temporary=bpy.data.collections.new('Temporary_G1_Bounds_Read');bpy.context.scene.collection.children.link(temporary)
    for o in objects+controls:
        if o.name not in temporary.objects:temporary.objects.link(o)
    bpy.context.view_layer.update()
    points=np.concatenate([np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices]) for o in objects])
    result={'path':str(path),'parts':{},'assembly_bbox':box(points)}
    for o in objects:
        v=np.array([tuple(o.matrix_world@p.co) for p in o.data.vertices])
        result['parts'][o.name]={'bbox':box(v),'triangles':len(o.data.polygons)}
    for o in objects+controls:bpy.data.objects.remove(o,do_unlink=True)
    # Loading a mesh also loads unlinked parent dependencies. Clear those IDs
    # before creating the new, contractually named pivots, avoiding .001 names.
    for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
    bpy.data.collections.remove(temporary)
    # Purge orphan imported target meshes/materials/images only after source import
    # would risk removing source data; here no head source has been loaded yet.
    for mesh in list(bpy.data.meshes):
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    return result


def albedo_faces(mesh,uvs):
    image=next((n.image for m in mesh.materials if m and m.use_nodes
                for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image
                and n.image.colorspace_settings.name=='sRGB'),None)
    if image is None:raise ValueError('Head source has no usable base-color image')
    w,h=image.size;arr=np.empty(w*h*4,dtype=np.float32);image.pixels.foreach_get(arr)
    arr=arr.reshape(h,w,4);mid=uvs.reshape(-1,3,2).mean(1)%1
    rgb=arr[np.minimum((mid[:,1]*h).astype(int),h-1),np.minimum((mid[:,0]*w).astype(int),w-1),:3]
    return rgb,{'name':image.name,'size':[w,h]}


def classify(h,rgb):
    x,y,z=h.T;a=np.abs(x)
    labels=np.full(len(h),'Head',dtype='<U12')
    white=(rgb.min(1)>.18)&(np.ptp(rgb,axis=1)<.22)
    red=(rgb[:,0]>.18)&(rgb[:,1]<rgb[:,0]*.82)&(rgb[:,2]<rgb[:,0]*.85)
    labels[(y<-.14)&(z<.315)&(z>.17)&(a<.34)]='Jaw'
    labels[(y<-.13)&(z<.195)&(a<.30)]='Beard'
    labels[(y<-.18)&(z>.37)&(z<.495)&(a<.065)]='Nose'
    crown=(a<.12)&(y<.10)&(y>-.34)&(z>.87)
    labels[crown]='Crown'
    ear=((((a-.355)/.125)**2+((z-.825)/.155)**2)<1.10)&(y>-.125)&(z>.67)
    labels[ear & (x>=0)]='Ear_L';labels[ear & (x<0)]='Ear_R'
    along=(a-.19)*.63+(z-.70)*.78
    across=-(a-.19)*.78+(z-.70)*.63
    brow=((along/.195)**2+(across/.071)**2<1.12)&(a>.046)&(a<.34)&(y<-.135)&(z>.535)&red
    brow &= ~ear & ~crown
    labels[brow&(x>=0)]='Brow_L';labels[brow&(x<0)]='Brow_R'
    return labels,{'white_samples':int(white.sum()),'red_samples':int(red.sum()),
                   'classifier':'New-source geometry + source base-color sampling, reviewed via ID views; anatomical boundaries remain estimates.'}


def sampled_region(mask,c,n,areas,origin,pivot_offset=None):
    ids=np.flatnonzero(mask)
    if len(ids)<3:return {'status':'insufficient_actual_samples','sample_faces':len(ids)}
    weight=areas[ids];weight=weight/max(weight.sum(),1e-20)
    center=np.sum(c[ids]*weight[:,None],axis=0)
    normal=np.sum(n[ids]*weight[:,None],axis=0);normal/=max(np.linalg.norm(normal),1e-20)
    result={'status':'measured_surface_region_plus_visual_estimate','source_asset':origin,
            'sample_faces':len(ids),'surface_bbox':box(c[ids]),
            'surface_center_area_weighted':center.tolist(),'mean_face_normal':normal.tolist(),
            'confidence':'medium; source pixels and geometric region, not an exact anatomical fit'}
    if pivot_offset is not None:result['recommended_overlay_center_estimate']=(center+np.array(pivot_offset)).tolist()
    return result


def landmarks(h,c,n,rgb,areas,labels,fit_scale):
    x,y,z=h.T;a=np.abs(x);out={'eyes':{},'side_medallions':{},'cheek_bells':{},'tassels':{}}
    for side,sgn in [('L',1),('R',-1)]:
        dark=(rgb.max(1)<.24)&(np.ptp(rgb,axis=1)<.13)
        eye=(x*sgn>.105)&(x*sgn<.245)&(y<-.18)&(z>.505)&(z<.615)&dark
        # Keep the central dark eye region instead of outer black decorative rings.
        eye &= ((x*sgn-.174)/.071)**2+((z-.554)/.058)**2<1
        result=sampled_region(eye,c,n,areas,ORIGIN)
        if result['sample_faces']>=3:
            center=np.array(result['surface_center_area_weighted']);norm=np.array(result['mean_face_normal'])
            center-=norm*.026
            result.update({'recommended_overlay_center_estimate':center.tolist(),
                           'recommended_globe_radius_estimate':.043,
                           'recommended_iris_radius_estimate':.024,
                           'placement_note':'Overlay center is moved inward from measured dark surface by .026 design units; preview depth/occlusion. Existing eye-frame geometry is retained.'})
        out['eyes'][side]=result
        gold=(rgb[:,0]>.28)&(rgb[:,1]>.17)&(rgb[:,2]<rgb[:,1]*.80)
        med=(x*sgn>.315)&(x*sgn<.455)&(y>-.21)&(y<.045)&(z>.47)&(z<.645)&gold
        out['side_medallions'][side]=sampled_region(med,c,n,areas,ORIGIN)
        bell=(x*sgn>.29)&(x*sgn<.45)&(y<-.10)&(y>-.28)&(z>.36)&(z<.49)&gold
        out['cheek_bells'][side]=sampled_region(bell,c,n,areas,ORIGIN)
        tassel=(x*sgn>.32)&(x*sgn<.48)&(y>-.22)&(y<.09)&(z>.28)&(z<.46)&(rgb[:,0]>rgb[:,1]*1.4)
        out['tassels'][side]=sampled_region(tassel,c,n,areas,ORIGIN)
    cap=(a<.054)&(y<-.19)&(z>.63)&(z<.72)
    out['forehead_medallion']=sampled_region(cap,c,n,areas,ORIGIN)
    tooth=(a<.30)&(y<-.16)&(z>.19)&(z<.31)&(rgb.min(1)>.36)&(np.ptp(rgb,axis=1)<.21)
    out['mouth_lower_teeth_band']=sampled_region(tooth,c,n,areas,ORIGIN)
    out['mouth_lower_teeth_band']['note']='Actual light tooth-band surface region; repeated visible rectangles are not yet separate native tooth objects.'
    out['mouth_jaw_bbox']=box(c[labels=='Jaw']) if np.any(labels=='Jaw') else None
    return out


def controls(collection,pivot_points):
    root=bpy.data.objects.new('Head_Candidate_Root',None);collection.objects.link(root)
    root['source_asset']=ORIGIN;root['semantic_front']='-Y';root['anatomical_left']='+X'
    pivots={}
    for part in HEAD_CLASSES:
        parent=pivots.get('Jaw') if part=='Beard' else (pivots.get('Head') if part!='Head' else root)
        p=bpy.data.objects.new('Pivot_'+part,None);collection.objects.link(p)
        p.parent=parent;p.empty_display_type='PLAIN_AXES';p.empty_display_size=.025
        p['source_asset']=ORIGIN
        base=pivot_points.get('Jaw') if part=='Beard' else (pivot_points.get('Head') if part!='Head' else np.zeros(3))
        p.location=np.array(pivot_points[part])-np.array(base)
        p['pivot_status']='Visual editing estimate; open source-face region cuts, no skin/deformation guarantee.'
        pivots[part]=p
    return root,pivots


def id_views(scene,collection,outdir,bb):
    outdir.mkdir(parents=True,exist_ok=True)
    views=bpy.data.collections.new('Candidate_ID_Diagnostic_Viewpoints');scene.collection.children.link(views)
    scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=scene.render.resolution_y=768
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT'
    scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
    scene.display.shading.background_type='WORLD';scene.world=bpy.data.worlds.new('Head_Candidate_Diagnostic_World')
    scene.world.color=(.045,.045,.045);scene.view_settings.view_transform='Standard'
    target=Vector((np.array(bb['min'])+np.array(bb['max']))*.5)
    extent=max(bb['dimensions']);files=[]
    for name,axis in [('front_minus_y',(0,-1,0)),('right_plus_x',(1,0,0)),('back_plus_y',(0,1,0)),('top_plus_z',(0,0,1))]:
        data=bpy.data.cameras.new('HeadCandidate_'+name);data.type='ORTHO';data.ortho_scale=extent*1.20
        camera=bpy.data.objects.new(data.name,data);views.objects.link(camera)
        camera.location=target+Vector(axis)*3;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.camera=camera;path=outdir/(name+'.png');scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True);files.append(str(path))
    views.hide_viewport=True;scene.render.engine='BLENDER_EEVEE'
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--target',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--report',type=Path)
    parser.add_argument('--diagnostics',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    root=args.root.resolve();src=(args.input or root/'generated/candidates/head_highdetail/Lion_head_highdetail_glb.glb').resolve()
    target=(args.target or blend_path('Lion_Detailed_Parts.blend', root=root)).resolve()
    output=(args.output or blend_path('Lion_Head_Candidate_Parts.blend', root=root)).resolve()
    report_path=(args.report or root/'docs/head_candidate_parts_report.json').resolve()
    diagnostics=(args.diagnostics or root/'docs/head_candidate_parts_diagnostics').resolve()
    if output.exists() or report_path.exists() or diagnostics.exists():
        raise FileExistsError('Candidate outputs already exist; use fresh explicit paths')
    before=sha(src);target_sha=sha(target);container=read_glb_json(src)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    target_report=read_target_bounds(target)
    # Source fit uses measured old head+beard+ears+crown+brow/nose union.
    old=target_report['assembly_bbox'];oldmin=np.array(old['min']);oldmax=np.array(old['max'])
    bpy.ops.import_scene.gltf(filepath=str(src),import_pack_images=True)
    source_objects=[o for o in bpy.data.objects if o.type=='MESH']
    if len(source_objects)!=1:raise ValueError('Expected one real head mesh; multi-mesh source needs explicit material-preserving handling')
    source=source_objects[0];mesh=source.data
    mesh.calc_loop_triangles()
    if any(len(p.vertices)!=3 for p in mesh.polygons):raise ValueError('Expected triangulated source')
    raw=np.array([tuple(source.matrix_world@v.co) for v in mesh.vertices],dtype=np.float64)
    rawmin=raw.min(0);rawmax=raw.max(0);dim=rawmax-rawmin
    scale=(oldmax[0]-oldmin[0])/dim[0]
    translate=np.array([(oldmin[0]+oldmax[0])*.5-(rawmin[0]+rawmax[0])*.5*scale,
                        oldmin[1]-rawmin[1]*scale,oldmax[2]-rawmax[2]*scale])
    pos=raw*scale+translate
    head_unit=raw/dim[2];head_unit[:,2]-=rawmin[2]/dim[2]
    faces=np.array([p.vertices[:] for p in mesh.polygons],dtype=np.int32)
    centroids=pos[faces].mean(1);hc=head_unit[faces].mean(1)
    cross=np.cross(pos[faces[:,1]]-pos[faces[:,0]],pos[faces[:,2]]-pos[faces[:,0]])
    areas=np.linalg.norm(cross,axis=1)*.5;normals=cross/np.maximum(np.linalg.norm(cross,axis=1)[:,None],1e-20)
    uv_layers={}
    for layer in mesh.uv_layers:
        a=np.empty(len(mesh.loops)*2,dtype=np.float32);layer.data.foreach_get('uv',a);uv_layers[layer.name]=a.reshape(-1,2)
    if not uv_layers:raise ValueError('Real source head has no UV map')
    rgb,albedo=albedo_faces(mesh,next(iter(uv_layers.values())))
    labels,classification=classify(hc,rgb)
    features=landmarks(hc,centroids,normals,rgb,areas,labels,scale)
    wpos,wfaces,weld_report=conservative_weld(pos,faces)
    before_stats=mesh_stats(mesh)
    temp=bpy.data.meshes.new('Head_SeamRepair_Audit');temp.from_pydata(wpos.tolist(),[],wfaces.tolist());temp.update()
    after_stats=mesh_stats(temp);bpy.data.meshes.remove(temp)
    if after_stats['overconnected_edges']>before_stats['overconnected_edges']:raise RuntimeError('Weld introduced overconnected edges')
    weld_report.update({'topology_before':before_stats,'topology_after':after_stats})
    # Pivots are fitted from source geometry regions rather than old-head positions.
    pivot_unit={'Head':(0,.25,.50),'Jaw':(0,-.09,.27),'Beard':(0,-.25,.18),
                'Ear_L':(.35,.01,.82),'Ear_R':(-.35,.01,.82),
                'Brow_L':(.18,-.19,.71),'Brow_R':(-.18,-.19,.71),
                'Nose':(0,-.30,.45),'Crown':(0,-.16,.88)}
    pivots_world={n:np.array([p[0]*dim[2],p[1]*dim[2],p[2]*dim[2]+rawmin[2]])*scale+translate for n,p in pivot_unit.items()}
    collection=bpy.data.collections.new('Lion_Head_Candidate_Parts');bpy.context.scene.collection.children.link(collection)
    root_obj,pivots=controls(collection,pivots_world);root_obj['source_sha256']=before
    materials=list(mesh.materials);mat_indices=np.array([p.material_index for p in mesh.polygons],dtype=np.int32)
    corner_normals=np.array([n.vector[:] for n in mesh.corner_normals],dtype=np.float32)
    normal_matrix=np.array(source.matrix_world.to_3x3().inverted_safe().transposed())
    corner_normals=corner_normals@normal_matrix.T;corner_normals/=np.maximum(np.linalg.norm(corner_normals,axis=1)[:,None],1e-20)
    parts=[];preserved_uv=True
    for label in HEAD_CLASSES:
        selected=np.flatnonzero(labels==label)
        if not len(selected):continue
        used=np.unique(wfaces[selected]);mapping=np.full(len(wpos),-1,dtype=np.int32);mapping[used]=np.arange(len(used))
        sub=bpy.data.meshes.new('Lion_'+label+'_HeadSourceMesh')
        sub.from_pydata((wpos[used]-pivots_world[label]).tolist(),[],mapping[wfaces[selected]].tolist());sub.update()
        for material in materials:sub.materials.append(material)
        sub.polygons.foreach_set('material_index',mat_indices[selected]);sub.polygons.foreach_set('use_smooth',np.ones(len(selected),dtype=bool))
        loopids=(selected[:,None]*3+np.arange(3)[None,:]).reshape(-1)
        for name,uv in uv_layers.items():
            layer=sub.uv_layers.new(name=name);layer.data.foreach_set('uv',uv[loopids].reshape(-1))
            actual=np.empty(len(loopids)*2,dtype=np.float32);layer.data.foreach_get('uv',actual)
            preserved_uv &= np.array_equal(actual,uv[loopids].reshape(-1))
        sub.normals_split_custom_set(corner_normals[loopids].tolist())
        sub.attributes.new(name='source_face_index',type='INT',domain='FACE').data.foreach_set('value',selected)
        sub.attributes.new(name='source_asset_id',type='INT',domain='FACE').data.foreach_set('value',np.ones(len(selected),dtype=np.int32))
        ob=bpy.data.objects.new('Lion_'+label,sub);collection.objects.link(ob);ob.parent=pivots[label];ob.color=COLORS[label]
        ob['source_asset']=ORIGIN;ob['source_sha256']=before
        ob['partition_note']='New head actual source triangle region; uncapped cuts. Source face index is local to head_highdetail_4055287, not original full-lion source.'
        parts.append({'name':ob.name,'class':label,'source_asset':ORIGIN,'source_triangles':len(selected),
                      'bbox_world':box(wpos[used]),'pivot_world':pivots_world[label].tolist(),
                      'parent':ob.parent.name,'stats':mesh_stats(sub)})
    if sum(p['source_triangles'] for p in parts)!=len(faces):raise RuntimeError('Source face conservation failed')
    if not preserved_uv:raise RuntimeError('Source UV changed during partition')
    bpy.data.objects.remove(source,do_unlink=True)
    if mesh.users==0:bpy.data.meshes.remove(mesh)
    bpy.context.view_layer.update()
    # Real post-parent world-position check prevents accidental double transforms.
    max_delta=0.;allids=[]
    for ob in collection.objects:
        if ob.type!='MESH':continue
        ids=np.empty(len(ob.data.polygons),dtype=np.int32);ob.data.attributes['source_face_index'].data.foreach_get('value',ids)
        allids.extend(ids.tolist())
        for p,i in zip(ob.data.polygons,ids):
            actual=np.array([tuple(ob.matrix_world@ob.data.vertices[j].co) for j in p.vertices])
            max_delta=max(max_delta,float(np.max(np.abs(actual-pos[faces[i]]))))
    if sorted(allids)!=list(range(len(faces))) or max_delta>3e-7:raise RuntimeError('Post-parent face/position verification failed')
    cut_map=defaultdict(lambda:{'edge_count':0,'length':0.})
    edge_labels=defaultdict(set)
    for f,label in zip(wfaces,labels):
        for a,b in zip(f,np.roll(f,-1)):edge_labels[tuple(sorted((int(a),int(b))))].add(label)
    for (a,b),names in edge_labels.items():
        if len(names)>1:
            key=' | '.join(sorted(names));cut_map[key]['edge_count']+=1;cut_map[key]['length']+=float(np.linalg.norm(wpos[a]-wpos[b]))
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    paths=id_views(scene,collection,diagnostics,box(pos))
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True,check_existing=False)
    report={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'source':{'path':str(src),'sha256':before,'sha256_after':sha(src),'source_asset':ORIGIN},
            'target_reference':target_report,'target_sha256_before':target_sha,'target_sha256_after':sha(target),
            'fit':{'method':'Uniform scale to original head assembly width; X center matched, frontmost Y matched, crown top Z matched. No anisotropic flattening.',
                   'uniform_scale':float(scale),'translation':translate.tolist(),'source_bbox':box(raw),'fitted_bbox':box(pos),
                   'orientation':{'front':'-Y','up':'+Z','anatomical_L':'+X'},
                   'rear_shell_overlap_delta_y':float(pos[:,1].max()-oldmax[1]),
                   'beard_bottom_delta_z':float(pos[:,2].min()-oldmin[2]),
                   'interpretation':'Closed generated rear shell extends farther into torso; beard is shorter under width-based fit. Verify fusion silhouette; no seamless attachment or physical dimensions asserted.'},
            'source_glb_materials':container.get('materials',[]),'normalTexture_declared':any('normalTexture' in m for m in container.get('materials',[])),
            'albedo':albedo,'classifier':classification,'seam_weld':weld_report,
            'parts':parts,'source_face_conservation':{'source_faces':len(faces),'assigned_faces':len(allids),'all_present_once':True,'max_post_parent_coordinate_delta':max_delta},
            'source_uv_loop_values_preserved_exactly':bool(preserved_uv),'feature_estimates_fitted_world':features,
            'part_cut_edges':dict(cut_map),'candidate_blend':str(output),'diagnostic_views':paths,'diagnostic_review_status':'pending actual visual review',
            'adoption_visual_assessment':'New head front is preferable to original full-lion G1: clearer multi-ring eye frames, forehead/cheek pattern and lower white rectangular tooth band. Rear shell contains extrapolated circular pattern/side pieces; fiber plates and washed baked color still need refinement.',
            'limits':['Candidate contains only new head source, not retained old head faces. Fusion must document removal/replacement of old head source regions.',
                      'No completed rig, watertight retopology, uncapped attachment repair, hair strands or independent teeth were created by this partition step.',
                      'Feature centers, radii and pivots are estimates from actual surface/color regions; verify overlay depth in fusion renders.',
                      'Raw source images remain packed and source GLB and target part file are preserved.']}
    if report['source']['sha256_after']!=before or report['target_sha256_after']!=target_sha:raise RuntimeError('Read-only input changed')
    report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'blend':str(output),'report':str(report_path),'parts':len(parts),'triangles':len(faces),'scale':float(scale),'fit':report['fit'],'features':features},ensure_ascii=False))


if __name__=='__main__':main()
