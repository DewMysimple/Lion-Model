"""Independent, read-only Blender reopen QA of the actual final lion artifacts.

Run separate fresh Blender processes for the two modes:
  blender --background --factory-startup --python-exit-code 1 --python verify_final_lion.py -- --master
  blender --background --factory-startup --python-exit-code 1 --python verify_final_lion.py -- --glb

Only JSON QA reports are written. A mechanical pass does not certify reference
fidelity, artistic quality, deformation topology, collision-free motion or renders.
"""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path, resolve_recorded_path

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

import bpy
import numpy as np

DEFAULT_ROOT = ROOT
PARTS=('Body','Head','Jaw','Beard','Tail','Ear_L','Ear_R','Crown',
       'Foreleg_L','Foreleg_R','Hindleg_L','Hindleg_R',
       'Forepaw_L','Forepaw_R','Hindpaw_L','Hindpaw_R')
EXPECTED_PARENT_GROUPS={'Body':None,'Head':'Body','Jaw':'Head','Beard':'Jaw','Tail':'Body',
    'Ear_L':'Head','Ear_R':'Head','Crown':'Head','Foreleg_L':'Body','Foreleg_R':'Body',
    'Hindleg_L':'Body','Hindleg_R':'Body','Forepaw_L':'Foreleg_L','Forepaw_R':'Foreleg_R',
    'Hindpaw_L':'Hindleg_L','Hindpaw_R':'Hindleg_R'}
HEAD_KEYS=('Head','Jaw','Beard','Ear_L','Ear_R','Brow_L','Brow_R','Nose','Crown')
HEAD_NAMES={'Lion_'+name for name in HEAD_KEYS}
G1_ORIGIN='g1_full_lion_4054240'
HEAD_ORIGIN='head_highdetail_4055287'

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def matrix_values(obj):return np.asarray(obj.matrix_world,dtype=float)

def mesh_world_points(obj):
    points=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',points);points=points.reshape(-1,3)
    matrix=matrix_values(obj)
    return points@matrix[:3,:3].T+matrix[:3,3]

def bbox(points):
    points=np.asarray(points)
    if not points.size:return None
    lo=points.min(axis=0);hi=points.max(axis=0)
    return {'min':lo.tolist(),'max':hi.tolist(),'dimensions':(hi-lo).tolist(),'center':((hi+lo)/2).tolist()}

def combined_bbox(objects):
    boxes=[]
    for obj in objects:
        if obj.type=='MESH' and obj.data.vertices:
            points=mesh_world_points(obj)
            boxes.extend((points.min(axis=0),points.max(axis=0)))
    return bbox(boxes)

def descendants(root):
    return list(root.children_recursive) if root else []

def under(obj,root):
    p=obj
    while p:
        if p==root:return True
        p=p.parent
    return False

def node_images(tree,seen=None):
    seen=seen or set()
    if not tree or tree.as_pointer() in seen:return set()
    seen.add(tree.as_pointer());images=set()
    for node in tree.nodes:
        if node.type in {'TEX_IMAGE','TEX_ENVIRONMENT'} and node.image:images.add(node.image)
        if node.type=='GROUP':images.update(node_images(node.node_tree,seen))
    return images

def inspect_images(objects,scene,errors):
    used=set()
    for obj in objects:
        if obj.type in {'MESH','CURVE','CURVES'}:
            for slot in obj.material_slots:
                if slot.material:used.update(node_images(slot.material.node_tree))
    if scene.world:used.update(node_images(scene.world.node_tree))
    result=[]
    for im in sorted(used,key=lambda i:i.name):
        raw=im.filepath
        resolved=bpy.path.abspath(raw) if raw else None
        packed=bool(im.packed_file or getattr(im,'packed_files',None))
        available=(packed or im.source=='GENERATED' or (resolved and Path(resolved).is_file()))
        item={'name':im.name,'size':list(im.size),'source':im.source,'packed':packed,
              'filepath':raw,'resolved_file':resolved,'dependency_available':bool(available),
              'color_space':im.colorspace_settings.name}
        result.append(item)
        if not available:errors.append('Referenced image dependency missing: '+im.name)
        if min(im.size)<1:errors.append('Referenced image has empty dimensions: '+im.name)
    libraries=[]
    for lib in bpy.data.libraries:
        path=bpy.path.abspath(lib.filepath);exists=Path(path).is_file()
        libraries.append({'name':lib.name,'filepath':path,'exists':exists})
        if not exists:errors.append('Linked Blender library missing: '+path)
    return {'referenced_images':result,'referenced_image_count':len(result),
            'all_referenced_images_packed':bool(result) and all(i['packed'] for i in result),
            'linked_libraries':libraries,
            'unused_image_count':len(set(bpy.data.images)-used)}

def mesh_record(obj,errors,core=False):
    mesh=obj.data
    points=mesh_world_points(obj)
    finite=bool(np.isfinite(points).all())
    if not finite:errors.append('Non-finite mesh coordinates: '+obj.name)
    mesh.calc_loop_triangles()
    uvs=[]
    for uv in mesh.uv_layers:
        data=np.empty(len(uv.data)*2,np.float32);uv.data.foreach_get('uv',data)
        isfinite=bool(np.isfinite(data).all())
        uvs.append({'name':uv.name,'loops':len(uv.data),'finite':isfinite})
        if not isfinite:errors.append('Non-finite UV: '+obj.name+'/'+uv.name)
    if core and (not uvs or len(mesh.loops)!=uvs[0]['loops']):errors.append('Missing or incomplete source UV: '+obj.name)
    material_names=[s.material.name if s.material else None for s in obj.material_slots]
    if not material_names or any(m is None for m in material_names):
        errors.append('Missing material reference: '+obj.name)
    for mod in obj.modifiers:
        if mod.type=='NODES' and mod.show_render and mod.node_group is None:
            errors.append('Enabled geometry node modifier has no node group: '+obj.name+'/'+mod.name)
    record={'name':obj.name,'parent':obj.parent.name if obj.parent else None,
            'vertices':len(mesh.vertices),'polygons':len(mesh.polygons),'triangles':len(mesh.loop_triangles),
            'world_bbox':bbox(points),'finite_world_coordinates':finite,'uv_layers':uvs,
            'materials':material_names,'modifiers':[{'name':m.name,'type':m.type,'viewport':m.show_viewport,'render':m.show_render} for m in obj.modifiers]}
    if core:
        import bmesh
        bm=bmesh.new();bm.from_mesh(mesh)
        record['topology']={'boundary_edges':sum(e.is_boundary for e in bm.edges),
            'overconnected_edges':sum(len(e.link_faces)>2 for e in bm.edges),
            'inconsistent_winding_edges':sum(e.is_manifold and not e.is_contiguous for e in bm.edges),
            'isolated_vertices':sum(not v.link_edges for v in bm.verts)}
        bm.free()
        if not mesh.vertices or not mesh.polygons:errors.append('Empty required source part: '+obj.name)
    return record

