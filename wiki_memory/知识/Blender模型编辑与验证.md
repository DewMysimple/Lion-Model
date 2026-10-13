---
type: knowledge
status: active
updated: 2026-10-13
topic: lion-blender-edit-verification
sources:
  - "scripts/assemble_quality_revision.py"
  - "blender/checkpoints/Lion_Body_Quality_Stage.blend"
  - "blender/checkpoints/Lion_Head_Quality_Stage_v2.blend"
  - "scripts/refine_lion_master.py"
  - "scripts/run_final_lion_verification.ps1"
  - "scripts/verify_final_lion.py"
  - "scripts/verify_draco_lion.py"
  - "docs/final_master_verification.json"
  - "docs/final_glb_verification.json"
  - "docs/final_draco_verification.json"
  - "docs/relocation_dependency_check.json"
  - "docs/Final_Model_Report.md"
  - "用户指令：2026-10-13 主文件不上传，使用 CMD 在其他环境生成"
  - "build_model.cmd"
  - "scripts/build_model.ps1"
  - "scripts/build_native_model.py"
  - "docs/model_build_verification.json"
  - "docs/native_reconstruction_comparison.json"
  - "docs/native_reference_signature.json"
---

# Blender 模型编辑与验证

适用于原生主文件的形体、材质、毛丝、部件及导出修改。先保留检查点，再修改明确部件；结构验证和参考近景验收分别执行。

## 编辑入口与产物

现有本地 `blender/Lion_Final_Master.blend` 保留约 98 万根曲线毛丝、20 个来源网格与独立细节，已忽略 Git。新的 Windows 环境从已跟踪阶段/资源通过 CMD 生成后进入编辑；入口真实构建及重开已通过。要求 Windows PowerShell 与 Blender 5.0.x，不需外部 Python 或云端调用。

需要先获取真实 LFS 内容，至少包括 `blender/checkpoints/Lion_Body_Quality_Stage.blend` 与 `Lion_Head_Quality_Stage_v2.blend`，以及后续材质/来源/掩码依赖。这个构建从真实 `.blend` 阶段组装与细化，并非只凭文本或无需资产重新生成。`exports/scene*.glb` 仅含抽样毛丝网格，不能代替完整原生重建。

在仓库根的 CMD 使用：

```cmd
build_model.cmd "F:\Blender\blender.exe"
```

默认输出主文件；第二位置参数可另选 `.blend`，已有输出默认保留。明确 `-Force` 才替换并留备份，所以人工修改模型前不要盲目强制重建。缺数据或 LFS 指针时脚本尝试定向拉取必需输入；资源已齐全且离线可加 `-NoLfsPull`。Blender 路径也可经 `LION_BLENDER` 指定，无显式路径时先本机 F 盘再 PATH。运行证据在忽略的 `cache/builds/<运行编号>/`，正式实测摘要在 docs。

来源网格 FACE 域 `source_face_index` 与 `source_asset` / `source_asset_id` 供逐来源审计。重建、合并或删除面时说明出处映射如何变化；旧“来源面全部恰好一次”检查可能不再适用，不能仅改 expected 数字使它通过。父子组织以 `Lion_Root` / `Pivot_*` 为主，源表面改变后需复核曲线贴根。

保存后以新进程重开模型。历史报告有旧 library datablock 记录，但本轮实际重开为 libraries=[] / linked_ids=[]，14 个图片均 packed；判断迁移后依赖要看当前重开，而非旧路径字符串。

## 验证命令与范围

在工程根按工程 README 的当前参数调用。既有 PowerShell 入口为：

```powershell
.\scripts\run_final_lion_verification.ps1 -MasterOnly
.\scripts\run_final_lion_verification.ps1 -GlbOnly
```

包装脚本使用 Blender `--background --factory-startup --python-exit-code 1`，实际重开原生/独立导入 GLB；无开关时检查两者，`-Draco` 追加压缩文件检查。指定路径可用 `-BlenderBinary 'F:\Blender\blender.exe'` 或环境变量 `LION_BLENDER`；无指定时先找该本机路径，再找 PATH 中 blender。Draco 独立入口：

