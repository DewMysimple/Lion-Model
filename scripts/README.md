# Local Blender workflow

The editable model is `blender/Lion_Final_Master.blend`. Continue modeling in that scene, and save separate versions under `blender/checkpoints/` before substantial changes. `blender/studies/` holds material and geometry comparisons; `blender/components/` holds reusable parts. Final exchange models are `exports/scene.glb` and `exports/scene_draco.glb`; experimental GLBs are under `exports/studies/`. Original provider GLB/ZIP files, reference images and texture atlases stay under `generated/`, `references/` and `textures/`.

`project_paths.py` derives the project root from its own location. `blend_path()` resolves the stable master and the reorganized checkpoints/studies. Scripts bootstrap sibling imports when run with Blender's `--python` from another working directory. The current executable is `F:\Blender\blender.exe`; set `LION_BLENDER` to use another installation.

## Rebuild the native master on another Windows machine

The main `.blend` is a local build output. From the cloned project directory, run this command in CMD with Blender 5.0.x installed:

```cmd
build_model.cmd "F:\Blender\blender.exe"
```

This reconstructs the accepted two-source model into `blender/Lion_Final_Master.blend` using tracked Body Quality Stage, Head Quality Stage v2, original source GLBs, brocade textures, landmarks and audited trim selection data. Git LFS is needed to download build inputs when the checkout still contains pointers; the command fetches only the required inputs rather than every historical asset. Blender's bundled Python and NumPy run all modeling stages. No cloud generation, separate Python installation, renders or GLB export are required.

Existing output is preserved by default. Choose a second output argument to compare a fresh build with local edits:

```cmd
build_model.cmd "F:\Blender\blender.exe" "cache\Lion_Reconstructed_Test.blend" -NoLfsPull
```

Relative outputs are resolved against this project. `-Force` explicitly allows replacement and keeps a timestamped backup; `-NoLfsPull` disables automatic LFS fetching; `-Help` displays usage. Omitting the first argument uses `LION_BLENDER`, the known workstation executable or Blender on PATH through the PowerShell entry point.

Construction runs in isolated copies under `cache/builds/`. The exact accepted sequence is assembly, material-boundary correction, audited trim recovery and final head ornaments. Only intermediate revision rendering is suppressed. A new Blender process must verify the native model before publication. Staging is then removed, and another fresh process verifies the actual output. Logs, source SHA256 inventory, timings and native verification remain in that run's `cache/builds/<run>/build_result.json`, `construction.json` and `native_verification.json`. These reports describe the reconstructed file; they do not overwrite the project's existing model verification records.

Run the independent native-master, uncompressed-GLB and Draco checks from the project directory:

```powershell
$env:LION_BLENDER = 'F:\Blender\blender.exe'
.\scripts\run_final_lion_verification.ps1 -Draco
```

`-MasterOnly` or `-GlbOnly` selects one basic mode. These commands reopen/import the real files in fresh Blender processes and write verification JSON; they do not save the models. Dual-source native verification also reads `blender/checkpoints/Lion_Detailed_Parts.blend` to establish the original retained body-face set. Draco verification reads both final GLBs, the native/GLB reports, and the completed Draco export settings. It needs no cached proxy `.blend`.

Render or export the existing master with:

```powershell
& $env:LION_BLENDER --background --factory-startup --python-exit-code 1 --python .\scripts\refine_lion_master.py -- render
& $env:LION_BLENDER --background --factory-startup --python-exit-code 1 --python .\scripts\refine_lion_master.py -- export
& $env:LION_BLENDER --background --factory-startup --python-exit-code 1 --python .\scripts\refine_lion_master.py -- export --draco
```

Rendering replaces the named final render outputs. Historical draft/revision comparisons go to `renders/studies/final_revisions/`. Exporting replaces the matching final GLB/report and creates a sampled mesh-fiber proxy scene under ignored `cache/`. Native curves remain editable in the master. Existing proxy object names and metadata retain their historical spellings for model/report compatibility.

The `build` mode reconstructs an earlier single-source stage and overwrites the master; it is not the entry point for continuing the accepted two-source assembly. Historical assembly scripts also write the master. Inspect their inputs and save a checkpoint before deliberately rerunning them.

Source inspection scenes are stored in `blender/studies/import_checks/`, with matching reports and diagnostic PNGs under `docs/`. `inspect_generated_asset.py` defaults to that native scene directory; `--blend-output` can select an explicit scene path. CLI source/report paths resolve from the project root, and existing outputs are preserved.

Accepted assembly uses Body Quality Stage and Head Quality Stage v2, followed by material-boundary correction, trim-cloth recovery and head ornament additions. Imported production helpers include `study_brocade_cylinder.py`, `study_head_forehead_brocade.py` and `probe_trim_cloth_recovery.py`. Preserve these helpers and the trim recovery `.npy/.npz` data even though their names describe studies or probes. Study renders are organized under `renders/studies/`.

Technical verification does not certify artistic fidelity, clean retopology, skin deformation or ultra-high-precision replication. Review the actual model and new renders against the reference after editing. Existing JSON measurements describe the exact model revision and hashes checked at that time.