def curve_record(obj,errors):
    data=obj.data;strands=0;points=0;finite=True;radii=[];spline_types=Counter();counts=[]
    if obj.type=='CURVE':
        for sp in data.splines:
            strands+=1;spline_types[sp.type]+=1
            seq=sp.bezier_points if sp.type=='BEZIER' else sp.points
            counts.append(len(seq));points+=len(seq)
            for point in seq:
                values=list(point.co)+[point.radius]
                if sp.type=='BEZIER':values+=list(point.handle_left)+list(point.handle_right)
                finite=finite and all(math.isfinite(v) for v in values)
                radii.append(point.radius)
    else:
        strands=len(data.curves);points=len(data.points)
        position=data.attributes.get('position')
        if position:
            values=np.empty(points*3,np.float32);position.data.foreach_get('vector',values)
            finite=bool(np.isfinite(values).all())
        else:finite=False
    stored=obj.get('fiber_strand_count')
    native_fiber=bool(obj.get('fiber_generator') or obj.get('fiber_emitter') or stored is not None)
    if not finite:errors.append('Non-finite curve coordinates/handles: '+obj.name)
    if native_fiber and not strands:errors.append('Empty native fiber object: '+obj.name)
    if stored is not None and int(stored)!=strands:errors.append('Stored native strand count differs from splines: '+obj.name)
    if native_fiber and obj.type=='CURVE' and data.bevel_depth<=0:errors.append('Fiber curve has no visible thickness: '+obj.name)
    if native_fiber and radii and (max(radii)<=0 or min(radii)<0):
        errors.append('Native fiber radius factors have no visible extent or include negative values: '+obj.name)
    material_names=[slot.material.name if slot.material else None for slot in obj.material_slots]
    if native_fiber and (not material_names or any(name is None for name in material_names)):
        errors.append('Native fiber material reference missing: '+obj.name)
    return {'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,
        'native_fiber':native_fiber,'emitter':obj.get('fiber_emitter'),'strands':strands,'control_points':points,
        'stored_strand_count':stored,'finite_coordinates_handles_radii':finite,'spline_types':dict(spline_types),'materials':material_names,
        'bevel_depth_local':float(data.bevel_depth) if obj.type=='CURVE' else None,
        'radius_factor_min':float(min(radii)) if radii else None,'radius_factor_max':float(max(radii)) if radii else None,
        'points_per_spline_min':min(counts) if counts else None,'points_per_spline_max':max(counts) if counts else None}

def eye_controls(objects,errors):
    result={}
    for side in ('L','R'):
        exact_names=('EyeBall_Rotation_'+side,'Pivot_Eye_'+side,'Pivot_Eyeball_'+side,'Eye_Control_'+side)
        candidates=[bpy.data.objects.get(n) for n in exact_names]
        candidates=[o for o in candidates if o and o in objects and o.type=='EMPTY']
        if not candidates:
            candidates=[o for o in objects if o.type=='EMPTY' and re.search(r'eye.*(rotation|pivot|control).*_'+side+r'$',o.name,re.I)]
        if not candidates:
            errors.append('Independent eyeball pivot missing: '+side);result[side]={'status':'missing'};continue
        control=candidates[0]
        children=descendants(control);globes=[o for o in children if o.type=='MESH' and re.search(r'eyeball|eye_globe|globe',o.name,re.I)]
        if not globes:errors.append('Eye control has no named eyeball mesh descendant: '+control.name)
        result[side]={'status':'found','name':control.name,'parent':control.parent.name if control.parent else None,
                      'world_position':list(control.matrix_world.translation),
                      'globe_meshes':[o.name for o in globes],'descendants':[o.name for o in children]}
    if all(result.get(s,{}).get('status')=='found' for s in ('L','R')):
        if result['L']['name']==result['R']['name']:errors.append('Both eyes share a single rotation control')
        for side,other in [('L','R'),('R','L')]:
            control=bpy.data.objects[result[side]['name']]
            protected=[bpy.data.objects.get('Lion_Head'),bpy.data.objects[result[other]['name']]]
            before={o.name:matrix_values(o).copy() for o in protected if o}
            original=control.matrix_basis.copy()
            own_globes=[bpy.data.objects[n] for n in result[side]['globe_meshes']]
            own_before={o.name:matrix_values(o).copy() for o in own_globes}
            from mathutils import Matrix
            control.matrix_basis=original@Matrix.Rotation(.15,4,'X');bpy.context.view_layer.update()
            isolated=all(np.allclose(matrix_values(bpy.data.objects[n]),m,rtol=0,atol=1e-8) for n,m in before.items())
            own_moved=bool(own_globes) and all(not np.allclose(matrix_values(bpy.data.objects[n]),m,rtol=0,atol=1e-8)
                                             for n,m in own_before.items())
            control.matrix_basis=original;bpy.context.view_layer.update()
            result[side]['rotation_does_not_move_head_or_other_eye']=bool(isolated)
            result[side]['rotation_changes_own_globe_world_matrix']=bool(own_moved)
            if not isolated:errors.append('Eye rotation changes Head or opposite eye: '+side)
            if not own_moved:errors.append('Eye rotation does not change its own globe: '+side)
    return result

