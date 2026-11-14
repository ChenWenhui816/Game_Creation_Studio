# Changelog

本文件记录 skill 的所有重要变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Changed

- 发布指南补充 v0.1.0 已发布状态、仓库与 Release 链接。

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
