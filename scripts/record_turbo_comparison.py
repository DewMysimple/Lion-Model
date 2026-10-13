"""Record manually reviewed, same-light/source-preserving Turbo vs G1 diagnostics."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import json
import struct
from pathlib import Path
from datetime import datetime, timezone

VIEW_NAMES = ["front_minus_y", "back_plus_y", "left_minus_x", "right_plus_x", "top_plus_z", "bottom_minus_z"]


def glb_json(path):
    raw = path.read_bytes()
    magic, version, declared = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2 or declared != len(raw):
        raise ValueError(f"Invalid/incomplete GLB: {path}")
    length, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A:
        raise ValueError("GLB first chunk is not JSON")
    return json.loads(raw[20:20 + length])


def summarize(folder):
    report = json.loads((folder / "asset_inspection.json").read_text(encoding="utf-8"))
    meshes = [o for o in report["objects"] if o["type"] == "MESH"]
    source = Path(report["input"]["path"])
    container = glb_json(source)
    dims = report["bounding_box_world"]["dimensions"]
    return {
        "source": str(source), "sha256": report["input"]["sha256_after"],
        "source_preserved_by_inspection": report["input"]["preserved"],
        "bytes": report["input"]["bytes"],
        "mesh_count": len(meshes), "material_count": len(report["materials"]),
        "triangles": sum(o["mesh"]["triangles"] for o in meshes),
        "vertices": sum(o["mesh"]["vertices"] for o in meshes),
        "bbox_world": report["bounding_box_world"],
        "normalized_width_over_height": dims[0] / dims[2],
        "normalized_length_over_height": dims[1] / dims[2],
        "image_datablocks": report["images"],
        "glb_material_definitions": container.get("materials", []),
        "material_texture_roles": [
            "Image_0 / texture 0 is base color (sRGB)",
            "Image_1 / texture 1 is packed metallic/roughness (Non-Color)",
            "Neither GLB declares a normalTexture; Non-Color alone must not be reported as a normal map"
        ],
        "mesh_edge_statistics": [o["mesh"]["edge_statistics"] for o in meshes],
        "view_resolution": [768, 768],
        "actual_reviewed_views": [str(folder / "renders" / (n + ".png")) for n in VIEW_NAMES],
        "semantic_orientation_reviewed": {"front": "-Y", "up": "+Z"},
    }


comparison = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "Actual Blender 5.0 import statistics and manual visual review of all six 768px renders for each raw source. Same inspection script, axis cameras, relative-scale lights and framing. No mesh splitting, source edits or added decoration. Visual judgments are qualitative, not computed fidelity scores.",
    "reference": str(ROOT / "references" / "reference_original.jpg"),
    "g1": summarize(ROOT / "docs" / "g1_comparison_inspection_768"),
    "turbo": summarize(ROOT / "docs" / "turbo_candidate_inspection"),
    "comparisons": [
        {"feature": "Whole silhouette", "observation": "Both preserve a broad lion head, long layered cloth body, four short legs, white beard and raised fan tail. Global width/height and length/height ratios are very close. Turbo does not show a major silhouette improvement.", "preference": "No clear winner", "confidence": "high"},
        {"feature": "Eye frame", "observation": "G1 retains several alternating red/white/dark rings; Turbo reduces the visible eye to a large dark glossy oval with a thin white border. Neither provides the reference's precise concentric iris construction.", "preference": "G1 closer to reference", "confidence": "high"},
        {"feature": "Brows and upper lip", "observation": "Turbo has larger, smoother solid red masses, particularly the two eyebrow lobes. G1 has more irregular corrugation but baked bright highlights. Neither has actual dense short fibers in the raw mesh.", "preference": "G1 retains more source surface detail; both require editable fibers", "confidence": "high"},
        {"feature": "Mouth and teeth", "observation": "Turbo shows a more legible red mouth opening than G1's dark/gold lump, but the white areas are blended streaks. Neither source shows the reference's clean repeated rectangular white upper/lower teeth as distinct geometry.", "preference": "Turbo slightly clearer mouth aperture, neither acceptable tooth structure", "confidence": "high"},
        {"feature": "Brocade motifs", "observation": "G1 side cloth retains blurred dark red/black scrolling motifs across gold panels. Turbo replaces much of this with broad almost blank pale gold/yellow stripes; this loss is especially obvious on the top view. Neither reaches the crisp reference embroidery.", "preference": "G1 clearly preferable", "confidence": "high"},
        {"feature": "Metal ornaments", "observation": "Turbo has a visibly gold central forehead sphere/dome and gold side medallions, compared with G1's washed/neutral forehead cap. Some hanging bells are more legible in Turbo. These are localized gains rather than a whole-model quality improvement.", "preference": "Turbo for localized gold appearance", "confidence": "medium-high"},
        {"feature": "Beard and tail", "observation": "Both raw sources reconstruct white fur as thick irregular plates/strips. Turbo tail has larger individually visible strips, but neither source contains editable native hair strands or realistic fiber density.", "preference": "No decisive quality gain", "confidence": "high"},
        {"feature": "Raw materials", "observation": "Turbo red areas have fewer baked bright patches and read more matte under the same studio lighting; G1 raw reds have obvious bright highlights. Both use only two 2048px textures, and both need distinct material regions for fur, cloth and metal.", "preference": "Turbo cleaner raw red appearance; G1 local material refinement already addresses this", "confidence": "medium-high"},
        {"feature": "Raw topology", "observation": "Turbo imports as one mesh with no >2-incidence edges in raw inspection, but has many boundary edges from separate vertices/UV seams. Higher triangle count does not prove separated components, clean topology, watertightness or fidelity. No seam weld or component partition has been attempted on Turbo.", "preference": "Not a quality decision from counts alone", "confidence": "high"},
    ],
    "recommendation": "Retain Turbo as a documented candidate, do not replace the current G1 basis for the whole lion. Prioritize clearer head/teeth/embroidery source data and local editable reconstruction; retain the existing G1 stage work. Turbo is useful as a local gold-ornament reference, but loses eye-frame and cloth pattern fidelity.",
    "limitations": [
        "Current G1 stage technical verification is not artistic acceptance of the high-fidelity target.",
        "No image similarity score, pixel-sharpness metric, deformation rig, watertightness or physical scale measurement is asserted.",
        "This report is based on raw sources; it does not compare all additions in the current G1 master against unrefined Turbo.",
        "Canonical G1 extraction thresholds and eye/metal positions have not been applied to Turbo.",
    ],
}
out = ROOT / "docs" / "turbo_candidate_comparison.json"
out.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
lines = ["# Turbo / G1 原始模型实际比较", "", "六方向均使用 Blender 实际导入、768×768、相同相对灯光和正交 framing；原 GLB 的 SHA 均未变化。", "", "|项目|G1|Turbo|", "|---|---:|---:|"]
for label, key in [("网格数", "mesh_count"), ("材质数", "material_count"), ("三角面数", "triangles"), ("顶点数", "vertices"), ("宽/高", "normalized_width_over_height"), ("长/高", "normalized_length_over_height")]:
    a, b = comparison["g1"][key], comparison["turbo"][key]
    lines.append(f"|{label}|{a:.6f}|{b:.6f}|" if isinstance(a, float) else f"|{label}|{a}|{b}|")
lines += ["", "两者均为 2 张 2048² 内嵌贴图：base color 与 packed metallic/roughness；GLB 未声明 normalTexture。", "", "建议保留 G1 作为现有精修基础。Turbo 额中央与侧面金属更明显、口腔开口略清楚，但眼框层次减少、眉唇更像光滑红块，锦纹尤其在俯视图退化为模糊金带。两者都缺少参考图的独立整齐方牙、密集真实纤维与清晰刺绣。299810 面并不表明 Turbo 整体更高精度。", "", "Turbo 未进行焊缝修复、部件划分或旧坐标套用。当前 G1 保留为阶段成果；此比较不构成最终艺术质量验收。", "", "实际六视图：", ""]
for n in VIEW_NAMES:
    lines.append(f"- G1 `{n}`: {comparison['g1']['actual_reviewed_views'][VIEW_NAMES.index(n)]}")
    lines.append(f"- Turbo `{n}`: {comparison['turbo']['actual_reviewed_views'][VIEW_NAMES.index(n)]}")
(ROOT / "docs" / "turbo_candidate_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Saved {out}")