def rigid_motion_controls(objects,errors,warnings):
    """Temporary in-memory poses; restore every basis and never save the artifact.

    These checks demonstrate actual rigid hierarchy motion and isolation. They
    deliberately do not certify collision-free motion or smooth skin deformation.
    """
    from mathutils import Matrix
    specifications=(('Head','Z',(-.12,.12),('Lion_Body','Pivot_Tail')),
                    ('Jaw','X',(.15,),('Lion_Head','Lion_Body','Pivot_Tail','Pivot_Eye_L','Pivot_Eye_R')),
                    ('Tail','X',(-.12,.12),('Lion_Head','Lion_Body','Pivot_Jaw','Pivot_Eye_L','Pivot_Eye_R')))
    result=[]
    for part,axis,angles,protected_names in specifications:
        control=bpy.data.objects.get('Pivot_'+part);own=bpy.data.objects.get('Lion_'+part)
        if not control or control not in objects or not own:
            errors.append('Rigid motion test control/mesh missing: '+part);continue
        protected=[bpy.data.objects[n] for n in protected_names if bpy.data.objects.get(n)]
        before={o.name:matrix_values(o).copy() for o in protected}
        own_before=matrix_values(own).copy();basis=control.matrix_basis.copy()
        limits=[]
        for constraint in control.constraints:
            record={'name':constraint.name,'type':constraint.type,'mute':constraint.mute,
                    'influence':constraint.influence,'owner_space':constraint.owner_space}
            if constraint.type=='LIMIT_ROTATION':
                record['axes']={name:{'enabled':getattr(constraint,'use_limit_'+name),
                    'minimum_radians':getattr(constraint,'min_'+name),'maximum_radians':getattr(constraint,'max_'+name)}
                    for name in ('x','y','z')}
            limits.append(record)
        poses=[]
        try:
            for angle in angles:
                control.matrix_basis=basis@Matrix.Rotation(angle,4,axis)
                bpy.context.view_layer.update()
                isolated=all(np.allclose(matrix_values(bpy.data.objects[n]),m,rtol=0,atol=1e-8) for n,m in before.items())
                moved=not np.allclose(matrix_values(own),own_before,rtol=0,atol=1e-8)
                children=[o for o in descendants(control) if o in objects]
                finite=all(np.isfinite(matrix_values(o)).all() for o in children+[control])
                poses.append({'requested_delta_radians':angle,'requested_delta_degrees':math.degrees(angle),
                    'own_mesh_matrix_changed':bool(moved),'protected_objects_unchanged':bool(isolated),
                    'all_descendant_transforms_finite':bool(finite),
                    'moved_source_mesh_bbox':combined_bbox([o for o in children if o.type=='MESH' and o.data.attributes.get('source_face_index')])})
                if not isolated:errors.append('Rigid '+part+' pose changes protected unrelated object')
                if not moved:errors.append('Rigid '+part+' requested pose does not move its own mesh')
                if not finite:errors.append('Rigid '+part+' pose generates non-finite transforms')
        finally:
            control.matrix_basis=basis;bpy.context.view_layer.update()
        restored=np.allclose(matrix_values(own),own_before,rtol=0,atol=1e-8)
        if not restored:errors.append('Rigid motion check did not restore '+part)
        active_limits=[c for c in limits if c['type']=='LIMIT_ROTATION' and not c['mute'] and c['influence']>0]
        if not active_limits:warnings.append(part+' rigid control has no active rotation-limit constraint; only the sampled pose range is verified.')
        result.append({'control':control.name,'axis':axis,'parent':control.parent.name if control.parent else None,
            'protected_objects':[o.name for o in protected],'constraint_records':limits,'active_rotation_limit_count':len(active_limits),
            'sampled_poses':poses,'neutral_pose_restored':bool(restored),
            'scope':'Actual sampled rigid editing poses and transform isolation. Constraint metadata is recorded; hard-stop enforcement, collision-free travel and deformation are not inferred.'})
    return result

def local_rotation_limit_checks(objects,errors,mode,required):
    """Verify actual native local hard stops; standard glTF receives metadata."""
    from mathutils import Matrix
    names=('Pivot_Head','Pivot_Jaw','Pivot_Tail','Pivot_Eye_L','Pivot_Eye_R','Pivot_Ear_L','Pivot_Ear_R')
    results=[]
    for name in names:
        control=bpy.data.objects.get(name)
        if not control or control not in objects:
            if required:errors.append('Required rotation-limit control missing: '+name)
            continue
        metadata=control.get('rotation_limits_degrees')
        try:declared=json.loads(metadata) if isinstance(metadata,str) else list(metadata) if metadata is not None else None
        except (ValueError,TypeError):declared=None
        constraints=[c for c in control.constraints if c.type=='LIMIT_ROTATION' and not c.mute and c.influence>.999]
        if mode=='glb':
            if required and (not declared or len(declared)!=3):errors.append('Exported rotation-limit metadata missing/invalid: '+name)
            results.append({'control':name,'mode':'metadata_only_standard_glTF','declared_limits_degrees':declared,
                'native_constraint_count_after_import':len(constraints),
                'scope':'Blender rotation constraints are not executable in standard glTF; limits are retained only as custom metadata.'})
            continue
        if not constraints:
            if required:errors.append('Native active rotation-limit constraint missing: '+name)
            continue
        local=[c for c in constraints if c.owner_space=='LOCAL']
        if len(local)!=1:
            if required:errors.append('Native control must have one full-influence LOCAL rotation-limit constraint: '+name)
            continue
        constraint=local[0]
        basis=control.matrix_basis.copy();before=matrix_values(control).copy()
        location,rotation,scale=basis.decompose();base_euler=rotation.to_euler('XYZ')
        tests=[]
        try:
            for axis,index in zip('xyz',range(3)):
                enabled=getattr(constraint,'use_limit_'+axis)
                lo=getattr(constraint,'min_'+axis);hi=getattr(constraint,'max_'+axis)
                if not enabled or hi<lo:
                    if required:errors.append('Invalid/disabled native rotation-limit axis: '+name+'/'+axis)
                    continue
                if declared:
                    try:match=np.allclose(np.deg2rad(declared[index]),[lo,hi],rtol=0,atol=1e-6)
                    except (ValueError,TypeError,IndexError):match=False
                    if not match:errors.append('Stored limit metadata differs from actual native constraint: '+name+'/'+axis)
                for stop,requested in [('minimum',max(-math.pi+.01,lo-.20)),('maximum',min(math.pi-.01,hi+.20))]:
                    euler=base_euler.copy();euler[index]=requested
                    control.matrix_basis=Matrix.LocRotScale(location,euler.to_quaternion(),scale)
                    bpy.context.view_layer.update()
                    effective=control.matrix_world.copy()
                    if control.parent:
                        effective=control.matrix_parent_inverse.inverted_safe()@control.parent.matrix_world.inverted_safe()@effective
                    observed=float(effective.to_euler('XYZ')[index])
                    finite=math.isfinite(observed) and np.isfinite(matrix_values(control)).all()
                    expected=lo if stop=='minimum' else hi
                    within=bool(finite and lo-2e-5<=observed<=hi+2e-5)
                    reaches=bool(finite and abs(observed-expected)<=2e-5)
                    tests.append({'axis':axis,'stop':stop,'requested_degrees':math.degrees(requested),
                        'observed_effective_local_degrees':math.degrees(observed),
                        'expected_stop_degrees':math.degrees(expected),'within_declared_range':within,'reaches_hard_stop':reaches})
                    if not within or not reaches:errors.append('Actual local hard-stop clamp failed: '+name+'/'+axis+'/'+stop)
        finally:
            control.matrix_basis=basis;bpy.context.view_layer.update()
        restored=bool(np.allclose(matrix_values(control),before,rtol=0,atol=2e-7))
        if not restored:errors.append('Hard-stop QA did not restore neutral control: '+name)
        results.append({'control':name,'constraint':constraint.name,'owner_space':constraint.owner_space,
            'declared_limits_degrees':declared,'actual_out_of_range_clamp_tests':tests,'neutral_restored':restored,
            'all_six_local_stops_verified':len(tests)==6 and all(t['within_declared_range'] and t['reaches_hard_stop'] for t in tests),
            'scope':'Actual native Blender LOCAL rigid-control constraint enforcement. Collision-free attachment travel and skin deformation remain unverified.'})
    return results

