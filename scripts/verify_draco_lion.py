"""Read-only actual Draco reimport plus binary attribute/quantization QA.

Writes only a dedicated JSON report. Neither model nor prior reports are saved.
The Blender importer and the bundled Draco decoder both read the actual file.
"""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path, resolve_recorded_path

import argparse
import ctypes as ct
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time

import bpy
import numpy as np
from mathutils.kdtree import KDTree

DTYPES={5120:np.int8,5121:np.uint8,5122:np.int16,5123:np.uint16,5125:np.uint32,5126:np.float32}
WIDTHS={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
CURRENT_REPORT=None


def save_report(path,report):
    def numpy_scalar(value):
        if isinstance(value,np.generic):return value.item()
        raise TypeError('Unexpected report value: '+type(value).__name__)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=numpy_scalar),encoding='utf8')


def add_normal_quantization_gate(report):
    """Apply a conservative finite 12-bit bound to the actual measured angles.

    Draco rounds L1-projected x/y, then obtains z by the remaining L1 sum.
    Its possible one-unit boundary correction gives component error bounds
    (.5,1.5,1)/center. Projection length is at least 1/sqrt(3).
    """
    detail=report['draco_verification'];errors=report['errors']
    bits=detail['completed_export_configuration']['export_draco_normal_quantization']
    center=((1<<bits)-2)/2
    angular_bound=float(np.degrees(np.arcsin(np.sqrt(10.5)/center)+64*np.finfo(np.float32).eps))
    normal_checks=[]
    for record in detail['per_primitive_actual_attribute_measurements']:
        if 'NORMAL' not in record['attributes']:continue
        angle=record['max_nearest_compatible_source_normal_angle_degrees']
        passed=angle is not None and np.isfinite(angle) and angle<=angular_bound
        record['normal_angle_quantization_budget_degrees']=angular_bound
        record['within_normal_quantization_budget']=bool(passed)
        normal_checks.append(bool(passed))
        if not passed:errors.append('Decoded normals exceed conservative 12-bit octahedral angular budget: '+record['name']+'/'+str(record['primitive_index']))
    if not normal_checks:errors.append('No actual decoded NORMAL angle measurements present')
    detail['normal_quantization_gate']={'bits_from_completed_export_configuration':bits,
        'octahedron_integer_center':center,'conservative_angular_budget_degrees':angular_bound,
        'primitives_measured':len(normal_checks),'all_measured_angles_within_budget':bool(normal_checks) and all(normal_checks),
        'derivation':'L1 projection has norm >=1/sqrt(3). Rounded integer x/y plus remaining-sum z and the one-unit boundary correction give projected component-error bounds (.5,1.5,1)/center. The angular bound is asin(sqrt(10.5)/center), plus 64 float32 epsilon radians for arithmetic slack. This is a conservative analytic bound inferred from the referenced encoding implementation, not an independently recovered bitstream parameter.',
        'primary_source':'https://github.com/google/draco/blob/main/src/draco/compression/attributes/normal_compression_utils.h',
        'comparison_scope':'Nearest compatible source NORMAL in the position/UV seam-candidate set; exact per-face-corner correspondence is not established.'}
    report['status']='pass' if not errors else 'fail'
    return report


def finalize_recorded_normal_gate(path):
    """Gate already captured actual decoder measurements, without another import."""
    import hashlib
    report=json.loads(path.read_text(encoding='utf8'))
    if report.get('mode')!='draco_glb' or report.get('draco_verification_pending'):
        raise ValueError('A completed actual Draco measurement report is required')
    for record in report['draco_verification']['preserved_inputs_and_prior_reports']:
        artifact=resolve_recorded_path(record['path'],path.resolve().parents[1])
        h=hashlib.sha256()
        with artifact.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=record['sha256_after']:raise ValueError('Recorded measurement input changed: '+str(artifact))
    add_normal_quantization_gate(report);save_report(path,report)
    print(json.dumps({'normal_gate_report':str(path),'status':report['status'],
        'normal_gate':report['draco_verification']['normal_quantization_gate'],'errors':report['errors']},ensure_ascii=False),flush=True)
    if report['errors']:raise RuntimeError('Recorded Draco normal gate failed')


