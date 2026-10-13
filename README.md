# Cantonese Lion Dance Model

An editable, reference-guided lion costume assembled from two Aholo Lux3D G1 assets and refined in Blender 5.0.0. The native assembly preserves 528,398 source triangles and 980,957 editable fiber strands, with clearer synthesized brocade, independent eyes, eleven added ivory teeth and metal ornaments.

The editable output is `blender/Lion_Final_Master.blend`, kept locally and excluded from Git. On a fresh clone, run `build_model.cmd "F:\Blender\blender.exe"` to reconstruct it from the versioned source stages before opening it in Blender. Crown, nose, legs and some hair boundaries still contain blurry textures or irregular generated surfaces. This is an improved generated model; exact physical reconstruction, clean closeup geometry and a finished animation rig remain development work. See [the model report](docs/Final_Model_Report.md) for measurements, provenance and known limitations.

## Project layout

| Location | Purpose |
|---|---|
| `blender/Lion_Final_Master.blend` | Local generated editable model and packed materials; excluded from Git |
| `build_model.cmd` | One-command Windows reconstruction entry |
| `blender/checkpoints/` | Versioned source stages retained for rebuilding, recovery and comparison |
| `blender/studies/` | Material, brocade, projection and recovery experiments |
| `blender/studies/import_checks/` | Imported source/component inspection scenes; matching reports remain in `docs/` |
| `blender/components/` | Reusable component and fiber examples |
| `exports/scene.glb` | Uncompressed portable model; 188,900,300 bytes |
| `exports/scene_draco.glb` | Compressed model; 67,544,592 bytes; requires Draco support |
| `exports/studies/` and `exports/components/` | Earlier stage exports and reusable component models |
| `generated/` | Original provider GLB/ZIP assets and candidate resources |
| `textures/` and `references/` | Source atlases, added textures, supplied image and brief |
| `renders/final/` | Fourteen beauty and five clay inspection views |
| `renders/studies/` | Retained modeling/material comparisons |
| `scripts/` and `docs/` | Modeling utilities, checks, measured results and art reviews |
| `wiki_memory/` | Standard project memory for later Agent work |
| `delivery/` | Local ZIP, SHA256 and verification sidecars; excluded from Git |
| `cache/` | Regenerable temporary export copy; excluded from Git |

Webpage preview bundles and browser tooling were removed at the user's request. Blender and the model files are the working deliverables.

## Editing and Agent handoff

Before an Agent task, follow [AGENTS.md](AGENTS.md), [the memory protocol](wiki_memory/AGENTS.md) and [memory navigation](wiki_memory/README.md). Read the current overview, constraints and todo pages, then the affected model/material knowledge. Update evidence, decisions, known issues and the next recovery step after authorized changes.

In Blender, begin with `Lion_Root` and named `Pivot_*` controls. Twenty source meshes retain origin IDs and UV0. Local controls allow limited rigid movement; they do not provide skinned dance motion or a completed blink mechanism. Curves follow parent transforms, but surface deformation requires grooming regeneration or reattachment. Save experimental alternatives in `blender/studies/`; preserve a useful checkpoint before replacing the master.

The full fibers stay editable in the master. GLB exports contain 131,276 sampled mesh strands, approximately one red strand in ten, one white strand in five and one tassel strand in three. Exporting reduces hair density and loses Blender rotation constraints. Source scale is a design height of 1 m, Z up and front -Y; it is not a measured costume dimension.

Brocade uses a 1254 x 1254 reference-inspired synthetic tile at a 0.20 m repeat on UV1, with a 2048 x 2048 procedural weave normal map. Its pattern and local cap engraving do not reproduce the exact photographed embroidery. The model retains overlaps, open boundaries and sheet-like fragments, and is not a watertight fabrication model.

## Rebuild after cloning

Install Git, Git LFS and Blender 5.0.0. Clone without initially downloading every large experiment, then run this in Windows CMD:

```bat
git lfs install
set "GIT_LFS_SKIP_SMUDGE=1"
git clone https://github.com/DewMysimple/Lion-Model.git
cd Lion-Model
set "GIT_LFS_SKIP_SMUDGE="
build_model.cmd "F:\Blender\blender.exe"
```

Use your actual `blender.exe` path. With no argument, the builder uses `LION_BLENDER`, then the known `F:\Blender\blender.exe` or a `blender` executable on PATH. The CMD entry delegates to the PowerShell builder, obtains the twelve required data inputs through targeted Git LFS hydration and reconstructs the current full model through assembly, material correction, trim recovery/grooming and final head detail. Blender supplies Python and NumPy; this reconstruction does not request new Lux3D generations or consume generation credits.

