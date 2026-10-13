"""Reuse only the verified study's projection UV and packed reference images."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
import bpy
import numpy as np

from study_cloth_projection import add_projection_material


def apply_studied_cloth_projection(body, study_path):
    """Add the study's +X projection to current Body materials, preserving trim.

    The body vertex/loop topology must still match the actual tested study.
    This callable does not load/replace the scene, transform parts or save files.
    """
    study_path = Path(study_path).resolve(strict=True)
    with bpy.data.libraries.load(str(study_path), link=False) as (available, loaded):
        if 'Lion_Body' not in available.objects:
            raise ValueError('Study has no actual Lion_Body')
        loaded.objects = ['Lion_Body']
    prototype = loaded.objects[0]
    try:
        if len(prototype.data.vertices) != len(body.data.vertices) or len(prototype.data.loops) != len(body.data.loops):
            raise ValueError('Current body topology differs from the projection study')
        size = len(body.data.vertices)*3
        current = np.empty(size, np.float32)
        studied = np.empty(size, np.float32)
        body.data.vertices.foreach_get('co', current)
        prototype.data.vertices.foreach_get('co', studied)
        if not np.array_equal(current, studied):
            raise ValueError('Current body positions differ from the projection study')
        uv_name = 'ReferenceClothWorldYZ_PositiveX'
        source = prototype.data.uv_layers.get(uv_name)
        if not source:
            raise ValueError('Study projection UV is absent')
        coordinates = np.empty(len(source.data)*2, np.float32)
        source.data.foreach_get('uv', coordinates)
        target = body.data.uv_layers.get(uv_name) or body.data.uv_layers.new(name=uv_name)
        target.data.foreach_set('uv', coordinates)
        photo = mask = None
        for material in prototype.data.materials:
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    if node.image.name.startswith('Reference_Cloth_Visible_Only_Mask'):
                        mask = node.image
                    elif Path(bpy.path.abspath(node.image.filepath)).name == 'left.png':
                        photo = node.image
        if not photo or not mask:
            raise ValueError('Study packed photo/mask could not be identified')
        for index, original in enumerate(list(body.data.materials)):
            if original:
                body.data.materials[index] = add_projection_material(original, photo, mask, uv_name)
        return {'body': body.name, 'topologyMatchedStudy': True, 'projectionUV': uv_name,
                'referenceImage': photo.name, 'maskImage': mask.name,
                'scope': 'Only +X-facing photographed cloth pixels; other areas use the current original material.'}
    finally:
        bpy.data.objects.remove(prototype, do_unlink=True)