def load_glb(path):
    data=path.read_bytes();magic,version,total=struct.unpack_from('<4sII',data)
    if magic!=b'glTF' or version!=2 or total!=len(data):raise ValueError('Invalid GLB: '+str(path))
    chunks={};at=12
    while at<len(data):
        size,kind=struct.unpack_from('<II',data,at);at+=8
        chunks[kind]=memoryview(data)[at:at+size];at+=size
    return json.loads(bytes(chunks[0x4e4f534a]).decode('utf8').rstrip('\x00 ')),chunks[0x004e4942],data


def view_bytes(doc,buffer,index):
    v=doc['bufferViews'][index]
    if v.get('buffer',0)!=0:raise ValueError('Unexpected nonembedded buffer')
    start=v.get('byteOffset',0);return buffer[start:start+v['byteLength']]


def accessor(doc,buffer,index):
    a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
    dtype=np.dtype(DTYPES[a['componentType']]).newbyteorder('<');width=WIDTHS[a['type']]
    start=v.get('byteOffset',0)+a.get('byteOffset',0)
    arr=np.ndarray((a['count'],width),dtype=dtype,buffer=buffer,offset=start,
                   strides=(v.get('byteStride',dtype.itemsize*width),dtype.itemsize)).copy()
    if a.get('normalized') and dtype.kind in 'ui':
        info=np.iinfo(dtype);arr=arr.astype(np.float32)/info.max
        if dtype.kind=='i':arr=np.maximum(arr,-1)
    return arr


def decoder_library():
    path=Path(bpy.utils.resource_path('LOCAL'))/'scripts/addons_core/io_scene_gltf2/extern_draco.dll'
    dll=ct.CDLL(str(path))
    signatures={
        'decoderCreate':(ct.c_void_p,[]),'decoderRelease':(None,[ct.c_void_p]),
        'decoderDecode':(ct.c_bool,[ct.c_void_p,ct.c_void_p,ct.c_size_t]),
        'decoderReadAttribute':(ct.c_bool,[ct.c_void_p,ct.c_uint32,ct.c_size_t,ct.c_char_p]),
        'decoderGetVertexCount':(ct.c_uint32,[ct.c_void_p]),
        'decoderGetIndexCount':(ct.c_uint32,[ct.c_void_p]),
        'decoderGetAttributeByteLength':(ct.c_size_t,[ct.c_void_p,ct.c_uint32]),
        'decoderCopyAttribute':(None,[ct.c_void_p,ct.c_uint32,ct.c_void_p]),
        'decoderReadIndices':(ct.c_bool,[ct.c_void_p,ct.c_size_t]),
        'decoderGetIndicesByteLength':(ct.c_size_t,[ct.c_void_p]),
        'decoderCopyIndices':(None,[ct.c_void_p,ct.c_void_p])}
    for name,(restype,argtypes) in signatures.items():
        getattr(dll,name).restype=restype;getattr(dll,name).argtypes=argtypes
    return dll,path


def decode_primitive(dll,doc,buffer,prim):
    ext=prim['extensions']['KHR_draco_mesh_compression'];raw=bytes(view_bytes(doc,buffer,ext['bufferView']))
    storage=ct.create_string_buffer(raw);decoder=dll.decoderCreate()
    try:
        if not dll.decoderDecode(decoder,storage,len(raw)):raise ValueError('Actual Draco decode failed')
        count=dll.decoderGetVertexCount(decoder);attrs={}
        for name,draco_id in ext['attributes'].items():
            a=doc['accessors'][prim['attributes'][name]]
            if count!=a['count']:raise ValueError('Decoded/accessor vertex counts differ')
            if not dll.decoderReadAttribute(decoder,draco_id,a['componentType'],a['type'].encode()):
                raise ValueError('Cannot decode '+name)
            out=np.empty((count,WIDTHS[a['type']]),DTYPES[a['componentType']])
            if out.nbytes!=dll.decoderGetAttributeByteLength(decoder,draco_id):raise ValueError('Attribute byte size mismatch')
            dll.decoderCopyAttribute(decoder,draco_id,ct.c_void_p(out.ctypes.data));attrs[name]=out
        ia=doc['accessors'][prim['indices']];icount=dll.decoderGetIndexCount(decoder)
        if icount!=ia['count'] or icount%3:raise ValueError('Decoded/accessor triangle index counts differ')
        if not dll.decoderReadIndices(decoder,ia['componentType']):raise ValueError('Cannot decode actual triangle indices')
        indices=np.empty(icount,DTYPES[ia['componentType']])
        if indices.nbytes!=dll.decoderGetIndicesByteLength(decoder):raise ValueError('Index byte size mismatch')
        dll.decoderCopyIndices(decoder,ct.c_void_p(indices.ctypes.data))
        if indices.size and int(indices.max())>=count:raise ValueError('Decoded index outside vertex array')
        return attrs,indices
    finally:dll.decoderRelease(decoder)


