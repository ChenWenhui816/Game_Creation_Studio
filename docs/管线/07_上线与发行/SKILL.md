---
name: pipeline-07_上线与发行
description: Release & Publishing pipeline for the UE5 solo game studio; use when working on this lane.
when_to_use: 把游戏变成可发布、可审核、可多语言、可回滚的发行版本。
inputs: 完整游戏 | 商店素材 | 本地化 | 构建/认证
outputs: Win/Steam 构建 | 主机认证构建 | 商店页/PV/截图 | 多语言 | 上线清单
gates: G7 上线清单
owner: studio
version: 0.7.3
---

# 07 · 上线与发行 · Agent Contract

Read `docs/管线/07_上线与发行/README.md` first.

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