def read_retained_g1_ids(path,total,errors):
    """Read actual detailed G1 face IDs without linking target objects to scene."""
    if not path.is_file():
        errors.append('Detailed original part reference missing: '+str(path));return None
    digest_before=sha256(path);before=set(bpy.data.objects)
    with bpy.data.libraries.load(str(path),link=False) as (available,requested):
        requested.objects=[n for n in available.objects if n.startswith('Lion_')]
    all_ids=[];retained=[];removed=[];retained_names=[];removed_names=[];face_counts={}
    try:
        for obj in requested.objects:
            if not obj or obj.type!='MESH':continue
            attr=obj.data.attributes.get('source_face_index')
            if attr is None:continue
            if attr.domain!='FACE' or attr.data_type!='INT' or len(attr.data)!=len(obj.data.polygons):
                errors.append('Invalid detailed-reference face attribute: '+obj.name);continue
            ids=np.empty(len(attr.data),np.int32);attr.data.foreach_get('value',ids)
            # Appended IDs may acquire .001 suffixes; use stable original basename.
            name=obj.name.split('.')[0];face_counts[name]=len(ids);all_ids.extend(ids.tolist())
            if name in HEAD_NAMES:removed.extend(ids.tolist());removed_names.append(name)
            else:retained.extend(ids.tolist());retained_names.append(name)
    finally:
        for obj in list(bpy.data.objects):
            if obj not in before:bpy.data.objects.remove(obj,do_unlink=True)
        for mesh in list(bpy.data.meshes):
            if mesh.users==0:bpy.data.meshes.remove(mesh)
    if sorted(all_ids)!=list(range(total)):errors.append('Detailed original reference does not cover G1 source faces exactly once')
    if set(removed_names)!=HEAD_NAMES:errors.append('Detailed original reference lacks one of the 9 replaced head regions')
    if sha256(path)!=digest_before:errors.append('Detailed original reference changed during read-only QA')
    return {'path':str(path),'sha256':digest_before,'retained_ids':np.array(sorted(retained),np.int32),
        'removed_ids':np.array(sorted(removed),np.int32),'retained_mesh_names':sorted(retained_names),
        'removed_mesh_names':sorted(removed_names),'per_part_face_counts':face_counts}

def source_duplicates(obj):
    """Native duplicate vertex-index triangles, retaining distinct source IDs."""
    if any(len(p.vertices)!=3 for p in obj.data.polygons):return []
    faces=np.array([p.vertices[:] for p in obj.data.polygons],np.int32)
    keys=np.sort(faces,axis=1);_,inverse,counts=np.unique(keys,axis=0,return_inverse=True,return_counts=True)
    ids=np.empty(len(faces),np.int32);obj.data.attributes['source_face_index'].data.foreach_get('value',ids)
    groups=[]
    for group in np.flatnonzero(counts>1):
        rows=np.flatnonzero(inverse==group)
        groups.append({'source_face_ids':sorted(ids[rows].tolist()),
                       'native_vertex_set':keys[rows[0]].tolist(),'extra_native_faces':len(rows)-1})
    return groups

