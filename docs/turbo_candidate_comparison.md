# Turbo / G1 原始模型实际比较

六方向均使用 Blender 实际导入、768×768、相同相对灯光和正交 framing；原 GLB 的 SHA 均未变化。

|项目|G1|Turbo|
|---|---:|---:|
|网格数|1|1|
|材质数|1|1|
|三角面数|286200|299810|
|顶点数|289321|258325|
|宽/高|0.904041|0.895029|
|长/高|1.603024|1.597658|

两者均为 2 张 2048² 内嵌贴图：base color 与 packed metallic/roughness；GLB 未声明 normalTexture。

建议保留 G1 作为现有精修基础。Turbo 额中央与侧面金属更明显、口腔开口略清楚，但眼框层次减少、眉唇更像光滑红块，锦纹尤其在俯视图退化为模糊金带。两者都缺少参考图的独立整齐方牙、密集真实纤维与清晰刺绣。299810 面并不表明 Turbo 整体更高精度。

Turbo 未进行焊缝修复、部件划分或旧坐标套用。当前 G1 保留为阶段成果；此比较不构成最终艺术质量验收。

实际六视图：

- G1 `front_minus_y`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\g1_comparison_inspection_768\renders\front_minus_y.png
- Turbo `front_minus_y`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\turbo_candidate_inspection\renders\front_minus_y.png
- G1 `back_plus_y`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\g1_comparison_inspection_768\renders\back_plus_y.png
- Turbo `back_plus_y`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\turbo_candidate_inspection\renders\back_plus_y.png
- G1 `left_minus_x`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\g1_comparison_inspection_768\renders\left_minus_x.png
- Turbo `left_minus_x`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\turbo_candidate_inspection\renders\left_minus_x.png
- G1 `right_plus_x`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\g1_comparison_inspection_768\renders\right_plus_x.png
- Turbo `right_plus_x`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\turbo_candidate_inspection\renders\right_plus_x.png
- G1 `top_plus_z`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\g1_comparison_inspection_768\renders\top_plus_z.png
- Turbo `top_plus_z`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\turbo_candidate_inspection\renders\top_plus_z.png
- G1 `bottom_minus_z`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\g1_comparison_inspection_768\renders\bottom_minus_z.png
- Turbo `bottom_minus_z`: C:\Users\Administrator\Desktop\模型2\Lion_3D_Project\docs\turbo_candidate_inspection\renders\bottom_minus_z.png
