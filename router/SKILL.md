---
name: studio-router
description: Route a game-studio request to one of the 8 pipelines and load only the relevant README/SKILL. Use when the user asks for game work without naming a pipeline.
when_to_use: Any new request in a UE5 solo studio project; detect engine/pipeline and load minimal docs.
inputs: user request, project files, current stage, engine version
outputs: pipeline id, docs to load, gate to run, next action
gates: maps to G0–G7
owner: producer
version: 0.7.4
---

# Studio Router / 工作室路由器

> 中文为主 / English summary at the bottom.
> 先判断“这是哪条管线、哪个阶段、需要什么证据”，再只加载相关文档。

## 1. 识别顺序

1. 引擎/项目：gamecheck.json、.uproject、project.godot、package.json；
2. 当前阶段：.gameconsole/state.json 的 current_stage；
3. 请求类型：剧本/美术/视频/音乐/白模/内容/上线；
4. 只加载 1 个主管线 + 最多 1 个协作管线；
5. 不确定时问一个澄清问题，不要一次加载 8 条管线。

## 2. 关键词路由

| 请求关键词 | 管线 | 先读 |
|---|---|---|
| 立项、范围、想法、平台 | P0 | docs/管线/00_立项/README.md |
| GDD、标准、数值、技术方案 | P1 | docs/管线/01_标准/README.md |
| 剧本、故事、角色、台词、场景、镜头、分镜 | P2/P4 | docs/管线/02_剧本/README.md |
| 白模、UE、工程、蓝图、性能、输入 | P3 | docs/管线/03_白模与技术/README.md |
| 美术、资产、Blender、贴图、UI、PV、视频 | P4 | docs/管线/04_美术与视频/README.md |
| 音乐、音效、配音、混音、Wwise、MetaSounds | P5 | docs/管线/05_音乐与音频/README.md |
| 关卡、敌人、Boss、任务、收集、内容 | P6 | docs/管线/06_内容生产/README.md |
| 打包、Steam、主机、商店、认证、发布 | P7 | docs/管线/07_上线与发行/README.md |
| MCP、工具、权限、审计 | 跨管线 | mcp/README.md |

## 3. 输出格式

Agent 必须先输出：

~~~text
管线：P2 剧本
阶段：当前 P0，前置未完成
加载：docs/管线/02_剧本/README.md + docs/管线/02_剧本/SKILL.md
先跑：gamecheck gate script（需先填 docs/14、15）
下一步：补场景/台词/镜头 ID
~~~

## 4. 路由规则

- 不读全部 references；
- 不跳过闸门；
- 跨管线变更要求 Producer 建变更单；
- 引擎不匹配时先停下确认（UE5 vs 2D/Unity/Godot）；
- 2D/微信/Three.js 线后置，不按 UE 管线处理。

## 5. 工具

~~~powershell
python scripts/studio.py route "给主角加一段追逐戏，要分镜和配音"
python scripts/studio.py explain 02
python scripts/studio.py next --project .
~~~

---

### English Summary

Route each request to one primary pipeline and at most one collaborator, load only that README/SKILL, and name the gate plus next action.
Do not load all references or skip gates; engine mismatch is a stop-and-confirm condition.
