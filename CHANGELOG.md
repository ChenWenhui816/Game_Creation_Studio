# Changelog

本文件记录 skill 的所有重要变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.7.3] - 2026-11-17

### Added

- DeepSeek Harness 对接：dsh_bridge.py + studio-headless profile，复用 DSH 账号凭据。
- 控制台「让 DSH 继续」按钮；POST /api/handoff/run、GET /api/handoff/status。
- 当前会话（DSH_SESSION_ID）或新会话运行交接包。
- docs/DeepSeekHarness对接.md、docs/创作流程.md。
- P1 GDD/美术/技术文档由当前 agent 展开，gate spec 23 通过 / 0 失败。

## [0.7.2] - 2026-11-17

### Fixed

- P0 冻结后自动生成交接包，并把 P0 一句话/世界/主角/对抗者/体量播种到 P1 GDD。
- 冻结后网页弹窗展示交接包，可复制给当前 agent。
- 新增 agent_bridge.py：监听 handoff 并调用外部 agent CLI；桌面版读取 .gameconsole/agent.json 自动启动。
- 文档填写区：黄色【待填】高亮、固定 H2/H3 灰锁、字段面板直接填入。
- P0 handoff 体量/平台/主角抽取修正。

## [0.7.1] - 2026-11-17

### Added

- 6 个可切换工作室角色：Producer / Design / Tech / Art / Audio / QA-Release。
- router/SKILL.md：8 管线请求路由；studio.py route 关键词路由。
- docs/参考库与能力映射.md：明确 Donchitos / gamedev / agency / Superpowers 吸收与未采用项。
- docs/工作室流程目录.md：8 管线 × 6 角色 × 冲刺/里程碑/周节奏。
- 角色职责、禁止项、交接与 English Summary。

## [0.7.0] - 2026-11-17

### Added

- 8 管线结构：立项、标准、剧本、白模与技术、美术与视频、音乐与音频、内容生产、上线与发行。
- 剧本圣经/分镜镜头表/音乐音频设计/视频 PV 制作单模板。
- 新闸门：`gate script` / `gate art` / `gate audio`。
- 8 管线 README + SKILL.md 契约（中文为主，英文摘要）。
- `scripts/studio.py`：pipelines / explain / doctor / next。
- MCP Gateway POC：配置、doctor/list/tools/call、权限与审计；ADR 0001 UE MCP 选型。
- 资产卡 JSON Schema、资产注册表扫描/校验 CLI。
- UE 5.8 锁定与 5.9/6.0 升级策略文档。

### Changed

- 控制台从 6 阶段扩展到 8 管线，旧项目自动迁移新阶段状态。
- 文档目录新增 docs/管线、mcp、schemas、ADR。

## [0.6.0] - 2026-11-16

### Added

- 变更单 diff：批准时保存基线，查看 before/after 统一 diff。
- 证据上传：拖拽/选择文件上传到 docs/evidence/，单文件 ≤ 6 MB。
- 章节拖拽排序：H2 章节可拖动重排，保存后生成版本。
- 阶段修改高亮：相对最近冻结/初始版本显示变更文档、增删行与统一 diff。
- 下游影响推理：根据关键词给出 P2/P3/P5 检查建议。
- 制作总览仪表盘：阶段完成环、闸门/文档统计、按阶段时间柱状图、最近计时。
- 制作计时：开始/停止计时，按阶段累计，持久化到项目状态。

### Changed

- UI 科技感重做：网格背景、玻璃卡片、霓虹强调、紧凑顶栏。
- 版本号提升到 0.6.0。

## [0.5.0] - 2026-11-16

### Added

- Inno Setup 安装包：开始菜单、卸载、可选桌面快捷方式、按用户安装。
- 代码签名脚本与 CI Secrets 钩子：无证书跳过，有证书签名 exe/setup。
- 桌面版自动更新：检查、下载、SHA-256 校验、退出替换、自动重启。
- 控制台变更单向导：冻结后创建/批准/拒绝变更，再次冻结标记生效。
- 章节/检查项层级面板：H2/H3 树、checkbox 勾选、追加章节/检查项。
- 证据墙：读取 `docs/evidence/` 的截图、录屏与文件。
- `docs/安装包与签名.md`。

### Changed

- 版本号提升到 0.5.0；桌面构建 workflow 增加安装包、签名与自动更新资产上传。

## [0.4.0] - 2026-11-16

### Added

- Windows 桌面版入口 `scripts/console_app.py`：本地服务 + pywebview/WebView2 窗口，关闭窗口即停止服务。
- PyInstaller 构建配置 `build/desktop.spec`、`build/build_desktop.ps1`、`requirements-desktop.txt`。
- GitHub Actions `build-desktop`：打 tag 自动构建 Windows zip artifact。
- `scripts/version.py` 单一版本源 + GitHub Releases 更新检查（UI「检查更新」）。
- 桌面版首次运行把 skill 释放到 `%LOCALAPPDATA%`；项目仍创建在用户选择的目录。
- `docs/桌面版.md`：构建、分发、版本更新与边界说明。