def master_provenance(source_parts,root,source_records,errors,dual):
    if not source_parts:
        errors.append('Master has no source_face_index provenance; source conservation is unproven')
        return {'attribute_present':False},[]
    records={r['source_asset']:r for r in source_records}
    expected_reference=None
    if dual:expected_reference=read_retained_g1_ids(blend_path('Lion_Detailed_Parts.blend', root=root),records[G1_ORIGIN]['triangle_mesh_definition_count'],errors)
    totals={origin:r['triangle_mesh_definition_count'] for origin,r in records.items()}
    coverage={origin:np.zeros(count,np.int32) for origin,count in totals.items()}
    names={origin:[] for origin in records};native_counts={};export_expectations=[]
    known_dup_path=root/'docs/brocade_uv_study_clear_v2_reimport.json'
    known_body_groups=set()
    if dual and known_dup_path.is_file():
        known=read_json(known_dup_path)
        known_body_groups={tuple(sorted(g['sourceFaceIds'])) for g in known.get('sourceDuplicateGroups',[])}
    for obj in source_parts:
        origin=obj.get('source_asset')
        if not dual:origin=G1_ORIGIN
        if origin not in coverage:
            errors.append('Missing/unrecognized source_asset on provenance mesh: '+obj.name);continue
        names[origin].append(obj.name)
        attribute=obj.data.attributes['source_face_index']
        if attribute.domain!='FACE' or attribute.data_type!='INT' or len(attribute.data)!=len(obj.data.polygons):
            errors.append('Invalid source face attribute domain/type/length: '+obj.name);continue
        ids=np.empty(len(attribute.data),np.int32);attribute.data.foreach_get('value',ids)
        if len(ids) and (ids.min()<0 or ids.max()>=len(coverage[origin])):
            errors.append('Out-of-range source face provenance: '+obj.name);continue
        if obj.get('source_sha256') and obj['source_sha256']!=records[origin]['sha256']:
            errors.append('Source hash property differs from actual source GLB: '+obj.name)
        if dual:
            asset_id=obj.data.attributes.get('source_asset_id')
            if not asset_id or asset_id.domain!='FACE' or asset_id.data_type!='INT' or len(asset_id.data)!=len(ids):
                errors.append('Invalid/missing source_asset_id on dual-source part: '+obj.name)
            else:
                values=np.empty(len(ids),np.int32);asset_id.data.foreach_get('value',values)
                if not np.all(values==(1 if origin==HEAD_ORIGIN else 0)):
                    errors.append('Numeric origin attribute disagrees with named origin: '+obj.name)
        np.add.at(coverage[origin],ids,1);native_counts[obj.name]=len(ids)
        duplicate_groups=source_duplicates(obj) if dual else []
        approved=0
        if obj.name=='Lion_Body' and duplicate_groups:
            actual_groups={tuple(g['source_face_ids']) for g in duplicate_groups}
            if actual_groups==known_body_groups and len(actual_groups)==13:
                approved=sum(g['extra_native_faces'] for g in duplicate_groups)
            else:errors.append('Body native duplicate groups differ from specifically inspected 13-group GLB export allowance')
        validation=None
        if duplicate_groups:
            # Validate only a temporary mesh copy, never the native master.
            # This establishes the particular export reduction for every actual
            # part rather than allowing an arbitrary count tolerance.
            temporary=obj.data.copy()
            try:
                changed=temporary.validate(clean_customdata=False)
                validated_attr=temporary.attributes.get('source_face_index')
                if not validated_attr or validated_attr.domain!='FACE' or len(validated_attr.data)!=len(temporary.polygons):
                    errors.append('Temporary validated copy lost face provenance: '+obj.name)
                    kept_ids=np.array([],np.int32)
                else:
                    kept_ids=np.empty(len(validated_attr.data),np.int32);validated_attr.data.foreach_get('value',kept_ids)
                removed_ids=set(ids.tolist())-set(kept_ids.tolist())
                duplicate_ids=set(i for group in duplicate_groups for i in group['source_face_ids'])
                expected_removed=sum(g['extra_native_faces'] for g in duplicate_groups)
                exact=(len(removed_ids)==expected_removed and removed_ids<=duplicate_ids and
                    all(sum(i in removed_ids for i in group['source_face_ids'])==group['extra_native_faces'] for group in duplicate_groups)
                    and len(temporary.polygons)==len(ids)-expected_removed)
                validation={'actual_temporary_copy_validate_changed':bool(changed),
                    'native_faces':len(ids),'validated_copy_faces':len(temporary.polygons),
                    'removed_source_face_ids':sorted(removed_ids),'removed_ids_exactly_one_extra_per_recorded_duplicate_group':bool(exact),
                    'native_original_mesh_not_validated_or_modified':True}
                if not exact:errors.append('Temporary export-validation reduction differs from specifically recorded duplicate groups: '+obj.name)
                elif obj.name!='Lion_Body' or approved==expected_removed:approved=expected_removed
            finally:bpy.data.meshes.remove(temporary)
        export_expectations.append({'name':obj.name,'source_asset':origin,'native_source_faces':len(ids),
            'native_duplicate_vertex_triangle_groups':duplicate_groups,
            'approved_glb_duplicate_face_reduction':approved,
            'expected_glb_triangles_after_known_export_validation':len(ids)-approved,
            'actual_temporary_copy_validation':validation,
            'allowance_evidence':str(known_dup_path) if obj.name=='Lion_Body' and approved else
                'Actual source IDs, same native vertex triangles and transient native-copy validation in this report' if approved else None})
    origin_results={}
    for origin,counts in coverage.items():
        expected=np.ones(len(counts),np.int32)
        if origin==G1_ORIGIN and dual:
            expected[:]=0
            if expected_reference is not None:expected[expected_reference['retained_ids']]=1
        match=bool(np.array_equal(counts,expected))
        origin_results[origin]={'original_source_triangles':len(counts),'expected_retained_face_count':int(expected.sum()),
            'actual_native_source_references':int(counts.sum()),'expected_retained_faces_all_once':match,
            'missing_expected_faces':int(np.count_nonzero((expected==1)&(counts==0))),
            'repeated_face_id_count':int(np.count_nonzero(counts>1)),
            'unexpected_removed_face_id_count':int(np.count_nonzero((expected==0)&(counts>0))),
            'source_mesh_names':sorted(names[origin]),
            'expected_face_id_set_sha256':hashlib.sha256(np.flatnonzero(expected).astype('<i4').tobytes()).hexdigest()}
        if not match:errors.append('Actual native face coverage differs from approved retained set: '+origin)
    if dual and expected_reference:
        if set(names[G1_ORIGIN])!=set(expected_reference['retained_mesh_names']):errors.append('Retained G1 mesh set differs from actual original non-head partitions')
        if set(names[HEAD_ORIGIN])!=HEAD_NAMES:errors.append('New-head source mesh set is not the approved 9-part head')
        if len(source_parts)!=20:errors.append('Dual-source native scene must contain the actual 20 source-part meshes')
    expectation_summary=None
    if expected_reference:
        expectation_summary={k:v for k,v in expected_reference.items() if k not in {'retained_ids','removed_ids'}}
        expectation_summary['retained_source_face_count']=len(expected_reference['retained_ids'])
        expectation_summary['removed_original_head_face_count']=len(expected_reference['removed_ids'])
        expectation_summary['removed_original_head_faces_absent_from_final_native']=origin_results[G1_ORIGIN]['unexpected_removed_face_id_count']==0
    return {'attribute_present':True,'dual_source':dual,'source_mesh_names':[o.name for o in source_parts],
        'origins':origin_results,'approved_retained_g1_reference':expectation_summary,
        'actual_source_triangle_references':sum(int(c.sum()) for c in coverage.values()),
        'all_expected_origin_face_sets_exactly_once':all(v['expected_retained_faces_all_once'] for v in origin_results.values()),
        'per_part_native_face_counts':native_counts,
        'scope':'Face-index coverage is proved separately for each source origin. Replaced G1 head faces are intentionally absent, rather than falsely retained.'},export_expectations

