"""Read-only curvature/cloth-continuity probe of actual misclassified trim faces."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(ROOT / "scripts"))
from lion_material_tools import image_pixels, sample_uv_colors


def surface(obj):
    mesh = obj.data
    positions = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get("co", positions)
    positions = positions.reshape(-1, 3)
    matrix = np.asarray(obj.matrix_world, np.float64)
    world = positions @ matrix[:3, :3].T + matrix[:3, 3]
    faces = np.empty(len(mesh.polygons) * 3, np.int32)
    mesh.polygons.foreach_get("vertices", faces)
    faces = faces.reshape(-1, 3)
    centers = world[faces].mean(axis=1)
    normals = np.empty(len(mesh.loops) * 3, np.float32)
    mesh.corner_normals.foreach_get("vector", normals)
    normals = normals.reshape(-1, 3, 3).mean(axis=1)
    normals = normals @ np.linalg.inv(matrix[:3, :3])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-8)
    ids = np.empty(len(mesh.polygons), np.int32)
    mesh.attributes["source_face_index"].data.foreach_get("value", ids)
    return centers, normals, ids


def main():
    bpy.ops.wm.open_mainfile(filepath=str(blend_path("Lion_Body_Quality_Stage.blend")))
    bpy.context.view_layer.update()
    trim = bpy.data.objects["Lion_Body_Red_Trim"]
    body = bpy.data.objects["Lion_Body"]
    centers, normals, source_ids = surface(trim)
    mesh = trim.data
    coordinates = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get("co", coordinates)
    coordinates = coordinates.reshape(-1, 3)
    matrix = np.asarray(trim.matrix_world, np.float64)
    world = coordinates @ matrix[:3, :3].T + matrix[:3, 3]
    faces = np.empty(len(mesh.polygons) * 3, np.int32)
    mesh.polygons.foreach_get("vertices", faces)
    faces = faces.reshape(-1, 3)
    triangle_points = world[faces]
    edges = triangle_points[:, [1, 2, 0]] - triangle_points
    max_edge = np.linalg.norm(edges, axis=2).max(axis=1)
    areas = np.linalg.norm(np.cross(edges[:, 0], -edges[:, 2]), axis=1) * .5
    uv = np.empty(len(mesh.loops) * 2, np.float32)
    mesh.uv_layers[0].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 3, 2)
    barycentric = np.array([(i / 6, j / 6, 1 - (i+j)/6)
                            for i in range(1, 5) for j in range(1, 6-i)], np.float32)
    atlas = bpy.data.images.load(str(ROOT / "textures" / "generated" / "original_basecolor_atlas.png"), check_existing=False)
    sampled = sample_uv_colors(image_pixels(atlas), np.einsum("nc,fcx->fnx", barycentric, uv))
    r, g, b = np.moveaxis(sampled, -1, 0)
    gold = (g - b > .075) & (g / np.maximum(r, 1e-6) > .54) & (r > .3)
    gold_fraction = gold.mean(axis=1)
    color_range = np.ptp(sampled, axis=1).max(axis=1)
    body_centers, body_normals, _ = surface(body)
    total_centers = np.concatenate((centers, body_centers))
    total_normals = np.concatenate((normals, body_normals))
    neighbourhood = KDTree(len(total_centers))
    for index, center in enumerate(total_centers):
        neighbourhood.insert(Vector(center), index)
    neighbourhood.balance()
    body_tree = KDTree(len(body_centers))
    for index, center in enumerate(body_centers):
        body_tree.insert(Vector(center), index)
    body_tree.balance()
    variance = np.zeros(len(centers), np.float32)
    convex = np.zeros(len(centers), np.float32)
    planar_rms = np.zeros(len(centers), np.float32)
    cloth_distance = np.zeros(len(centers), np.float32)
    neighbours = np.zeros(len(centers), np.int32)
    body_signed_height = np.zeros(len(centers), np.float32)
    body_normal_alignment = np.zeros(len(centers), np.float32)
    for index, (center, normal) in enumerate(zip(centers, normals)):
        nearby = neighbourhood.find_range(Vector(center), .021)
        indices = np.array([item[1] for item in nearby], np.int32)
        offsets = total_centers[indices] - center
        distances = np.linalg.norm(offsets, axis=1)
        alignment = total_normals[indices] @ normal
        valid = (distances > .003) & (alignment > .45)
        indices, offsets, alignment = indices[valid], offsets[valid], alignment[valid]
        neighbours[index] = len(indices)
        if len(indices) >= 5:
            signed_height = offsets @ normal
            variance[index] = np.median(1 - alignment)
            convex[index] = -np.median(signed_height)
            planar_rms[index] = np.sqrt(np.mean(np.square(signed_height)))
        else:
            variance[index] = 1
            convex[index] = 1
            planar_rms[index] = 1
        _, body_index, distance = body_tree.find(Vector(center))
        cloth_distance[index] = distance
        body_signed_height[index] = np.dot(center-body_centers[body_index], body_normals[body_index])
        body_normal_alignment[index] = np.dot(normal, body_normals[body_index])
        if index % 6000 == 0:
            print("Trim geometry probe", index, len(centers), flush=True)
    npz = ROOT / "docs" / "trim_geometry_features.npz"
    np.savez_compressed(npz, centers=centers, normals=normals, source_ids=source_ids,
                        variance=variance, convex=convex, planar_rms=planar_rms,
                        cloth_distance=cloth_distance, neighbours=neighbours,
                        face_area=areas, max_edge=max_edge, gold_fraction=gold_fraction,
                        body_signed_height=body_signed_height, body_normal_alignment=body_normal_alignment,
                        color_range=color_range, sampled_mean_rgb=sampled.mean(axis=1))
    examples = {}
    for index in (23181, 23996):
        examples[str(index)] = {"source_id": int(source_ids[index]),
                               "center": centers[index].tolist(), "normal": normals[index].tolist(),
                               "median_normal_variance": float(variance[index]),
                               "convex_height_m": float(convex[index]),
                               "plane_rms_m": float(planar_rms[index]),
                               "distance_to_Body_m": float(cloth_distance[index]),
                               "area_m2": float(areas[index]), "max_edge_m": float(max_edge[index]),
                               "gold_fraction": float(gold_fraction[index]),
                               "color_range": float(color_range[index]),
                               "sampled_mean_rgb": sampled[index].mean(axis=0).tolist(),
                               "neighbours": int(neighbours[index])}
        examples[str(index)]["nearest_body_signed_height_m"] = float(body_signed_height[index])
        examples[str(index)]["nearest_body_normal_alignment"] = float(body_normal_alignment[index])
    probes = []
    for curvature in (.0008, .0012, .0016, .0022):
        selected = ((convex < curvature) & (variance < .028)
                    & (planar_rms < .0035) & (cloth_distance < .030))
        probes.append({"convex_threshold_m": curvature,
                       "selected_faces": int(selected.sum()),
                       "examples_selected": {str(index): bool(selected[index]) for index in (23181, 23996)}})
    report = {"input": str(blend_path("Lion_Body_Quality_Stage.blend")),
              "trim_faces": len(centers), "body_faces": len(body_centers),
              "neighbour_radius_m": .021, "examples": examples, "probes": probes,
              "feature_file": str(npz),
              "quantiles": {key: np.quantile(value, [0, .1, .25, .5, .75, .9, 1]).tolist()
                            for key, value in (("variance", variance), ("convex_m", convex),
                                               ("plane_rms_m", planar_rms), ("cloth_distance_m", cloth_distance))}}
    report["face_area_quantiles_m2"] = np.quantile(areas, [0, .1, .25, .5, .75, .9, 1]).tolist()
    report["max_edge_quantiles_m"] = np.quantile(max_edge, [0, .1, .25, .5, .75, .9, 1]).tolist()
    (ROOT / "docs" / "trim_geometry_probe.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