```powershell
& 'F:\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python 'scripts\verify_draco_lion.py' -- --root '.'
```

既有模型核心验证和新 CMD 均 pass。CMD 的隔离暂存只含 12 数据、15 Python 模块及 CMD/PS 配方，未复制旧主文件；四阶段后先验证暂存输出，发布并删除暂存，再独立重开。记录时核对 JSON 状态、SHA、日期、errors/warnings，不只看退出码。完整两文件原生语义对照也实际 pass，见 `docs/native_reconstruction_comparison.json`。

明显形体或材质变化应做受影响部件近景及正/侧/背整体比较，保持镜头、照明和原参考可对照。技术通过不能证明图案保真、毛密度或表面质量。

## 写入边界

`refine_lion_master.py` 缺省入口是历史 `build`，会从早期整狮部件保存主文件。当前双来源结果还依赖 `assemble_quality_revision.py`、材质边界修正、`finalize_quality_revision.py` 和 `apply_final_head_detail.py` 等阶段；缺省 build 不能当作重新验证，否则可能覆盖当前组合结果。

其 `-- render` 从主文件生成正式视图；`-- export` 生成未压缩 GLB，`-- export --draco` 生成压缩 GLB。它们更新衍生产物和报告，应在完成主文件保存后按当前源码运行，导出后再验证。源面变化或新增部件可能需要维护来源审计规范，旧 export 哈希不适用于新文件。

## 证据与限制

2026-10-13 读取当前脚本、迁移初始重开及本轮原生/未压缩/Draco JSON（17:26:18/17:26:27/17:26:37 +08:00，均 pass）。检查发生在资产基线提交前，含本轮脚本本地变更；之后资产提交为 `20d98f7` / `a2c1521`，脚本尚未提交。主文件和两份 GLB SHA 未变。

原生已有 Head/Jaw/Tail、左右 Eye/Ear 共 7 个 LOCAL LimitRotation，含 42 次越界钳制与回中性测试。严格 Draco 检查实际解码 230 个 primitive / 3,524,821 个三角形，最大逐来源部件边界差 5.960464477539062e-7 设计单位，零错误/三个格式警告；仍不证明绑定变形、碰撞安全、舞动或眨眼。

新入口实际命令为 `build_model.cmd "F:\Blender\blender.exe" "cache\Lion_Builder_Final_Proof.blend" -NoLfsPull`；Windows CMD → PS5 → Blender5.0.0，117.621 秒，构建/两次独立重开均退出 0。输出 194,703,053 字节，SHA `8e0fffeb3915d8e7b2b7c83d22bb87f52afb59aaa628d8d01d90da21d17d9f60`。原件仍为 `60eac7...` 且未覆盖；14 图片打包为相对路径，无活动库/链接数据。源及配方 29 个哈希未变，重建结构仍为 256 对象/20 来源网格/528,398 来源面/980,957 毛丝/3,121,088 控制点，零原生错误/警告。

两文件实际比较了 256 对象、4,553 数组字段、15 材质语义与 10 图像内容语义，零错误/警告/不支持项。来源几何、UV、自定义法线、全部曲线控制数据、变换、控制、着色图与解码像素覆盖；生成基本体的边/多边形存储重排已证等价。仅已准确对应的生成法线和 11 颗牙齿 UV 接受明确 float32 舍入，最大分别 1.1920929e-7 / 5.9604645e-8；来源 UV/自定义法线和曲线仍精确一致，不是统一放宽阈值。

可移植参考签名为 `docs/native_reference_signature.json`。语义比较排除场景灯光/相机/render-view、UI、路径、保存字节及无关运行元数据；不能据此声称新渲染、绑定或艺术质量提高。本轮是在本机隔离目录验证，另一物理机器及 Git 远端新克隆仍未受测。最新结果写报告与单份日志。
