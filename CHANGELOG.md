# Changelog

本文件记录 skill 的所有重要变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