The builder stages work in the ignored cache and validates the full editable result before publishing `blender/Lion_Final_Master.blend`. A second fresh Blender process reopens the actual output after staging is removed. Logs and reports are under `cache/builds/<run>/`, including `build_result.json`, `construction.json` and `native_verification.json`. This recipe reproduces the source geometry, native curves and added ornaments rather than importing the reduced GLB proxy. A newly saved Blender file need not have the original archive SHA256 because save metadata and paths differ. The real CMD reconstruction passed on Windows/Blender 5.0.0 in 117.621 seconds: 256 asset objects, twenty source parts, 528,398 source triangles, 980,957 native strands and 3,121,088 fiber control points. A read-only comparison with the original master also passed: positions, source UV/custom normals, full curves, transforms, constraints, shaders and decoded images match exactly. Generated primitive storage order differs; its topology/corner correspondence is proven. Only recomputed primitive normals and tooth UV interpolation differ by at most 1.1921e-7 and 5.9605e-8 respectively, within the disclosed one-spacing float32 budget. See `docs/model_build_verification.json` and `docs/native_reconstruction_comparison.json` for actual evidence.

An existing output is preserved. Choose another `.blend` path as a second argument for a trial build, or explicitly add `-Force` to replace the local master after verification while keeping a timestamped backup. Use `-NoLfsPull` when all required inputs are already local, and `-Help` for the command contract.

## Git and Git LFS

The requested remote is [DewMysimple/Lion-Model](https://github.com/DewMysimple/Lion-Model). The main `Lion_Final_Master.blend` is ignored and is not part of the Git upload. Reconstruction scripts and required stage assets remain versioned; stage Blender files, portable models, raster textures/renders, provider ZIPs and selection arrays use Git LFS through `.gitattributes`. To obtain optional studies or other binary files after a minimal clone, run `git lfs pull`.

Coordinate one writer per tracked `.blend` stage; Git cannot merge two Blender edits. Use Git LFS locks for shared stage edits when needed. Save reusable model changes in source/stage inputs or reconstruction scripts and commit them with required textures, verification evidence and memory updates. An edit saved only to the ignored local master will not reach another environment through Git. Commit exports and final renders when they represent intended deliverables. Delivery archives, caches, logs and Blender recovery files remain local.

## Verification and packaging

Run in the project root with Blender 5.0.0; adjust the executable path for another machine. The ancillary memory/package commands below use a Python 3.10+ executable; reconstruction itself uses Blender's bundled Python:

```powershell
powershell -NoProfile -File scripts/run_final_lion_verification.ps1
& 'F:\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/verify_draco_lion.py -- --root .
python wiki_memory/工具/memory.py index --project . --apply
python wiki_memory/工具/memory.py check --project . --require-ready
python scripts/package_lion_delivery.py --dry-run
```

The model verifiers check the current two-source structure, source coverage, image packing, controls and export comparisons. Planned topology/source changes may require updating those expectations with documented evidence. Technical passes do not certify photographic fidelity; inspect beauty and clay views.

For optional comparison against the versioned initial-model signature, use Blender with `scripts/compare_native_reconstruction.py -- --expected-signature docs/native_reference_signature.json --rebuilt blender/Lion_Final_Master.blend --report cache/native_signature_check.json`. Run this through the same `--background --factory-startup --python-exit-code 1 --python` flags shown above. It verifies asset data; scene cameras, lighting, UI selection and path/save metadata are outside its scope. After accepted model/source changes, deliberately refresh the baseline signature instead of treating the original shape as a permanent constraint.

Render current master views with `& 'F:\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/refine_lion_master.py -- render`. This writes the nineteen final PNGs and their inventory. The script's historical `build` mode reconstructs an earlier one-source stage; it does not reproduce every subsequent refinement automatically.

Build the local master first in a fresh clone and rerun `scripts/run_final_lion_verification.ps1` to bind the core report to its new save hash; the builder's cache report does not replace that delivery report. After stable checks, run `python scripts/package_lion_delivery.py` to create `delivery/Model_Delivery.zip`. Existing outputs are preserved by default. Use `--replace` to regenerate the existing delivery set, or choose a separate filename with `--output delivery/Model_Delivery_<revision>.zip`. Replacement keeps the old set until the new ZIP passes CRC/source-hash checks and new metadata are ready; each file is then atomically replaced, with rollback protection for ordinary publication errors. The three files are separate filesystem updates, so after a process interruption inspect leftover `.partial`/`.rollback` files and verify the final checksum.

The local package includes the real local `.blend` master, source/model resources, the CMD entry, scripts and memory. Excluding the master from Git does not exclude it from this local model delivery. It verifies ZIP CRC, every included source SHA256, unchanged source bytes during packaging and the whole archive SHA256. Its internal `package_manifest.json` inventories actual files; adjacent `.verification.json` and `.sha256` record completed archive checks without circular hash references.
