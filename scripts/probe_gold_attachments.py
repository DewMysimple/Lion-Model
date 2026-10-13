"""Read-only gold surface probes on the actual approved source mesh and UVs."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import sys,json,hashlib
import bpy,numpy as np
R = ROOT
sys.path.insert(0,str(R/'scripts'))
from organize_lion_parts import canonical_positions,box
from lion_material_tools import image_pixels,find_basecolor_image,sample_uv_colors,color_classes
source=R/'generated/Lux3D_Lion_Base_glb.glb'
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source),import_pack_images=True)
o=next(o for o in bpy.data.objects if o.type=='MESH');m=o.data
p,_=canonical_positions(o);f=np.array([q.vertices[:] for q in m.polygons]);c=p[f].mean(axis=1)
e1=p[f[:,1]]-p[f[:,0]];e2=p[f[:,2]]-p[f[:,0]];cross=np.cross(e1,e2);area=np.linalg.norm(cross,axis=1)*.5
n=cross/np.maximum(np.linalg.norm(cross,axis=1)[:,None],1e-20)
uv=np.empty(len(m.loops)*2,np.float32);m.uv_layers[0].data.foreach_get('uv',uv);uv=uv.reshape(-1,3,2).mean(axis=1)
rgb=sample_uv_colors(image_pixels(find_basecolor_image(m.materials[0])),uv)
classes=color_classes(rgb);gold=classes['gold']
regions={
    'Forehead_Cap':(abs(c[:,0])<.080)&(c[:,1]<-.480)&(c[:,2]>.720)&(c[:,2]<.840),
    'Cheek_Medallion_L':(c[:,0]>.230)&(c[:,1]>-.570)&(c[:,1]<-.280)&(c[:,2]>.570)&(c[:,2]<.750),
    'Cheek_Medallion_R':(c[:,0]<-.230)&(c[:,1]>-.570)&(c[:,1]<-.280)&(c[:,2]>.570)&(c[:,2]<.750),
    'Cheek_Hanging_Bell_L':(c[:,0]>.230)&(c[:,1]>-.570)&(c[:,1]<-.280)&(c[:,2]>.415)&(c[:,2]<.585),
    'Cheek_Hanging_Bell_R':(c[:,0]<-.230)&(c[:,1]>-.570)&(c[:,1]<-.280)&(c[:,2]>.415)&(c[:,2]<.585),
    'Tail_Bell_L':(c[:,0]>.055)&(c[:,0]<.250)&(c[:,1]>.535)&(c[:,2]>.490)&(c[:,2]<.675),
    'Tail_Bell_R':(c[:,0]<-.055)&(c[:,0]>-.250)&(c[:,1]>.535)&(c[:,2]>.490)&(c[:,2]<.675),
    'Forehead_Convex_Cap_Narrow':(abs(c[:,0])<.056)&(c[:,1]<-.635)&(c[:,2]>.745)&(c[:,2]<.825),
    'Cheek_Medallion_Narrow_L':(c[:,0]>.290)&(c[:,1]>-.445)&(c[:,1]<-.355)&(c[:,2]>.610)&(c[:,2]<.705),
    'Cheek_Medallion_Narrow_R':(c[:,0]<-.290)&(c[:,1]>-.445)&(c[:,1]<-.355)&(c[:,2]>.610)&(c[:,2]<.705),
    'Cheek_Hanging_Bell_Narrow_L':(c[:,0]>.295)&(c[:,1]>-.470)&(c[:,1]<-.410)&(c[:,2]>.545)&(c[:,2]<.600),
    'Cheek_Hanging_Bell_Narrow_R':(c[:,0]<-.295)&(c[:,1]>-.470)&(c[:,1]<-.410)&(c[:,2]>.545)&(c[:,2]<.600),
}
results={}
for name,region in regions.items():
    if name=='Forehead_Convex_Cap_Narrow':
        capmask=(np.ptp(rgb,axis=1)/np.maximum(rgb.max(axis=1),1e-6)<.28)&(rgb.min(axis=1)>.38)
        mask=region&capmask;pc=c[mask];weight=area[mask]
    else:
        mask=region&(gold>.25);pc=c[mask];weight=area[mask]*gold[mask]
    if len(pc)<5:
        results[name]={'status':'insufficient_samples','count':len(pc)};continue
    center=np.average(pc,axis=0,weights=weight);normal=np.average(n[mask],axis=0,weights=weight)
    normal/=max(np.linalg.norm(normal),1e-20)
    results[name]={'status':'measured_neutral_metal_like_surface_region' if name=='Forehead_Convex_Cap_Narrow' else 'measured_gold_colored_surface_region',
        'selected_face_count':len(pc),'gold_face_count':int(np.count_nonzero(gold[mask]>.25)),
        'selected_surface_area_design_units2':float(area[mask].sum()),
        'gold_surface_area_design_units2':float(area[mask&(gold>.25)].sum()),'surface_weighted_center':center.tolist(),
        'weighted_face_normal':normal.tolist(),'surface_bbox':box(pc),
        'mean_rgb_srgb':np.average(rgb[mask],axis=0,weights=weight).tolist(),
        'highest_gold_faces':[{'center':c[i].tolist(),'normal':n[i].tolist(),'rgb':rgb[i].tolist(),'gold':float(gold[i])}
                              for i in np.flatnonzero(mask)[np.argsort(gold[mask])[-8:]]],
        'confidence':('Central grey/beige cap sampled from low-saturation source UV colour plus spatial bounds; placement is a visual estimate, not exact ornament recovery.'
                      if name=='Forehead_Convex_Cap_Narrow' else
                      'Region membership from real UV gold appearance plus spatial bounds; separates neither geometric ornament extent nor internal mechanism.')}
(R/'docs/gold_attachment_surface_probe.json').write_text(json.dumps({'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'parts':results},indent=2))
print(json.dumps(results))
