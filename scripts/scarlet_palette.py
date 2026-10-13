"""Measured, bounded scarlet correction with explicit PNG/FILE texture loading.

Run inside Blender. Does not save the master or alter geometry/UVs. Appearance
masks recolor existing atlas pixels; they do not invent or replace textile motifs.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


import json
from pathlib import Path
import struct
import sys
import zlib

import bpy
import numpy as np

sys.path.insert(0, str(ROOT / "scripts"))
from lion_material_tools import image_pixels


def _png_chunk(kind, data):
    checksum = zlib.crc32(kind + data) & 0xffffffff
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def save_encoded_rgba_png(path, rgba):
    """Write exact 8-bit encoded RGBA, without a Blender color transform."""
    array = np.clip(np.rint(np.asarray(rgba, dtype=np.float32) * 255), 0, 255).astype(np.uint8)
    height, width = array.shape[:2]
    if array.shape[-1] != 4:
        raise ValueError("PNG writer expects RGBA")
    rows = array[::-1].reshape(height, width * 4)
    filtered = np.empty((height, width * 4 + 1), dtype=np.uint8)
    filtered[:, 0] = 0
    filtered[:, 1:] = rows
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    content = (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header)
               + _png_chunk(b"IDAT", zlib.compress(filtered.tobytes(), 6))
               + _png_chunk(b"IEND", b""))
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _scarlet_mask(rgb):
    red, green, blue = np.moveaxis(rgb, -1, 0)
    maximum = rgb.max(axis=-1)
    minimum = rgb.min(axis=-1)
    saturation = (maximum - minimum) / np.maximum(maximum, 1e-6)
    mask = np.clip((red - green - .045) / .13, 0, 1)
    mask *= np.clip((.83 - green / np.maximum(red, 1e-6)) / .19, 0, 1)
    mask *= np.clip((.84 - blue / np.maximum(red, 1e-6)) / .22, 0, 1)
    # Warm yellow/gold has a larger G-B gap. Keep those motif pixels intact.
    mask *= np.clip((.17 - (green - blue)) / .07, 0, 1)
    mask *= np.clip((saturation - .13) / .18, 0, 1)
    mask *= np.clip((red - .23) / .15, 0, 1)
    return mask


def refine_scarlet_palette(bundle, output_dir=None):
    """Return an updated material bundle and real scarlet color/diagnostic maps.

    `bundle` may contain original encoded RGBA `pixels` and/or `maps['basecolor']`.
    Existing `maps` entries remain. The function never edits the original atlas.
    `new_basecolor_image` is a packed FILE image freshly reloaded from the PNG.
    """
    output = Path(output_dir or ROOT / "textures" / "generated").resolve()
    output.mkdir(parents=True, exist_ok=True)
    if "pixels" in bundle:
        rgba = np.array(bundle["pixels"], dtype=np.float32, copy=True)
    elif bundle.get("maps", {}).get("basecolor"):
        rgba = image_pixels(bundle["maps"]["basecolor"])
    else:
        raise ValueError("Bundle requires encoded atlas pixels or maps['basecolor']")
    rgb = rgba[..., :3]
    mask = _scarlet_mask(rgb)
    target = rgb.copy()
    target[..., 0] *= .90
    # Cap the washed-out pink ratios, keeping existing spatial intensity detail.
    target[..., 1] = np.minimum(rgb[..., 1] * .64, target[..., 0] * .26)
    target[..., 2] = np.minimum(rgb[..., 2] * .64, target[..., 0] * .23)
    refined = rgba.copy()
    refined[..., :3] = rgb * (1 - mask[..., None]) + target * mask[..., None]
    path = save_encoded_rgba_png(output / "lion_basecolor_scarlet.png", refined)
    image = bpy.data.images.load(str(path), check_existing=False)
    image.name = "Lion_Atlas_Color_Scarlet"
    image.colorspace_settings.name = "sRGB"
    image.pack()
    # Reloaded values must match intended encoded values within 8-bit rounding.
    actual = image_pixels(image)
    error = float(np.abs(actual - refined).max())
    if error > 1 / 255 + 1e-6 or image.source != "FILE" or image.is_float:
        raise RuntimeError("Scarlet PNG FILE/encoded-pixel verification failed")
    diagnostic = np.ones_like(rgba)
    diagnostic[..., :3] = mask[..., None]
    mask_path = save_encoded_rgba_png(output / "lion_scarlet_color_mask.png", diagnostic)
    changed = mask > .8
    report = {
        "basecolor": str(path), "soft_mask": str(mask_path),
        "source_pixels_space": "Encoded sRGB, bottom-left origin",
        "loaded_image_source": image.source, "loaded_image_is_float": bool(image.is_float),
        "loaded_color_space": image.colorspace_settings.name,
        "saved_png_max_encoded_error": error,
        "strong_mask_pixel_fraction": float(changed.mean()),
        "strong_mask_mean_before_srgb": rgb[changed].mean(axis=0).tolist(),
        "strong_mask_mean_after_srgb": refined[..., :3][changed].mean(axis=0).tolist(),
        "limits": ["Color/hue inference only; red embroidered yarn pixels may be adjusted alongside red fur.",
                   "Yellow/gold hues and near-neutral white/gray are protected by hue and saturation gates.",
                   "All atlas UV positions and baked motifs remain; this does not recover embroidery detail.",
                   "Actual Cycles/Standard emission-chip testing found no double-gamma in the previous create_png output."]}
    (output / "scarlet_palette_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    result = dict(bundle)
    result["maps"] = dict(bundle.get("maps", {}))
    result["maps"]["basecolor"] = image
    result["new_basecolor_image"] = image
    result["scarlet_report"] = report
    return result


def refine_master_palette(project_root=ROOT):
    """Reload master atlas texture nodes, recolor scarlet, reduce fiber whiteness.

    Call after opening master. Returns report. Caller saves the master. Repeated
    calls use the unchanged pre-scarlet PNG baseline and do not compound recolor.
    """
    root = Path(project_root).resolve()
    textures = root / "textures" / "generated"
    reloaded = []
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        for node in material.node_tree.nodes:
            if node.type != "TEX_IMAGE" or node.image is None:
                continue
            old = node.image
            filename = Path(bpy.path.abspath(old.filepath)).name
            if filename not in {"lion_basecolor_refined.png", "lion_basecolor_scarlet.png",
                                "lion_roughness_color_inferred.png", "lion_metallic_color_inferred.png",
                                "lion_weave_appearance_mask.png"}:
                continue
            source = textures / ("lion_basecolor_refined.png" if "basecolor" in filename else filename)
            image = bpy.data.images.load(str(source), check_existing=False)
            image.colorspace_settings.name = "sRGB" if "basecolor" in filename else "Non-Color"
            image.pack()
            node.image = image
            reloaded.append({"material": material.name, "node": node.name,
                             "path": str(source), "color_space": image.colorspace_settings.name})
    baseline = bpy.data.images.load(str(textures / "lion_basecolor_refined.png"), check_existing=False)
    baseline.colorspace_settings.name = "sRGB"
    bundle = refine_scarlet_palette({"pixels": image_pixels(baseline)}, textures)
    replaced = []
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                filename = Path(bpy.path.abspath(node.image.filepath)).name
                if filename in {"lion_basecolor_refined.png", "lion_basecolor_scarlet.png"}:
                    node.image = bundle["new_basecolor_image"]
                    replaced.append(material.name)
    fiber_updates = []
    for name, specular, sheen in (("Fiber_Red_Scarlet", .18, .16), ("Fiber_Warm_Ivory", .22, .20)):
        material = bpy.data.materials.get(name)
        if material is None:
            continue
        shader = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
        shader.inputs["Specular IOR Level"].default_value = specular
        shader.inputs["Sheen Weight"].default_value = sheen
        fiber_updates.append({"material": name, "specular_ior_level": specular, "sheen_weight": sheen})
    report = {"texture_file_reload": reloaded, "scarlet": bundle["scarlet_report"],
              "recolored_materials": sorted(set(replaced)), "fiber_response_updates": fiber_updates,
              "geometry_and_uv_changed": False, "master_saved_by_function": False}
    (root / "docs" / "master_palette_adjustment.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
