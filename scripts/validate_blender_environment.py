"""Read-only Blender capability probe; writes JSON evidence, never a .blend file.

Run with:
  blender.exe --background --factory-startup --python validate_blender_environment.py
The default evidence path is ../docs/blender_environment.json.
An optional argument after '--' overrides that path.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path


import datetime
import json
import pathlib
import platform
import shutil
import subprocess
import sys
import traceback

import bpy


def decode(value):
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def inspect_operator(namespace, name):
    """Check registration and RNA without importing/exporting a test asset."""
    try:
        operator = getattr(getattr(bpy.ops, namespace), name)
        rna = operator.get_rna_type()
        return {
            "registered": True,
            "identifier": rna.identifier,
            "property_names": [prop.identifier for prop in rna.properties],
        }
    except Exception as exc:
        return {"registered": False, "error": str(exc)}


def inspect_cycles():
    result = {
        "compiled": bool(getattr(bpy.app.build_options, "cycles", False)),
        "backend_probes": {},
        "optix_gpu_available": False,
        "cuda_gpu_available": False,
        "render_executed": False,
        "scope": "Device enumeration only; no GPU kernel/render benchmark is claimed.",
    }
    addon = bpy.context.preferences.addons.get("cycles")
    if addon is None:
        result["error"] = "Cycles preferences are not registered."
        return result

    preferences = addon.preferences
    original_backend = preferences.compute_device_type
    try:
        for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            probe = {"supported_setting": False, "devices": []}
            result["backend_probes"][backend] = probe
            try:
                preferences.compute_device_type = backend
                probe["supported_setting"] = True
                preferences.refresh_devices()
                probe["devices"] = [
                    {
                        "name": device.name,
                        "type": device.type,
                        "id": device.id,
                        "enabled_in_session": bool(device.use),
                    }
                    for device in preferences.devices
                ]
                available = any(device["type"] == backend for device in probe["devices"])
                probe["gpu_device_enumerated"] = available
                if backend in ("OPTIX", "CUDA"):
                    result[backend.lower() + "_gpu_available"] = available
            except Exception as exc:
                probe["error"] = str(exc)
    finally:
        preferences.compute_device_type = original_backend
    result["preferred_backend"] = (
        "OPTIX" if result["optix_gpu_available"]
        else "CUDA" if result["cuda_gpu_available"]
        else "CPU"
    )
    return result


def inspect_nvidia():
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {"available": False}
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return {
            "available": completed.returncode == 0,
            "query_fields": ["name", "memory.total (MiB)", "driver_version"],
            "rows": completed.stdout.strip().splitlines(),
            "returncode": completed.returncode,
            "error": completed.stderr.strip() or None,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def main():
    output_path = ROOT / "docs" / "blender_environment.json"
    if "--" in sys.argv:
        arguments = sys.argv[sys.argv.index("--") + 1:]
        if arguments:
            output_path = pathlib.Path(arguments[0]).resolve()

    evidence = {
        "schema_version": 1,
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "purpose": "Verify the installed Blender environment before processing the user's generated lion asset.",
        "safety": {
            "background": bool(bpy.app.background),
            "blend_saved": False,
            "scene_created_or_modified": False,
            "user_preferences_saved": False,
        },
        "blender": {
            "version": bpy.app.version_string,
            "version_tuple": list(bpy.app.version),
            "binary_path": bpy.app.binary_path,
            "build_hash": decode(bpy.app.build_hash),
            "build_date": decode(bpy.app.build_date),
            "build_platform": decode(bpy.app.build_platform),
        },
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        },
        "gltf": {
            "import": inspect_operator("import_scene", "gltf"),
            "export": inspect_operator("export_scene", "gltf"),
            "roundtrip_executed": False,
            "scope": "Operator registration/RNA only; no placeholder asset was created.",
        },
        "cycles": inspect_cycles(),
        "nvidia": inspect_nvidia(),
    }
    evidence["checks"] = {
        "background_mode": evidence["safety"]["background"],
        "blender_5_or_newer": bpy.app.version >= (5, 0, 0),
        "gltf_import_operator": evidence["gltf"]["import"]["registered"],
        "gltf_export_operator": evidence["gltf"]["export"]["registered"],
        "cycles_compiled": evidence["cycles"]["compiled"],
        "optix_gpu_enumerated": evidence["cycles"]["optix_gpu_available"],
    }
    evidence["all_required_checks_passed"] = all(evidence["checks"].values())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ENVIRONMENT_EVIDENCE: " + str(output_path))
    print("ENVIRONMENT_CHECKS: " + json.dumps(evidence["checks"], ensure_ascii=False))
    print("ENVIRONMENT_PREFERRED_CYCLES_BACKEND: " + evidence["cycles"]["preferred_backend"])
    if not evidence["all_required_checks_passed"]:
        raise RuntimeError("One or more required environment checks failed; see the JSON evidence.")


if __name__ == "__main__":
    main()
