---
name: pipeline-03_白模与技术
description: Whitebox & Tech pipeline for the UE5 solo game studio; use when working on this lane.
when_to_use: 用 UE 5.8 做出能跑、能跳、能玩的最小灰盒，验证玩法而不是画面。
inputs: GDD | 技术方案 | 剧本场景需求
outputs: UE 5.8 工程 | 可玩灰盒关卡 | docs/10_测试记录.md | 盲测证据
gates: G3 白模可玩
owner: studio
version: 0.7.6
---

# 03 · 白模与技术 · Agent Contract

Read `docs/管线/03_白模与技术/README.md` first.

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
