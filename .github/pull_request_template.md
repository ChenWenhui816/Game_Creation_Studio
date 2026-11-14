<!-- 一个 PR 只做一件事。标题格式：<type>: <一句话>，例如 docs: 补充 G2 白模闸门的判据 -->

## 1. 这个 PR 改了什么

一句话说明，以及为什么现在要做：

【待填】

关联 issue（没有就写"无"）：#

## 2. 变更类型

- [ ] 新增内容（新模板 / 新章节 / 新检查项）
- [ ] 修正错误（事实错误、命令跑不通、链接失效）
- [ ] 改写表述（不改判定标准，只改说法）
- [ ] 调整文件结构（重命名 / 移动 / 删除）
- [ ] 基础设施（CI、测试、脚本、发布配置）

## 3. 影响的文件

| 文件 | 改了什么 |
|---|---|
| 【待填】 | 【待填】 |
| 【待填】 | 【待填】 |

## 4. 测试命令与结果

在仓库根目录执行，粘贴最后 3 行输出（不要只写"通过"）：

```powershell
python -m unittest discover -s tests -v
python scripts/gamecheck.py --help
git diff --check
```

结果：

```text
【待填：贴命令输出，注明退出码】
```

## 5. 自查清单

- [ ] 新增/修改的章节名与 `scripts/gamecheck.py` 的 `REQUIRED_SECTIONS`、既有模板一致（校验脚本按 H2 精确匹配；编写规范见 `docs/维护规范.md`）
- [ ] 没有遗留 `【待填】` 到非模板文件；模板里的占位符是设计的一部分
- [ ] 所有命令能在 Windows PowerShell 直接复制执行
- [ ] 没有编造 UE / GitHub / Steam / Epic 的参数、价格、政策；不确定处已写"以官方文档为准"并给链接
- [ ] 中文表述，动词开头，无"尽量 / 适当 / 差不多 / 好看"
- [ ] 表格不超过 12 行；超过已拆分
- [ ] 新增或删除模板时，已同步改 `SKILL.md` 文件索引与 `scripts/gamecheck.py` 的 `REQUIRED_SECTIONS`
- [ ] 新增检查项时，已在 `tests/test_gamecheck.py` 加用例

## 6. CHANGELOG

- [ ] 已在 `CHANGELOG.md` 的 `[Unreleased]` 下写一条（Added / Changed / Fixed / Removed 之一）
- [ ] 不需要更新（纯内部重构、无用户可见变化）——原因：【待填】

## 7. 风险与回滚

- 这个改动最可能在哪里出问题：【待填】
- 出问题时如何回滚（`git revert <hash>` 还是 `git checkout <tag>`）：【待填】
