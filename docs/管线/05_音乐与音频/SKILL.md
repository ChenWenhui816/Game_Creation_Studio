---
name: pipeline-05_音乐与音频
description: Music & Audio pipeline for the UE5 solo game studio; use when working on this lane.
when_to_use: 让音乐、音效、配音、混音和 UE 集成成为可交付、可本地化的管线。
inputs: 剧本/台词 | 分镜 cue | 美术氛围 | 平台/响度标准
outputs: 主题/stems | 音效库 | 配音/多语言 | 混音/母带 | MetaSounds/Wwise 集成
gates: G5 音频可集成
owner: studio
version: 0.7.2
---

# 05 · 音乐与音频 · Agent Contract

Read `docs/管线/05_音乐与音频/README.md` first.

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
