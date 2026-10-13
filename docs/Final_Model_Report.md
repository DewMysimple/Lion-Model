# Final Model Report

The supplied Cantonese lion reference has been developed into an editable Blender assembly with a clearer replacement head, dense native fibers, synthesized brocade and independent eye, tooth and metal details. All nineteen final render files were opened for artistic review. The result is a materially improved generated asset. Remaining crown, nose, leg and sheet-like hair defects do not support a claim of ultra-high-precision physical replication or uniformly clean closeup geometry.

The native master and uncompressed GLB passed independent stable-file checks for the recorded hashes. Independent compressed decoding/import and range-derived position/UV/normal checks also passed. A fresh relocation reopen found all fourteen images packed, no resolved linked IDs and no linked libraries. Current verification reports identify their actual input hashes and check times; rerun them after changing the model. Archive verification is reported in its adjacent sidecar after packaging.

## Sources and retained geometry

Both selected assets were generated through Aholo Lux3D, China region, version G1, with a requested target of 300,000 faces each. The supported request contract caps a single asset at 300,000 faces. The composite combines two real sources and local additions. A visually rejected G1Turbo candidate is not a source of the final scene.

| Source | Provider task | Actual source triangles | Retained native triangles |
|---|---|---:|---:|
| Complete lion | 4054240 | 286,200 | 242,792 |
| Separate head | 4055287 | 285,606 | 285,606 |
| Composite | Two selected sources | — | 528,398 |

The complete-lion head's 43,408 faces were intentionally replaced. Each retained native source face has a `source_face_index` and source-origin identifier. Independent QA confirms the two expected origin sets exactly once, with no missing or repeated retained IDs. Original UV data remain available.

Whole-lion submission began at `2026-10-11T22:07:04.377677+08:00`; download completed at `2026-10-11T22:13:12.673822+08:00`. Head submission began at `2026-10-11T15:40:17.930422+00:00`; download completed at `2026-10-11T15:47:00.233348+00:00`. These submission-to-download times exclude planning and local modeling. Provider server creation time and actual consumed credits were absent from the available task evidence and are not invented.

Original GLB SHA256 values:

- Whole lion: `10868714d52a4a4dbea9511ea4986738fdac4b39ba19ad858393f13b7255c3d4`.
- Separate head: `a32adcf39afbf971106d0ad6661ea32eee4dc783cfa2e45e11a7643e82a6fe13`.

Original GLBs and ZIPs remain under `generated/`. Source checks are in `lux3d_source_file_inspection.json` and `head_source_inspection.json`. Scene-execution evidence binds real final export hashes/tool calls to both selected sources. The compressed record is `scene_execution_draco.json`; its specification is `lux3d_delivery_spec_draco.json`.

## Actual local construction

Twenty editable source meshes sit under `Lion_Root`: body and separate wave trim; head, brows, crown, ears, jaw, beard and nose; four legs, four paws and tail. Named pivots, independent eyes and metal controls support selection and limited rigid movement. Eleven bevelled ivory teeth, fitted eye globes/rings, brass caps, bell shells and hanging tassels add local structure. Brows, nose and other features remain partly generated shells. No completed blink mechanism, skin deformation, costume interior or collision-free dance motion is supplied.

The stable master contains 980,957 native Bezier fiber strands in 66 fiber curve objects, with 3,121,088 control points. Red trim, white beard, paws and tail have distinct surface scopes. Fibers vary in length, bend, radius and clumping. They follow parent transforms; mesh deformation requires grooming regeneration or reattachment.

`textures/brocade_new/brocade_reference_synthesis.png` is a 1254 x 1254 AI synthesis guided by the reference's red/gold/dark floral character. It is a replacement design rather than precise embroidery recovery. `BrocadeCylinder_0p2m` uses body Y and an approximate elliptical X/Z cross-section on UV1, with a 0.20 m longitudinal repeat and underside seam. Fine border linework is imperfectly matched, so mathematical seamlessness is not claimed.

The real 2048 x 2048 `body_micro_weave_normal_2048.png` comes from a periodic procedural 128-thread interlacing field. A Non-Color image and standard UV1 NormalMap node use strength 0.18. This subtle woven response is not photometric measurement or modeled relief of every embroidered motif. Actual 0/0.18/0.25 study comparisons showed a small response under their lighting.

