"""Conservative recovery of printed cloth mistakenly split into G1 red trim.

This is a source-face appearance audit, not anatomical reconstruction. Run the
study on a copy; the saved mask can gate root's subsequent fiber regeneration.
The measured features belong to unchanged G1 source triangles and original UV0.
Never reuse this mask on another generated candidate or a deformed mesh.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import hashlib
import json
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(ROOT / "scripts"))
from probe_trim_cloth_recovery import surface
from study_brocade_cylinder import apply_cylindrical_brocade, add_camera, source_buffers


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def triangle_buffers(trim):
    mesh = trim.data
    if any(len(p.vertices) != 3 for p in mesh.polygons):
        raise ValueError("Only original G1 triangles are supported")
    faces = np.empty(len(mesh.polygons) * 3, np.int32)
    mesh.polygons.foreach_get("vertices", faces)
    return faces.reshape(-1, 3)


def adjacency(faces):
    """Shared-edge adjacency; no spatial bridge across nearby cloth folds."""
    result = [[] for _ in faces]
    edge_owner = {}
    for index, (a, b, c) in enumerate(faces):
        for first, second in ((a, b), (b, c), (c, a)):
            edge = (int(min(first, second)), int(max(first, second)))
            other = edge_owner.get(edge)
            if other is not None:
                result[index].append(other)
                result[other].append(index)
            else:
                edge_owner[edge] = index
    return result


def classify_trim_cloth(trim, root=ROOT):
    """Return (bool face_mask, report) validated against actual mesh provenance.

    The classifier combines real atlas variations, measured local planarity,
    coarse triangle density, and shared-edge support. Pure-red narrow convex
    folds are explicitly protected. Uncertain pure-red flat patches stay fur.
    """
    root = Path(root)
    with np.load(root / "docs" / "trim_geometry_features.npz") as stored:
        f = {key: stored[key] for key in stored.files}
    centers, normals, source_ids = surface(trim)
    if not np.array_equal(source_ids, f["source_ids"]):
        raise ValueError("Measured G1 source-face ordering does not match this mesh")
    max_center_delta = float(np.abs(centers - f["centers"]).max())
    if max_center_delta > 1e-7:
        raise ValueError("Source geometry was transformed or deformed; re-audit before using this mask")
    a, e = f["face_area"], f["max_edge"]
    v, c, rms = f["variance"], f["convex"], f["planar_rms"]
    d, n = f["cloth_distance"], f["neighbours"]
    gold, spread, rgb = f["gold_fraction"], f["color_range"], f["sampled_mean_rgb"]
    green_red = rgb[:, 1] / np.maximum(rgb[:, 0], 1e-6)
    blue_red = rgb[:, 2] / np.maximum(rgb[:, 0], 1e-6)
    pure_scarlet = ((green_red < .31) & (blue_red < .28)
                    & (spread < .055) & (gold < .01))
    convex_pure_ridge = ((c > .0015) & (v > .025) & (e < .019)
                        & (spread < .07) & (gold < .05))
    # Coarse triangle footprints agreeing with the nearest intact cloth plane
    # are useful even when a printed red patch has the same hue as fur. Signed
    # normal direction can flip on this reconstructed sheet, hence abs(dot).
    cloth_plane_supported = ((np.abs(f["body_signed_height"]) < .004)
                             & (np.abs(f["body_normal_alignment"]) > .985)
                             & (d < .026) & (a > .00006) & (e > .016))
    protected = (pure_scarlet & ~cloth_plane_supported) | convex_pure_ridge
    printed_evidence = (spread > .10) | (green_red > .34) | (gold > .10)
    # Actual ray probes found adjacent coarse side-sheet triangles whose
    # 21mm neighborhoods accidentally include the parallel inside sheet.
    # Their high RMS/convex value is not a raised fur ridge. For the side only,
    # coarse footprint + coherent normals + source print detail is a separate
    # gate; pure narrow red ridges remain protected below.
    coarse_side_sheet = ((np.abs(normals[:, 0]) > .85) & (v < .045)
                         & (a > .00010) & (e > .019) & (d < .030)
                         & ((spread > .065) | (green_red > .31) | (gold > .10)))
    # Sparse coarse triangles cannot provide a valid small-radius curvature
    # estimate. Their footprint + atlas detail provides a separate seed gate.
    coarse_printed = ((a > .00013) & (e > .022) & (d < .045)
                      & ((n < 8) | (c < .0013)) & printed_evidence)
    flat_printed = ((v < .028) & (c < .0012) & (rms < .0035)
                    & (d < .030) & (a > .000045) & printed_evidence)
    motif_patch = ((gold > .20) & (spread > .14) & (d < .032) & (e > .013))
    seeds = (coarse_printed | flat_printed | motif_patch | cloth_plane_supported
             | coarse_side_sheet) & ~protected
    mask = seeds.copy()
    links = adjacency(triangle_buffers(trim))
    eligible_growth = ((v < .045) & (c < .0018) & (rms < .0042)
                       & (d < .035) & (a > .000035)
                       & printed_evidence & ~protected)
    # One conservative shared-edge pass only. Broad geometric/color dilation
    # would leak across the wave boundary and repaint genuine trim.
    expanded = np.zeros(len(mask), np.bool_)
    for index in np.flatnonzero(eligible_growth & ~mask):
        selected_neighbors = [j for j in links[index]
                              if seeds[j] and np.dot(normals[index], normals[j]) > .97]
        if len(selected_neighbors) >= 2:
            expanded[index] = True
    mask |= expanded
    # Drop small multi-triangle clusters unsupported by a coarse cloth patch;
    # retain an isolated large triangle such as audited example 23181.
    seen = np.zeros(len(mask), np.bool_)
    component_sizes = []
    removed = 0
    for first in np.flatnonzero(mask):
        if seen[first]:
            continue
        pending, component = [int(first)], []
        seen[first] = True
        while pending:
            index = pending.pop()
            component.append(index)
            for neighbor in links[index]:
                if mask[neighbor] and not seen[neighbor]:
                    seen[neighbor] = True
                    pending.append(neighbor)
        indices = np.array(component, np.int32)
        if (len(component) < 3 and a[indices].sum() < .00032
                and not np.any(cloth_plane_supported[indices])):
            mask[indices] = False
            removed += len(indices)
        else:
            component_sizes.append(len(component))
    report = {
        "object": trim.name,
        "sourceFaces": len(mask),
        "recoveredClothFaces": int(mask.sum()),
        "retainedScarletTrimFaces": int((~mask).sum()),
        "recoveredWorldAreaM2": float(a[mask].sum()),
        "retainedWorldAreaM2": float(a[~mask].sum()),
        "coarsePrintedSeeds": int(coarse_printed.sum()),
        "flatPrintedSeeds": int(flat_printed.sum()),
        "motifSeeds": int(motif_patch.sum()),
        "matchingNearestClothPlaneSeeds": int(cloth_plane_supported.sum()),
        "coarsePrintedSideSheetSeeds": int(coarse_side_sheet.sum()),
        "protectedPureOrConvexScarletFaces": int(protected.sum()),
        "sharedEdgeGrowthFaces": int(expanded.sum()),
        "unsupportedTinyClusterFacesRemoved": removed,
        "connectedSelectedComponents": len(component_sizes),
        "largestSelectedComponentFaces": sorted(component_sizes, reverse=True)[:20],
        "maxMeasuredCenterDeltaM": max_center_delta,
        "sourceFaceOrderingExact": True,
        "examples": {str(i): {"sourceFaceId": int(source_ids[i]),
                             "recoveredAsCloth": bool(mask[i]),
                             "centerWorld": centers[i].tolist(),
                             "originalMeanSrgb": rgb[i].tolist(),
                             "pureScarletProtected": bool(protected[i])}
                     for i in (23181, 23996)},
        "limitations": [
            "Partial appearance recovery from low-resolution source texture and triangulated surface; uncertain red faces remain trim.",
            "Triangle curvature is a local estimate, not a measured physical embroidery height.",
            "Shared-edge growth is one pass with two selected neighbors and normal alignment above .97.",
            "Pure-red cloth recovery additionally requires coarse triangle area, a nearby intact cloth plane, less than 4mm signed plane offset, and normal alignment above .985. Remaining uncertain flat fur/printed cloth can leave red islands.",
            "Mask is specific to original G1 source-face IDs, triangle ordering, and normalized geometry.",
            "Fiber roots must be regenerated with the inverse face mask; this utility never silently deletes curves.",
        ],
    }
    if not mask[23181] or mask[23996]:
        raise RuntimeError("Audited flat-cloth / convex-scarlet examples lost their required protection")
    return mask.astype(np.bool_), report


def save_recovery_mask(trim, mask, root=ROOT):
    root = Path(root)
    _, _, ids = surface(trim)
    path = root / "docs" / "trim_cloth_recovery_mask.npy"
    np.save(path, mask)
    np.save(root / "docs" / "trim_cloth_recovery_source_ids.npy", ids)
    attr = trim.data.attributes.get("recovered_brocade_face")
    if attr is None:
        attr = trim.data.attributes.new("recovered_brocade_face", "BOOLEAN", "FACE")
    if attr.domain != "FACE" or attr.data_type != "BOOLEAN":
        raise ValueError("Existing recovery attribute has an incompatible type")
    attr.data.foreach_set("value", mask)
    return path


def load_recovery_mask(trim, root=ROOT):
    """Read the audited Boolean mask, rejecting source-face order mismatches."""
    root = Path(root)
    mask = np.load(root / "docs" / "trim_cloth_recovery_mask.npy")
    expected = np.load(root / "docs" / "trim_cloth_recovery_source_ids.npy")
    centers, _, ids = surface(trim)
    with np.load(root / "docs" / "trim_geometry_features.npz") as features:
        original_centers = features["centers"]
    if mask.dtype != np.bool_ or mask.shape != (len(trim.data.polygons),):
        raise ValueError("Recovery mask has an incompatible dtype or face count")
    if not np.array_equal(ids, expected) or np.max(np.abs(centers-original_centers)) > 1e-7:
        raise ValueError("Recovery mask is not valid for this object's actual provenance/geometry")
    return mask


def apply_trim_cloth_recovery(trim, mask=None, root=ROOT, texture_path=None):
    """Apply the supplied actual brocade PNG only on audited source faces.

    Returns a result with face_mask ndarray plus JSON-compatible report.
    Caller owns curve root filtering/regeneration. No curve or geometry changes.
    """
    root = Path(root)
    if mask is None:
        mask = load_recovery_mask(trim, root)
    if texture_path is None:
        texture_path = root / "textures" / "brocade_new" / "brocade_reference_synthesis.png"
    result = apply_cylindrical_brocade(trim, texture_path, .20, .18, face_mask=mask)
    save_recovery_mask(trim, mask, root)
    return {"face_mask": mask, "report": result}


def diagnostic_material(name, color):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    return material


def diagnostic_render(scene, body, trim, mask, output, camera):
    """Workbench diagnostic; green recovered cloth, red retained raised trim."""
    saved_body = [p.material_index for p in body.data.polygons]
    saved_trim = [p.material_index for p in trim.data.polygons]
    body.data.materials.append(diagnostic_material("Audit_Remaining_Cloth_Gray", (.38, .46, .51)))
    trim.data.materials.append(diagnostic_material("Audit_Retained_Trim_Red", (.70, .06, .08)))
    trim.data.materials.append(diagnostic_material("Audit_Recovered_Cloth_Green", (.04, .72, .30)))
    for p in body.data.polygons:
        p.material_index = len(body.data.materials)-1
    for index, p in enumerate(trim.data.polygons):
        p.material_index = len(trim.data.materials)-1 if mask[index] else len(trim.data.materials)-2
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.show_shadows = True
    scene.display.shading.background_type = "WORLD"
    scene.camera = camera
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    for p, index in zip(body.data.polygons, saved_body):
        p.material_index = index
    for p, index in zip(trim.data.polygons, saved_trim):
        p.material_index = index


def main():
    source = blend_path("Lion_Body_Quality_Stage.blend")
    master = blend_path("Lion_Final_Master.blend")
    hashes = {str(path): digest(path) for path in (source, master)}
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.view_layer.update()
    trim, body = bpy.data.objects["Lion_Body_Red_Trim"], bpy.data.objects["Lion_Body"]
    source_buffers_before = source_buffers(trim)
    mask, report = classify_trim_cloth(trim)
    mask_path = save_recovery_mask(trim, mask)
    report["maskPath"] = str(mask_path)
    report["sourceIdsPath"] = str(ROOT / "docs" / "trim_cloth_recovery_source_ids.npy")
    reports = ROOT / "docs" / "trim_cloth_recovery_report.json"
    reports.write_text(json.dumps(report, indent=2), encoding="utf-8")
    render_dir = ROOT / "renders" / "studies" / "trim_cloth_recovery"
    render_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.resolution_x = 960
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    camera = add_camera("TrimClothRecovery_Close_PositiveX", .19, .46, .68)
    # Geometry/material diagnostics deliberately hide curves, so old wrongly
    # seeded roots cannot conceal the classification. They are not deleted.
    hidden = []
    for obj in bpy.data.objects:
        if obj.type == "CURVE" and not obj.hide_render:
            obj.hide_render = True
            hidden.append(obj.name)
    scene.view_settings.view_transform = "AgX"
    diagnostic_render(scene, body, trim, mask, render_dir / "mask_diagnostic.png", camera)
    scene.render.engine = "BLENDER_EEVEE"
    texture = ROOT / "textures" / "brocade_new" / "brocade_reference_synthesis.png"
    report["bodyStudyMaterial"] = apply_cylindrical_brocade(body, texture, .20, .18)
    scene.camera = camera
    scene.render.filepath = str(render_dir / "before_trim_recovery.png")
    bpy.ops.render.render(write_still=True)
    report["trimStudyMaterial"] = apply_trim_cloth_recovery(trim, mask)["report"]
    scene.render.filepath = str(render_dir / "after_trim_recovery.png")
    bpy.ops.render.render(write_still=True)
    target = blend_path("Lion_Trim_Cloth_Recovery_Study.blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=True, check_existing=False)
    report.update({"studyBlend": str(target), "inputBlend": str(source),
                   "renders": str(render_dir), "curvesHiddenForDiagnostic": hidden,
                   "curvesDeleted": 0, "curveVisibilityStudyOnly": True,
                   "originalUvAndSourceIdsPreserved": source_buffers_before == source_buffers(trim),
                   "protectedInputsPreserved": all(digest(path) == value for path, value in hashes.items()),
                   "visualAcceptance": "Pending actual inspection of generated comparison images."})
    reports.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["originalUvAndSourceIdsPreserved"] or not report["protectedInputsPreserved"]:
        raise RuntimeError("Protected original UV/source data or stage/master files changed")
    print("TRIM_RECOVERY_STUDY_DONE", report["recoveredClothFaces"], str(reports), flush=True)


if __name__ == "__main__":
    main()
