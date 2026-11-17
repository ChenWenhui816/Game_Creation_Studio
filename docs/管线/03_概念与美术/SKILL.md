---
name: pipeline-03_概念与美术
description: Concept & Art pipeline for the UE5 solo game studio; use when working on this lane.
when_to_use: 先定概念、风格、色板、视觉锚点和资产清单，再进白模与测试。
inputs: GDD | 剧本场景需求 | 美术偏好 | 资产预算
outputs: docs/02_美术圣经.md | docs/05_资产清单.csv | 概念图/色板 | 管线验证
gates: G3 概念与美术锁定
owner: studio
version: 0.9.0
---

# 03 · 概念与美术 · Agent Contract

Read `docs/管线/03_概念与美术/README.md` first.

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
