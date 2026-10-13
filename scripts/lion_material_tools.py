"""Preserve a generated UV atlas and create bounded, color-derived PBR response.

This module executes in Blender. Color classes are heuristic appearance masks,
not recovered embroidery geometry or measured physical material maps. The source
atlas is copied byte-for-byte when packed, never edited in place. No API calls.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


from pathlib import Path
import hashlib
import json
import zipfile

import bpy
import numpy as np


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def linear_to_srgb(values):
    values = np.asarray(values, dtype=np.float32)
    return np.where(values <= 0.0031308, values * 12.92,
                    1.055 * np.power(np.maximum(values, 0), 1 / 2.4) - 0.055)


def srgb_to_linear(values):
    values = np.asarray(values, dtype=np.float32)
    return np.where(values <= 0.04045, values / 12.92,
                    np.power(np.maximum((values + 0.055) / 1.055, 0), 2.4))


def image_pixels(image):
    """Return RGBA pixels, bottom-left origin, in the image's stored color space.

    The generated source's 8-bit sRGB image has been checked against its original
    PNG bytes: these values are sRGB encoded, not scene-linear. Do not decode
    twice when sampling this source for appearance classification.
    """
    width, height = image.size
    rgba = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(rgba)
    return rgba.reshape(height, width, 4)


def find_basecolor_image(material):
    """Follow the Principled base-color input instead of trusting image names."""
    shaders = [node for node in material.node_tree.nodes
               if node.type == "BSDF_PRINCIPLED"]
    if not shaders:
        raise ValueError("Material has no Principled shader")
    visited = set()

    def trace(socket):
        for link in socket.links:
            node = link.from_node
            if node.as_pointer() in visited:
                continue
            visited.add(node.as_pointer())
            if node.type == "TEX_IMAGE" and node.image:
                return node.image
            for input_socket in node.inputs:
                found = trace(input_socket)
                if found:
                    return found
        return None

    image = trace(shaders[0].inputs["Base Color"])
    if image is None:
        raise ValueError("No base-color image connected to shader")
    return image


def extract_zip_sources(zip_path, output_dir):
    """Extract original files without interpreting unspecified filter channels."""
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = []
    with zipfile.ZipFile(zip_path) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            normalized = entry.filename.replace("\\", "/")
            target = (output / normalized).resolve()
            if not target.is_relative_to(output):
                raise ValueError("Archive path escapes extraction directory")
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(entry)
            if not target.exists():
                target.write_bytes(data)
            elif target.read_bytes() != data:
                raise FileExistsError("Existing source differs: %s" % target)
            records.append({"archive_entry": entry.filename, "path": str(target),
                            "bytes": len(data), "sha256": file_digest(target),
                            "interpretation": "Unmodified source; channel semantics unverified"})
    return records


def color_classes(rgba_srgb):
    """Return soft red/gold/white masks from perceptual color, without noise."""
    rgb = np.clip(rgba_srgb[..., :3], 0, 1)
    red, green, blue = np.moveaxis(rgb, -1, 0)
    maximum, minimum = rgb.max(axis=-1), rgb.min(axis=-1)
    saturation = (maximum - minimum) / np.maximum(maximum, 1e-5)
    red_mask = np.clip((red - green - 0.07) / 0.18, 0, 1)
    red_mask *= np.clip((red - blue - 0.08) / 0.22, 0, 1)
    red_mask *= np.clip((saturation - 0.25) / 0.25, 0, 1)
    # Reject orange/beige textile from the red-fur class using hue ratio.
    red_mask *= np.clip((0.68 - green / np.maximum(red, 1e-5)) / 0.25, 0, 1)
    gold_mask = np.clip((green - blue - 0.06) / 0.18, 0, 1)
    gold_mask *= np.clip((green / np.maximum(red, 1e-5) - 0.43) / 0.32, 0, 1)
    gold_mask *= np.clip((red - blue - 0.12) / 0.25, 0, 1)
    gold_mask *= (1 - red_mask) * np.clip((maximum - 0.28) / 0.35, 0, 1)
    white_mask = np.clip((0.24 - saturation) / 0.16, 0, 1)
    white_mask *= np.clip((minimum - 0.44) / 0.30, 0, 1)
    return {"red": red_mask, "gold": gold_mask, "white": white_mask,
            "srgb": rgb, "saturation": saturation}


def sample_uv_colors(rgba_srgb, uvs):
    """Sample original atlas in encoded sRGB. UVs wrap; rows start at bottom."""
    uvs = np.asarray(uvs, dtype=np.float32)
    height, width = rgba_srgb.shape[:2]
    x = np.floor(np.mod(uvs[..., 0], 1.0) * width).astype(np.int64)
    y = np.floor(np.mod(uvs[..., 1], 1.0) * height).astype(np.int64)
    return rgba_srgb[np.minimum(y, height - 1), np.minimum(x, width - 1), :3]


def create_png(name, data, path, color_space="Non-Color"):
    height, width = data.shape[:2]
    if data.ndim == 2:
        rgba = np.empty((height, width, 4), dtype=np.float32)
        rgba[..., :3] = data[..., None]
        rgba[..., 3] = 1
    else:
        rgba = np.array(data, dtype=np.float32, copy=True)
    image = bpy.data.images.new(name, width=width, height=height, alpha=True)
    image.colorspace_settings.name = color_space
    image.pixels.foreach_set(rgba.ravel())
    image.update()
    image.filepath_raw = str(Path(path).resolve())
    image.file_format = "PNG"
    image.save()
    image.pack()
    return image


def preserve_atlas(image, output, stem="original_basecolor_atlas"):
    """Save a source image byte-for-byte when its original packed bytes exist."""
    packed = image.packed_file
    if packed:
        data = bytes(packed.data)
        suffix = ".png" if data.startswith(b"\x89PNG") else ".jpg" if data[:2] == b"\xff\xd8" else ".bin"
        path = output / (stem + suffix)
        if path.exists() and path.read_bytes() != data:
            raise FileExistsError("Refusing to replace preserved atlas")
        if not path.exists():
            path.write_bytes(data)
    else:
        source = Path(bpy.path.abspath(image.filepath))
        if not source.is_file():
            raise FileNotFoundError("No original packed image or image file")
        path = output / (stem + source.suffix)
        if path.exists() and path.read_bytes() != source.read_bytes():
            raise FileExistsError("Refusing to replace preserved atlas")
        if not path.exists():
            path.write_bytes(source.read_bytes())
    return path


def prepare_lion_material(source_material, output_dir, *, weave=True):
    """Build and return a material bundle usable on meshes with the source UVs.

    Returns material, basecolor_image (original), pixels (original sRGB RGBA),
    adjusted_basecolor_image, maps, texture_paths, report. Atlas/UVs stay intact.
    No part classification is asserted. Gold/red/white maps are appearance guesses.
    """
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_image = find_basecolor_image(source_material)
    atlas_path = preserve_atlas(source_image, output)
    source_pixels = image_pixels(source_image)
    masks = color_classes(source_pixels)
    red_mask, gold_mask, white_mask = masks["red"], masks["gold"], masks["white"]
    rgb = masks["srgb"].copy()
    # Maintain baked motif boundaries while reducing pastel red and beige washout.
    red_adjusted = rgb * np.array([0.96, 0.88, 0.86], dtype=np.float32)
    rgb = rgb * (1 - red_mask[..., None]) + red_adjusted * red_mask[..., None]
    gold_adjusted = rgb * np.array([1.015, 1.005, 0.92], dtype=np.float32)
    rgb = np.clip(rgb * (1 - gold_mask[..., None]) + gold_adjusted * gold_mask[..., None], 0, 1)
    adjusted = source_pixels.copy()
    adjusted[..., :3] = rgb
    roughness = np.clip(0.72 + 0.12 * red_mask + 0.14 * white_mask - 0.25 * gold_mask, 0.45, 0.88)
    metallic = np.clip(0.48 * gold_mask, 0, 0.48)
    weave_mask = np.clip(1 - 0.86 * red_mask - 0.88 * white_mask, 0, 1)
    maps = {
        "basecolor": create_png("Lion_Atlas_Color_Refined", adjusted, output / "lion_basecolor_refined.png", "sRGB"),
        "roughness": create_png("Lion_Color_Derived_Roughness", roughness, output / "lion_roughness_color_inferred.png"),
        "metallic": create_png("Lion_Color_Derived_Metallic", metallic, output / "lion_metallic_color_inferred.png"),
        "weave_mask": create_png("Lion_Weave_Appearance_Mask", weave_mask, output / "lion_weave_appearance_mask.png"),
    }
    material = bpy.data.materials.new("Lion_Atlas_PBR_Refined")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (900, 80)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (630, 80)
    shader.inputs["Specular IOR Level"].default_value = 0.27
    shader.inputs["IOR"].default_value = 1.46
    shader.inputs["Coat Weight"].default_value = 0
    shader.inputs["Sheen Weight"].default_value = 0.12
    shader.inputs["Sheen Roughness"].default_value = 0.75
    links.new(shader.outputs["BSDF"], output_node.inputs["Surface"])
    coordinates = nodes.new("ShaderNodeTexCoord")
    coordinates.location = (-900, 0)
    image_nodes = {}
    for index, (key, image) in enumerate(maps.items()):
        node = nodes.new("ShaderNodeTexImage")
        node.name = "Lion_" + key
        node.label = key + " (same generated UV atlas)"
        node.image = image
        node.location = (-620, 500 - index * 270)
        links.new(coordinates.outputs["UV"], node.inputs["Vector"])
        image_nodes[key] = node
    links.new(image_nodes["basecolor"].outputs["Color"], shader.inputs["Base Color"])
    links.new(image_nodes["roughness"].outputs["Color"], shader.inputs["Roughness"])
    links.new(image_nodes["metallic"].outputs["Color"], shader.inputs["Metallic"])
    if weave:
        # Two regular perpendicular sine bands, not a stochastic noise coating.
        bands = []
        for axis, y in (("X", -480), ("Y", -700)):
            band = nodes.new("ShaderNodeTexWave")
            band.name = "Regular_Weave_" + axis
            band.wave_type = "BANDS"
            band.bands_direction = axis
            band.wave_profile = "SIN"
            band.location = (-340, y)
            band.inputs["Scale"].default_value = 100
            band.inputs["Distortion"].default_value = 0
            band.inputs["Detail"].default_value = 0
            links.new(coordinates.outputs["UV"], band.inputs["Vector"])
            bands.append(band)
        product = nodes.new("ShaderNodeMath")
        product.operation = "MULTIPLY"
        product.location = (-80, -480)
        links.new(bands[0].outputs["Fac"], product.inputs[0])
        links.new(bands[1].outputs["Fac"], product.inputs[1])
        mask_product = nodes.new("ShaderNodeMath")
        mask_product.operation = "MULTIPLY"
        mask_product.location = (150, -360)
        links.new(product.outputs[0], mask_product.inputs[0])
        links.new(image_nodes["weave_mask"].outputs["Color"], mask_product.inputs[1])
        bump = nodes.new("ShaderNodeBump")
        bump.location = (390, -180)
        bump.inputs["Strength"].default_value = 0.07
        bump.inputs["Distance"].default_value = 0.00065
        links.new(mask_product.outputs[0], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    material["appearance_inference"] = "Color-derived PBR only; not measured textile or recovered embroidery"
    material["source_atlas_sha256"] = file_digest(atlas_path)
    paths = {key: image.filepath_raw for key, image in maps.items()}
    report = {
        "source_material": source_material.name, "source_image": source_image.name,
        "source_atlas": str(atlas_path), "source_atlas_sha256": file_digest(atlas_path),
        "size": list(source_image.size), "source_pixels_space": "Stored encoded sRGB RGBA, bottom-left origin; empirically checked against original PNG bytes",
        "derived_maps": paths,
        "classification": "Soft masks derived from original perceptual RGB; same atlas and UVs",
        "roughness_range": [float(roughness.min()), float(roughness.max())],
        "metallic_range": [float(metallic.min()), float(metallic.max())],
        "mask_mean": {key: float(masks[key].mean()) for key in ("red", "gold", "white")},
        "limitations": [
            "Color cannot distinguish red fur from red embroidered cloth without spatial part classification.",
            "Gold color suggests partial metallic thread response; it does not prove metal composition.",
            "Baked highlights and shadows remain in original texture; exact reflectance cannot be recovered.",
            "Original 2048px motif atlas is retained; this does not reconstruct original embroidery stitches.",
            "Regular UV weave is a subtle generic microstructure; generated UV islands lack true textile warp directions.",
        ],
    }
    (output / "material_refinement_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"material": material, "basecolor_image": source_image, "pixels": source_pixels,
            "adjusted_basecolor_image": maps["basecolor"], "maps": maps,
            "texture_paths": paths, "report": report}


def apply_lion_material(objects, bundle):
    """Assign a prepared material without modifying source mesh positions or UVs."""
    material = bundle["material"] if isinstance(bundle, dict) else bundle
    for obj in objects:
        if obj.type != "MESH":
            continue
        if len(obj.data.materials):
            for index in range(len(obj.data.materials)):
                obj.data.materials[index] = material
        else:
            obj.data.materials.append(material)
