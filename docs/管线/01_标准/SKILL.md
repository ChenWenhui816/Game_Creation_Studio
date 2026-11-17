---
name: pipeline-01_标准
description: Standards & Docs pipeline for the UE5 solo game studio; use when working on this lane.
when_to_use: 把玩法、美术、技术、数值和资产规格变成可判定的唯一真相源。
inputs: 立项书 | 参考作品 | UE 5.8 目标平台
outputs: docs/01_游戏设计文档.md | docs/02_美术圣经.md | docs/03_技术方案.md | docs/05_资产清单.csv | docs/06_数值表.csv
gates: G1 标准可判定
owner: studio
version: 0.9.0
---

# 01 · 标准 · Agent Contract

Read `docs/管线/01_标准/README.md` first.

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
