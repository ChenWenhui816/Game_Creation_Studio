# 管线使用说明 / Pipeline Guides

> 中文为主，English summary at each guide.
> 8 条生产管线不是瀑布；它们是并行车道，由治理闸门管理。

| # | 管线 | 英文 | 闸门 |
|---|---|---|---|
| 00 | 立项 | Concept & Scope | G0 立项书可复述 |
| 01 | 标准 | Standards & Docs | G1 标准可判定 |
| 02 | 剧本与叙事 | Script & Narrative | G2 剧本可拍 |
| 03 | 概念与美术 | Concept & Art | G3 概念与美术锁定 |
| 04 | 测试与技术 | Test & Tech | G4 白模/测试可玩 |
| 05 | 音乐与音频 | Music & Audio | G5 音频可集成 |
| 06 | 内容生产 | Content Production | G6 全流程通关 |
| 07 | 上线与发行 | Release & Publishing | G7 上线清单 |

## 角色、路由与来源

- 角色：agents/README.md
- 路由：router/SKILL.md
- 参考库吸收：docs/参考库与能力映射.md
- 运行手册：docs/工作室流程目录.md

## 先读什么

1. 先读当前管线的 README（本目录）；
2. 再读对应 `SKILL.md`，agent 按契约执行；
3. 用 `studio explain <编号>` 在终端快速查看；
4. 用 `studio doctor` 检查环境；
5. 用 `studio next` 看下一步。

## 通用规则

- 文档是唯一真相源；阶段文件夹是版本/冻结快照；
- 每个交付必须有证据（截图/录屏/命令输出）；
- 修改冻结内容必须走变更单；
- 资产必须登记来源、许可证、AI 模型/提示词；
- 本地文件优先；MCP/Gateway 只是工具层。

## English Summary

Eight production lanes: concept, standards, script, whitebox/tech, art/video, music/audio, content, release.
They are parallel lanes governed by gates, not a strict waterfall. Each lane has a human-readable README and an agent-facing SKILL.md.