def nearest_errors(reference,decoded,uv_ref=None,uv_dec=None,normal_ref=None,normal_dec=None,uv_bound=None):
    """Actual unordered vertex-position comparison; inspect all decoded UVs/normals.

    Candidate corner attributes at identical/nearby source positions account for
    UV seams and hard normal splits. This is attribute-set parity, not an exact
    per-face corner correspondence or a proof of triangle connectivity parity.
    """
    tree=KDTree(len(reference))
    for i,point in enumerate(reference):tree.insert(point,i)
    tree.balance();forward=0.;uv_max=0.;angle_max=0.;unmatched_uv=0;unmatched_indices=[]
    pos_span=float(np.ptp(reference,axis=0).max())
    step=pos_span/(2**20-1)
    numerical=4*np.finfo(np.float32).eps*max(float(np.abs(reference).max()),pos_span,np.finfo(np.float32).tiny)
    radius=(np.sqrt(3)*.5*step+numerical)*1.0001
    for i,point in enumerate(decoded):
        _,closest,dist=tree.find(point);forward=max(forward,float(dist))
        if uv_ref is None and normal_ref is None:continue
        candidates=tree.find_range(point,radius)
        if not candidates:candidates=[(None,closest,dist)]
        candidate_ids=np.asarray([c[1] for c in candidates],dtype=np.int64)
        if uv_ref is not None:
            diffs=np.abs(uv_ref[candidate_ids].astype(float)-uv_dec[i])
            normalized=np.max(diffs/uv_bound,axis=1);best_index=int(np.argmin(normalized))
            uv_max=max(uv_max,float(diffs[best_index].max()))
            candidates_uv=candidate_ids[np.all(diffs<=uv_bound,axis=1)]
            if not len(candidates_uv):
                unmatched_uv+=1;unmatched_indices.append(i);candidates_uv=candidate_ids[[best_index]]
            candidate_ids=candidates_uv
        if normal_ref is not None:
            originals=normal_ref[candidate_ids].astype(float);current=normal_dec[i].astype(float)
            lengths=np.linalg.norm(originals,axis=1)*np.linalg.norm(current)
            valid=lengths>0
            if not valid.all():raise ValueError('Decoded or source normal has zero length')
            cos=np.clip((originals@current)/lengths,-1,1)
            angle=float(np.degrees(np.arccos(cos)).min());angle_max=max(angle_max,angle)
    reverse_tree=KDTree(len(decoded))
    for i,point in enumerate(decoded):reverse_tree.insert(point,i)
    reverse_tree.balance();reverse=max(float(reverse_tree.find(point)[2]) for point in reference)
    return {'max_decoded_to_original_local_position_distance':forward,
        'max_original_to_decoded_local_position_distance':reverse,
        'symmetric_local_vertex_set_distance':max(forward,reverse),
        'position_quantization_step_from_actual_primitive_range':step,
        'position_nearest_rounding_euclidean_bound_with_float32_slack':radius,
        'within_position_quantization_budget':bool(max(forward,reverse)<=radius),
        'max_nearest_compatible_source_uv_component_delta':uv_max if uv_ref is not None else None,
        'uv_component_budget':uv_bound.tolist() if uv_ref is not None else None,
        'decoded_uv_vertices_without_compatible_original_uv':unmatched_uv if uv_ref is not None else None,
        'uv_unmatched_decoded_vertex_indices':unmatched_indices,
        'max_nearest_compatible_source_normal_angle_degrees':angle_max if normal_ref is not None else None,
        'position_vertices_compared_forward':len(decoded),'position_vertices_compared_reverse':len(reference)}


