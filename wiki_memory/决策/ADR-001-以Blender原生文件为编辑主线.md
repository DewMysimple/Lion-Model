---
type: decision
status: active
updated: 2026-10-13
topic: lion-native-first-project
sources:
  - "用户指令：2026-10-13 后续 Agent 开发和调整均以模型与 Blender 文件为主，不需要网页预览"
  - "scripts/assemble_quality_revision.py"
  - "blender/checkpoints/Lion_Body_Quality_Stage.blend"
  - "blender/checkpoints/Lion_Head_Quality_Stage_v2.blend"
  - "docs/Final_Model_Report.md"
  - "docs/final_master_verification.json"
  - "docs/project_cleanup_inventory.json"
  - ".gitattributes"
  - ".gitignore"
  - "用户指令：2026-10-13 主 Blender 文件可以不上传，需要 CMD 在其他开发环境构建生成"
  - "build_model.cmd"
  - "scripts/build_model.ps1"
  - "scripts/build_native_model.py"
  - "docs/model_build_verification.json"
  - "docs/native_reconstruction_comparison.json"
---

# ADR-001：以 Blender 原生文件为编辑主线

## 背景与选择

用户明确选择围绕模型和 Blender 工程继续开发，并要求清理网页相关内容。因此 `blender/Lion_Final_Master.blend` 是持续编辑主入口，GLB 保留为交换导出；浏览器查看器不再作为工程恢复、交付或验收入口。这是用户已决要求，不是 Agent 推断的新产品方向。

用户随后允许主文件不上传，并要求其他环境能通过 CMD 构建。已采用将主文件作为本地生成物、从 Git 跟踪及本轮未发布历史排除的方案；仓库保留真实检查点、构建代码和资源，用 `build_model.cmd` 生成完整原生文件。它延续原生编辑主线，改变主文件的版本交付方式。

## 理由与取舍

主文件含可编辑曲线毛丝、来源面属性、分部件、材质和 Blender 旋转限位；GLB 抽样毛丝并只记录部分控制元数据。原生更适合后续逐部件重建及烘焙，直接回导 GLB 会损失相关编辑数据。

代价是构建仍依赖 Blender 和较大的阶段 `.blend` / 素材，仓库仍使用 LFS；需先取 LFS 实体再构建，不能只有脚本或将所有 `.blend` 删除。构建须重现当前来源、曲线、细节和材质，并有真实无主文件测试证据。主文件可本地保留和进入离线包，Git 管理所需输入及代码。

## 实施状态与范围

原生主文件仍为编辑入口，checkpoint、study、实验渲染和实验导出已迁移，网页及无关产物已清除 3,598,156,789 字节，脚本路径已修正并完成编译/引用检查。原生和两份 GLB 字节未变，本轮完整技术复验 pass；模型艺术内容未修改。

阶段按 `.gitattributes` 使用 LFS，主文件/交付/缓存已忽略。CMD 已从无旧主文件暂存重建，删除暂存后重开 pass；默认保护输出，明确 `-Force` 才替换并备份。输入哈希保全和独立完整资产语义对照均实际 pass，覆盖来源/曲线/控制/材质/像素，排除灯光、相机、UI、路径及保存字节。

新 reproducible-main 索引不含主文件，旧本轮未发布 main 仍待替换；LFS 全量对象已传，但远端分支尚未发布。最终 Git 历史排除、完整远端和新包仍待验收，本页不提前宣称这些完成。

决策仅适用于当前醒狮工程及已授权模型编辑，不降低艺术质量要求。Git 操作按本工程已有授权和当前任务范围判断，资料不独立授权其他项目或其他远端。

## 验证线索

检查 Git 发布历史不含主文件、新克隆构建前读取记忆不要求主文件存在，并通过 CMD 在另一位置生成完整主模型；独立重开验证曲线、来源、细部和材质。根 README 提供实际构建命令，工程与包无网页依赖。模型修改后继续做结构及艺术两类验收。

2026-10-13 依据为明确用户要求、实际源码、CMD/PS5/Blender5.0.0 构建实测及完整原生对照报告。原件哈希未变，构建保存字节不同但受测资产语义等价。Git、新克隆及最终包尚需验收，证据由正式报告和唯一维护日志补齐。
