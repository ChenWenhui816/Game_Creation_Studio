---
name: pipeline-04_测试与技术
description: Test & Tech pipeline for the UE5 solo game studio; use when working on this lane.
when_to_use: 用白模验证移动/相机/战斗/性能/存档；先证明能玩，再铺内容。
inputs: GDD | 技术方案 | 美术圣经 | 资产清单 | 剧本场景
outputs: UE 5.8 工程 | 灰盒关卡 | docs/10_测试记录.md | 性能/盲测证据
gates: G4 白模/测试可玩
owner: studio
version: 0.9.0
---

# 04 · 测试与技术 · Agent Contract

Read `docs/管线/04_测试与技术/README.md` first.

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