def resolve_native_duplicate_alternatives(root,master_report,name,originals,decoded,indices,stats):
    """Permit another native member only in an already verified duplicate group.

    All actual decoded triangle corners must match that member's position, every
    UV layer, normal and cyclic winding; isolated nearest-position matches do
    not establish this specific exception. No mesh is edited or saved.
    """
    expectation=next((e for e in master_report['source_export_triangle_expectations'] if e['name']==name),None)
    if not expectation:return None
    groups=expectation.get('native_duplicate_vertex_triangle_groups',[])
    if not groups:return None
    before=set(bpy.data.objects)
    try:
        with bpy.data.libraries.load(master_report['input']['path'],link=False) as (available,requested):
            requested.objects=[name]
        native=requested.objects[0]
        if native is None or native.type!='MESH':raise ValueError('Native duplicate-candidate mesh unavailable')
        mesh=native.data;fa=mesh.attributes['source_face_index'];faceids=np.empty(len(fa.data),np.int32)
        fa.data.foreach_get('value',faceids);face_by_id={int(fid):i for i,fid in enumerate(faceids)}
        uv_names=sorted(k for k in originals if k.startswith('TEXCOORD_'))
        uv_budget=np.asarray(stats['uv_component_budget']);radius=stats['position_nearest_rounding_euclidean_bound_with_float32_slack']
        angle_budget=float(np.degrees(np.arcsin(np.sqrt(10.5)/2047)+64*np.finfo(np.float32).eps))
        candidates=[]
        for group in groups:
            for fid in group['source_face_ids']:
                if fid not in face_by_id:raise ValueError('Recorded duplicate source member missing from actual master')
                poly=mesh.polygons[face_by_id[fid]]
                if sorted(poly.vertices)!=group['native_vertex_set']:raise ValueError('Actual duplicate native vertex set differs from passing report')
                points=[];uvs=[];normals=[]
                for loop_id in poly.loop_indices:
                    vi=mesh.loops[loop_id].vertex_index
                    points.append(np.asarray(mesh.vertices[vi].co)[[0,2,1]]*np.array([1,1,-1]))
                    normals.append(np.asarray(mesh.corner_normals[loop_id].vector)[[0,2,1]]*np.array([1,1,-1]))
                    uv=[]
                    for uv_name in uv_names:
                        uvindex=int(uv_name.split('_')[-1]);v=mesh.uv_layers[uvindex].data[loop_id].uv
                        uv.extend([float(v[0]),1-float(v[1])])
                    uvs.append(uv)
                candidates.append({'source_face_id':fid,'group_source_face_ids':group['source_face_ids'],
                    'native_vertex_set':group['native_vertex_set'],'native_face_index':poly.index,
                    'points':np.asarray(points),'uvs':np.asarray(uvs),'normals':np.asarray(normals)})
        bad=set(stats['uv_unmatched_decoded_vertex_indices']);tris=indices.reshape(-1,3)
        triangle_indices=np.flatnonzero(np.any(np.isin(tris,list(bad)),axis=1))
        resolutions=[];extra_points=[];extra_uvs=[];extra_normals=[];covered=set()
        for ti in triangle_indices:
            decoded_ids=tris[ti];dpoints=decoded['POSITION'][decoded_ids].astype(float)
            duvs=np.concatenate([decoded[sem][decoded_ids] for sem in uv_names],axis=1).astype(float)
            dn=decoded['NORMAL'][decoded_ids].astype(float);matches=[]
            for candidate in candidates:
                for shift in range(3):
                    order=np.roll(np.arange(3),shift)
                    pos_errors=np.linalg.norm(dpoints-candidate['points'][order],axis=1)
                    if not np.all(pos_errors<=radius):continue
                    uv_errors=np.abs(duvs-candidate['uvs'][order])
                    if not np.all(uv_errors<=uv_budget):continue
                    n=candidate['normals'][order];angles=np.degrees(np.arccos(np.clip(np.sum(n*dn,axis=1)/(np.linalg.norm(n,axis=1)*np.linalg.norm(dn,axis=1)),-1,1)))
                    if not np.all(angles<=angle_budget):continue
                    matches.append((candidate,order,pos_errors,uv_errors,angles))
            if len(matches)!=1:return None
            candidate,order,pos_errors,uv_errors,angles=matches[0]
            resolutions.append({'actual_decoded_triangle_index':int(ti),'actual_decoded_vertex_indices':decoded_ids.tolist(),
                'retained_native_source_face_id':candidate['source_face_id'],
                'already_verified_duplicate_source_face_group':candidate['group_source_face_ids'],
                'actual_native_vertex_set':candidate['native_vertex_set'],
                'max_position_error':float(pos_errors.max()),'max_uv_component_error':float(uv_errors.max()),
                'max_normal_angle_degrees':float(angles.max()),'cyclic_source_winding_matches':True})
            covered.update(int(i) for i in decoded_ids if i in bad)
            extra_points.extend(candidate['points']);extra_uvs.extend(candidate['uvs']);extra_normals.extend(candidate['normals'])
        if covered!=bad or not resolutions:return None
        if len({tuple(r['already_verified_duplicate_source_face_group']) for r in resolutions})!=len(resolutions):return None
        augmented_points=np.concatenate([originals['POSITION'],np.asarray(extra_points)],axis=0)
        augmented_uvs=np.concatenate([np.concatenate([originals[sem] for sem in uv_names],axis=1),np.asarray(extra_uvs)],axis=0)
        augmented_normals=np.concatenate([originals['NORMAL'],np.asarray(extra_normals)],axis=0)
        corrected=nearest_errors(augmented_points,decoded['POSITION'],augmented_uvs,
            np.concatenate([decoded[sem] for sem in uv_names],axis=1),augmented_normals,decoded['NORMAL'],uv_budget)
        if corrected['decoded_uv_vertices_without_compatible_original_uv']:return None
        corrected['specific_native_duplicate_member_alternatives']={
            'strict_uncompressed_reference_unmatched_vertices':sorted(bad),
            'strict_uncompressed_reference_max_uv_delta':stats['max_nearest_compatible_source_uv_component_delta'],
            'strict_uncompressed_reference_max_normal_angle_degrees':stats['max_nearest_compatible_source_normal_angle_degrees'],
            'verified_native_master_sha256':master_report['input']['sha256_after'],
            'actual_decoded_triangles_verified_against_native_source_members':resolutions,
            'scope':'These exact already approved duplicate triangle groups retained a different native member during the two exports. Full triangle position, every UV layer, normals and cyclic winding are proved against actual native source corners. No arbitrary UV or normal tolerance is allowed.'}
        return corrected
    finally:
        for ob in list(bpy.data.objects):
            if ob not in before:bpy.data.objects.remove(ob,do_unlink=True)