def glb_container(path,errors):
    with path.open('rb') as f:
        magic,version,total=struct.unpack('<4sII',f.read(12))
        if magic!=b'glTF' or version!=2 or total!=path.stat().st_size:
            errors.append('Invalid GLB v2 header/declared length')
        length,kind=struct.unpack('<II',f.read(8));payload=f.read(length)
        if kind!=0x4E4F534A:raise ValueError('First GLB chunk is not JSON')
        doc=json.loads(payload.decode('utf8').rstrip('\x00 '))
    external=[]
    for im in doc.get('images',[]):
        uri=im.get('uri')
        if uri and not uri.startswith('data:'):external.append(uri)
    for buf in doc.get('buffers',[]):
        uri=buf.get('uri')
        if uri and not uri.startswith('data:'):external.append(uri)
    if external:errors.append('GLB has external image/buffer dependencies: '+', '.join(external))
    primitive_triangle_counts=[];mesh_counts=[]
    accessors=doc.get('accessors',[])
    for mesh in doc.get('meshes',[]):
        current_count=0;unsupported=[]
        for primitive in mesh.get('primitives',[]):
            mode=primitive.get('mode',4)
            accessor_index=primitive.get('indices',primitive.get('attributes',{}).get('POSITION'))
            count=accessors[accessor_index].get('count',0) if accessor_index is not None else 0
            if mode==4 and count%3==0:
                primitive_triangle_counts.append(count//3);current_count+=count//3
            else:unsupported.append({'mode':mode,'accessor_count':count})
        mesh_counts.append({'triangles':current_count,'unsupported_primitives':unsupported})
    node_counts=[]
    for index,node in enumerate(doc.get('nodes',[])):
        if 'mesh' not in node:continue
        count=mesh_counts[node['mesh']]
        node_counts.append({'node_index':index,'name':node.get('name'),'mesh_definition_index':node['mesh'],
            'triangle_accessor_count':count['triangles'],'unsupported_primitives':count['unsupported_primitives']})
    return {'gltf_version':doc.get('asset',{}).get('version'),'nodes':len(doc.get('nodes',[])),
            'meshes':len(doc.get('meshes',[])),'materials':len(doc.get('materials',[])),
            'images':len(doc.get('images',[])),'external_resource_uris':external,
            'extensions_used':doc.get('extensionsUsed',[]),
            'triangle_mesh_definition_count':sum(primitive_triangle_counts),
            'triangle_primitive_count':len(primitive_triangle_counts),
            'mesh_node_triangle_accessor_counts':node_counts,
            'embedded_resource_scope':'Core glTF image and buffer URIs are checked. Extension-specific non-core resources require separate inspection.',
            'node_names':[n.get('name') for n in doc.get('nodes',[])]}

def structural_review(objects):
    # These queries identify obvious named controls/geometry; absence is reported,
    # never turned into a claim that reference-required detail does not matter.
    categories={'brows':r'brow','nose_and_muzzle':r'nose|muzzle','side_ornaments':r'cheek|side.*ornament|side.*gold',
                'wave_trims':r'wave.*trim|trim.*wave|body_red_trim','tassels':r'tassel','bells':r'bell',
                'eyelids_or_blink_control':r'eyelid|blink'}
    return {name:{'named_candidates':[o.name for o in objects if re.search(pattern,o.name,re.I)],
                  'scope':'Name presence is indirect evidence. Independently editable structure and visual fidelity require inspection.'}
            for name,pattern in categories.items()}

def gold_controls(objects,errors):
    names=('Pivot_Forehead_Metal','Pivot_SideMedallion_L','Pivot_SideMedallion_R',
           'Pivot_CheekBell_L','Pivot_CheekBell_R','Pivot_TailBell_L','Pivot_TailBell_R')
    records=[]
    for name in names:
        pivot=bpy.data.objects.get(name)
        if not pivot or pivot.type!='EMPTY' or pivot not in objects:
            errors.append('Required added metal-feature control missing: '+name)
            records.append({'name':name,'status':'missing'});continue
        meshes=[o for o in descendants(pivot) if o.type=='MESH']
        if not meshes:errors.append('Metal-feature control has no mesh descendants: '+name)
        records.append({'name':name,'status':'present','parent':pivot.parent.name if pivot.parent else None,
            'world_position':list(pivot.matrix_world.translation),'mesh_descendants':[o.name for o in meshes],
            'mesh_world_bbox':combined_bbox(meshes),
            'scope':'Added metal feature and editable transform control verified. This does not prove an internal mechanism, seam-free attachment or absence of overlap with the preserved source.'})
    return records

def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--master',action='store_true');m.add_argument('--glb',action='store_true')
    p.add_argument('--root',type=Path,default=DEFAULT_ROOT);p.add_argument('--input',type=Path)
    p.add_argument('--source',type=Path,help='Original G1 whole-lion source GLB.')
    p.add_argument('--head-source',type=Path,help='Actual separately generated head source GLB for dual-source QA.')
    p.add_argument('--dual-source',action='store_true',help='Require the retained G1 body plus new isolated-head origin sets.')
    p.add_argument('--master-report',type=Path,help='Verified native-master report used by independent GLB QA.')
    p.add_argument('--report',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root=a.root.resolve();mode='master' if a.master else 'glb'
    path=resolve_project_path(a.input,root) if a.input else (blend_path('Lion_Final_Master.blend',root=root) if a.master else root/'exports/scene.glb')
    report=(a.report or root/('docs/final_master_verification.json' if a.master else 'docs/final_glb_verification.json')).resolve()
    if not path.is_file():raise FileNotFoundError('Final artifact not yet available: '+str(path))
    initial_sha=sha256(path);errors=[];warnings=[]
    source_glb=(a.source or root/'generated/Lux3D_Lion_Base_glb.glb').resolve()
    source_record=None;expected_source_triangles=None;source_records=[]
    if source_glb.is_file():
        source_container=glb_container(source_glb,errors)
        expected_source_triangles=source_container['triangle_mesh_definition_count']
        source_record={'source_asset':G1_ORIGIN,'path':str(source_glb),'sha256':sha256(source_glb),
                       'triangle_mesh_definition_count':expected_source_triangles,
                       'mesh_definitions':source_container['meshes']}
        if expected_source_triangles<=0:errors.append('Original source GLB has no verifiable triangle primitive count')
        source_records.append(source_record)
    else:errors.append('Original approved source GLB missing: '+str(source_glb))
    container=None
    if a.master:bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        container=glb_container(path,errors);bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path),import_pack_images=True)
    scene=bpy.context.scene;bpy.context.view_layer.update()
    lionroot=bpy.data.objects.get('Lion_Root')
    if lionroot is None:errors.append('Lion_Root hierarchy node missing')
    objects=descendants(lionroot)
    if lionroot:objects=[lionroot]+objects
    master_report=(a.master_report or root/'docs/final_master_verification.json').resolve()
    previous_master=read_json(master_report) if a.glb and master_report.is_file() else None
    assembly_path=root/'docs/quality_revision_assembly.json'
    assembly=read_json(assembly_path) if assembly_path.is_file() else None
    dual=bool(a.dual_source or any(o.get('source_asset')==HEAD_ORIGIN for o in objects)
        or (a.glb and previous_master and previous_master.get('source_face_provenance',{}).get('dual_source')))
    if dual:
        head_source=(a.head_source or root/'generated/candidates/head_highdetail/Lion_head_highdetail_glb.glb').resolve()
        if not head_source.is_file():errors.append('Approved new-head source GLB missing: '+str(head_source))
        else:
            head_container=glb_container(head_source,errors)
            source_records.append({'source_asset':HEAD_ORIGIN,'path':str(head_source),'sha256':sha256(head_source),
                'triangle_mesh_definition_count':head_container['triangle_mesh_definition_count'],
                'mesh_definitions':head_container['meshes']})
        if assembly:
            claimed={record['source_asset']:record for record in assembly.get('source_assets',[])}
            for record in source_records:
                if record['source_asset'] not in claimed:errors.append('Executed assembly has no origin record: '+record['source_asset'])
                elif claimed[record['source_asset']].get('sha256')!=record['sha256']:
                    errors.append('Executed assembly origin hash differs from actual GLB: '+record['source_asset'])
    for obj in objects:
        if not np.isfinite(matrix_values(obj)).all():errors.append('Non-finite object transform: '+obj.name)
    required=[];hierarchy=[]
    for part in PARTS:
        mesh=bpy.data.objects.get('Lion_'+part);pivot=bpy.data.objects.get('Pivot_'+part)
        if not mesh or mesh.type!='MESH':errors.append('Required mesh missing: Lion_'+part)
        if not pivot or pivot.type!='EMPTY':errors.append('Required pivot missing: Pivot_'+part)
        if mesh:
            required.append(mesh)
            if lionroot and not under(mesh,lionroot):errors.append('Source part outside Lion_Root: '+mesh.name)
            if pivot and mesh.parent!=pivot:errors.append('Unexpected direct mesh parent: '+mesh.name)
        expected_parent='Pivot_'+EXPECTED_PARENT_GROUPS[part] if EXPECTED_PARENT_GROUPS[part] else 'Lion_Root'
        if pivot:
            hierarchy.append({'name':pivot.name,'parent':pivot.parent.name if pivot.parent else None,'world_position':list(pivot.matrix_world.translation)})
            if not pivot.parent or pivot.parent.name!=expected_parent:
                errors.append('Unexpected pivot hierarchy: '+pivot.name)
    # Final detailing partitions the same source into 20 meshes. Discover the
    # complete source set from actual face provenance, then use the verified
    # master names when inspecting the exported GLB, which has no face attributes.
    source_parts=[o for o in objects if o.type=='MESH' and o.data.attributes.get('source_face_index')]
    provenance={'attribute_present':bool(source_parts),'source_mesh_names':[o.name for o in source_parts]}
    source_export_expectations=[]
    if a.master:
        if not source_records or (dual and len(source_records)!=2):
            errors.append('Actual source GLB origin records incomplete; native provenance cannot be certified')
        else:
            provenance,source_export_expectations=master_provenance(source_parts,root,source_records,errors,dual)
        refinement_path=root/'docs/final_refinement.json'
        if refinement_path.is_file():
            expected_source_names=read_json(refinement_path).get('source_part_meshes',[])
            if expected_source_names and set(expected_source_names)!=set(o.name for o in source_parts):
                errors.append('Actual source provenance mesh names differ from executed refinement record')
            provenance['executed_refinement_expected_names']=expected_source_names
            claimed_sha=read_json(refinement_path).get('source_glb_sha256')
            if claimed_sha and source_record and claimed_sha!=source_record['sha256']:
                errors.append('Original source GLB hash differs from executed refinement record')
    if a.glb:
        source_names=[]
        if previous_master:source_names=previous_master.get('source_part_names',[])
        elif (root/'docs/final_refinement.json').is_file():
            source_names=read_json(root/'docs/final_refinement.json').get('source_part_meshes',[])
        if source_names:
            source_parts=[]
            for name in source_names:
                obj=bpy.data.objects.get(name)
                if obj and obj.type=='MESH' and obj in objects:source_parts.append(obj)
                else:errors.append('Detailed source part missing from GLB: '+name)
            provenance={'attribute_present':False,'dual_source':dual,'source_mesh_names':source_names,
                        'scope':'Names cross-checked against reopened master; face-index conservation cannot be re-proved from standard glTF.'}
    if not source_parts:source_parts=required
    meshes=[mesh_record(o,errors,o in source_parts) for o in objects if o.type=='MESH']
    curves=[curve_record(o,errors) for o in objects if o.type in {'CURVE','CURVES'}]
    native=[c for c in curves if c['native_fiber']]
    if a.master and sum(c['strands'] for c in native)==0:errors.append('Master has no editable native fiber strands')
    eyes=eye_controls(objects,errors)
    motions=rigid_motion_controls(objects,errors,warnings)
    limits=local_rotation_limit_checks(objects,errors,mode,dual)
    metals=gold_controls(objects,errors)
    resources=inspect_images(objects,scene,errors)
    if a.master and not resources['all_referenced_images_packed']:
        warnings.append('Some referenced images are externally available rather than packed; see resource records.')
    core_box=combined_bbox(source_parts)
    master_comparison=None
    glb_triangle_comparison=None
    if a.glb and master_report.is_file():
        previous=read_json(master_report);target=previous.get('source_part_world_bbox')
        if previous.get('status')!='pass':errors.append('Referenced native-master QA is not a passing technical verification')
        master_input=previous.get('input',{})
        verified_master_path=resolve_recorded_path(master_input['path'],root) if master_input.get('path') else None
        if not verified_master_path or not verified_master_path.is_file():
            errors.append('Referenced native-master report artifact cannot be resolved in this project')
        elif sha256(verified_master_path)!=master_input.get('sha256_after'):
            errors.append('Referenced native-master report is stale: master file changed after its QA')
        expectations=previous.get('source_export_triangle_expectations',[])
        if dual and not expectations:errors.append('Dual-source GLB QA has no per-part verified native export expectations')
        if dual and set(e['name'] for e in expectations)!=set(o.name for o in source_parts):
            errors.append('Dual-source export expectations do not cover exactly all actual 20 source-part names')
        if expectations:
            actual={o.name:len(o.data.loop_triangles) for o in source_parts}
            checks=[]
            for expectation in expectations:
                name=expectation['name'];expected=expectation['expected_glb_triangles_after_known_export_validation']
                equal=actual.get(name)==expected
                nodes=[n for n in container.get('mesh_node_triangle_accessor_counts',[]) if n['name']==name]
                accessor_actual=nodes[0]['triangle_accessor_count'] if len(nodes)==1 else None
                accessor_match=len(nodes)==1 and accessor_actual==expected and not nodes[0]['unsupported_primitives']
                checks.append({'name':name,'native_source_faces':expectation['native_source_faces'],
                    'specifically_approved_duplicate_export_reduction':expectation['approved_glb_duplicate_face_reduction'],
                    'expected_glb_triangles':expected,'actual_container_accessor_triangles':accessor_actual,
                    'container_accessor_count_matches':bool(accessor_match),
                    'actual_reimport_triangles':actual.get(name),'reimport_count_matches':equal,'matches':bool(equal and accessor_match)})
                if not equal:errors.append('GLB reimport source triangle count differs from specifically verified export expectation: '+name)
                if not accessor_match:errors.append('Actual GLB container source-node triangle accessor count differs from verified expectation: '+name)
            glb_triangle_comparison={'per_part':checks,'all_counts_match':all(c['matches'] for c in checks),
                'specifically_verified_total_duplicate_export_reduction':sum(e['approved_glb_duplicate_face_reduction'] for e in expectations),
                'scope':'Only specific duplicate-vertex triangles with actual native-source IDs and temporary-copy validation are allowed to collapse on export. GLB raw accessors and independent Blender reimport counts are both checked. Standard GLB does not retain native per-face origin IDs.'}
        if target and core_box:
            delta=max(abs(x-y) for key in ('min','max') for x,y in zip(target[key],core_box[key]))
            master_comparison={'master_report':str(master_report),'max_core_bbox_delta_design_units':delta,
                               'within_0_002_design_units':delta<=.002,
                               'scope':'Source-part outer bounds only; this does not establish texture, hair or artistic parity.'}
            if delta>.002:errors.append('GLB core bounds differ from reopened master by more than .002 design units')
    elif a.glb:
        if dual:errors.append('Dual-source GLB QA requires a verified native-master report')
        else:warnings.append('Master QA report missing; no direct exported/master bound comparison is claimed.')
    if core_box:
        if abs(core_box['dimensions'][2]-1)>.003:errors.append('Source part design height differs from 1 m normalization')
        if abs(core_box['min'][2])>.002:errors.append('Source paws do not rest at design ground Z=0')
    exclusions=[{'name':o.name,'type':o.type} for o in bpy.data.objects if o not in objects]
    render={'engine':scene.render.engine,'resolution':[scene.render.resolution_x,scene.render.resolution_y],
            'resolution_percentage':scene.render.resolution_percentage,'active_camera':scene.camera.name if scene.camera else None,
            'camera_count':sum(o.type=='CAMERA' for o in bpy.data.objects),'light_count':sum(o.type=='LIGHT' for o in bpy.data.objects),
            'samples':scene.cycles.samples if scene.render.engine=='CYCLES' else None}
    if a.master and (not scene.camera or render['light_count']==0):warnings.append('Master has no active camera or studio lights; renderer configuration requires review.')
    after_sha=sha256(path)
    if initial_sha!=after_sha:errors.append('Artifact changed on disk during read-only QA; a concurrent save invalidates this snapshot')
    result={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'mode':mode,'status':'pass' if not errors else 'fail',
        'input':{'path':str(path),'bytes':path.stat().st_size,'sha256_before':initial_sha,'sha256_after':after_sha,'preserved':initial_sha==after_sha},
        'approved_source_glb':source_record,
        'approved_source_assets':source_records,'dual_source_composite':dual,
        'blender_version':bpy.app.version_string,'scope':'Actual artifact independently reopened/imported; only technical checks listed here are certified. Full specification and artistic acceptance remain separate.',
        'asset_root':lionroot.name if lionroot else None,'asset_object_count':len(objects),
        'asset_type_counts':dict(Counter(o.type for o in objects)),
        'source_part_world_bbox':core_box,'asset_mesh_world_bbox':combined_bbox([o for o in objects if o.type=='MESH']),
        'source_part_count':len(source_parts),'source_part_names':[o.name for o in source_parts],
        'required_major_part_count':len(required),'source_face_provenance':provenance,
        'source_export_triangle_expectations':source_export_expectations,
        'mesh_records':meshes,'pivot_hierarchy':hierarchy,
        'native_curve_records':curves,'native_fiber_object_count':len(native),
        'native_fiber_strand_count':sum(c['strands'] for c in native),
        'native_fiber_control_point_count':sum(c['control_points'] for c in native),
        'independent_eye_controls':eyes,'added_metal_feature_controls':metals,
        'rigid_motion_controls':motions,
        'native_rotation_limits_or_glb_metadata':limits,
        'dependencies':resources,'glb_container':container,
        'master_export_bounds_comparison':master_comparison,'render_configuration':render,
        'glb_source_triangle_count_comparison':glb_triangle_comparison,
        'objects_excluded_from_asset_counts':exclusions,'additional_structure_review':structural_review(objects),
        'errors':errors,'warnings':warnings,
        'unverified_requirements':['Reference-view shape, color, embroidery and fur fidelity require actual multi-angle image review.',
            'Native local rotation hard stops and sampled rigid editing poses are checked; collision-free attachment travel and skin deformation remain unverified. Standard GLB stores limit metadata only.',
            'Native fiber splines do not by themselves prove appropriate strand density, root placement or realistic fur.',
            'Source non-manifold edges and intentional open partitions are reported; printability and watertightness are not claimed.',
            'Names do not prove independent sculptural detail for brows, nose, eyelids, side ornaments or wave-trim bases.',
            'GLB container and bounds checks do not establish viewport/render appearance parity.']}
    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'report':str(report),'mode':mode,'status':result['status'],'asset_objects':len(objects),
                      'source_parts':len(source_parts),'native_strands':result['native_fiber_strand_count'],'errors':errors,'warnings':warnings},ensure_ascii=False))
    if errors:raise RuntimeError('Final lion technical QA failed; inspect '+str(report))

if __name__=='__main__':main()
