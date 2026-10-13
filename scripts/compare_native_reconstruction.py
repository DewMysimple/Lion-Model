"""Read-only native reconstruction proof; run with Blender 5.0.x.

Two real files, with optional portable baseline signature:
  blender --background --factory-startup --python-exit-code 1 --python this.py --
    --baseline baseline.blend --rebuilt rebuilt.blend --report comparison.json
    --write-baseline-signature baseline_signature.json

Capture without a second native file:
  ... -- --capture baseline.blend --signature baseline_signature.json

Compare a rebuilt file against the portable initial-model signature:
  ... -- --expected-signature baseline_signature.json --rebuilt rebuilt.blend
    --report comparison.json

Neither input .blend is saved. Source/curve/shader data compare exactly. Primitive
storage permutations need canonical proof; only generated smooth normals and
tooth UV interpolation admit the disclosed float32 one-spacing roundoff budget.
Decoded pixels establish image equivalence when container bytes differ. This
utility proves the chosen baseline recipe, not future modeling quality. Update
the reference deliberately when authorized model/source changes are accepted.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import zlib

import bpy
import numpy as np


SCHEMA = "lion-project.native-signature/v1"
SCOPE = {
    "included": [
        "Named Lion_Root descendants, object types, hierarchy, local/world/parent-inverse matrices and visibility",
        "All asset meshes: coordinates, edges, loop topology, polygon material/smooth flags, UVs, supported attributes and evaluated corner normals",
        "All native Curve splines: settings, ordered control points, handles, radii, tilt, weights and handle types",
        "Asset modifiers and constraints: supported RNA values and named ID references",
        "Used materials: shader nodes/default values/links and supported node properties; semantic material-slot bindings",
        "Used images: decoded pixel hashes, size/color-space/alpha settings and separate packed-container byte hashes",
    ],
    "excluded": [
        "Scene lighting, cameras, render/view settings and objects outside Lion_Root",
        "Unused datablocks, node layout/UI labels, object selection and mesh .select_*/.uv_select_* attributes",
        "File paths, save timestamps, source file byte identity and nonsemantic run/path custom metadata",
        "Material/image datablock names; bindings are compared by actual shader and pixel content",
    ],
    "comparison": "Exact geometry/source/shader hashes with proven edge/polygon storage permutations. Only derived normals of generated meshes without custom normals and eleven generated tooth UVs receive one float32 unit-scale spacing (2^-23) after exact topology/coordinate correspondence. Source UVs/custom normals and all curves remain exact. Codec differences require identical decoded pixels/settings.",
}
UI_PROPERTIES = {
    "rna_type", "name", "name_full", "label", "location", "width", "height", "dimensions",
    "select", "hide", "show_options", "show_preview", "show_texture", "use_custom_color",
    "parent", "id_data", "is_property_set", "is_property_readonly",
    "show_expanded", "is_override_data", "is_valid", "error_location", "error_rotation",
    "show_viewport", "show_render", "show_in_editmode", "show_on_cage",
}
CURVE_PROPERTIES = (
    "dimensions", "resolution_u", "resolution_v", "render_resolution_u", "render_resolution_v",
    "twist_mode", "twist_smooth", "fill_mode", "bevel_depth", "bevel_resolution",
    "bevel_mode", "bevel_factor_start", "bevel_factor_end", "bevel_factor_mapping_start",
    "bevel_factor_mapping_end", "use_fill_caps", "extrude", "offset", "use_radius",
    "use_path", "path_duration", "use_path_follow", "use_stretch", "use_deform_bounds",
)
SPLINE_PROPERTIES = (
    "type", "use_cyclic_u", "use_cyclic_v", "resolution_u", "resolution_v", "order_u", "order_v",
    "use_endpoint_u", "use_endpoint_v", "use_bezier_u", "use_bezier_v",
    "radius_interpolation", "tilt_interpolation",
)
SOURCE_PROPERTIES = (
    "fiber_emitter", "source_asset", "source_part", "decorative_curve_export",
    "rotation_limits_degrees", "rotation_limits_scope",
)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def simple(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Nonfinite native scalar encountered")
        return value
    try:
        return [simple(item) for item in value]
    except TypeError:
        raise TypeError(type(value).__name__)


class Capture:
    def __init__(self):
        self.arrays = {}
        self.array_records = {}
        self.material_cache = {}
        self.materials = {}
        self.material_names = {}
        self.image_cache = {}
        self.images = {}
        self.image_codecs = {}
        self.decoded_cache = {}
        self.warnings = []
        self.unsupported = []
        self.reordering_proofs = {}
        self.roundoff_fields = {}

    def array(self, key, values):
        data = np.ascontiguousarray(values)
        if data.dtype.kind == "f" and not np.isfinite(data).all():
            raise ValueError("Nonfinite data in " + key)
        record = {"dtype": data.dtype.str, "shape": list(data.shape), "sha256": hashlib.sha256(data.tobytes()).hexdigest()}
        if data.size:
            record["min"] = simple(data.min().item())
            record["max"] = simple(data.max().item())
        self.arrays[key] = data
        self.array_records[key] = record
        return record

    def foreach(self, key, collection, property_name, width=1, dtype=np.float32):
        data = np.empty((len(collection), width), dtype=dtype) if width > 1 else np.empty(len(collection), dtype=dtype)
        if data.size:
            collection.foreach_get(property_name, data.reshape(-1))
        self.array(key, data)

    def rna(self, item, context, *, exclude=(), depth=0):
        if item is None:
            return None
        result = {}
        for prop in item.bl_rna.properties:
            name = prop.identifier
            if name in UI_PROPERTIES or name in exclude or name.startswith("bl_"):
                continue
            try:
                value = getattr(item, name)
                if prop.type in {"BOOLEAN", "INT", "FLOAT", "STRING", "ENUM"}:
                    result[name] = simple(value)
                elif prop.type == "POINTER":
                    if value is None:
                        result[name] = None
                    elif isinstance(value, bpy.types.ID):
                        result[name] = {"id_type": value.bl_rna.identifier, "name": value.name}
                    elif depth < 5:
                        result[name] = self.rna(value, context + "/" + name, depth=depth + 1)
                    else:
                        self.unsupported.append(context + "/" + name + ": pointer recursion limit")
                elif prop.type == "COLLECTION" and name not in {"inputs", "outputs", "internal_links"}:
                    if depth < 5:
                        result[name] = [self.rna(entry, context + "/" + name, depth=depth + 1) for entry in value]
                    else:
                        self.unsupported.append(context + "/" + name + ": collection recursion limit")
            except (AttributeError, TypeError, RuntimeError) as error:
                self.unsupported.append(context + "/" + name + ": " + type(error).__name__)
        return result

    def image(self, image):
        cached = self.image_cache.get(image.as_pointer())
        if cached:
            return cached
        packed = image.packed_file
        packed_hash = hashlib.sha256(bytes(packed.data)).hexdigest() if packed else None
        size = list(image.size)
        cache_key = (packed_hash, tuple(size), image.colorspace_settings.name)
        decoded = self.decoded_cache.get(cache_key) if packed_hash else None
        if decoded is None:
            pixels = np.empty(len(image.pixels), np.float32)
            image.pixels.foreach_get(pixels)
            if not pixels.size or not np.isfinite(pixels).all():
                raise ValueError("Image has missing/nonfinite decoded pixels: " + image.name)
            decoded = {"pixels": pixels, "sha256": hashlib.sha256(pixels.tobytes()).hexdigest()}
            if packed_hash:
                self.decoded_cache[cache_key] = decoded
        record = {
            "size": size, "channels": image.channels, "pixel_count": int(decoded["pixels"].size),
            "pixel_sha256": decoded["sha256"], "colorspace": image.colorspace_settings.name,
            "alpha_mode": image.alpha_mode, "source": image.source,
        }
        identity = json_hash(record)
        self.images[identity] = record
        self.arrays["image/" + identity + "/pixels"] = decoded["pixels"]
        self.image_codecs.setdefault(identity, [])
        self.image_codecs[identity].append({"name": image.name, "packed": bool(packed), "packed_byte_sha256": packed_hash})
        if not packed:
            self.warnings.append("Used image is not packed: " + image.name)
        self.image_cache[image.as_pointer()] = identity
        return identity

    def tree(self, tree, context, active_trees=()):
        if tree is None:
            return None
        if tree.as_pointer() in active_trees:
            raise ValueError("Recursive shader group in " + context)
        active_trees = (*active_trees, tree.as_pointer())
        ordered = list(tree.nodes)
        node_ids = {node.as_pointer(): index for index, node in enumerate(ordered)}
        nodes = []
        for index, node in enumerate(ordered):
            properties = self.rna(node, context + "/node" + str(index), exclude={"image", "node_tree", "texture_mapping", "color_mapping", "color"})
            # Shader IDs/data are handled by content instead of workstation paths
            # or generated datablock names.
            properties.pop("texture", None)
            record = {"type": node.bl_idname, "properties": properties, "inputs": [], "outputs": []}
            if hasattr(node, "image"):
                record["image"] = self.image(node.image) if node.image else None
            if hasattr(node, "node_tree"):
                record["group"] = self.tree(node.node_tree, context + "/group" + str(index), active_trees)
            for name in ("texture_mapping", "color_mapping"):
                if hasattr(node, name):
                    record[name] = self.rna(getattr(node, name), context + "/" + name)
            for direction in ("inputs", "outputs"):
                for socket in getattr(node, direction):
                    default = simple(socket.default_value) if hasattr(socket, "default_value") else None
                    record[direction].append({"type": socket.bl_idname, "identifier": socket.identifier, "default": default})
            nodes.append(record)
        links = sorted((node_ids[link.from_node.as_pointer()], list(link.from_node.outputs).index(link.from_socket),
                        node_ids[link.to_node.as_pointer()], list(link.to_node.inputs).index(link.to_socket),
                        bool(link.is_muted)) for link in tree.links)
        return {"nodes": nodes, "links": links}

    def material(self, material):
        if material is None:
            return None
        cached = self.material_cache.get(material.as_pointer())
        if cached:
            return cached
        settings = {}
        for name in ("use_nodes", "diffuse_color", "metallic", "roughness", "surface_render_method",
                     "use_backface_culling", "use_backface_culling_shadow", "use_backface_culling_lightprobe_volume",
                     "use_transparency_overlap", "use_transparent_shadow", "use_raytrace_refraction",
                     "thickness_mode", "refraction_depth", "alpha_threshold"):
            if hasattr(material, name):
                settings[name] = simple(getattr(material, name))
        record = {"settings": settings, "tree": self.tree(material.node_tree, "material/" + material.name)}
        identity = json_hash(record)
        self.materials[identity] = record
        self.material_names.setdefault(identity, []).append(material.name)
        self.material_cache[material.as_pointer()] = identity
        return identity

    def mesh(self, obj):
        mesh = obj.data
        prefix = "object/" + obj.name + "/mesh/"
        self.foreach(prefix + "coordinates", mesh.vertices, "co", 3)
        self.foreach(prefix + "edges", mesh.edges, "vertices", 2, np.int32)
        self.foreach(prefix + "loop_vertices", mesh.loops, "vertex_index", dtype=np.int32)
        self.foreach(prefix + "loop_edges", mesh.loops, "edge_index", dtype=np.int32)
        for name, dtype in (("loop_start", np.int32), ("loop_total", np.int32), ("material_index", np.int32), ("use_smooth", np.bool_)):
            self.foreach(prefix + "polygons_" + name, mesh.polygons, name, dtype=dtype)
        uv_names = []
        for layer in mesh.uv_layers:
            uv_names.append(layer.name)
            self.foreach(prefix + "uv/" + layer.name, layer.data, "uv", 2)
        attr_names = []
        attr_types = {
            "FLOAT": ("value", 1, np.float32), "INT": ("value", 1, np.int32),
            "BOOLEAN": ("value", 1, np.bool_), "FLOAT_VECTOR": ("vector", 3, np.float32),
            "FLOAT2": ("vector", 2, np.float32), "FLOAT_COLOR": ("color", 4, np.float32),
            "BYTE_COLOR": ("color", 4, np.float32), "INT32_2D": ("value", 2, np.int32),
            "INT16_2D": ("value", 2, np.int32),
        }
        for attr in mesh.attributes:
            if attr.name.startswith((".select_", ".uv_select_")):
                continue
            attr_names.append({"name": attr.name, "domain": attr.domain, "type": attr.data_type})
            if attr.data_type in attr_types:
                field, width, dtype = attr_types[attr.data_type]
                self.foreach(prefix + "attribute/" + attr.name, attr.data, field, width, dtype)
            else:
                self.unsupported.append(prefix + "attribute/" + attr.name + ": " + attr.data_type)
        if hasattr(mesh, "corner_normals"):
            self.foreach(prefix + "corner_normals", mesh.corner_normals, "vector", 3)
        self.canonical_mesh(prefix, mesh, attr_names, uv_names)
        return {"vertices": len(mesh.vertices), "edges": len(mesh.edges), "loops": len(mesh.loops),
                "polygons": len(mesh.polygons), "uv_names": uv_names, "attributes": attr_names,
                "has_custom_normals": mesh.has_custom_normals,
                "active_uv_index": mesh.uv_layers.active_index,
                "render_uv_names": [layer.name for layer in mesh.uv_layers if layer.active_render]}

    def canonical_mesh(self, prefix, mesh, attributes, uv_names):
        """Prove full mesh equivalence under edge/polygon storage permutations.

        Vertex indices remain fixed and coordinates are compared separately.
        Polygon winding remains directed; only the first cyclic corner is moved.
        Every per-face/corner captured value moves with its actual polygon/loop.
        Loop-edge references are independently checked against adjacent vertices.
        """
        edges = self.arrays[prefix + "edges"]
        loop_vertices = self.arrays[prefix + "loop_vertices"]
        loop_edges = self.arrays[prefix + "loop_edges"]
        starts = self.arrays[prefix + "polygons_loop_start"]
        totals = self.arrays[prefix + "polygons_loop_total"]
        if not np.array_equal(starts, np.cumsum(np.r_[0, totals[:-1]], dtype=np.int32)) or int(totals.sum()) != len(loop_vertices):
            raise ValueError("Polygon loops do not cover the mesh exactly once: " + prefix)
        face_fields = [prefix + "polygons_material_index", prefix + "polygons_use_smooth"]
        corner_fields = [prefix + "loop_vertices", prefix + "corner_normals"]
        corner_fields += [prefix + "uv/" + name for name in uv_names]
        edge_fields = []
        internal = {"position", ".edge_verts", ".corner_vert", ".corner_edge"}
        covered = [prefix + "edges", prefix + "loop_edges", prefix + "polygons_loop_start", prefix + "polygons_loop_total"]
        for attr in attributes:
            key = prefix + "attribute/" + attr["name"]
            if key not in self.arrays:
                continue
            if attr["name"] in internal:
                if attr["name"] != "position":
                    covered.append(key)
                continue
            if attr["domain"] == "FACE":
                face_fields.append(key)
            elif attr["domain"] == "CORNER":
                corner_fields.append(key)
            elif attr["domain"] == "EDGE":
                edge_fields.append(key)
        covered += face_fields + corner_fields + edge_fields
        # Primitive operators can permute topology storage, producing last-bit
        # float32 accumulation/interpolation differences. These exceptions are
        # explicit and narrow; all source data and native curves remain exact.
        round_keys = {}
        has_source = mesh.attributes.get("source_face_index") is not None
        if not has_source and not mesh.has_custom_normals:
            round_keys[prefix + "corner_normals"] = "Recomputed generated-mesh smooth normal; exact coordinates/topology/smooth flags and no authored custom normal"
        object_name = prefix.split("/")[1]
        if not has_source and object_name.startswith("Lion_Tooth_"):
            for key in corner_fields:
                if "/uv/" in key or ("/attribute/" in key and key.rsplit("/", 1)[1] in uv_names):
                    round_keys[key] = "UV interpolation of the locally bevelled ivory tooth primitive; exact vertex/topology correspondence"
        exact_corner_fields = [key for key in corner_fields if key not in round_keys]
        covered = [key for key in covered if key not in round_keys]
        edge_payloads = []
        for index, pair in enumerate(edges):
            payload = np.sort(pair).tobytes()
            payload += b"".join(np.asarray(self.arrays[key][index]).tobytes() for key in edge_fields)
            edge_payloads.append(payload)
        face_payloads = []
        face_orders = []
        for face, (start, total) in enumerate(zip(starts, totals)):
            start, total = int(start), int(total)
            vertices = loop_vertices[start:start + total]
            if total < 3:
                raise ValueError("Polygon has fewer than three corners: " + prefix)
            actual_pairs = np.sort(edges[loop_edges[start:start + total]], axis=1)
            expected_pairs = np.sort(np.column_stack((vertices, np.roll(vertices, -1))), axis=1)
            if not np.array_equal(actual_pairs, expected_pairs):
                raise ValueError("Loop edges do not connect their actual adjacent corners: " + prefix)
            candidates = np.flatnonzero(vertices == vertices.min())
            rotated = []
            for offset in candidates:
                indexes = start + np.roll(np.arange(total), -int(offset))
                payload = np.int32(total).tobytes()
                payload += b"".join(np.asarray(self.arrays[key][face]).tobytes() for key in face_fields)
                payload += b"".join(np.ascontiguousarray(self.arrays[key][indexes]).tobytes() for key in exact_corner_fields)
                rotated.append((payload, indexes))
            payload, indexes = min(rotated, key=lambda candidate: candidate[0])
            face_payloads.append(payload)
            face_orders.append((payload, indexes))
        ordered_corners = np.concatenate([indexes for _, indexes in sorted(face_orders, key=lambda record: record[0])])
        for key, reason in round_keys.items():
            values = np.ascontiguousarray(self.arrays[key][ordered_corners], dtype=np.float32)
            self.roundoff_fields[key] = {
                "dtype": values.dtype.str, "shape": list(values.shape),
                "canonical_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
                "absolute_budget": float(np.finfo(np.float32).eps), "reason": reason,
                "encoding": "zlib-base64-float32", "data": base64.b64encode(zlib.compress(values.tobytes(), 9)).decode("ascii"),
            }
        for label, payloads, fields in (("canonical_edges", edge_payloads, edge_fields),
                                       ("canonical_faces", face_payloads, face_fields + exact_corner_fields)):
            digest = hashlib.sha256()
            for payload in sorted(payloads):
                digest.update(np.int32(len(payload)).tobytes())
                digest.update(payload)
            key = prefix + label
            self.array_records[key] = {"dtype": "canonical-native-records", "shape": [len(payloads)],
                                       "sha256": digest.hexdigest(), "field_order": fields}
        self.reordering_proofs[prefix] = {"proof_fields": [prefix + "canonical_edges", prefix + "canonical_faces"],
                                           "covered_storage_fields": sorted(set(covered)),
                                           "loop_edge_adjacency_validated": True}

    def curve(self, obj):
        data = obj.data
        prefix = "object/" + obj.name + "/curve/"
        count = len(data.splines)
        metadata = np.zeros((count, len(SPLINE_PROPERTIES) + 1), np.int32)
        enum_values = {}
        totals = {"BEZIER": 0, "OTHER": 0}
        for index, spline in enumerate(data.splines):
            points = spline.bezier_points if spline.type == "BEZIER" else spline.points
            metadata[index, 0] = len(points)
            totals["BEZIER" if spline.type == "BEZIER" else "OTHER"] += len(points)
            for column, name in enumerate(SPLINE_PROPERTIES, 1):
                value = getattr(spline, name)
                if isinstance(value, str):
                    choices = enum_values.setdefault(name, sorted(item.identifier for item in spline.bl_rna.properties[name].enum_items))
                    value = choices.index(value)
                metadata[index, column] = int(value)
        self.array(prefix + "spline_settings", metadata)
        field_specs = {"co": 3, "handle_left": 3, "handle_right": 3, "radius": 1, "tilt": 1, "weight_softbody": 1}
        bezier = {name: np.empty((totals["BEZIER"], width), np.float32) if width > 1 else np.empty(totals["BEZIER"], np.float32) for name, width in field_specs.items()}
        handles = np.empty((totals["BEZIER"], 2), np.int8)
        other = {name: np.empty((totals["OTHER"], width), np.float32) if width > 1 else np.empty(totals["OTHER"], np.float32) for name, width in {"co": 4, "radius": 1, "tilt": 1, "weight": 1, "weight_softbody": 1}.items()}
        handle_choices = ["FREE", "VECTOR", "ALIGNED", "AUTO"]
        bez_offset = other_offset = 0
        for spline in data.splines:
            if spline.type == "BEZIER":
                points = spline.bezier_points
                end = bez_offset + len(points)
                for name in bezier:
                    points.foreach_get(name, bezier[name][bez_offset:end].reshape(-1))
                for index, point in enumerate(points, bez_offset):
                    handles[index] = (handle_choices.index(point.handle_left_type), handle_choices.index(point.handle_right_type))
                bez_offset = end
            else:
                points = spline.points
                end = other_offset + len(points)
                for name in other:
                    points.foreach_get(name, other[name][other_offset:end].reshape(-1))
                other_offset = end
        for name, values in bezier.items():
            self.array(prefix + "bezier/" + name, values)
        self.array(prefix + "bezier/handle_types", handles)
        for name, values in other.items():
            self.array(prefix + "other/" + name, values)
        settings = {name: simple(getattr(data, name)) for name in CURVE_PROPERTIES if hasattr(data, name)}
        return {"splines": count, "bezier_points": totals["BEZIER"], "other_points": totals["OTHER"],
                "settings": settings, "spline_property_order": list(SPLINE_PROPERTIES),
                "spline_enum_choices": enum_values, "handle_type_choices": handle_choices}

    def snapshot(self, path):
        started = time.monotonic()
        before = file_hash(path)
        bpy.ops.wm.open_mainfile(filepath=str(path))
        bpy.context.view_layer.update()
        root = bpy.data.objects.get("Lion_Root")
        if root is None:
            raise ValueError("Lion_Root is missing in " + path.name)
        descendants = [root]
        for obj in descendants:
            descendants.extend(obj.children)
        objects = {}
        for index, obj in enumerate(sorted(descendants, key=lambda entry: entry.name)):
            if index % 16 == 0 or obj.type == "CURVE":
                print("CAPTURE_ASSET", index + 1, len(descendants), obj.name, obj.type, flush=True)
            prefix = "object/" + obj.name + "/"
            for name in ("matrix_world", "matrix_basis", "matrix_parent_inverse"):
                self.array(prefix + name, np.asarray(getattr(obj, name), dtype=np.float32))
            record = {
                "type": obj.type, "parent": obj.parent.name if obj.parent else None,
                "parent_type": obj.parent_type, "parent_bone": obj.parent_bone,
                "rotation_mode": obj.rotation_mode,
                "visibility": {name: simple(getattr(obj, name)) for name in ("hide_render", "hide_viewport", "visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter", "visible_shadow") if hasattr(obj, name)},
                "provenance": {name: simple(obj[name]) for name in SOURCE_PROPERTIES if name in obj},
                "constraints": [self.rna(constraint, prefix + "constraint", exclude={"owner_space"}) | {"type": constraint.type, "owner_space": constraint.owner_space} for constraint in obj.constraints],
                "modifiers": [self.rna(modifier, prefix + "modifier") | {"type": modifier.type, "show_viewport": modifier.show_viewport, "show_render": modifier.show_render} for modifier in obj.modifiers],
                "material_slots": [self.material(slot.material) for slot in obj.material_slots],
            }
            if obj.type == "MESH":
                record["data"] = self.mesh(obj)
            elif obj.type == "CURVE":
                record["data"] = self.curve(obj)
            elif obj.type != "EMPTY":
                self.unsupported.append(prefix + "data type: " + obj.type)
            objects[obj.name] = record
        after = file_hash(path)
        if before != after:
            raise ValueError("Read-only capture input changed: " + path.name)
        asset = {"objects": objects, "arrays": self.array_records, "materials": self.materials, "images": self.images}
        covered = {key for proof in self.reordering_proofs.values() for key in proof["covered_storage_fields"]} | set(self.roundoff_fields)
        canonical_asset = {**asset, "arrays": {key: value for key, value in self.array_records.items() if key not in covered}}
        return {
            "schema": SCHEMA, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "blender_version": bpy.app.version_string,
            "file": {"name": path.name, "bytes": path.stat().st_size, "sha256_before": before, "sha256_after": after, "preserved": True},
            "asset_sha256": json_hash(canonical_asset), "ordered_storage_sha256": json_hash(asset), "asset": asset,
            "reordering_proofs": self.reordering_proofs,
            "primitive_roundoff_fields": self.roundoff_fields,
            "image_codecs": self.image_codecs, "material_names": self.material_names,
            "asset_object_count": len(objects), "capture_seconds": time.monotonic() - started,
            "warnings": self.warnings, "unsupported": sorted(set(self.unsupported)), "scope": SCOPE,
        }


def flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from flatten(child, prefix + "/" + str(key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from flatten(child, prefix + "/" + str(index))
        if not value:
            yield prefix, []
    else:
        yield prefix, value


def compare(expected, actual, expected_arrays, actual_arrays):
    errors = []
    warnings = []
    differences = []
    storage_reorderings = []
    measured_roundoff = []
    a = expected["asset"]
    b = actual["asset"]
    for section in ("objects", "materials", "images"):
        left = dict(flatten(a[section]))
        right = dict(flatten(b[section]))
        for key in sorted(set(left) | set(right)):
            if left.get(key) != right.get(key):
                differences.append({"section": section, "field": key, "expected": left.get(key), "actual": right.get(key)})
    left_arrays = a["arrays"]
    right_arrays = b["arrays"]
    proved_storage_fields = set()
    proved_prefixes = set()
    for prefix, proof in expected.get("reordering_proofs", {}).items():
        current = actual.get("reordering_proofs", {}).get(prefix)
        if proof == current and all(left_arrays.get(key) == right_arrays.get(key) for key in proof["proof_fields"]):
            proved_storage_fields.update(proof["covered_storage_fields"])
            proved_prefixes.add(prefix)
    accepted_roundoff_fields = set()
    for key, old in expected.get("primitive_roundoff_fields", {}).items():
        new = actual.get("primitive_roundoff_fields", {}).get(key)
        prefix = key.split("/mesh/", 1)[0] + "/mesh/"
        coordinate_exact = all(left_arrays.get(prefix + name) == right_arrays.get(prefix + name) for name in ("coordinates", "attribute/position"))
        if new is None or prefix not in proved_prefixes or not coordinate_exact or old["shape"] != new["shape"] or old["dtype"] != new["dtype"] or old["absolute_budget"] != new["absolute_budget"] or old["reason"] != new["reason"]:
            continue
        a_values = np.frombuffer(zlib.decompress(base64.b64decode(old["data"])), dtype=np.dtype(old["dtype"])).reshape(old["shape"])
        b_values = np.frombuffer(zlib.decompress(base64.b64decode(new["data"])), dtype=np.dtype(new["dtype"])).reshape(new["shape"])
        if hashlib.sha256(a_values.tobytes()).hexdigest() != old["canonical_sha256"] or hashlib.sha256(b_values.tobytes()).hexdigest() != new["canonical_sha256"]:
            raise ValueError("Primitive roundoff evidence payload hash differs from its descriptor")
        delta = np.abs(a_values.astype(np.float64) - b_values.astype(np.float64))
        maximum = float(delta.max()) if delta.size else 0.0
        if maximum <= old["absolute_budget"]:
            accepted_roundoff_fields.add(key)
            if np.count_nonzero(delta):
                record = {"field": key, "reason": old["reason"], "changed_components": int(np.count_nonzero(delta)),
                          "maximum_absolute_difference": maximum, "absolute_budget": old["absolute_budget"],
                          "budget_scope": "One float32 spacing at unit magnitude, applied only after exact canonical topology/coordinate proof; no source-data tolerance"}
                if key.endswith("corner_normals"):
                    dots = np.einsum("ij,ij->i", a_values.astype(np.float64), b_values.astype(np.float64))
                    lengths = np.linalg.norm(a_values.astype(np.float64), axis=1) * np.linalg.norm(b_values.astype(np.float64), axis=1)
                    record["maximum_normal_angle_degrees"] = float(np.degrees(np.arccos(np.clip(dots / lengths, -1, 1))).max())
                measured_roundoff.append(record)
    for key in sorted(set(left_arrays) | set(right_arrays)):
        left = left_arrays.get(key)
        right = right_arrays.get(key)
        if left == right:
            continue
        if key in accepted_roundoff_fields:
            continue
        difference = {"section": "array", "field": key, "expected": left, "actual": right}
        old = expected_arrays.get(key) if expected_arrays else None
        new = actual_arrays.get(key)
        if old is not None and new is not None and old.shape == new.shape:
            mismatch = old != new
            difference["changed_elements"] = int(np.count_nonzero(mismatch))
            if old.size and old.dtype.kind in "fbiu" and new.dtype.kind in "fbiu":
                delta = np.abs(old.astype(np.float64) - new.astype(np.float64))
                difference["max_absolute_difference"] = float(delta.max())
                if old.ndim == 2 and old.shape[1] == 3:
                    difference["max_vector_distance"] = float(np.linalg.norm(delta, axis=1).max())
        else:
            difference["measurement_scope"] = "Portable signature has hashes/bounds/counts; original arrays are unavailable for pointwise distance."
        if key in proved_storage_fields:
            difference["equivalence_proof"] = "Exact canonical edge and directed cyclic polygon-corner records, including captured UVs/normals/material/attributes"
            storage_reorderings.append(difference)
        else:
            differences.append(difference)
    if differences:
        errors.append("Native asset data or shader semantics differ from the chosen baseline")
    if expected.get("unsupported") or actual.get("unsupported"):
        errors.append("Capture has unsupported semantic fields; inspect scope before claiming complete covered equivalence")
    for identity in sorted(set(expected.get("image_codecs", {})) & set(actual.get("image_codecs", {}))):
        old_hashes = sorted({entry["packed_byte_sha256"] for entry in expected["image_codecs"][identity] if entry.get("packed_byte_sha256")})
        new_hashes = sorted({entry["packed_byte_sha256"] for entry in actual["image_codecs"][identity] if entry.get("packed_byte_sha256")})
        if old_hashes != new_hashes:
            warnings.append({"image_semantic_id": identity, "reason": "Packed container bytes differ; exact decoded pixels and image settings establish equivalence", "expected_packed_hashes": old_hashes, "actual_packed_hashes": new_hashes})
    warnings.extend(expected.get("warnings", []) + actual.get("warnings", []))
    return {
        "schema": "lion-project.native-reconstruction-comparison/v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "status": "pass" if not errors else "fail",
        "baseline": {"file": expected["file"], "asset_sha256": expected["asset_sha256"], "blender_version": expected["blender_version"]},
        "rebuilt": {"file": actual["file"], "asset_sha256": actual["asset_sha256"], "blender_version": actual["blender_version"]},
        "asset_objects": actual["asset_object_count"], "array_fields": len(right_arrays),
        "used_material_semantics": len(b["materials"]), "used_image_semantics": len(b["images"]),
        "differences": differences, "proven_storage_reorderings": storage_reorderings,
        "measured_primitive_float32_roundoff": measured_roundoff, "errors": errors, "warnings": warnings,
        "unsupported_expected": expected.get("unsupported", []), "unsupported_actual": actual.get("unsupported", []),
        "scope": SCOPE,
    }


def write_json(path, value):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    if temporary.exists():
        raise FileExistsError("Existing signature/report temporary file requires inspection")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--rebuilt", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--signature", type=Path)
    parser.add_argument("--expected-signature", type=Path)
    parser.add_argument("--write-baseline-signature", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    input_paths = {path.resolve() for path in (args.baseline, args.rebuilt, args.capture, args.expected_signature) if path}
    output_paths = [path.resolve() for path in (args.report, args.signature, args.write_baseline_signature) if path]
    if len(set(output_paths)) != len(output_paths) or any(path in input_paths or path.suffix.lower() != ".json" for path in output_paths):
        parser.error("Reports/signatures must be distinct JSON outputs and cannot replace any input")
    if args.capture:
        if not args.signature or args.baseline or args.rebuilt or args.expected_signature:
            parser.error("Capture mode requires --capture and --signature only")
        capture = Capture()
        result = capture.snapshot(args.capture.resolve(strict=True))
        write_json(args.signature, result)
        print("NATIVE_SIGNATURE_CAPTURED", result["asset_object_count"], result["asset_sha256"], flush=True)
        if result["unsupported"]:
            raise ValueError("Signature capture has unsupported fields: " + "; ".join(result["unsupported"]))
        return
    if not args.rebuilt or not args.report or bool(args.baseline) == bool(args.expected_signature):
        parser.error("Comparison needs --rebuilt/--report and exactly one of --baseline or --expected-signature")
    baseline_capture = None
    if args.baseline:
        baseline_capture = Capture()
        expected = baseline_capture.snapshot(args.baseline.resolve(strict=True))
        if args.write_baseline_signature:
            write_json(args.write_baseline_signature, expected)
    else:
        expected = json.loads(args.expected_signature.read_text(encoding="utf-8-sig"))
        if expected.get("schema") != SCHEMA:
            raise ValueError("Unexpected native reference signature schema")
    rebuilt_capture = Capture()
    actual = rebuilt_capture.snapshot(args.rebuilt.resolve(strict=True))
    result = compare(expected, actual, baseline_capture.arrays if baseline_capture else None, rebuilt_capture.arrays)
    write_json(args.report, result)
    print("NATIVE_RECONSTRUCTION_COMPARISON", result["status"], len(result["differences"]), "differences", flush=True)
    if result["errors"]:
        raise ValueError("; ".join(result["errors"]))


if __name__ == "__main__":
    main()