def main():
    global CURRENT_REPORT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    a=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root=a.root.resolve();compressed=root/'exports/scene_draco.glb';raw=root/'exports/scene.glb'
    target=root/'docs/final_draco_verification.json';native=root/'docs/final_master_verification.json'
    CURRENT_REPORT=target
    spec=importlib.util.spec_from_file_location('lion_base_qa',root/'scripts/verify_final_lion.py')
    qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)
    preserved=[compressed,raw,native,root/'docs/final_glb_verification.json',blend_path('Lion_Final_Master.blend', root=root)]
    hashes={str(p):qa.sha256(p) for p in preserved};start=time.time()
    # Base QA really imports this compressed GLB in the fresh Blender process.
    sys.argv=['verify_draco_lion.py','--','--glb','--dual-source','--root',str(root),
              '--input',str(compressed),'--master-report',str(native),'--report',str(target)]
    qa.main();report=qa.read_json(target);errors=report['errors']
    report['status']='running';report['draco_verification_pending']=True;save_report(target,report)
    export=qa.read_json(root/'docs/final_export_draco.json')
    if export['sha256']!=hashes[str(compressed)]:errors.append('Actual compressed hash differs from completed export record')
    settings=export.get('compression',{})
    expected_bits={'export_draco_position_quantization':20,'export_draco_texcoord_quantization':16,'export_draco_normal_quantization':12}
    if any(settings.get(k)!=v for k,v in expected_bits.items()):errors.append('Unexpected completed-export quantization configuration')
    rd,rb,rstorage=load_glb(raw);dd,db,dstorage=load_glb(compressed)
    if 'KHR_draco_mesh_compression' not in dd.get('extensionsRequired',[]):errors.append('Draco decoder requirement is not declared')
    equivalence={}
    for category in ('materials','textures','samplers','scenes','scene'):
        equivalence[category]=rd.get(category)==dd.get(category)
        if not equivalence[category]:errors.append('Compressed/uncompressed JSON differs in '+category)
    node_keys=('name','mesh','children','translation','rotation','scale','matrix','extras')
    simplify=lambda doc:[{k:n[k] for k in node_keys if k in n} for n in doc.get('nodes',[])]
    equivalence['node_hierarchy_transforms_and_metadata']=simplify(rd)==simplify(dd)
    if not equivalence['node_hierarchy_transforms_and_metadata']:errors.append('Compressed hierarchy/transform/metadata changed')
    images=[]
    if len(rd.get('images',[]))!=len(dd.get('images',[])):errors.append('Embedded image count changed')
    for i,(rimage,dimage) in enumerate(zip(rd.get('images',[]),dd.get('images',[]))):
        import hashlib
        rh=hashlib.sha256(view_bytes(rd,rb,rimage['bufferView'])).hexdigest()
        dh=hashlib.sha256(view_bytes(dd,db,dimage['bufferView'])).hexdigest()
        same=rh==dh and rimage.get('mimeType')==dimage.get('mimeType')
        images.append({'image_index':i,'name':dimage.get('name'),'compressed_sha256':dh,'uncompressed_sha256':rh,'identical':same})
        if not same:errors.append('Embedded texture bytes changed: '+str(i))
    dll,dllpath=decoder_library();records=[];quant_bounds_by_name={};decoded_triangles=0
    native_report=qa.read_json(native);master_meshes={m['name']:m for m in native_report['mesh_records']}
    actual_meshes={o.name:o for o in bpy.data.objects if o.type=='MESH'}
    for node in dd['nodes']:
        if 'mesh' not in node:continue
        name=node['name'];mesh_index=node['mesh'];dmesh=dd['meshes'][mesh_index];rmesh=rd['meshes'][mesh_index]
        if len(dmesh['primitives'])!=len(rmesh['primitives']):raise ValueError('Primitive partition changed: '+name)
        matrix=qa.matrix_values(actual_meshes[name]);max_world_budget=np.zeros(3)
        for pi,(dp,rp) in enumerate(zip(dmesh['primitives'],rmesh['primitives'])):
            if dp.get('material')!=rp.get('material') or set(dp['attributes'])!=set(rp['attributes']):errors.append('Primitive material/attribute semantics changed: '+name)
            if 'KHR_draco_mesh_compression' not in dp.get('extensions',{}):raise ValueError('Non-Draco primitive: '+name)
            dattrs,indices=decode_primitive(dll,dd,db,dp);decoded_triangles+=len(indices)//3
            originals={sem:accessor(rd,rb,ai) for sem,ai in rp['attributes'].items()}
            if any(not np.isfinite(v).all() for v in dattrs.values()):errors.append('Nonfinite decoded attribute: '+name)
            uv_names=sorted(sem for sem in originals if sem.startswith('TEXCOORD_'))
            uvref=np.concatenate([originals[sem] for sem in uv_names],axis=1) if uv_names else None
            uvdec=np.concatenate([dattrs[sem] for sem in uv_names],axis=1) if uv_names else None
            uvbound=None
            if uv_names:
                uvbudgets=[]
                for sem in uv_names:
                    original_uv=originals[sem];uvspan=float(np.ptp(original_uv,axis=0).max())
                    uvbudgets.extend([.5*uvspan/(2**16-1)+4*np.finfo(np.float32).eps*max(float(np.abs(original_uv).max()),uvspan,np.finfo(np.float32).tiny)]*original_uv.shape[1])
                uvbound=np.asarray(uvbudgets)
            stats=nearest_errors(originals['POSITION'],dattrs['POSITION'],uvref,uvdec,
                originals.get('NORMAL'),dattrs.get('NORMAL'),uvbound)
            if stats['decoded_uv_vertices_without_compatible_original_uv']:
                resolved=resolve_native_duplicate_alternatives(root,native_report,name,originals,dattrs,indices,stats)
                if resolved is not None:stats=resolved
            if not stats['within_position_quantization_budget']:errors.append('Decoded positions exceed range-derived 20-bit budget: '+name+'/'+str(pi))
            if stats['decoded_uv_vertices_without_compatible_original_uv']:errors.append('Decoded UVs exceed range-derived 16-bit budget: '+name+'/'+str(pi))
            # Scalar quantization spacing is shared across position components.
            # Signed axis conversion preserves the row absolute sums.
            span=float(np.ptp(originals['POSITION'],axis=0).max());step=span/(2**20-1)
            local_abs=np.max(np.abs(originals['POSITION']),axis=0)
            world_roundoff=8*np.finfo(np.float32).eps*(np.abs(matrix[:3,:3])@np.full(3,float(local_abs.max()))+np.abs(matrix[:3,3]))
            world_budget=.5*step*np.sum(np.abs(matrix[:3,:3]),axis=1)+world_roundoff
            max_world_budget=np.maximum(max_world_budget,world_budget)
            records.append({'name':name,'primitive_index':pi,'material_index':dp.get('material'),
                'actual_decoded_triangles':len(indices)//3,'attributes':list(dattrs),'measured_uv_semantics':uv_names,**stats,
                'world_bbox_component_budget':world_budget.tolist()})
        quant_bounds_by_name[name]=max_world_budget
        if len(records)%10==0:print('DRACO_ATTRIBUTE_PROGRESS '+name+' '+str(round(time.time()-start,1))+'s',flush=True)
    part_bounds=[]
    for name in native_report['source_part_names']:
        expected=master_meshes[name]['world_bbox'];actual=qa.bbox(qa.mesh_world_points(actual_meshes[name]));budget=quant_bounds_by_name[name]
        delta=np.max(np.abs(np.array([actual['min'],actual['max']])-np.array([expected['min'],expected['max']])),axis=0)
        passed=bool(np.all(delta<=budget))
        part_bounds.append({'name':name,'max_bbox_delta_by_world_axis':delta.tolist(),
            'range_derived_world_quantization_and_float32_budget':budget.tolist(),'within_budget':passed})
        if not passed:errors.append('Source part bbox exceeds primitive-range Draco budget vs native master: '+name)
    original_report=qa.read_json(root/'docs/final_glb_verification.json')
    if original_report['input']['sha256_after']!=hashes[str(raw)]:errors.append('Uncompressed comparison report is stale')
    if decoded_triangles!=sum(m['triangles'] for m in report['mesh_records']):errors.append('Direct Draco decoded triangle total disagrees with actual reimport')
    if decoded_triangles!=sum(m['triangles'] for m in original_report['mesh_records']):errors.append('Actual compressed triangle total differs from verified uncompressed file')
    actual_records={m['name']:m for m in report['mesh_records']}
    original_records={m['name']:m for m in original_report['mesh_records']}
    all_mesh_bbox_checks=[]
    if set(actual_records)!=set(original_records):errors.append('Compressed/uncompressed complete mesh name set differs')
    for name in sorted(set(actual_records)&set(original_records)):
        current=actual_records[name]['world_bbox'];previous=original_records[name]['world_bbox']
        delta=np.max(np.abs(np.array([current['min'],current['max']])-np.array([previous['min'],previous['max']])),axis=0)
        passed=bool(np.all(delta<=quant_bounds_by_name[name]))
        all_mesh_bbox_checks.append({'name':name,'max_bbox_delta_by_world_axis':delta.tolist(),
            'range_derived_world_quantization_and_float32_budget':quant_bounds_by_name[name].tolist(),'within_budget':passed})
        if not passed:errors.append('Mesh bbox exceeds primitive-range budget vs verified uncompressed export: '+name)
    core_bounds_delta=max(abs(x-y) for key in ('min','max') for x,y in zip(
        report['source_part_world_bbox'][key],native_report['source_part_world_bbox'][key]))
    asset_bounds_delta=max(abs(x-y) for key in ('min','max') for x,y in zip(
        report['asset_mesh_world_bbox'][key],original_report['asset_mesh_world_bbox'][key]))
    preserved_records=[{'path':str(p),'sha256_before':hashes[str(p)],'sha256_after':qa.sha256(p),'preserved':hashes[str(p)]==qa.sha256(p)} for p in preserved]
    if not all(p['preserved'] for p in preserved_records):errors.append('Model or prior QA file changed during read-only verification')
    report['mode']='draco_glb';report['status']='pass' if not errors else 'fail'
    report.pop('draco_verification_pending',None)
    report['draco_verification']={'completed_export_configuration':settings,
        'quantization_bits_scope':'Export log configuration is cross-checked; decoded errors are measured. Bit counts are not independently extracted from the compressed bitstream.',
        'decoder_library':str(dllpath),'all_mesh_primitives_actually_decoded':True,
        'compressed_primitives':len(records),'actual_decoded_triangles':decoded_triangles,
        'uncompressed_path':str(raw),'uncompressed_sha256':hashes[str(raw)],
        'size_ratio_compressed_over_uncompressed':compressed.stat().st_size/raw.stat().st_size,
        'container_equivalence':equivalence,'embedded_image_byte_comparison':images,
        'per_primitive_actual_attribute_measurements':records,'source_part_quantization_bounds_vs_native_master':part_bounds,
        'all_mesh_bounds_vs_verified_uncompressed_export':all_mesh_bbox_checks,
        'max_combined_source_bbox_delta_vs_native_master':core_bounds_delta,
        'max_combined_asset_mesh_bbox_delta_vs_uncompressed_web_export':asset_bounds_delta,
        'max_measured_source_part_bbox_delta':max(max(p['max_bbox_delta_by_world_axis']) for p in part_bounds),
        'max_measured_symmetric_local_position_distance':max(p['symmetric_local_vertex_set_distance'] for p in records),
        'max_measured_uv_component_delta':max((p['max_nearest_compatible_source_uv_component_delta'] or 0) for p in records),
        'max_measured_nearest_compatible_normal_angle_degrees':max((p['max_nearest_compatible_source_normal_angle_degrees'] or 0) for p in records),
        'preserved_inputs_and_prior_reports':preserved_records,'elapsed_seconds':time.time()-start,
        'limitations':['Position/UV/normal measurements compare unordered vertex attribute sets and compatible seam candidates, not exact face-corner correspondence or topology equivalence.',
            'Draco is lossy for position, UV and normal attributes. Embedded raster texture bytes and material definitions are compared exactly.',
            'A Draco-capable viewer/loader is required. Native curve editing and Blender hard-stop constraints are not available in standard glTF.',
            'Sampled mesh fiber proxies match the verified uncompressed GLB, not the full 980957 native strand set.']}
    report['master_export_bounds_comparison']['strict_draco_quantization_gate']=all(p['within_budget'] for p in part_bounds)
    add_normal_quantization_gate(report)
    save_report(target,report)
    print(json.dumps({'report':str(target),'status':report['status'],'decoded_triangles':decoded_triangles,
        'source_parts':report['source_part_count'],'max_source_bbox_delta':report['draco_verification']['max_measured_source_part_bbox_delta'],
        'errors':errors,'warnings':report['warnings']},ensure_ascii=False),flush=True)
    if errors:raise RuntimeError('Draco QA failed; inspect '+str(target))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        if CURRENT_REPORT and CURRENT_REPORT.is_file():
            failed=json.loads(CURRENT_REPORT.read_text(encoding='utf8'))
            failed['status']='fail';failed.setdefault('errors',[]).append(type(exc).__name__+': '+str(exc))
            save_report(CURRENT_REPORT,failed)
        raise