### Changed

- 控制台创建项目与运行闸门改为进程内调用 gamecheck，消除打包后 `sys.executable` 依赖。
- 资源路径支持 PyInstaller `_MEIPASS`，控制台可在打包环境运行。

## [0.3.0] - 2026-11-16

### Added

- 本地可视化制作控制台：`scripts/gameconsole.py` + `console_web/`，零第三方依赖，只监听 127.0.0.1。
- 项目启动向导：项目名 + 一句话想法 + 工程目录 → 自动创建本地工程、P0 立项书草稿，并进入 P0 面板。
- 六阶段可视化：P0–P5 状态、闸门红绿灯、当前阶段、下一步建议。
- 环节工作台：文档树 + Markdown 编辑/预览 + 保存 + 版本列表 + 恢复。
- 保存 / 冻结 / 下一步状态机：冻结前自动跑闸门，通过后生成快照并锁定文档；未冻结不能下一步。
- 每环节本地文件夹：`stages/00_立项/` … `stages/05_上线/`，含 README、每次保存的版本副本、冻结快照。
- agent 交接收件箱：`gameconsole.py submit` 提交交付单，网页通过/退回并记录原因。
- 控制台单元/HTTP 测试与使用指南 `docs/控制台使用指南.md`。

### Fixed

- Windows 下 `gameconsole.py --help` 中文输出使用 UTF-8，避免 CLI/CI 编码失败。

### Changed

- `README.md`、`README.en.md`、`SKILL.md`、`SKILL.en.md` 增加控制台入口与 v0.3.0 能力表。
- `docs/维护规范.md`、CI 同步控制台文件与检查。

## [0.2.0] - 2026-11-14

### Added

- 中英双语入口：`README.en.md`、`SKILL.en.md`、`references/en/00-overview.md`；中文入口加语言切换链接。
- `scripts/ue_import_assets.py`：按资产清单批量导入 FBX/GLB，自动设置材质、碰撞、LOD；支持 `--dry-run` 无 UE 校验。
- `scripts/daily_gallery.py`：扫描 UE 截图，按日期生成自包含 HTML/Markdown 巡览页，支持 `--days`、`--compare`、`--json`。
- 键鼠 + 手柄双输入：GDD/技术方案/测试记录/上线清单与 `gate release` 都要求两套设备可完成全流程、热切换与重映射。
- `gamecheck.py change check`：变更单 ↔ 资产清单双向引用校验（CO- 编号、影响资产、清单 source/note）。
- `gate release` 发布检查自动化：12/13 清单、双输入、双语商店素材（胶囊图尺寸/截图/文案/预告片/字幕）、变更对账。
- `templates/13_多语言商店素材清单.md`：中英商店文案、截图、预告片字幕、胶囊图、元数据与合规逐项判定。
- `tests/test_ue_import_assets.py`、`tests/test_daily_gallery.py`；CI 覆盖新脚本。

### Changed

- `gamecheck.py init` 复制 14 份模板、`gamecheck.py` 与 `store/` 目录；项目内可直接运行校验器。
- `docs/维护规范.md`、`README.md`、`SKILL.md`、`references/00`、`02`、`04`、`05` 同步 v0.2 命令与判据。
- 发布指南补充 v0.1.0/v0.2.0 已发布状态与链接。

## [0.1.0] - 2026-11-14

### Added

- 六阶段制作流程：P0 立项 → P1 标准与文档 → P2 技术底座+白模 → P3 资产管线+垂直切片 → P4 内容生产 → P5 打磨+Demo 上线。
- 六道可执行闸门：G0–G5，配套 `scripts/gamecheck.py`（init / doc check / gate spec·whitebox·assets·slice·content·release / numbers check / manifest check）。
- 七份 references：总览、立项、文档标准、3D 美术资产管线、UE5 引擎实现、打磨与 Demo 上线、风险与反模式。
- 十三份模板：立项书、GDD、美术圣经、技术方案、关卡设计、资产清单、数值表、交付单、验收单、变更单、测试记录、周报、Demo 上线清单。
- `docs/设计说明.md`：从原始设想到本流程的逐条对照与改造理由。
- `docs/GitHub发布指南.md`：从零创建仓库、推送、发 Release、后续迭代与安装升级。
- `gamecheck.py init` 会把 13 份模板与校验器复制进游戏项目，项目内可直接运行 `python scripts/gamecheck.py ...`。
- 数值表 key 采用点号命名（`move.jump.height`），同时兼容下划线别名；`numbers check` 复算 g=2h/t²、v=2h/t。
- `docs/维护规范.md`：固定章节、九段结构、改动联动清单与本地测试要求。
- `AGENTS.md`：给 Codex/DSH 等工具的仓库规则入口。
- GitHub Actions CI：Windows + Ubuntu 双平台跑 39 个单元测试。
- 设计原则：可判定优先、白模先行、证据交付、唯一真相源、决策收敛。
