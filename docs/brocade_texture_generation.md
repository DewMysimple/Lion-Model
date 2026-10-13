# Reference-guided synthetic brocade texture experiment

This is a newly synthesized textile design inspired by the user's reference
lion's gold/red/dark motifs. It is not an exact recovery of the original woven
pattern, an authentic historical fabric record, or a measured reflectance map.
Original reference photos and original model atlases remain unchanged.

Tool: built-in image_gen. Exactly one texture-generation call is authorized for
this experiment; no Lux3D call. Intended destination: `textures/brocade_new`.

## English prompt

Use case: product-mockup
Asset type: seamless square flat base-color textile tile for a ceremonial Guangfu Cantonese lion cloth material.
Input images: the original multi-view photograph and the lion's side photograph are color, textile density and traditional scroll/floral motif references only. This output is a new design synthesis inspired by the real reference textile, not a claimed extraction or reconstruction of its exact motifs.
Primary request: Generate ONE high-resolution perfectly flat orthographic square seamless repeating brocade fabric texture tile. Fill the whole square edge to edge, with no border. Use a deep warm scarlet red woven ground, very fine warm gold thread ornament as the dominant design, and restrained dark black-green accents. Use small coherent traditional curved cloud scrolls, flower/petal medallions, curling vine and leaf forms inspired by the actual red/gold/dark-green cloth shown on the reference lion. Organize the pattern as a dense elegant multi-motif repeating brocade, with roughly 5-6 small main floral/scroll motif units across the tile and finer gold-thread curls and outlines between them. Motifs must be distinguishable and finely drawn, not random gold dots, melted paint or decorative noise.
Materials: real woven textile appearance, subtle regular warp/weft thread structure, crisp delicate embroidery-like gold lines embedded in the cloth. No sculpted relief, thick engraved metal, inflated forms, shiny gold sheet, random flecks or gritty noise. This is a usable BASE-COLOR map with even neutral diffuse illumination, no lighting highlights, directional shadows, baked folds or specular reflections.
Composition: front-facing flat 2D textile surface, no perspective, no draping, no body, lion face, fur, bells, tassels, clothing silhouette, photography set, objects or text. Every edge must connect naturally to the opposite edge under tiling on both axes; complete flowing motif continuity at seams. Keep no frame or outer solid-color margin. Uniform detail density and color balance throughout the square.
Output clarity: fine material detail and clear motif boundaries at the largest practical square resolution. Red ground remains deep warm red, gold remains warm gold, dark accents remain near-black green. No pale pink/beige recoloring, no typography, labels, logo or watermark. Do not include a tiled preview collage; return the single tile itself.

## Validation

One built-in call completed successfully in 28.8 seconds. The selected original
is copied to `textures/brocade_new/brocade_reference_synthesis.png`, 1254x1254px,
with SHA256 `75b4c86681f9363c622f8ec33b537efa8d08e8a282523a7d8a70ba37a705496c`.
It was inspected as a standalone image and as a real 3x3 repeated texture on a
Blender plane under a flat emission shader with Standard color management. The
repeat render is `textures/brocade_new/brocade_three_by_three_repeat.png`.

Actual inspection: flat red/gold/dark-green floral/cloud textile, clear coherent
motifs and fine regular woven detail, no draping/perspective/body/fur/text, no
empty border. No pronounced continuous light/dark seam band appears in the 3x3
repeat. A few fine vine outlines misalign at repeated boundaries. This is an
approximately tileable visual design, not a mathematically proven seamless tile.
No second generation or image retouching was performed.

Suggested physical tile: 0.18-0.25m. At 0.25m, main medallions are about 6-8cm
wide and the smallest flower units about 1-2cm. Begin at 0.20-0.22m for denser
cloth ornamentation and judge actual model renders. Leave the generated image's
horizontal/vertical axes unchanged; use horizontal repeat around the torso and
vertical repeat along its Y length. Place the cylindrical wrap discontinuity on
the belly/hidden surface, not a prominent side cloth panel.

The warm gold is a base-color design color, not measured metal reflectance.
Roughness and metallic response still require a separate material design.

## Generation provenance

- Inputs: `references/reference_original.jpg`, `references/left.png`.
- Built-in image_gen original output:
  `C:/Users/Administrator/.codex/generated_images/01a12b59-de45-76a1-a6b7-b170b2a00070/exec-c90fad09-6ff9-4cbc-8fdf-020d6e46295e.png`.
- The original generated PNG remains in place, and the reference originals remain
  unchanged. This is a new reference-inspired design synthesis.
