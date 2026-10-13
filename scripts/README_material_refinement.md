# Generated lion material refinement

Run inside Blender 5.0. The source GLB is preserved and no API is called.

```python
from lion_material_tools import prepare_lion_material, apply_lion_material, sample_uv_colors, color_classes
bundle = prepare_lion_material(source_material, project_root / "textures" / "generated")
apply_lion_material(mesh_objects, bundle)
rgb = sample_uv_colors(bundle["pixels"], uvs)
classes = color_classes(rgb)
```

`bundle["pixels"]` is the original 2048px atlas as a `(height, width, 4)` NumPy
array. Rows begin at the bottom, matching UV coordinates. RGB values are the
stored sRGB encoded channels, verified against original PNG bytes. `sample_uv_colors`
returns encoded RGB. `basecolor_image` is the original image; `maps` contains the
real new color, roughness, metallic and weave appearance mask images.

Suggested initial red region filter: `r > .35`, `r-g > .12`, `r-b > .13`,
`saturation > .32`, plus anatomical region bounds. Suggested white filter:
`min(rgb) > .55`, `saturation < .22`, plus beard/sideburn/paw/tail region bounds.
Color filters alone do not distinguish fur from cloth or baked bright highlights.

`study_lion_materials.py` writes `blender/studies/Lion_Material_Study.blend`, original and
refined 512px front/side renders with identical geometry and lighting, and
`docs/material_study.json`. `docs/material_pixel_encoding_verification.json`
records the independent PNG/pixel color-space comparison. The material study
records an unchanged SHA256 for the original GLB.

Original packed atlas bytes remain in `textures/generated/original_basecolor_atlas.png`
and `original_metallicroughness_atlas.png`. All seven raw ZIP files are preserved
under `textures/generated/original_zip`. RawReflect/Gloss/Fresnel/Refract labels
are retained as supplied and their undocumented channel semantics are not asserted.

New response maps are appearance estimates from the real atlas colors. No random
gold flecks or invented embroidery motifs are added. Original baked highlights,
shadows and 2048px motif detail remain. These maps cannot recover physical thread
composition or original embroidery stitches. The small, regular perpendicular
Wave texture bump is stored in the Blender shader. A GLB export carries the PNG
color/roughness/metallic maps; it does not carry the same procedural weave bump.
