"""Package the editable Blender/model project with verified archive bytes.

Run from the project root:
    python scripts/package_lion_delivery.py --dry-run
    python scripts/package_lion_delivery.py

Default output: delivery/Model_Delivery.zip with SHA256/verification sidecars.
Writing refuses existing outputs unless --replace is explicit. Dry runs validate
real inputs without writing. Replacement verifies the new ZIP before publication.
No webpage bundle or Git object database is included.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import zipfile


SECRET_KEYS = {
    "apikey", "authorization", "password", "secret", "accesskey", "accesskeyid",
    "accesskeysecret", "accesstoken", "oustoken", "ststoken", "securitytoken",
    "signedurl", "presignedurl",
}
PRIVATE_NAMES = {"credentials.json", "config.private.json", ".env", "approval.json", "quote.json"}
EXCLUDED_COMPONENTS = {
    ".git", ".cache", "cache", "__pycache__", "node_modules", "private", "delivery",
    "temporary_qa", "preview_qa", ".pytest_cache", ".mypy_cache",
}
EXCLUDED_DOCS = {
    "goal_waiting_for_spending_decision.json", "modeling_plan.json",
    "final_package_arguments.json", "final_package_dry_run.json",
}
TEXT_SUFFIXES = {".json", ".md", ".txt", ".py", ".ps1", ".cmd", ".yaml", ".yml", ".toml"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".exr", ".hdr", ".tif", ".tiff", ".webp"}
MODEL_SUFFIXES = {".blend", ".glb", ".gltf", ".bin", ".obj", ".mtl", ".fbx", ".usdz", ".stl", ".dae", ".abc", ".usd", ".usdc", ".zip"}
DATA_SUFFIXES = {".npy", ".npz"}
PROJECT_FOLDERS = ("blender", "generated", "exports", "textures", "references", "renders", "docs", "scripts", "wiki_memory")
ROOT_FILES = ("README.md", "AGENTS.md", ".gitattributes", ".gitignore", "build_model.cmd")
CORE_REPORTS = {
    "docs/final_master_verification.json": "master",
    "docs/final_glb_verification.json": "scene",
    "docs/final_draco_verification.json": "draco_scene",
}
FINAL_RENDERS = (
    "hero", "front", "left", "right", "back", "top", "head", "eye", "mouth",
    "crown", "body_trim", "brocade", "paw", "tail", "clay_front", "clay_left",
    "clay_right", "clay_back", "clay_top",
)
SIGNED_URL = re.compile(r'https?://[^\s"\'<>]{1,2048}\?(?:[^\s"\'<>]{0,2048})(?:signature|security-token|x-amz-|ossaccesskeyid|token|expires)=?', re.I)
BEARER_VALUE = re.compile(r'Bearer\s+[A-Za-z0-9_.-]{12,}')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_safe_json(value, location: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in SECRET_KEYS:
                raise ValueError(f"Sensitive JSON field in {location}; inspect privately before delivery")
            assert_safe_json(child, location)
    elif isinstance(value, list):
        for child in value:
            assert_safe_json(child, location)
    elif isinstance(value, str) and (SIGNED_URL.search(value) or BEARER_VALUE.search(value)):
        raise ValueError(f"Temporary link or credential value in {location}; inspect privately before delivery")


def inspect_delivery_text(path: Path, archive_name: str) -> None:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in ROOT_FILES:
        return
    content = path.read_text(encoding="utf-8-sig")
    if SIGNED_URL.search(content) or BEARER_VALUE.search(content):
        raise ValueError(f"Temporary link or credential value in {archive_name}; inspect privately before delivery")
    if path.suffix.lower() == ".json":
        assert_safe_json(json.loads(content), archive_name)


def check_embedded_glb(path: Path) -> None:
    with path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12:
            raise ValueError(f"Truncated GLB: {path.name}")
        magic, version, length = struct.unpack("<4sII", header)
        if magic != b"glTF" or version != 2 or length != path.stat().st_size:
            raise ValueError(f"Invalid GLB container: {path.name}")
        chunk_header = stream.read(8)
        if len(chunk_header) != 8:
            raise ValueError(f"Truncated GLB JSON header: {path.name}")
        size, kind = struct.unpack("<II", chunk_header)
        if kind != 0x4E4F534A or size > length - 20:
            raise ValueError(f"Invalid GLB JSON chunk: {path.name}")
        data = json.loads(stream.read(size).decode("utf-8").rstrip(" \0"))
    assert_safe_json(data, path.name)
    for resource in data.get("buffers", []) + data.get("images", []):
        uri = resource.get("uri")
        if uri is not None and not uri.startswith("data:"):
            raise ValueError(f"GLB has an unpacked external resource: {path.name}")


def excluded(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    filename = path.name.lower()
    if parts & EXCLUDED_COMPONENTS or any(part.startswith(("previewbundle", "offline_preview", "preview_qa")) for part in parts):
        return True
    if filename in PRIVATE_NAMES or filename.startswith(".env."):
        return True
    if path.suffix.lower() in {".log", ".pyc", ".tmp", ".partial", ".html", ".css", ".js", ".cjs", ".wasm"}:
        return True
    if re.search(r"\.blend\d+$", filename) or ".template." in filename or (".before-build-" in filename and filename.endswith(".blend")):
        return True
    # Keep small native modeling diagnostics and production recovery helpers.
    # Root cleanup defines which studies survive; no blanket probe exclusion.
    return filename in EXCLUDED_DOCS


def contained_file(project: Path, value: str | Path) -> Path:
    candidate = Path(value)
    candidate = candidate if candidate.is_absolute() else project / candidate
    if candidate.is_symlink():
        raise ValueError("Delivery inputs must not be symlinks")
    candidate = candidate.resolve(strict=True)
    if not candidate.is_relative_to(project) or not candidate.is_file():
        raise ValueError("Delivery inputs must be real files inside the project directory")
    return candidate


def validate_report(project: Path, report: Path, artifact: Path) -> dict:
    evidence = json.loads(report.read_text(encoding="utf-8-sig"))
    if evidence.get("status") != "pass" or evidence.get("errors"):
        raise ValueError(f"Required final model verification has not passed: {report.name}")
    recorded = evidence.get("input", {})
    digest = sha256(artifact)
    if recorded.get("sha256_after") != digest or recorded.get("sha256_before") != digest or recorded.get("preserved") is not True:
        raise ValueError(f"Required final model report is stale: {report.name}")
    if recorded.get("bytes") != artifact.stat().st_size:
        raise ValueError(f"Required report records a different artifact size: {report.name}")
    # Project relocation changes paths, not artifact identity. Preserve historical
    # report paths; bind evidence to the expected role and exact SHA256/size here.
    return {
        "report": report.relative_to(project).as_posix(),
        "reportSha256": sha256(report),
        "artifact": artifact.relative_to(project).as_posix(),
        "sha256": digest,
        "recordedAt": evidence.get("recorded_at_utc"),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    result.add_argument("--master", default="blender/Lion_Final_Master.blend")
    result.add_argument("--scene", default="exports/scene.glb")
    result.add_argument("--draco-scene", default="exports/scene_draco.glb")
    result.add_argument("--render-dir", default="renders/final")
    result.add_argument("--required-report", action="append", default=[], help="Additional completed report to include")
    result.add_argument("--required-render", action="append", default=[], help="Additional required final render to include")
    result.add_argument("--input-blend", action="append", default=[], help="Additional native construction input to include")
    result.add_argument("--source-artifact", action="append", default=[], help="Additional source artifact to include")
    result.add_argument("--output", default="delivery/Model_Delivery.zip", help="New ZIP inside the project's delivery directory")
    result.add_argument("--replace", action="store_true", help="Replace this output trio only after the new ZIP and metadata are fully prepared and verified")
    result.add_argument("--dry-run", action="store_true")
    return result


def publish_verified(pairs: list[tuple[Path, Path]], *, replace: bool) -> None:
    """Atomically replace each prepared file with error rollback for the trio.

    Same-directory hard links preserve old files without copying a multi-GB ZIP.
    Three renames are not one filesystem transaction: a process interruption may
    leave rollback/temp files. The final SHA256 detects an incomplete publication.
    """
    backups: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for temporary, target in pairs:
            if target.exists():
                if not replace:
                    raise FileExistsError(f"Output appeared during packaging; preserve it or use --replace: {target.name}")
                backup = target.with_name(target.name + ".rollback")
                os.link(target, backup)
                backups[target] = backup
        for temporary, target in pairs:
            temporary.replace(target)
            replaced.append(target)
    except BaseException as error:
        rollback_errors = []
        for target in reversed(replaced):
            try:
                backup = backups.pop(target, None)
                if backup is not None:
                    backup.replace(target)
                elif target.is_file():
                    target.unlink()
            except OSError as restore_error:
                rollback_errors.append(f"{target.name}: {restore_error}")
        for backup in backups.values():
            if backup.is_file():
                backup.unlink()
        if rollback_errors:
            raise RuntimeError("Archive publication rollback needs inspection: " + "; ".join(rollback_errors)) from error
        raise
    else:
        for backup in backups.values():
            backup.unlink()


def main() -> None:
    args = parser().parse_args()
    project = Path(args.project_root).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("Project root is not a directory")
    output = Path(args.output)
    output = (output if output.is_absolute() else project / output).resolve()
    if not output.is_relative_to((project / "delivery").resolve()) or output.suffix.lower() != ".zip":
        raise ValueError("Output must be a .zip inside the project's delivery directory")
    sidecar = output.with_name(output.name + ".verification.json")
    checksum = output.with_name(output.name + ".sha256")
    partial = output.with_name(output.name + ".partial")
    sidecar_temp = sidecar.with_name(sidecar.name + ".partial")
    checksum_temp = checksum.with_name(checksum.name + ".partial")
    if not args.dry_run:
        for target in (partial, sidecar_temp, checksum_temp) + tuple(target.with_name(target.name + ".rollback") for target in (output, sidecar, checksum)):
            if target.exists():
                raise FileExistsError(f"Existing temporary/rollback file requires inspection: {target.name}")
        if not args.replace:
            for target in (output, sidecar, checksum):
                if target.exists():
                    raise FileExistsError(f"Existing output is preserved; choose a new output or use --replace: {target.name}")
    files: dict[str, Path] = {}

    def add(source: Path) -> None:
        if source.is_symlink():
            raise ValueError("Symlink delivery inputs are refused")
        source = source.resolve(strict=True)
        if not source.is_relative_to(project):
            raise ValueError("Delivery input resolves outside the project")
        relative = source.relative_to(project)
        if excluded(relative):
            return
        name = relative.as_posix()
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError("Archive paths must be portable relative paths")
        if name in files and files[name] != source:
            raise ValueError(f"Duplicate archive entry: {name}")
        inspect_delivery_text(source, name)
        # LFS pointers cannot stand in for actual model/image bytes.
        with source.open("rb") as stream:
            if stream.read(128).startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                raise ValueError(f"Fetch the real Git LFS content before packaging: {name}")
        if source.suffix.lower() == ".glb":
            check_embedded_glb(source)
        files[name] = source

    artifacts = {
        # The master is a local generated output excluded from Git. Packaging
        # still delivers the real editable model, so run build_model.cmd first
        # in a fresh clone and retain its successful current native QA report.
        "master": contained_file(project, args.master),
        "scene": contained_file(project, args.scene),
        "draco_scene": contained_file(project, args.draco_scene),
    }
    if artifacts["master"].suffix.lower() != ".blend" or any(artifacts[key].suffix.lower() != ".glb" for key in ("scene", "draco_scene")):
        raise ValueError("The native master must be .blend and both portable exports must be .glb")
    verification_inputs = []
    for relative, role in CORE_REPORTS.items():
        report = contained_file(project, relative)
        verification_inputs.append(validate_report(project, report, artifacts[role]))
        add(report)
        add(artifacts[role])
    for relative in ROOT_FILES + ("docs/Final_Model_Report.md", "wiki_memory/AGENTS.md", "wiki_memory/README.md", "wiki_memory/.memory.json"):
        source = contained_file(project, relative)
        if source.suffix.lower() == ".md" and re.search(r'\bTODO_FINAL[A-Z0-9_]*\b', source.read_text(encoding="utf-8-sig")):
            raise ValueError("Final documentation must contain actual evidence before packaging")
        add(source)
    render_dir = Path(args.render_dir)
    render_dir = (render_dir if render_dir.is_absolute() else project / render_dir).resolve(strict=True)
    if not render_dir.is_relative_to(project) or not render_dir.is_dir():
        raise ValueError("Final renders must be a real directory inside the project")
    for stem in FINAL_RENDERS:
        add(contained_file(project, render_dir / (stem + ".png")))
    for value in args.required_report + args.required_render + args.source_artifact:
        add(contained_file(project, value))
    for value in args.input_blend:
        source = contained_file(project, value)
        if source.suffix.lower() != ".blend":
            raise ValueError("Additional native construction inputs must be .blend files")
        add(source)
    for folder in PROJECT_FOLDERS:
        directory = project / folder
        if not directory.is_dir():
            raise ValueError(f"Required model project directory is missing: {folder}")
        for source in sorted(directory.rglob("*")):
            if not source.is_file() or excluded(source.relative_to(project)):
                continue
            permitted = source.suffix.lower() in TEXT_SUFFIXES | IMAGE_SUFFIXES | MODEL_SUFFIXES | DATA_SUFFIXES
            permitted |= source.name == ".gitkeep"
            if permitted:
                add(source)
    if args.dry_run:
        print(json.dumps({
            "dryRun": True, "replace": args.replace, "output": output.relative_to(project).as_posix(),
            "fileCount": len(files), "totalSourceBytes": sum(path.stat().st_size for path in files.values()),
            "verificationInputs": verification_inputs, "paths": sorted(files),
        }, indent=2, ensure_ascii=True))
        return

    records = [{"path": name, "size": source.stat().st_size, "sha256": sha256(source)} for name, source in sorted(files.items())]
    recorded_files = {record["path"]: record for record in records}
    for accepted in verification_inputs:
        if recorded_files[accepted["artifact"]]["sha256"] != accepted["sha256"] or recorded_files[accepted["report"]]["sha256"] != accepted["reportSha256"]:
            raise ValueError("A verified model or its report changed before the archive inventory was finalized")
    manifest = {
        "schema": "lion-project.package-inputs/v2",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "subject": "Editable Cantonese lion dance Blender/model project",
        "files": records,
        "verificationInputs": verification_inputs,
        "scope": "Actual native/model files, resources, scripts and project memory; no browser preview or Git object database.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    created_partial = False
    created_metadata: list[Path] = []
    try:
        with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            created_partial = True
            for name, source in sorted(files.items()):
                archive.write(source, arcname="Lion_3D_Project/" + name)
            archive.writestr("Lion_3D_Project/package_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        with zipfile.ZipFile(partial, "r") as archive:
            bad_entry = archive.testzip()
            if bad_entry is not None:
                raise ValueError(f"Archive CRC verification failed: {bad_entry}")
            if len(archive.infolist()) != len(records) + 1:
                raise ValueError("Archive entry count differs from the planned file inventory")
            for record in records:
                digest = hashlib.sha256()
                with archive.open("Lion_3D_Project/" + record["path"], "r") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != record["sha256"] or archive.getinfo("Lion_3D_Project/" + record["path"]).file_size != record["size"]:
                    raise ValueError(f"Archive bytes differ from inventoried source: {record['path']}")
                if sha256(files[record["path"]]) != record["sha256"]:
                    raise ValueError(f"Source changed during packaging: {record['path']}")
            if json.loads(archive.read("Lion_3D_Project/package_manifest.json")) != manifest:
                raise ValueError("Archived manifest differs from the actual file inventory")
        archive_digest = sha256(partial)
        verification = {
            "schema": "lion-project.package-verification/v2",
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "archiveName": output.name,
            "size": partial.stat().st_size,
            "sha256": archive_digest,
            "sourceFileCount": len(records),
            "zipEntryCount": len(records) + 1,
            "crcVerified": True,
            "allIncludedSourceHashesVerified": True,
            "sourcesUnchangedDuringPackaging": True,
            "verificationInputs": verification_inputs,
            "excluded": ["delivery outputs", "Git/LFS database", "private configuration", "logs", "caches", "Blender backups", "temporary web QA", "unfilled templates", "webpage previews"],
        }
        with sidecar_temp.open("x", encoding="utf-8") as stream:
            created_metadata.append(sidecar_temp)
            json.dump(verification, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        with checksum_temp.open("x", encoding="ascii") as stream:
            created_metadata.append(checksum_temp)
            stream.write(archive_digest + "  " + output.name + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        publish_verified([(partial, output), (sidecar_temp, sidecar), (checksum_temp, checksum)], replace=args.replace)
        print(json.dumps(verification, ensure_ascii=True))
    except BaseException:
        if created_partial and partial.is_file():
            partial.unlink()
        for temporary in created_metadata:
            if temporary.is_file():
                temporary.unlink()
        raise


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
