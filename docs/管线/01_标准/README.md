# 01 · 标准 使用说明

> 中文为主 / Chinese primary · English summary at the bottom.

## 目标

把玩法、美术、技术、数值和资产规格变成可判定的唯一真相源。

## 什么时候用

在当前阶段的**这个管线**需要产出/验收时使用；不要等所有前置 100% 完成才开始概念探索。

## 输入

- 立项书
- 参考作品
- UE 5.8 目标平台

## 输出

- docs/01_游戏设计文档.md
- docs/02_美术圣经.md
- docs/03_技术方案.md
- docs/05_资产清单.csv
- docs/06_数值表.csv

## 步骤

1. GDD 写清核心循环、操作、战斗、关卡、UI、音频、范围。
2. 美术圣经锁风格、色板、比例、材质、UI、命名。
3. 技术方案锁 UE 5.8、插件、目录、性能预算、存档、构建、MCP。
4. 资产清单先定 16 列表头，再逐条登记。
5. 数值表保证 g=2h/t²、v=2h/t 自洽。

## 验收闸门

**G1 标准可判定**

## 工具

- gamecheck gate spec
- numbers check
- manifest check

## 交接

P2 剧本：故事/场景/镜头；P3 白模：按 GDD 做灰盒。

## 文件位置

- 文档：docs/
- 阶段版本/冻结：stages/01_标准/
- 证据：docs/evidence/
- 资产：assets/、art/Source/、art/Export/

## 注意事项

标准书不是散文；每条都要能被检查或 3 秒人眼判定。

---

### English Summary

Standards & Docs: 把玩法、美术、技术、数值和资产规格变成可判定的唯一真相源。
Inputs: 立项书; 参考作品; UE 5.8 目标平台.
Outputs: docs/01_游戏设计文档.md; docs/02_美术圣经.md; docs/03_技术方案.md; docs/05_资产清单.csv; docs/06_数值表.csv.
Gate: G1 标准可判定.
