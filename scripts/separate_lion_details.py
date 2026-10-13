"""Conservative UV/color/position detail partition of the real Lux3D surface.

Execute in Blender. This separates existing source triangles, not reconstructed
fur/embroidery meshes. The callable takes the current part meshes and original
atlas pixels. The source mesh remains complete once all output pieces are shown.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(ROOT / "scripts"))
from lion_material_tools import image_pixels, find_basecolor_image, sample_uv_colors

DETAILS = {
    "Brow_L": {"parent": "Head", "pivot": (.18, -.48, .82), "color": (1.0, .69, .04, 1)},
    "Brow_R": {"parent": "Head", "pivot": (-.18, -.48, .82), "color": (1.0, .69, .04, 1)},
    "Nose": {"parent": "Head", "pivot": (0, -.735, .635), "color": (.10, .88, .33, 1)},
    "Body_Red_Trim": {"parent": "Body", "pivot": (0, .12, .57), "color": (.89, .10, .12, 1)},
}


def mesh_buffers(mesh):
    if any(len(face.vertices) != 3 for face in mesh.polygons):
        raise ValueError("Detail partition expects source triangles")
    vertices = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", vertices)
    faces = np.empty(len(mesh.polygons) * 3, dtype=np.int32)
    mesh.polygons.foreach_get("vertices", faces)
    uvs = {}
    for layer in mesh.uv_layers:
        array = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        layer.data.foreach_get("uv", array)
        uvs[layer.name] = array.reshape(-1, 2)
    corners = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", corners)
    indices = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("material_index", indices)
    smooth = np.empty(len(mesh.polygons), dtype=bool)
    mesh.polygons.foreach_get("use_smooth", smooth)
    provenance = mesh.attributes.get("source_face_index")
    if provenance is None:
        raise ValueError("Missing source_face_index provenance on %s" % mesh.name)
    source_ids = np.empty(len(mesh.polygons), dtype=np.int32)
    provenance.data.foreach_get("value", source_ids)
    return {"vertices": vertices.reshape(-1, 3), "faces": faces.reshape(-1, 3),
            "uvs": uvs, "normals": corners.reshape(-1, 3), "material_indices": indices,
            "smooth": smooth, "source_ids": source_ids, "materials": list(mesh.materials)}


def partition_mesh(name, buffer, selected):
    faces = buffer["faces"][selected]
    used = np.unique(faces)
    mapping = np.full(len(buffer["vertices"]), -1, dtype=np.int32)
    mapping[used] = np.arange(len(used))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(buffer["vertices"][used].tolist(), [], mapping[faces].tolist())
    mesh.update()
    for material in buffer["materials"]:
        mesh.materials.append(material)
    mesh.polygons.foreach_set("material_index", buffer["material_indices"][selected])
    mesh.polygons.foreach_set("use_smooth", buffer["smooth"][selected])
    loops = (selected[:, None] * 3 + np.arange(3)).reshape(-1)
    for layer_name, uvs in buffer["uvs"].items():
        layer = mesh.uv_layers.new(name=layer_name)
        layer.data.foreach_set("uv", uvs[loops].ravel())
        actual = np.empty(len(loops) * 2, dtype=np.float32)
        layer.data.foreach_get("uv", actual)
        if not np.array_equal(actual, uvs[loops].ravel()):
            raise RuntimeError("UV values changed during detail partition")
    mesh.normals_split_custom_set(buffer["normals"][loops].tolist())
    # Blender compresses native custom split normals in the new loop-fan basis.
    # Preserve source vectors independently as exact float32 corner attributes.
    normals_attribute = mesh.attributes.new(name="source_corner_normal", type="FLOAT_VECTOR", domain="CORNER")
    normals_attribute.data.foreach_set("vector", buffer["normals"][loops].ravel())
    saved_normals = np.empty(len(loops) * 3, dtype=np.float32)
    normals_attribute.data.foreach_get("vector", saved_normals)
    if not np.array_equal(saved_normals, buffer["normals"][loops].ravel()):
        raise RuntimeError("Exact source corner normal attribute changed")
    attribute = mesh.attributes.new(name="source_face_index", type="INT", domain="FACE")
    attribute.data.foreach_set("value", buffer["source_ids"][selected])
    return mesh


def pure_red(rgb):
    red = np.maximum(rgb[..., 0], 1e-6)
    return ((red > .35) & (rgb[..., 1] / red < .65)
            & (rgb[..., 2] / red < .60) & (red - rgb[..., 1] > .14))


def substantial_components(faces, mask, minimum_faces):
    """Reject isolated red pigment speckles; connectivity alone is not anatomy."""
    selected = np.flatnonzero(mask)
    parent = np.arange(len(selected))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    edges = {}
    for local_index, face_index in enumerate(selected):
        a, b, c = faces[face_index]
        for first, second in ((a, b), (b, c), (c, a)):
            edge = (int(min(first, second)), int(max(first, second)))
            if edge in edges:
                first_root, second_root = find(local_index), find(edges[edge])
                if first_root != second_root:
                    parent[first_root] = second_root
            else:
                edges[edge] = local_index
    roots = np.array([find(index) for index in range(len(selected))], dtype=np.int32)
    counts = Counter(roots)
    result = np.zeros(len(faces), dtype=bool)
    result[selected] = np.array([counts[root] >= minimum_faces for root in roots])
    return result


def face_selection(obj, buffer, pixels):
    matrix = np.array(obj.matrix_world, dtype=np.float64)
    homogeneous = np.column_stack((buffer["vertices"], np.ones(len(buffer["vertices"]))))
    world = (homogeneous @ matrix.T)[:, :3]
    centers = world[buffer["faces"]].mean(axis=1)
    corner_uvs = next(iter(buffer["uvs"].values())).reshape(-1, 3, 2)
    center_rgb = sample_uv_colors(pixels, corner_uvs.mean(axis=1))
    # Sample within each triangle, not exact corners at atlas-island borders.
    inside_uvs = corner_uvs * .65 + corner_uvs.mean(axis=1)[:, None, :] * .35
    inside_rgb = sample_uv_colors(pixels, inside_uvs)
    red = pure_red(center_rgb) & (pure_red(inside_rgb).sum(axis=1) >= 2)
    x, y, z = centers.T
    labels = np.full(len(centers), "remaining", dtype="U32")
    if obj.name == "Lion_Head":
        # Brow ridges are above the eye-white regions and in front of the skull.
        brow = (red & (np.abs(x) > .050) & (np.abs(x) < .325)
                & (y < -.425) & (y > -.665) & (z > .725) & (z < .915))
        brow = substantial_components(buffer["faces"], brow, 35)
        labels[brow & (x >= 0)] = "Brow_L"
        labels[brow & (x < 0)] = "Brow_R"
        # A small central protruding nose patch; preserve all adjacent eye/muzzle rings.
        nose = ((np.abs(x) < .041) & (y < -.715)
                & (z > .602) & (z < .668))
        labels[nose] = "Nose"
    elif obj.name == "Lion_Body":
        # Restrict to the draped torso. No front neck, underside, limbs or tail base.
        trim = (red & (y > -.255) & (y < .555)
                & (z > .320) & (z < .785)
                & ((np.abs(x) > .155) | (z > .625)))
        trim = substantial_components(buffer["faces"], trim, 140)
        labels[trim] = "Body_Red_Trim"
    return labels, world, centers, center_rgb


def snapshot(meshes):
    records = {}
    for obj in meshes:
        if obj.type != "MESH":
            continue
        buffer = mesh_buffers(obj.data)
        matrix = np.array(obj.matrix_world, dtype=np.float64)
        homogeneous = np.column_stack((buffer["vertices"], np.ones(len(buffer["vertices"]))))
        world = (homogeneous @ matrix.T)[:, :3]
        triangles = world[buffer["faces"]]
        uvs = next(iter(buffer["uvs"].values())).reshape(-1, 3, 2)
        normals = buffer["normals"].reshape(-1, 3, 3)
        for index, source_id in enumerate(buffer["source_ids"]):
            if int(source_id) in records:
                raise RuntimeError("Duplicate original source face ID")
            records[int(source_id)] = (triangles[index], uvs[index], normals[index])
    return records


def separate_details(meshes, pixels):
    """Split named detail triangles; return mesh_objects/new_objects/report.

    Input is normalized to height 1m, front -Y, L=+X. Pixel RGB is original atlas
    sRGB, bottom-left origin. The two caller-owned Head/Body objects retain their
    names and parent pivots. New details inherit source world transforms and are
    parented to new functional pivots below Pivot_Head or Pivot_Body.
    """
    meshes = list(meshes)
    bpy.context.view_layer.update()
    before = snapshot(meshes)
    created = []
    reports = []
    for obj in list(meshes):
        if obj.name not in {"Lion_Head", "Lion_Body"}:
            continue
        original_mesh = obj.data
        buffer = mesh_buffers(original_mesh)
        labels, world, centers, rgb = face_selection(obj, buffer, pixels)
        groups = {label: np.flatnonzero(labels == label) for label in DETAILS
                  if np.any(labels == label)}
        # Very small accidental selections stay in their mother mesh.
        groups = {label: selected for label, selected in groups.items() if len(selected) >= 30}
        if not groups:
            continue
        selected_all = np.concatenate(list(groups.values()))
        remaining = np.setdiff1d(np.arange(len(labels)), selected_all)
        matrix_world = obj.matrix_world.copy()
        for label, selected in groups.items():
            definition = DETAILS[label]
            parent = bpy.data.objects.get("Pivot_" + definition["parent"])
            if parent is None:
                raise ValueError("Required mother pivot missing")
            pivot = bpy.data.objects.new("Pivot_" + label, None)
            obj.users_collection[0].objects.link(pivot)
            pivot.empty_display_type = "PLAIN_AXES"
            pivot.empty_display_size = .025
            pivot.parent = parent
            pivot.matrix_world.translation = Vector(definition["pivot"])
            pivot["pivot_status"] = "Estimated editing pivot; no validated deformation joint"
            bpy.context.view_layer.update()
            detail = bpy.data.objects.new("Lion_" + label,
                                          partition_mesh("Lion_" + label + "_Mesh", buffer, selected))
            obj.users_collection[0].objects.link(detail)
            detail.parent = pivot
            detail.matrix_world = matrix_world
            detail.color = definition["color"]
            detail["source_parent_part"] = obj.name
            detail["part_selection_method"] = "Existing source triangles selected by actual UV color and conservative world-coordinate bounds"
            detail["rigging_status"] = "Open uncapped appearance partition; not reconstructed anatomical topology"
            positions = world[np.unique(buffer["faces"][selected])]
            reports.append({"name": detail.name, "source_part": obj.name,
                            "triangles": len(selected), "pivot": pivot.name,
                            "parent_pivot": parent.name,
                            "bbox": {"min": positions.min(axis=0).tolist(),
                                     "max": positions.max(axis=0).tolist()},
                            "mean_srgb": rgb[selected].mean(axis=0).tolist()})
            created.append(detail)
        obj.data = partition_mesh(obj.name + "_Remaining_Mesh", buffer, remaining)
        if not original_mesh.users:
            bpy.data.meshes.remove(original_mesh)
        reports.append({"name": obj.name, "status": "mother surface after removal",
                        "triangles": len(remaining)})
    bpy.context.view_layer.update()
    all_meshes = meshes + created
    after = snapshot(all_meshes)
    same_ids = set(before) == set(after)
    positions_exact = True
    uvs_exact = True
    max_position_delta = 0.0
    max_normal_delta = 0.0
    max_normal_angle = 0.0
    for source_id, (positions, uvs, normals) in before.items():
        actual_positions, actual_uvs, actual_normals = after[source_id]
        error = float(np.abs(positions - actual_positions).max())
        max_position_delta = max(max_position_delta, error)
        positions_exact &= error < 1e-7
        uvs_exact &= np.array_equal(uvs, actual_uvs)
        max_normal_delta = max(max_normal_delta, float(np.abs(normals - actual_normals).max()))
        cosine = np.sum(normals * actual_normals, axis=1) / np.maximum(
            np.linalg.norm(normals, axis=1) * np.linalg.norm(actual_normals, axis=1), 1e-8)
        angle = float(np.degrees(np.arccos(np.clip(cosine, -1, 1))).max())
        max_normal_angle = max(max_normal_angle, angle)
    report = {
        "parts": reports,
        "face_conservation": {"input_triangles": len(before), "output_triangles": len(after),
                              "every_input_source_face_present_once": same_ids},
        "positions_preserved_within_1e_7": positions_exact,
        "max_world_position_delta_m": max_position_delta,
        "uv_loop_values_exactly_preserved": uvs_exact,
        "max_corner_normal_delta": max_normal_delta,
        "max_corner_normal_angle_degrees": max_normal_angle,
        "source_corner_normal_float32_attribute_exactly_preserved": True,
        "selection": "Actual original atlas RGB centroid and 3 in-triangle samples, plus normalized world coordinates",
        "component_filter": "Body red face components smaller than 140 shared-edge-connected triangles and brow red components smaller than 35 triangles remain in their mother surfaces",
        "limitations": [
            "These are conservative source-surface appearance regions, not complete or watertight anatomical components.",
            "Color may confuse red embroidery with fur; torso selection excludes gold-colored pixels but cannot prove every selected face is fur.",
            "Brow selections exclude white eye rings and central gold forehead but do not restore complete brow attachment loops.",
            "Only the small central protruding nose surface is isolated; neighbouring painted ornaments remain in Head.",
            "Uncapped boundaries remain and require retopology before deforming the detail independently.",
            "Native custom normals are re-encoded in Blender's changed loop-fan basis; source normals remain exact in source_corner_normal CORNER FLOAT_VECTOR attributes, and native shading error is measured separately.",
        ],
    }
    if not same_ids or len(before) != len(after) or not positions_exact or not uvs_exact:
        raise RuntimeError("Detail partition changed source face/position/UV conservation")
    if max_normal_delta > .01:
        raise RuntimeError("Source corner normals changed beyond Blender quantization tolerance: %.9f" % max_normal_delta)
    return {"mesh_objects": all_meshes, "new_objects": created, "report": report}


def render_diagnostics(scene, meshes, output):
    output.mkdir(parents=True, exist_ok=True)
    for obj in meshes:
        label = obj.name.removeprefix("Lion_")
        obj.color = DETAILS[label]["color"] if label in DETAILS else (.30, .38, .45, 1)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.show_shadows = True
    scene.display.shading.background_type = "WORLD"
    scene.view_settings.view_transform = "Standard"
    viewpoints = [("front", (0, -.53, .5), (0, -1, 0), 1.82),
                  ("side", (0, 0, .5), (-1, 0, 0), 1.82),
                  ("head_front_close", (0, -.52, .74), (0, -1, 0), .83),
                  ("body_side_close", (0, .12, .52), (-1, 0, 0), 1.05)]
    collection = bpy.data.collections.new("Detail_Diagnostic_Cameras")
    scene.collection.children.link(collection)
    paths = []
    for name, target, axis, scale in viewpoints:
        data = bpy.data.cameras.new("Detail_" + name)
        data.type = "ORTHO"
        data.ortho_scale = scale
        camera = bpy.data.objects.new(data.name, data)
        collection.objects.link(camera)
        target = Vector(target)
        camera.location = target + Vector(axis) * 4
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = camera
        path = output / (name + ".png")
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        paths.append(str(path))
    collection.hide_viewport = True
    scene.render.engine = "BLENDER_EEVEE"
    return paths


def main():
    source = blend_path("Lion_Parts_Working.blend")
    before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("Lion_")]
    material = next(obj for obj in meshes if obj.name == "Lion_Head").data.materials[0]
    pixels = image_pixels(find_basecolor_image(material))
    result = separate_details(meshes, pixels)
    report = result["report"]
    report["diagnostic_renders"] = render_diagnostics(bpy.context.scene, result["mesh_objects"], ROOT / "docs" / "detail_parts_diagnostics")
    report["diagnostic_palette"] = {"remaining": "gray blue", "brows": "yellow", "nose": "green", "body red trim": "red"}
    report["diagnostic_review"] = "pending actual image inspection"
    output = blend_path("Lion_Detailed_Parts.blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    report["blend"] = str(output)
    report["source_blend"] = str(source)
    report["source_blend_preserved"] = before_hash == hashlib.sha256(source.read_bytes()).hexdigest()
    (ROOT / "docs" / "detail_parts_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "face_conservation": report["face_conservation"],
                      "details": [obj.name for obj in result["new_objects"]]}))


if __name__ == "__main__":
    main()
