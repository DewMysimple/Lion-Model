"""Editable, surface-sampled fine fibers for Blender 5.x.

This module has no scene side effects when imported. It uses real 3D CURVE
splines, not a particle system. Each emitter receives separate curve objects;
every strand remains an individually editable Bezier spline. Existing meshes,
materials, collections and parents are never merged or replaced.

Lengths and radii are in *world scene units*. For a one metre lion, start with
length=(0.012, 0.03), radius=(0.00012, 0.0002) for short red velvet. White fringe
can use length=(0.06, 0.20), radius=(0.00010, 0.00018), droop=0.7. Density is
strands per square world unit; count is an alternative explicit strand budget.

Example::

    results = create_fibers([bpy.data.objects['Red_Base']], count=12000,
        length=(0.012, 0.03), radius=(0.00012, 0.0002),
        direction=(0, 0, -1), direction_strength=0.5,
        triangle_filter=lambda tri: tri['center'].z > 0.3,
        material=red_fiber_material, seed=32)

triangle_filter receives a dictionary including emitter, area, center, normal,
world vertices/vertex normals, polygon/material indices, UVs and corner colors.
sample_filter receives that dictionary plus barycentric weights, position,
normal and interpolated uv/color. This supports precise texture/region masks
without hardcoding this lion's geometry. The callbacks may return False to
exclude a surface. Length, radius and direction may also be callables accepting
(sample, random.Random). A scalar or two-value interval is accepted for length
and radius. Mesh deformation after creation requires regeneration or a binding
modifier; parenting preserves object transforms, not vertex correspondence.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from bisect import bisect_left
from dataclasses import dataclass
import math
import random

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree


@dataclass
class FiberResult:
    emitter: object
    objects: list
    stats: dict


def _unit(value, fallback=(0, 0, 1)):
    vector = Vector(value)
    return vector.normalized() if vector.length_squared > 1e-16 else Vector(fallback)


def _choose(spec, sample, rng):
    if callable(spec):
        return float(spec(sample, rng))
    if isinstance(spec, (tuple, list)):
        return rng.uniform(float(spec[0]), float(spec[1]))
    return float(spec)


def _snapshot_triangles(emitter, triangle_filter, use_evaluated):
    """Copy the sampling data, then release the temporary evaluated mesh."""
    if emitter.type != 'MESH':
        raise TypeError('Fiber emitter must be a MESH object: ' + emitter.name)
    bpy.context.view_layer.update()
    evaluated = None
    mesh = emitter.data
    if use_evaluated:
        evaluated = emitter.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh(preserve_all_data_layers=True,
                                 depsgraph=bpy.context.evaluated_depsgraph_get())
    records, cumulative, total = [], [], 0.0
    try:
        mesh.calc_loop_triangles()
        world = emitter.matrix_world.copy()
        normal_matrix = world.to_3x3().inverted_safe().transposed()
        uv_layer = mesh.uv_layers.active
        color_layer = mesh.color_attributes.active_color
        for triangle in mesh.loop_triangles:
            vertices = tuple(world @ mesh.vertices[index].co for index in triangle.vertices)
            edge_a, edge_b = vertices[1] - vertices[0], vertices[2] - vertices[0]
            area = edge_a.cross(edge_b).length * 0.5
            if area < 1e-16:
                continue
            normal = _unit(normal_matrix @ triangle.normal)
            vertex_normals = tuple(_unit(normal_matrix @ mesh.vertices[index].normal)
                                   for index in triangle.vertices)
            uvs = (tuple(tuple(uv_layer.data[index].uv) for index in triangle.loops)
                   if uv_layer else None)
            colors = None
            if color_layer:
                indices = triangle.loops if color_layer.domain == 'CORNER' else triangle.vertices
                colors = tuple(tuple(color_layer.data[index].color) for index in indices)
            record = dict(emitter=emitter, triangle_index=triangle.index,
                          polygon_index=triangle.polygon_index,
                          material_index=triangle.material_index, vertices=vertices,
                          vertex_normals=vertex_normals, area=area,
                          center=(vertices[0] + vertices[1] + vertices[2]) / 3,
                          normal=normal, uv_corners=uvs, color_corners=colors)
            if triangle_filter is not None and not triangle_filter(record):
                continue
            total += area
            records.append(record)
            cumulative.append(total)
    finally:
        if evaluated is not None:
            evaluated.to_mesh_clear()
    return records, cumulative, total


def _surface_sample(records, cumulative, area, rng):
    record = records[min(bisect_left(cumulative, rng.random() * area), len(records) - 1)]
    # Uniform area sampling, unlike two independent barycentric random values.
    root = math.sqrt(rng.random())
    weights = (1 - root, root * (1 - rng.random()), 0)
    weights = (weights[0], weights[1], 1 - weights[0] - weights[1])
    sample = dict(record)
    sample['barycentric'] = weights
    sample['position'] = sum((v * w for v, w in zip(record['vertices'], weights)), Vector())
    sample['normal'] = _unit(sum((n * w for n, w in zip(record['vertex_normals'], weights)), Vector()),
                             record['normal'])
    for field, corners, dimensions in [('uv', 'uv_corners', 2), ('color', 'color_corners', 4)]:
        values = record[corners]
        sample[field] = tuple(sum(values[j][i] * weights[j] for j in range(3))
                              for i in range(dimensions)) if values else None
    return sample


def _random_tangent(normal, rng):
    reference = Vector((1, 0, 0)) if abs(normal.x) < 0.8 else Vector((0, 1, 0))
    first = _unit(normal.cross(reference))
    second = normal.cross(first)
    angle = rng.random() * math.tau
    return first * math.cos(angle) + second * math.sin(angle)


def _strand_direction(sample, spec, strength, spread, rng):
    normal = sample['normal']
    desired = spec(sample, rng) if callable(spec) else spec
    tangent = Vector((0, 0, 0))
    if desired is not None:
        desired = _unit(desired)
        tangent = desired - normal * desired.dot(normal)
        if tangent.length_squared > 1e-12:
            tangent.normalize()
    result = normal * max(0.08, 1 - strength) + tangent * strength
    result += _random_tangent(normal, rng) * rng.uniform(0.0, spread)
    return _unit(result, normal)


def add_fibers(emitter, *, count=5000, density=None, length=(0.012, 0.03),
               radius=(0.00012, 0.0002), direction=None, direction_strength=0.55,
               droop=0.3, gravity=(0, 0, -1), angular_spread=0.30,
               bend=0.15, clump=0.15, clump_count=None, clump_radius=None,
               seed=0, point_count=(3, 6), root_lift=None, triangle_filter=None,
               sample_filter=None, collection=None, parent='emitter', material=None,
               use_evaluated=True, max_splines_per_object=20000,
               resolution=3, bevel_resolution=0, name=None):
    """Create a bounded set of editable fibers without changing the emitter.

    clump is [0,1] lateral attraction towards nearby virtual guide roots.
    Guides are area sampled and clump_radius bounds their influence. Root lift
    defaults to 0.25 times each strand radius. Gravity bends progressively,
    leaving roots aligned with the surface rather than starting inside it.
    Returns FiberResult(objects, stats); count zero creates no scene data.
    """
    if not 0 <= direction_strength <= 1 or not 0 <= clump <= 1:
        raise ValueError('direction_strength and clump must be within [0,1]')
    if droop < 0 or angular_spread < 0 or bend < 0:
        raise ValueError('droop, angular_spread and bend must be nonnegative')
    if max_splines_per_object < 1:
        raise ValueError('max_splines_per_object must be positive')
    if isinstance(point_count, int):
        point_min = point_max = point_count
    else:
        point_min, point_max = point_count
    if not 3 <= point_min <= point_max <= 6:
        raise ValueError('Use 3 to 6 Bezier control points per strand')
    records, cumulative, area = _snapshot_triangles(emitter, triangle_filter, use_evaluated)
    requested = max(0, int(round(area * density))) if density is not None else max(0, int(count))
    stats = dict(seed=int(seed), requested=requested, actual=0, accepted_triangles=len(records),
                 emitter_area_world=area, editable_splines=True, geometry_type='CURVE',
                 world_units=True, limitations=[
                     'Transform parenting only; regenerate after mesh deformation.',
                     'Native curves require conversion on an export copy for GLB.',
                     'Area sampling alone is not a reference-fidelity acceptance check.'])
    if not records or requested == 0:
        return FiberResult(emitter, [], stats)
    rng = random.Random(seed)
    samples = []
    attempts = 0
    # Bounded rejection prevents an accidentally empty texture mask hanging Blender.
    while len(samples) < requested and attempts < requested * 40:
        sample = _surface_sample(records, cumulative, area, rng)
        attempts += 1
        if sample_filter is None or sample_filter(sample):
            samples.append(sample)
    stats['sampling_attempts'] = attempts
    stats['actual'] = len(samples)
    if not samples:
        return FiberResult(emitter, [], stats)
    lengths = [max(1e-7, _choose(length, sample, rng)) for sample in samples]
    radii = [max(1e-8, _choose(radius, sample, rng)) for sample in samples]
    median_length = sorted(lengths)[len(lengths) // 2]
    guide_tree = None
    guide_positions = []
    if clump > 0:
        guides = max(1, min(len(samples), int(clump_count or max(8, math.sqrt(len(samples)) * 2))))
        guide_indices = rng.sample(range(len(samples)), guides)
        guide_positions = [samples[index]['position'].copy() for index in guide_indices]
        guide_tree = KDTree(guides)
        for index, point in enumerate(guide_positions):
            guide_tree.insert(point, index)
        guide_tree.balance()
    influence_radius = clump_radius if clump_radius is not None else median_length * 0.9
    if collection is None:
        collection = next(iter(emitter.users_collection), bpy.context.scene.collection)
    actual_parent = emitter if isinstance(parent, str) and parent == 'emitter' else parent
    if actual_parent is False:
        actual_parent = None
    gravity_vector = _unit(gravity, (0, 0, -1))
    objects = []
    name = name or emitter.name + '_Fine_Fibers'
    nominal_radius = max(radii)
    current_curve = None
    realized_lengths = []
    for index, (sample, strand_length, strand_radius) in enumerate(zip(samples, lengths, radii)):
        if index % max_splines_per_object == 0:
            curve = bpy.data.curves.new(name + '_Geometry_' + str(len(objects) + 1), 'CURVE')
            curve.dimensions = '3D'
            curve.resolution_u = max(1, int(resolution))
            curve.render_resolution_u = max(1, int(resolution))
            curve.bevel_depth = nominal_radius
            curve.bevel_resolution = max(0, int(bevel_resolution))
            curve.use_fill_caps = True
            if material is not None:
                curve.materials.append(material)
            obj = bpy.data.objects.new(name + '_' + str(len(objects) + 1), curve)
            collection.objects.link(obj)
            if actual_parent is not None:
                obj.parent = actual_parent
                obj.matrix_parent_inverse = actual_parent.matrix_world.inverted_safe()
            obj.matrix_world = Matrix.Identity(4)
            obj['fiber_emitter'] = emitter.name
            obj['fiber_seed'] = int(seed)
            obj['fiber_world_radius_max'] = nominal_radius
            obj['fiber_generator'] = 'fiber_tools.add_fibers'
            obj['fiber_binding'] = 'Transform parent; static sampled surface'
            objects.append(obj)
            current_curve = curve
        normal = sample['normal']
        base = sample['position'] + normal * (strand_radius * 0.25 if root_lift is None else root_lift)
        strand_direction = _strand_direction(sample, direction, direction_strength, angular_spread, rng)
        tangent_a = _random_tangent(strand_direction, rng)
        tangent_b = strand_direction.cross(tangent_a)
        curl_phase = rng.random() * math.tau
        curl_size = strand_length * bend * rng.uniform(0.35, 1.0)
        droop_variation = droop * rng.uniform(0.65, 1.35)
        pull = Vector()
        if guide_tree is not None:
            _, guide_index, distance = guide_tree.find(sample['position'])
            if influence_radius > 0 and distance < influence_radius:
                pull = guide_positions[guide_index] - sample['position']
                pull -= normal * pull.dot(normal)
                pull *= clump * (1 - distance / influence_radius)
        control_points = rng.randint(int(point_min), int(point_max))
        spline = current_curve.splines.new('BEZIER')
        spline.bezier_points.add(control_points - 1)
        last = None
        measured_length = 0.0
        for point_index, point in enumerate(spline.bezier_points):
            t = point_index / (control_points - 1)
            # Individual strand length, roots, phase and bending differ. Small
            # curvature is distributed along the shaft, not a rigid brush.
            curl = (tangent_a * math.sin(curl_phase + t * math.pi * 1.5)
                    + tangent_b * math.cos(curl_phase + t * math.pi))
            curl *= curl_size * math.sin(t * math.pi * 0.75) * t
            position = base + strand_direction * strand_length * t
            position += gravity_vector * strand_length * droop_variation * t * t * 0.6
            position += curl + pull * t * t
            point.co = position
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'
            # Finite root radius and fine, nonzero tip prevent tube-like ends.
            point.radius = strand_radius / nominal_radius * (0.06 + 0.94 * (1 - t) ** 0.75)
            if last is not None:
                measured_length += (position - last).length
            last = position
        realized_lengths.append(measured_length)
    for obj in objects:
        obj['fiber_strand_count'] = len(obj.data.splines)
    stats.update(object_names=[obj.name for obj in objects], curve_object_count=len(objects),
                 length_requested_range=[min(lengths), max(lengths)],
                 length_control_polygon_range=[min(realized_lengths), max(realized_lengths)],
                 radius_root_range=[min(radii), max(radii)],
                 radius_tip_range=[min(radii) * 0.06, max(radii) * 0.06],
                 control_point_range=[int(point_min), int(point_max)],
                 clump=float(clump), clump_radius=float(influence_radius),
                 material=material.name if material else None)
    return FiberResult(emitter, objects, stats)


def create_fibers(emitters, **kwargs):
    """Apply the same fiber settings to multiple emitters, with distinct seeds.

    emitters may be objects, names, or dictionaries with ``emitter`` and per-item
    overrides, e.g. {'emitter': brow, 'length': (0.06, 0.10), 'count': 8000}.
    Seeds are deterministic and offset per emitter; callers may override them.
    """
    results = []
    base_seed = int(kwargs.get('seed', 0))
    for index, entry in enumerate(emitters):
        settings = dict(kwargs)
        settings['seed'] = base_seed + index * 1009
        if isinstance(entry, dict):
            entry = dict(entry)
            emitter = entry.pop('emitter')
            settings.update(entry)
        else:
            emitter = entry
        if isinstance(emitter, str):
            emitter = bpy.data.objects[emitter]
        results.append(add_fibers(emitter, **settings))
    return results
