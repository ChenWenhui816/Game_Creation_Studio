# 07 · 上线与发行 使用说明

> 中文为主 / Chinese primary · English summary at the bottom.

## 目标

把游戏变成可发布、可审核、可多语言、可回滚的发行版本。

## 什么时候用

在当前阶段的**这个管线**需要产出/验收时使用；不要等所有前置 100% 完成才开始概念探索。

## 输入

- 完整游戏
- 商店素材
- 本地化
- 构建/认证

## 输出

- Win/Steam 构建
- 主机认证构建
- 商店页/PV/截图
- 多语言
- 上线清单

## 步骤

1. 锁版本，做 Release 分支与回滚方案。
2. 打包/烘焙/性能/内存/存档兼容测试。
3. 准备商店素材：胶囊图、截图、PV、文案、字幕、多语言。
4. 主机认证：TRC/TCR、手柄、断网、存档、崩溃。
5. 上线演练与发布；保留 hotfix 与回滚包。

## 验收闸门

**G7 上线清单**

## 工具

- UE 打包
- Steamworks/主机 SDK
- store/
- gamecheck gate release

## 交接

发布后：hotfix、社区、数据、下一版。

## 文件位置

- 文档：docs/
- 阶段版本/冻结：stages/07_上线与发行/
- 证据：docs/evidence/
- 资产：assets/、art/Source/、art/Export/

## 注意事项

主机 SDK/认证受 NDA；PC/Steam 先跑通，再并行主机。微信/网页后置为独立 2D 线。

---

### English Summary

Release & Publishing: 把游戏变成可发布、可审核、可多语言、可回滚的发行版本。
Inputs: 完整游戏; 商店素材; 本地化; 构建/认证.
Outputs: Win/Steam 构建; 主机认证构建; 商店页/PV/截图; 多语言; 上线清单.
Gate: G7 上线清单.