A conservative geometry/appearance audit recovered 2,394 flat cloth faces from the trim mesh, leaving 22,359 trim faces. Source IDs, Boolean mask and geometry features are included. Red fibers were regenerated with the inverse mask. Some uncertain red islands remain conservatively classified as trim. A forehead window applies the new tile to 371 original faces through `ForeheadPlane_XZ_0p2m`, preserving UV0 and protecting the central badge. Its new/old motif boundary is visible.

Three metal caps each have 32 bead objects and a five-petal wire ornament: 96 beads and three floral wires total. These are local design synthesis. Original source atlases remain elsewhere, with photographed highlights, softer markings and material boundaries.

## Baseline native and export measurements

| Property | Actual measurement |
|---|---|
| Original baseline native file | Blender 5.0.0; 194,707,673 bytes; a rebuilt save may differ |
| Asset objects | 256: 155 meshes, 69 curves, 32 empties |
| Source partitions / triangles | 20 / 528,398 retained native triangle IDs |
| Fiber strands / control points | 980,957 / 3,121,088 |
| Source bounds | Approximately 0.904041 x 1.603024 x 1.000000 m |
| Native image resources | Fourteen packed images; relocation reopen resolves no linked IDs/libraries |
| Uncompressed GLB | 188,900,300 bytes; 256 nodes, 224 meshes, 18 materials |
| Portable export triangles | 3,524,821 across actual triangular mesh primitives |
| Embedded GLB images | 7; no external core buffer/image dependency |
| Sampled strand proxies | 131,276 |
| Compressed GLB | 67,544,592 bytes; Draco level 7 |
| Draco configuration | Position 20 bits, UV 16 bits, normal 12 bits |
| Source triangles in GLB | 528,321 after 77 audited duplicate-vertex collapses |

Native source IDs remain unchanged. The 77 export reductions are proven duplicate-vertex groups, not a general allowance for missing geometry: body 13; head 42; brows 4; ears 6; jaw 2; beard 3; forelegs 3; hindleg 1; hindpaw 1; tail 2. Actual raw GLB accessor counts and independent Blender import counts match each source-part expectation.

The portable copy samples red fibers at stride 10, white fibers at stride 5 and tassels at stride 3 into exportable meshes. Native curves remain in the master. This changes density and silhouette detail. Draco uses lossy position, UV and normal quantization and requires a capable decoder. Compression does not establish mobile performance; full retopology, hair-card and production LOD sets are not delivered.

Recorded original baseline/export SHA256 values:

- Original native baseline: `60eac7eda5fc8b44ead32cf2507e13b076c6dd2833d285aceaa9c1cab9901cbe`.
- Uncompressed GLB: `45749d94450a21139cabfe4ac940be35ddeba5cb63926096090aa8dec3ce1e26`.
- Draco GLB: `67402920513a76600a05041e3e1fc880ae1a098794f06d54c00db88b2d42ac10`.

## Validation and visual review

`final_master_verification.json` passes stable master reopen, exact dual-source coverage, twenty partitions, `Lion_Root` hierarchy, packed images, native curves and bounded rigid-control isolation. File hashes before/after match. `final_glb_verification.json` passes independent uncompressed import, raw per-part counts, source/export bounds, retained control hierarchy and all audited duplicate reductions. These checks concern actual structure and tested controls; they do not prove precise artistic reconstruction.

Final beauty PNGs are `hero`, `front`, `left`, `right`, `back`, `top`, `head`, `eye`, `mouth`, `crown`, `body_trim`, `brocade`, `paw` and `tail` under `renders/final/`. Five clay views are `clay_front`, `clay_left`, `clay_right`, `clay_back` and `clay_top`. Hero is 1600 x 1100, other beauty views 1400 x 1000, and clay views 900 x 700. All nineteen real files were opened. The beauty inventory is `final_render_views.json`; the primary and independent secondary artistic reviews are `final_visual_review_primary.md` and `final_visual_review_secondary.md`. Draft and revision stills are excluded from archived final renders.

Views show a recognizable stance, layered trim, four paws and raised tail. New floral cloth is clearer; red/white curves add real silhouette fibers; eyes, teeth, caps, bead rings, floral wire and bells are visible. Defects remain material: blurry crown/nose artwork, inferred pale rear-head texture, and softer leg artwork/coarse shapes. Triangular or sheet-like generated hair remains at brows, ears, beard edges and tail. Cloth/trim borders are ragged with isolated red triangles; added detail can overlap source teeth or metal markings. Forehead cloth meets the old motif visibly. Clay views expose irregular/open shells and intentionally do not display complete colored grooming.

