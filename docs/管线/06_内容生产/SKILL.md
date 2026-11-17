---
name: pipeline-06_内容生产
description: Content Production pipeline for the UE5 solo game studio; use when working on this lane.
when_to_use: 把白模、资产、剧本、音频组装成完整可通关的游戏。
inputs: 白模 | 资产库 | 剧本/任务 | 音频
outputs: 全部关卡 | 敌人/Boss/收集 | 剧情/任务/UI | 周报与验收单
gates: G6 全流程通关
owner: studio
version: 0.7.4
---

# 06 · 内容生产 · Agent Contract

Read `docs/管线/06_内容生产/README.md` first.

## 必须做

- 输出写入声明的文件/目录，不覆盖冻结内容；
- 每个交付附证据；
- 变更走变更单；
- 资产/音频/视频登记来源与许可证；
- 不绕过闸门。

## 不要做

- 不编造 UE/主机/平台 API；
- 不把 AI 生成物直接当最终资产；
- 不在本管线修改其他管线的唯一真相源。
