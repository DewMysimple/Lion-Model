# GLB inspection

Run from the project directory with a real generated GLB and a fresh output directory. Set `LION_BLENDER` to your executable; this workstation uses `F:\Blender\blender.exe`:

```powershell
$blenderBinary = if ($env:LION_BLENDER) { $env:LION_BLENDER } else { 'F:\Blender\blender.exe' }
& $blenderBinary --background --factory-startup --python-exit-code 1 --python .\scripts\inspect_generated_asset.py -- --input .\generated\Lux3D_Lion_Base_glb.glb --output-dir .\cache\new_import_inspection
```

Add `--render` to produce six 384px Eevee PNGs. The script saves `导入检查.blend` with orthographic cameras and an `asset_inspection.json` report. It packs imported images and preserves the source GLB, checking its SHA256 before and after import. Existing inspection output is rejected.

The report describes imported objects, original mesh topology, UV layers, materials, images, curves, armatures and animation data. Boundary edges are counted separately from other non-manifold edges. Mesh counts do not include evaluated modifiers or certify printability. Camera names use Blender world axes; they do not prove the asset's front direction. Render files require visual review. Imported object structure, hair and animation still require acceptance against the modeling brief.

Missing input fails before creating output, with nonzero process status when `--python-exit-code 1` is used. No placeholder model is created. This failure path was executed in Blender 5.0.0 during the original import work.

The normal path was also executed in Blender 5.0.0 using the real local `exports/components/Lion_Editable_Components.glb`. It imported 25 mesh objects, 5 hierarchy empties and 7 materials, saved the inspection `.blend`, and rendered all six 384px views. Each view was visually inspected with no object clipping; the two eyes overlap in side projection as expected. The source SHA256 remained unchanged. Retained inspection and verification records are under `docs/component_roundtrip_check/`.

`verify_component_roundtrip.py` reopens that saved inspection scene to compare its 30 node names/types/parents, mesh triangle counts and material slots against the source GLB. All checks passed, including seven standard PBR base colors, metallic factors and roughness factors, and all six PNG dimensions. The GLB does not contain the native procedural micro-bump. This verification concerns only the locally built eye/ring/bell components; it does not establish cloud generation or complete-lion acceptance. Image textures, curves, armatures and animation branches have not been exercised with a real input.