`final_draco_verification.json` passes independent Blender import plus actual decoder inspection of all 230 compressed primitives. Its 3,524,821 triangles, twenty source parts, hierarchy/transforms, materials and seven embedded texture byte hashes match the verified export expectations. Maximum source-part world-bound difference is 0.000000596046 m; maximum symmetric local vertex-set position distance is 0.000001145453 m. All measured UVs meet their actual primitive-range 16-bit budgets. Maximum compatible normal angle is 0.0590085 degrees, below the documented conservative 12-bit bound of 0.0911355 degrees.

Three already audited duplicate head groups retained different valid original members during the compressed/uncompressed exports: source-face pairs [61128, 75119], [101833, 101849] and [170867, 170868]. The nine affected corners were individually matched to actual native duplicate members, including position, both UV layers, normals and cyclic triangle winding; tolerances were not enlarged to hide disagreement. These triangles need not use the same UV/normal member as the uncompressed file. The remaining measurements compare unordered vertex attribute sets with compatible seam candidates, rather than proving every face-corner or all topology identical. Quantization settings are cross-checked against the completed export record; their bit counts are not independently extracted from the compressed bitstream.

Native rotation constraints do not transfer into standard glTF. Head, jaw and tail export motion lack active hard-stop constraints; only the sampled rigid pose range was verified. Compressed mesh proxies do not recreate native editable curves. Native master, uncompressed file and prior verification reports remained byte-identical throughout the read-only compressed check.

## Reconstructing the full local master

The root `build_model.cmd` is the Windows entry for a fresh clone: `build_model.cmd "F:\Blender\blender.exe"`. Supply the installed Blender binary, rather than its launcher. The delegated PowerShell builder fetches the necessary Git LFS inputs, stages a separate working project in the ignored cache and runs the actual accepted refinement chain:

1. `assemble_quality_revision.py`: combine the body and detailed head stages; add brocade, eyes, eleven teeth, caps, bells and tassels.
2. `correct_quality_material_boundaries.py`: restore atlas boundaries and regenerate selected head fibers.
3. `finalize_quality_revision.py`: apply the audited trim cloth mask, regenerate trim fibers and add native limits.
4. `apply_final_head_detail.py`: apply the forehead cloth window and the 96 beads/three floral wires.

The chain requires the body/head quality stages, source GLBs for provenance, the fitted landmark report, brocade/normal textures and audited trim mask/source-ID/features data. Native source-coverage QA also reads `Lion_Detailed_Parts.blend`. The production trim helper and material/groom modules remain included. Blender's bundled Python/NumPy run the construction; this does not call the provider or use additional generation credits. The old `refine_lion_master.py build` mode produces an earlier one-source stage and is not the full reconstruction entry.

The actual corrected CMD run completed in 117.621 seconds on Windows / Blender 5.0.0, constructing `cache/Lion_Builder_Final_Proof.blend` without copying the final master. The builder captured twelve data inputs and fifteen Python modules plus the CMD/PowerShell entries: twenty-nine input records. Fresh-process native QA before publication and after staging removal passed with zero errors/warnings, 256 asset objects, twenty source parts, 528,398 retained source triangles, 980,957 strands and 3,121,088 control points. All fourteen images were packed and had project-relative paths; no resolved linked libraries/IDs remained. The measured run is summarized by `docs/model_build_verification.json`.

The original file remained at SHA256 `60eac7eda5fc8b44ead32cf2507e13b076c6dd2833d285aceaa9c1cab9901cbe`. The separately saved proof is 194,703,053 bytes, SHA256 `8e0fffeb3915d8e7b2b7c83d22bb87f52afb59aaa628d8d01d90da21d17d9f60`. File byte identity is not claimed.

`scripts/compare_native_reconstruction.py` independently reopened both files without saving either. `docs/native_reconstruction_comparison.json` passes all 4,553 captured array fields and their stated semantics: mesh positions, source UV/custom-normal data, all native curve control points/handles/radii/tilt, hierarchy/matrices/rigid controls, fifteen bound material semantics and ten unique decoded image semantics. The corresponding exact-field asset fingerprint is `f50759a15f927d335ddbb3743fbcddb5ea72a09300a83d64cec04e07971c1ce2` in both files.

