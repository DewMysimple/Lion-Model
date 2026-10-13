# G1 trim / printed-cloth recovery study

This is a conservative repair of the original source-face partition. Color
alone incorrectly classified printed red cloth as red fur. The recovery mask
uses the original atlas, actual source UV0, original face IDs, local normal and
triangle-density measurements, nearby intact cloth-plane support, and one
shared-edge expansion pass. It is specific to the G1 source and normalized
geometry, not transferable to another cloud candidate.

The final mask recovers 2,394 of 24,753 Trim faces, covering 0.41535 square
meters of the reconstructed surface. It retains 22,359 faces as scarlet trim.
The percentage of faces differs from the area percentage because cloth uses
larger triangles than the densely triangulated raised waves.

The unchanged positive-X orthographic camera has target (0, .19, .46), scale
.68, and 960 by 640 output. In the actual comparison the large blurry red
cloth islands in the central/left lower fields become continuous brocade;
the convex wave ridges remain red. Some ambiguous small red islands remain,
especially at trim junctions. No full semantic or anatomical separation is
claimed. All curves are hidden only in the diagnostic copy to expose the
material boundaries. The curves are preserved and not silently deleted.

Actual ray probes confirm source face 266756 (Trim polygon 23181) is a coarse
flat printed patch selected for recovery. Polygon 23996 / source face 268437
has a fine pure-red texture and a convex fold; it remains trim. The additional
coarse flat side-sheet examples 23149, 23151, 23154, 23173 and 23176 are
selected even when a 21mm neighborhood includes another nearby sheet and
therefore gives an unreliable signed-height/plane-RMS estimate.

## Integration

```python
from recover_trim_cloth import load_recovery_mask, apply_trim_cloth_recovery

trim = bpy.data.objects["Lion_Body_Red_Trim"]
mask = load_recovery_mask(trim, ROOT)
result = apply_trim_cloth_recovery(trim, mask, ROOT)

# Remove old Trim-only fiber objects, then regenerate its true-fur roots:
triangle_filter = lambda triangle: not mask[triangle["polygon_index"]]
```

`load_recovery_mask` verifies exact source-face order and original world
triangle centroids. `apply_trim_cloth_recovery` uses the delivery agent's
single-image cylinder material at the same .20m world tile scale as Body.
It changes only selected material assignments, adds UV1 and a Boolean FACE
attribute `recovered_brocade_face`, and preserves UV0, topology, positions,
normals, original face IDs and all unselected material indices. Call it before
Trim cylinder UV has been added; the helper rejects duplicate study UV.

The new brocade PNG is an explicitly synthesized reference-inspired design.
It is not the exact recovered reference motif. Its Repeat test is visually
approximate and can still show small edge-stroke discontinuities.

## Actual artifacts

- `blender/Lion_Trim_Cloth_Recovery_Study.blend`
- `docs/trim_cloth_recovery_mask.npy` (np.bool_, one entry per actual polygon)
- `docs/trim_cloth_recovery_source_ids.npy` (matching original FACE provenance)
- `docs/trim_geometry_features.npz` (original measured source geometry/color)
- `docs/trim_cloth_recovery_report.json`
- `docs/trim_cloth_recovery_reopen_verification.json`
- `renders/trim_cloth_recovery/mask_diagnostic.png` (green recovered cloth,
  red retained trim, gray remaining Body)
- `renders/trim_cloth_recovery/before_trim_recovery.png`
- `renders/trim_cloth_recovery/after_trim_recovery.png`

The input `Lion_Body_Quality_Stage.blend` and `Lion_Final_Master.blend` were
read only and their hashes were checked unchanged after the study. Body's
brocade selection in the study is the existing cylinder helper's broad
garment gate; this Trim repair does not prove that every Body triangle near
raised trim caps is cloth. Native curves require regeneration after mesh
deformation or any change to the recovery mask.
