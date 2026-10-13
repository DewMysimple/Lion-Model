# Isolated lion-head reference generation

Tool: built-in image_gen; reference-guided new image, not a measured recovery.
Inputs: `references/reference_original.jpg` (identity and four-view appearance),
`references/front.png` (facial layering and ornament placement), and
`references/left.png` (three-dimensional shell/cheek/ear appearance).

## English prompt

Use case: product-mockup
Asset type: a high-detail isolated lion-head reference image for subsequent 3D reconstruction.
Primary request: Produce ONE coherent photographic product image of only the complete head of the very same traditional Guangfu Cantonese southern dancing lion shown in the reference images. Change the composition to a slightly elevated 45-degree front three-quarter view showing the entire front and the viewer-left side of its head. Remove the entire cloth body, legs, paws and tail. Preserve the complete wide head shell, both ears, the small crown ornament, the open mouth and the complete hanging white beard. The lower edge ends naturally below the beard. Both sides' cheek bells and red hanging tassels remain attached to the head.
Input images: Image 1 is the original four-view montage and is the authoritative subject identity/color/material reference. Image 2 is the same lion's frontal detail view. Image 3 is the same lion's side view. Use them together to maintain the same object; do not copy the montage layout into the output.
Scene/backdrop: uniform plain medium gray studio background with clean empty space around and beneath the isolated head. No pedestal, mannequin, body stub, neck tube, text, collage, labels, props or watermark.
Style/medium: sharp photorealistic studio product photography of a real handmade ceremonial lion head, faithful to the specific references rather than a generic lion or cartoon. Even soft lighting, crisp material boundaries and deep readable focus throughout the head; no artificial bloom or painterly smoothing.
Composition/framing: single head centered, filling about 80 percent of the square frame, three-quarter angle at about 45 degrees yaw and very slight elevation. Keep both ears, crown, all bells/tassels, beard tips and all head silhouette in frame with safe margins.
Color palette: rich saturated scarlet red plush, warm golden embroidery and polished gold fittings, black/dark green brocade accents, ivory white fur and trim. Avoid pale pink, salmon, beige overall tint or a newly invented palette.
Materials/textures: abundant real scarlet fur on the long sharply curved eyebrow ridges and thick curled moustache/lip borders; the distinctive narrow white fur edges under the brows; layered white/red/black concentric eye surrounds; large dark convex glossy eyeballs with warm metal iris rings; separate warm polished spherical forehead metal medallion in its circular decorative mounting; the patterned forehead cap and small red/gold stacked crown; matching decorative cheek disks, small golden bells with readable slits and clappers, and fine vertically hanging red thread tassels. Keep the reference's actual ornate red/gold/dark traditional brocade and painted motifs visible between plush regions. Retain crisp rectangular ivory decorative teeth along the upper and lower open-mouth rim, a dark mouth cavity with the reference's red inner ornament, and long naturally clumped smooth white beard fibers.
Constraints: Maintain the reference head's wide imposing proportions, huge expressive eyes, steep arched brows, nose/muzzle motif and layered construction. Do not turn it into an animal skull, a short cute mascot, a fantasy beast or a cartoon. No extra horns, antennas, jewel clusters, handles, limbs or ornaments. Do not shrink the beard, close the mouth, omit the white square teeth or replace ornate patterns with random gold specks. Do not hallucinate a claim of scientifically recovered hidden embroidery; make a faithful visual synthesis from the provided views.

## Validation

Two built-in calls completed successfully. The first image had only a slight
three-quarter angle; it remains at `references/head_refined_front_bias.png`.
One targeted second call changed the camera yaw while retaining the first image's
subject. The selected output is `references/head_refined_three_quarter.png`.

Actual image inspection confirms one complete isolated head on gray, with no
body, legs, paws or tail. Both eyes are anatomically coherent: the near eye is
fully readable and the far eye is naturally foreshortened/partly occluded. Both
ears, crown, cheek fittings, hanging tassels, open mouth, separate decorative
ivory block teeth, and complete white beard are visible. Scarlet fur and existing
red/gold/dark motifs are much clearer than the first standard 3D model's renders.
The second view has a substantial three-quarter angle, approximately the requested
45 degrees visually; camera calibration is not available from a generated photo.

This is a synthesized input reference, not a 3D output or evidence that the final
model meets the original specification. Tiny pattern details and some ornamental
bead placement are interpretive; no recovery of real unseen embroidery is claimed.

## Targeted second-call prompt

Use case: precise-object-edit. Edit the FIRST image, the already isolated high-detail Guangfu lion head. Make only ONE targeted change: rotate the viewpoint substantially farther around the head to a TRUE roughly 45-degree front three-quarter view, exposing the viewer-left cheek/temple side clearly and showing substantial three-dimensional shell depth. The current first image is still too close to a frontal view. In the new view the nearer left eye and cheek disc are larger and fully readable; the farther eye is foreshortened, while both eyes remain present. The nose/moustache should visibly project beyond the farther cheek. View height remains only slightly above eye level.
Preserve the identity, proportions, exact saturated scarlet plush and narrow white edges, black convex glossy eyes and warm metallic rings, round gold forehead medallion, ornate red/gold/dark-green motifs, both ears, stacked red/gold crown, small cheek gold bells and their fine vertically hanging red tassels, the broad open mouth with clearly separated ivory rectangular decorative teeth, and the complete naturally clumped long white beard. The second and third reference images show the original same lion identity and side construction. Do not introduce new ornamental bead clusters or change motifs deliberately.
The output remains ONE coherent extremely sharp photorealistic product photo of ONLY the complete detached lion HEAD on plain uniform medium gray studio background. Absolutely no torso, body stub, neck tube, legs, paws, tail, pedestal, mannequin, text, collage or watermark. Keep all ears, crown, side tassels and beard tips in frame with clear safe margins, with clean empty gray background under the beard. Do not crop off the head or simplify its geometry. No cute squat cartoon, no pastel pink, no random gold specks. Preserve material clarity and the overall visual refinement of the first image; change camera yaw only.

## Tool evidence

- Mode: built-in image_gen with local referenced-image paths; no CLI/API fallback.
- First output: `C:/Users/Administrator/.codex/generated_images/01a12b59-de45-76a1-a6b7-b170b2a00070/exec-e0b86d7a-0c6d-4dab-b9f2-ef4733031e33.png`.
- Selected second output: `C:/Users/Administrator/.codex/generated_images/01a12b59-de45-76a1-a6b7-b170b2a00070/exec-1562bb61-3331-42a8-8618-47ddc96bc192.png`.
- Both originals are retained; selected image is copied into the project.
