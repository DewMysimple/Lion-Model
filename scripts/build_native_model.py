"""Rebuild the accepted two-source lion inside a disposable staging project.

Invoked by build_model.ps1 with Blender's bundled Python. No cloud requests,
rendering or GLB export are performed. The existing modeling stages are reused.
"""
from pathlib import Path, PureWindowsPath
import argparse
import json
import os
import re
import runpy
import sys
import time
import traceback

import bpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-project", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    root = Path(__file__).resolve().parents[1]
    source = args.source_project.resolve()
    target = args.target.resolve()
    if root == source or root.name != "staging":
        raise ValueError("This driver must run from the isolated staging copy")
    if bpy.app.version[:2] != (5, 0):
        raise RuntimeError("The accepted reconstruction requires Blender 5.0.x")
    sys.path.insert(0, str(root / "scripts"))
    import refine_lion_master as pipeline

    skipped = []

    def skip_revision_render(name, *unused, **options):
        if not name.startswith("revision"):
            raise ValueError("Unexpected non-revision render requested by reconstruction")
        skipped.append(name)
        print("SKIPPED_REVISION_RENDER", name, flush=True)

    pipeline.render_view = skip_revision_render
    stages = []
    for filename in ("assemble_quality_revision.py", "correct_quality_material_boundaries.py",
                     "finalize_quality_revision.py", "apply_final_head_detail.py"):
        started = time.monotonic()
        print("BUILD_STAGE_START", filename, flush=True)
        runpy.run_path(str(root / "scripts" / filename), run_name="__main__")
        stages.append({"script": filename, "elapsed_seconds": time.monotonic() - started})
        print("BUILD_STAGE_DONE", filename, flush=True)

    # All image bytes must live in the native file. Metadata paths refer to the
    # final project location, never the staging directory that will be removed.
    image_records = []
    for image in bpy.data.images:
        if not image.has_data and not image.packed_file:
            continue
        if not image.packed_file:
            image.pack()
        old = image.filepath
        parts = PureWindowsPath(old).parts
        indexes = [i for i, part in enumerate(parts) if part.lower() == "textures"]
        if indexes:
            relative = Path(*parts[indexes[-1]:])
        else:
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", image.name)
            relative = Path("textures") / "packed" / (safe if Path(safe).suffix else safe + ".png")
        image.filepath = "//" + Path(os.path.relpath(source / relative, target.parent)).as_posix()
        image_records.append({"name": image.name, "filepath": image.filepath,
                              "packed": bool(image.packed_file), "size": list(image.size)})
    linked = [item.name for item in bpy.data.user_map() if getattr(item, "library", None)]
    if linked:
        raise RuntimeError("Reconstructed model unexpectedly has linked datablocks: " + ", ".join(linked))
    for library in list(bpy.data.libraries):
        bpy.data.libraries.remove(library)
    for item in bpy.data.user_map():
        for key in list(item.keys()):
            value = item.get(key)
            if isinstance(value, str) and str(root) in value:
                item[key] = value.replace(str(root), str(source))
    bpy.context.scene.render.filepath = str(source / "renders" / "final" / "hero.png")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(pipeline.MASTER), compress=True, relative_remap=False)
    report = {
        "schema": "lion-project.native-build-stages/v1", "status": "constructed",
        "blender_version": bpy.app.version_string, "stages": stages,
        "revision_renders_skipped": skipped, "images": image_records,
        "libraries": [], "linked_ids": [], "staged_master": str(pipeline.MASTER),
        "native_fiber_strands": sum(len(o.data.splines) for o in bpy.data.objects
                                    if o.type == "CURVE" and "fiber_emitter" in o),
        "scope": "Accepted four-stage reconstruction; publication requires fresh-process native verification."
    }
    args.result.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("NATIVE_BUILD_CONSTRUCTED", report["native_fiber_strands"], flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
