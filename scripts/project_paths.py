"""Project-relative paths shared by the local Blender modeling tools.

This module has no Blender dependency and creates no directories on import.
Set LION_BLENDER to the actual blender executable when using another machine.
"""
from pathlib import Path, PureWindowsPath
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
BLENDER = ROOT / "blender"
CHECKPOINTS = BLENDER / "checkpoints"
STUDIES = BLENDER / "studies"
COMPONENTS = BLENDER / "components"
CACHE = ROOT / "cache"
EXPORT_STUDIES = ROOT / "exports" / "studies"
MASTER = BLENDER / "Lion_Final_Master.blend"
STUDY_INPUT_NAMES = {"Lion_Head_Cloth_Input_Copy.blend", "Brocade_Tile_Probe.blend"}


def blend_path(name, root=ROOT):
    """Resolve a native stage by name, keeping the editable master stable."""
    name = Path(name).name
    if not name.lower().endswith(".blend"):
        raise ValueError("Expected a .blend file name")
    base = Path(root) / "blender"
    if name == "Lion_Final_Master.blend":
        return base / name
    if "study" in name.lower() or name in STUDY_INPUT_NAMES:
        return base / "studies" / name
    return base / "checkpoints" / name


def resolve_project_path(value, root=ROOT):
    """Interpret a CLI path relative to the project instead of the caller's cwd."""
    path = Path(value).expanduser()
    return (path if path.is_absolute() else Path(root) / path).resolve()


def resolve_recorded_path(value, root=ROOT):
    """Resolve historical project-local paths without rewriting evidence records.

    Reports retain the original workstation path. Their artifact hashes must be
    checked against this project's relocated file, including moved native stages.
    """
    parts = PureWindowsPath(str(value)).parts
    markers = {"lion_3d_project", Path(root).name.lower()}
    matching = [i for i, part in enumerate(parts) if part.lower() in markers]
    if matching:
        relative = Path(*parts[matching[-1] + 1:])
    else:
        original = Path(value)
        if original.is_absolute():
            return original
        relative = Path(*parts)
    candidate = Path(root) / relative
    if candidate.is_file():
        return candidate
    if relative.parts and relative.parts[0] == "blender" and relative.suffix.lower() == ".blend":
        return blend_path(relative.name, root=root)
    if len(relative.parts) == 3 and relative.parts[0] == "docs" and relative.name == "导入检查.blend":
        return Path(root) / "blender" / "studies" / "import_checks" / (relative.parts[1] + ".blend")
    if relative.parts and relative.parts[0] == "exports" and relative.suffix.lower() == ".glb" and ("study" in relative.name.lower() or relative.name == "Lion_G1_Refined_Stage.glb"):
        return Path(root) / "exports" / "studies" / relative.name
    if len(relative.parts) > 2 and relative.parts[:2] == ("renders", "final") and relative.name.startswith(("draft", "revision")):
        return Path(root) / "renders" / "studies" / "final_revisions" / relative.name
    if len(relative.parts) > 1 and relative.parts[0] == "renders" and relative.parts[1] not in {"final", "studies"}:
        return Path(root) / "renders" / "studies" / Path(*relative.parts[1:])
    return candidate


def blender_executable():
    """Choose the configured binary, the known workstation binary, or PATH."""
    configured = os.environ.get("LION_BLENDER")
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError("LION_BLENDER does not point to a Blender executable")
        return candidate.resolve()
    workstation = Path(r"F:\Blender\blender.exe")
    if workstation.is_file():
        return workstation
    found = shutil.which("blender")
    if found:
        return Path(found).resolve()
    raise FileNotFoundError("Set LION_BLENDER to your Blender executable")
