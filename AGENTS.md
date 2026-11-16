# 本仓库规则（给 agent）

本仓库是一个 **AI agent 技能包**，不是游戏工程。本文件只用于维护本仓库；游戏项目请使用 `gamecheck.py init` 生成的 `AGENTS.md`。你可能是来做两件事之一：

## A. 用这套 skill 做一个游戏

1. 读 `SKILL.md`，按阶段路由表加载 `references/` 下对应文件。
2. 在游戏项目根执行 `scripts/gamecheck.py` 的闸门命令，读退出码。
3. 遵守八条铁律：标准书唯一真相、用户三类决策、证据交付、偏离先记录、数值单一来源、闸门只修内容、每日 commit、变更单与资产清单对账。
4. 每个任务交 `docs/07_交付单/`；资产/系统验收用 `docs/08_验收单/`。

## B. 修改这套 skill

1. 先读 `CONTRIBUTING.md` 与 `docs/维护规范.md`（维护期规范）。
   控制台：`scripts/gameconsole.py` + `console_web/`；启动 `python scripts/gameconsole.py serve`。
2. 改 `templates/` 的固定 H2 章节名时，必须同步改 `scripts/gamecheck.py` 的 `REQUIRED_SECTIONS`、`tests/` 与 `references/`，否则 CI 会红。
3. 本地验证：
   ```bash
   python -m unittest discover -s tests -v
   python scripts/gamecheck.py --help
   ```
4. 更新 `CHANGELOG.md`，按 `feat/fix/docs/test/chore` 写提交信息。
5. 发布流程见 `docs/GitHub发布指南.md`。

## 禁止

- 提交 `__pycache__/`、`.venv/`、`sample/`、`out/`、`.gamecheck/`
- 在未同步校验规则的情况下改模板章节名
- 把校验器改成依赖第三方库（必须保持 Python 标准库）
- 直接修改已发布 tag 的历史
