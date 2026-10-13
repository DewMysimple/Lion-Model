
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_paths import ROOT, CHECKPOINTS, STUDIES, CACHE, MASTER, blend_path, resolve_project_path

import bpy
import json
from pathlib import Path

root = ROOT
bpy.ops.wm.open_mainfile(filepath=str(blend_path("Lion_Material_Study.blend", root=root)))
image = bpy.data.images["Image_0"]
points = [(100,100), (900,1400), (1100,1700), (1000,1500), (500,1200)]
results = []
for x,y in points:
    index = (y * image.size[0] + x) * 4
    results.append({"x":x,"y":y,"image_pixels":list(image.pixels[index:index+4])})
(root / "docs" / "material_pixel_probe.json").write_text(json.dumps(results,indent=2))
print(results)
