"""Inspect an existing GLB in background Blender; never generate replacement geometry."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

import bmesh
import bpy
from mathutils import Vector


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects
              if obj.type in {"MESH", "CURVE", "CURVES", "SURFACE", "FONT"}
              and (obj.type != "MESH" or len(obj.data.vertices))
              for corner in obj.bound_box]
    if not points:
        return None
    minimum = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    maximum = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    return {"min": list(minimum), "max": list(maximum),
            "dimensions": list(maximum - minimum), "center": list((maximum + minimum) / 2)}


def mesh_info(mesh):
    mesh.calc_loop_triangles()
    topology = bmesh.new()
    try:
        topology.from_mesh(mesh)
        boundary = sum(edge.is_boundary for edge in topology.edges)
        non_manifold = sum(not edge.is_manifold for edge in topology.edges)
        edge_stats = {
            "non_manifold_including_boundary": non_manifold,
            "boundary": boundary,
            "non_manifold_excluding_boundary": non_manifold - boundary,
            "wire": sum(edge.is_wire for edge in topology.edges),
            "more_than_two_incident_faces": sum(len(edge.link_faces) > 2 for edge in topology.edges),
            "manifold_with_inconsistent_winding": sum(
                edge.is_manifold and not edge.is_contiguous for edge in topology.edges),
            "isolated_vertices": sum(not vertex.link_edges for vertex in topology.verts),
        }
    finally:
        topology.free()
    return {
        "data_name": mesh.name,
        "vertices": len(mesh.vertices), "edges": len(mesh.edges),
        "polygons": len(mesh.polygons), "triangles": len(mesh.loop_triangles),
        "edge_statistics": edge_stats,
        "uv_layers": [{"name": layer.name, "loops": len(layer.data),
                       "active_render": layer.active_render} for layer in mesh.uv_layers],
    }


def object_info(obj):
    result = {"name": obj.name, "type": obj.type,
              "parent": obj.parent.name if obj.parent else None,
              "matrix_world": [list(row) for row in obj.matrix_world],
              "bounding_box_world": bounds([obj]),
              "materials": [slot.material.name if slot.material else None
                            for slot in obj.material_slots],
              "modifiers": [{"name": item.name, "type": item.type} for item in obj.modifiers]}
    if obj.type == "MESH":
        result["mesh"] = mesh_info(obj.data)
    elif obj.type == "CURVE":
        result["curve"] = {"splines": len(obj.data.splines),
                           "points": sum(len(s.points) + len(s.bezier_points)
                                         for s in obj.data.splines)}
    elif obj.type == "CURVES":
        result["hair_curves"] = {"curves": len(obj.data.curves), "points": len(obj.data.points)}
    elif obj.type == "ARMATURE":
        result["armature"] = {"bones": [bone.name for bone in obj.data.bones]}
    animation = obj.animation_data
    result["animation"] = {"action": animation.action.name if animation and animation.action else None,
                           "nla_tracks": len(animation.nla_tracks) if animation else 0}
    return result


def material_info(material):
    textures = []
    if material.use_nodes and material.node_tree:
        textures = [{"node": node.name, "image": node.image.name if node.image else None,
                     "interpolation": node.interpolation, "extension": node.extension}
                    for node in material.node_tree.nodes if node.type == "TEX_IMAGE"]
    return {"name": material.name, "uses_nodes": material.use_nodes, "image_texture_nodes": textures}


def viewpoints(scene, box):
    collection = bpy.data.collections.new("Inspection_Viewpoints")
    scene.collection.children.link(collection)
    center = Vector(box["center"])
    extent = max(max(box["dimensions"]), 0.001)
    axes = {"front_minus_y": (0, -1, 0), "back_plus_y": (0, 1, 0),
            "left_minus_x": (-1, 0, 0), "right_plus_x": (1, 0, 0),
            "top_plus_z": (0, 0, 1), "bottom_minus_z": (0, 0, -1)}
    cameras = []
    for name, axis in axes.items():
        data = bpy.data.cameras.new(name)
        data.type = "ORTHO"
        data.ortho_scale = extent * 1.2
        data.clip_start = max(extent * 0.0001, 0.000001)
        data.clip_end = extent * 10 + 10
        camera = bpy.data.objects.new(name, data)
        collection.objects.link(camera)
        camera.location = center + Vector(axis) * (extent * 3 + 1)
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        cameras.append(camera)
    for index, offset in enumerate(((2, -3, 4), (-3, -1, 2), (1, 3, 3))):
        data = bpy.data.lights.new("Inspection_Area_%d" % index, "AREA")
        data.energy = 350 * extent ** 2
        data.shape = "DISK"
        data.size = extent * 2
        light = bpy.data.objects.new(data.name, data)
        collection.objects.link(light)
        light.location = center + Vector(offset) * extent
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cameras[0]
    return cameras


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--blend-output", type=Path, help="Optional native scene path; default is blender/studies/import_checks/<report-directory>.blend.")
    parser.add_argument("--render", action="store_true", help="Render six Eevee inspection PNGs.")
    parser.add_argument("--resolution", type=int, default=384, help="Square diagnostic PNG size, default 384px.")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if not 128 <= args.resolution <= 4096:
        raise ValueError("Inspection render resolution must be between 128 and 4096px.")
    source, output = resolve_project_path(args.input), resolve_project_path(args.output_dir)
    if not source.is_file():
        raise FileNotFoundError("Real input GLB does not exist: %s" % source)
    if source.suffix.lower() != ".glb":
        raise ValueError("Input must be a real .glb file.")
    with source.open("rb") as handle:
        if handle.read(4) != b"glTF":
            raise ValueError("Input does not have a GLB header.")
    blend = resolve_project_path(args.blend_output) if args.blend_output else STUDIES / "import_checks" / (output.name + ".blend")
    if blend.suffix.lower() != ".blend":
        raise ValueError("Native inspection output must use the .blend extension.")
    report_path = output / "asset_inspection.json"
    if blend.exists() or report_path.exists() or (args.render and (output / "renders").exists()):
        raise FileExistsError("Inspection output already exists; choose a fresh output directory.")
    before = digest(source)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source), import_pack_images=True)
    imported = list(bpy.data.objects)
    bpy.context.view_layer.update()
    box = bounds(imported)
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "input": {"path": str(source), "bytes": source.stat().st_size, "sha256_before": before},
        "scope": "Original imported datablocks; modifiers are listed but not applied. "
                 "World-axis camera labels do not establish the asset's semantic front. "
                 "Topology statistics alone do not establish visual fidelity, separated parts, hair, rig quality or animation acceptance.",
        "bounding_box_world": box,
        "object_type_counts": {kind: sum(obj.type == kind for obj in imported)
                               for kind in sorted({obj.type for obj in imported})},
        "objects": [object_info(obj) for obj in imported],
        "materials": [material_info(material) for material in bpy.data.materials],
        "images": [{"name": item.name, "size": list(item.size), "channels": item.channels,
                    "source": item.source, "filepath": item.filepath,
                    "packed": bool(item.packed_file), "color_space": item.colorspace_settings.name}
                   for item in bpy.data.images],
        "render": {"requested": args.render, "status": "not_requested", "files": []},
    }
    if box is None:
        raise ValueError("Imported GLB contains no inspectable visible geometry.")
    scene = bpy.context.scene
    cameras = viewpoints(scene, box)
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("Inspection_World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.12, 0.12, 0.12, 1)
    scene.world = world
    output.mkdir(parents=True, exist_ok=True)
    blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), check_existing=False)
    report["blend"] = str(blend)
    report["input"]["sha256_after"] = digest(source)
    report["input"]["preserved"] = report["input"]["sha256_after"] == before
    def save_report():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    save_report()
    if not report["input"]["preserved"]:
        raise RuntimeError("Source GLB changed during inspection.")
    if args.render:
        render_dir = output / "renders"
        render_dir.mkdir()
        report["render"]["status"] = "running"
        save_report()
        try:
            for camera in cameras:
                scene.camera = camera
                path = render_dir / (camera.name + ".png")
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                if not path.is_file() or path.stat().st_size == 0:
                    raise RuntimeError("Render output missing: %s" % path)
                report["render"]["files"].append(str(path))
                save_report()
            report["render"]["status"] = "completed_unreviewed"
        except Exception as exc:
            report["render"].update(status="failed", error=str(exc))
            save_report()
            raise
        save_report()
    print("Inspection saved: %s" % report_path)


if __name__ == "__main__":
    main()
