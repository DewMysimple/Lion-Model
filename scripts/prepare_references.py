"""Prepare original reference crops for Lux3D without inventing image content."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
from PIL import Image, ImageDraw

PROJECT = ROOT
SOURCE_IMAGE = PROJECT / "references" / "reference_original.jpg"
SOURCE_BRIEF = PROJECT / "references" / "user_modeling_brief_original.md"
VIEWS = [
    ("left", (615, 83, 1528, 678), None),
    ("front", (60, 64, 580, 677), (60, 64, 224, 91)),
    ("back", (1542, 70, 2048, 678), (1542, 70, 1740, 88)),
    ("top", (60, 741, 1060, 1135), (60, 741, 152, 765)),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-image", type=Path, default=SOURCE_IMAGE)
    parser.add_argument("--source-brief", type=Path, default=SOURCE_BRIEF)
    args = parser.parse_args()
    source_image = resolve_project_path(args.source_image)
    source_brief = resolve_project_path(args.source_brief)
    if not source_image.is_file() or not source_brief.is_file():
        raise FileNotFoundError("Supply the original reference image and modeling brief")
    references = PROJECT / "references"
    docs = PROJECT / "docs"
    references.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    for source, target in ((source_image, references / "reference_original.jpg"),
                           (source_brief, references / "user_modeling_brief_original.md")):
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    original = Image.open(source_image).convert("RGB")
    if original.size != (2048, 1152):
        raise ValueError("Crop coordinates require the inspected 2048 x 1152 image")
    records = []
    for name, box, label_box in VIEWS:
        prepared = original.copy()
        if label_box:
            # The label rectangle is outside the lion. Preserve all subject pixels.
            sample = {"front": (240, 86), "back": (1755, 80), "top": (160, 755)}[name]
            ImageDraw.Draw(prepared).rectangle(label_box, fill=original.getpixel(sample))
        cropped = prepared.crop(box)
        path = references / (name + ".png")
        cropped.save(path)
        records.append({"view": name, "path": str(path), "crop": box,
                        "backgroundLabelMask": label_box, "size": cropped.size,
                        "sha256": digest(path)})
    data = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceImage": str(references / "reference_original.jpg"),
        "sourceSha256": digest(source_image),
        "views": records,
        "inputOrder": [entry[0] for entry in VIEWS],
        "notes": ["The views are an artistic montage, not calibrated orthographic projections.",
                  "No subject repainting, rescaling, AI image generation or mirroring was used.",
                  "Only small background title remnants were masked in front, back and top crops.",
                  "Detail panels are inspection references, not additional whole-object inputs."],
    }
    (docs / "reference_preparation.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps({"status": "prepared", "views": [{"name": r["view"], "size": r["size"]} for r in records]}))


if __name__ == "__main__":
    main()