The comparison records 1,050 storage-order differences proven equivalent by canonical undirected edges and directed cyclic polygon-corner records. It also records 127 generated-normal/tooth-UV fields with last-bit arithmetic differences: maximum normal component difference `1.1920928955078125e-7`, maximum normal angle `0.0000071940246157` degrees, and tooth UV difference `5.960464477539063e-8`. Only recomputed normals of generated meshes without authored custom normals and UV interpolation of the eleven named tooth primitives receive one float32 unit-scale spacing, `2^-23`, after exact coordinates/topology correspondence. Source UVs/custom normals, source geometry and full curves stay exact; no general geometry tolerance was introduced. The exact-field fingerprint excludes only these separately measured fields and proven storage permutations.

`docs/native_reference_signature.json` preserves a portable initial-model reference so another environment can verify a rebuilt model without obtaining the original main file. The utility also supports `--expected-signature` comparison and `--capture` for a deliberately accepted new baseline. Scene lighting/cameras/render settings, unused datablocks, UI selection, path/save metadata and datablock naming are outside this asset comparison; it does not prove every byte or every scene setting identical. Both compared native files stayed byte-identical during the read-only proof. Actual reports contain zero errors, warnings or unsupported captured fields.

## Model-focused layout and continued editing

The editable master is the local generated `blender/Lion_Final_Master.blend`, excluded from Git upload. Retained construction inputs are in `blender/checkpoints/`, material/cloth experiments in `blender/studies/` and reusable examples in `blender/components/`. Original provider GLB/ZIP assets stay under `generated/`. Independent model exports remain `exports/scene.glb` and `exports/scene_draco.glb`. The compressed file needs a Draco-capable importer.

Fourteen beauty and five clay PNGs are under `renders/final/`; retained study comparisons are under `renders/studies/`. Textures, references, trim recovery arrays/features, scripts and model verification records remain available. Webpage preview bundles, browser dependencies and browser QA were removed as requested. The original model bytes were preserved during folder reorganization; later reconstruction saves are verified structurally rather than asserted byte-identical.

`docs/relocation_dependency_check.json` records the actual post-move Blender reopen: fourteen of fourteen images packed, libraries empty and linked IDs empty. The historical master report had listed an unused source-library datablock; that stale entry disappears on the fresh reopen. Moving construction files therefore did not introduce a resolved link dependency in the authoritative master. Some historical reports retain the original workstation paths for provenance; `scripts/project_paths.py` resolves current checkpoint/study paths without rewriting old evidence.

The root `AGENTS.md` integrates standard project memory under `wiki_memory/`. Later Agents should read its protocol, navigation and current state before editing, then save actual changes, verification scope and a recoverable next step. The memory checker establishes the required layout/readiness; human review and artifact checks are still needed to support the facts.

Git manages reconstruction scripts, documents and memory as text. The configured Git LFS patterns cover source/stage Blender inputs, GLB/FBX assets, original ZIPs, raster textures/renders and selection arrays; the final native master is ignored as requested. Coordinate one writer per tracked stage, use LFS locks when collaborating and commit reusable source/stage changes with the assets and evidence required to rebuild them. Changes saved only in the ignored local master are not propagated by Git. `delivery/`, `cache/`, logs and Blender recovery backups are ignored. The requested remote is [DewMysimple/Lion-Model](https://github.com/DewMysimple/Lion-Model); actual push status and revision belong in the current project memory.

After the local master has been built, the package script writes `delivery/Model_Delivery.zip` and adjacent `.verification.json` / `.sha256` files. It checks the three native/export PASS reports against current exact SHA256 and byte counts, inventories real native/model folders and includes the local editable master, root CMD entry, scripts, root configuration and project memory. The user's Git exclusion of the master does not remove it from local ZIP delivery. It excludes Git/LFS databases, delivery recursion, caches, logs, recovery files and webpage artifacts. After writing, it verifies ZIP CRC, every archived file against its inventoried source SHA256, sources unchanged during packaging, the stored manifest and the complete archive hash. With explicit `--replace`, the old delivery set remains until the new ZIP and metadata are prepared, followed by atomic file replacements with hard-link rollback protection. A process interruption can still leave a partial multi-file publication; checksum bindings and leftover temporary/rollback files expose that condition. Completed results are authoritative only when present in the new sidecar; a dry run is an inventory, not a completed package.

Editing, rendering, verification, LFS collaboration and package commands are documented in the root README. Preserve source IDs and UV0, inspect intersections when moving pivots and regenerate grooming when deforming a source surface. Exact crown/nose/leg reconstruction, clean hair/cloth boundaries and a proper deformation/blink rig remain work. Generated overlaps, open borders and inferred hidden surfaces prevent a watertight fabrication claim or an exact costume-interior reconstruction.
