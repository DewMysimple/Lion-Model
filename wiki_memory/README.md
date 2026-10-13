---
type: moc
status: active
updated: 2026-10-13
topic: memory-entry
sources:
  - "wiki_memory/.memory.json"
  - "AGENTS.md"
---

# 工程记忆导航

本项目使用 `standard`。选择者是用户：2026-10-13 明确要求按所指 Skill 的标准版构建记忆，用于后续 Agent 围绕模型与 Blender 文件继续开发。模式以 `.memory.json` 为准；本目录是唯一有效记忆根，根 `AGENTS.md` 已接入读取协议。

开始任务先读本页与维护协议，再读项目概览、当前约束和当前待办。涉及模型结构、材质或导出时补读系统架构与已知问题；随后只检索当前任务相关的有效决策和知识。模型文件及正式验证报告的位置由状态页提供，本页不复制这些事实。

- [记忆维护协议](AGENTS.md)
- [工作日志 MOC](日志/MOC_工作日志.md)

按主题检索可用 `rg -n "头冠|毛丝|材质|导出|Git" wiki_memory`。需要历史来由时再读日志 MOC；日志按六类目录归档，每个任务只保留一份主日志。知识和决策页完成后由索引工具生成对应 MOC 与下方导航，不另建入口页。

维护时在工程根运行 `python "wiki_memory/工具/memory.py" index --project "." --apply` 和 `python "wiki_memory/工具/memory.py" check --project "." --require-ready`。工具检查引用、字段及布局，不能代替打开模型、查看渲染或核实 Git 远端。具体规则以维护协议为准。

<!-- wiki-memory:auto:start -->

## 当前状态

- [[当前状态/已知问题.md|已知问题]] — active
- [[当前状态/当前待办.md|当前待办]] — active
- [[当前状态/当前约束.md|当前约束]] — active
- [[当前状态/系统架构.md|系统架构]] — active
- [[当前状态/项目概览.md|项目概览]] — active

- [[决策/MOC_决策.md|工程决策目录]] — 1 页，按主题或模块检索。
- [[知识/MOC_知识.md|稳定知识目录]] — 1 页，按主题或模块检索。

<!-- wiki-memory:auto:end -->
