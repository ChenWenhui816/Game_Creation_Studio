# 贡献指南

> 面向：未来的你自己、其他使用者、被派来改这个仓库的 agent。
> 一句话规则：**一个改动只做一件事；没有测试和 CHANGELOG 的改动不合并。**

本仓库不是游戏工程，是**流程 skill**。改它的唯一目的是让"下一款游戏少走一次弯路"。所以判断一次改动该不该进的顺序是：

1. 它让哪条标准更可判定？
2. 它有没有对应的测试或证据？
3. 它会不会让已发布版本的使用者无感升级失败？

三个都答不上来，先开 issue，别写代码。

---

## 0. 改什么、怎么走

| 你要改的 | 走法 | 必须带的 |
|---|---|---|
| 错别字、失效链接、示例数字写错 | 直接提交 `main` | 一个 `fix:` 或 `docs:` 提交 |
| 某个模板的某一节填法、references 里一段解释 | 直接提交 `main` | 本地测试 + CHANGELOG |
| 模板的固定 H2 章节名、文件重命名/删除 | 开 `feat/` 或 `docs/` 分支 + PR | 同步改 `scripts/gamecheck.py`、`tests/`、`SKILL.md` |
| 新增模板、新增校验规则、新增闸门检查项 | 先开 issue（模板：新模板或规则），再开分支 + PR | 测试用例、CHANGELOG、影响的文件清单 |
| 改 CI、LICENSE、发布流程 | 开分支 + PR，合并后 24 小时再发版 | 在 PR 描述里写明回滚方式 |

> 判断标准：**改动会不会让别人的 `gamecheck` 结果变化？** 会 → 必须走 PR + 测试；不会 → 直接 `main`。

---

## 1. 本地环境

只依赖 Python 标准库，不需要 `pip install`。Windows PowerShell 下执行：

```powershell
cd Personal_Game_Studio_UE   # 换成你的克隆目录
python --version
python -m unittest discover -s tests -v
python scripts/gamecheck.py --help
```

看到 `OK` 才算环境正常；`python` 命令不存在时先装 Python 3.10 或更高版本（CI 用 Python 3.12，见 `.github/workflows/ci.yml`）。

开工前先确认工作区干净：

```powershell
git status
```

输出 `nothing to commit, working tree clean` 再动手。有未提交改动时先 `git stash` 或提交，不要混着改。

---

## 2. 提 Issue

先搜索已有 issue，避免重复。本仓库有两个模板：

| 模板 | 什么时候用 | 必须填 |
|---|---|---|
| 流程问题 | 按文档/闸门走，结果和文档写的不一样；或判据无法判定 | 阶段、闸门、期望 vs 实际、复现步骤、版本号、退出码 |
| 新模板或规则 | 想新增/修改模板、校验规则、闸门检查项 | 解决什么问题（带数字）、验收标准、影响的文件 |

一条好 issue 与一条坏 issue 的区别：

| 反例（会被要求补充） | 正例 |
|---|---|
| "G2 感觉太严了" | "G2 要求灰盒 60fps，但我的机器是 4060，白模只有 45fps；期望文档给出机器基线，实际没有" |
| "模板不好用" | "填 `templates/05_资产清单.csv` 时 `license` 列没有可选值说明，填了 3 次被退回 3 次" |
| "发布流程跑不通" | "执行 `git push origin v0.1.0` 返回 403，PAT 已勾 repo scope，完整输出见下" |

没有版本号和证据的 issue，一律先补再排期。

---

## 3. 提交信息规范

采用 Conventional Commits 的精简子集，**中文写正文**，一行标题不超过 50 个字符：

```text
<type>: <动词开头的短句>
```

| type | 用于 | 示例 | 进 CHANGELOG 吗 |
|---|---|---|---|
| `feat` | 新增模板、规则、闸门、章节 | `feat: 新增性能验收单模板` | 进 Added |
| `fix` | 修正事实错误、跑不通的命令、失效链接 | `fix: 修正 G2 盲测人数与闸门表不一致` | 进 Fixed |
| `docs` | 只改说明、示例、措辞 | `docs: 补充资产导入 30 分钟的计时口径` | 进 Changed（内容有变时） |
| `test` | 只改测试 | `test: 补充章节顺序颠倒的用例` | 不进 |
| `chore` | CI、依赖、发布、目录整理 | `chore: 发布 v0.1.0` | 不进 |
| `refactor` | 不改行为的代码整理 | `refactor: 抽出章节解析函数` | 不进 |

补充规则：

- 标题用**动词开头**，不加句号，不写"更新了一下"。
- 正文写**为什么**，不写"改了哪几行"（`git diff` 已经说明）。
- 破坏性改动：类型后加 `!`，例如 `feat!: 重命名全部模板为 NN_ 前缀`，并在正文写 `BREAKING CHANGE:` 与迁移办法。
- 一个提交只做一件事。改了 5 个文件但只有 1 个目的，可以；改了 5 个目的，拆成 5 个提交。

---

## 4. 分支与 PR

- `main` 任何时候都应可发布、CI 应全绿。
- 小改动直接提交 `main`；下面四类**必须开分支 + PR**：
  1. 改模板的固定 H2 章节名；
  2. 改 `scripts/gamecheck.py` 的判定逻辑或退出码；
  3. 重命名、移动、删除文件；
  4. 改 CI、LICENSE、发布流程。
- 分支命名：`feat/性能验收单`、`fix/g2-盲测人数`、`docs/安装说明`（中文可以，但不要空格）。

```powershell
git switch -c feat/add-perf-checklist
# 改文件、跑测试
git add -A
git commit -m "feat: 新增性能验收单模板"
git push -u origin feat/add-perf-checklist
```

PR 要求：

1. 用 `.github/pull_request_template.md` 的七节全部填完，测试结果贴**命令输出**，不写"已通过"。
2. 自己 review 一遍再请求合并；solo 项目也**至少等 24 小时**再合并，给自己冷静期。
3. 合并用 **Squash and merge**，一个 PR 在 `main` 上只留一个提交，保持线性历史。
4. PR 标题与最终 squash 提交标题一致。
5. 合并后删除远程分支：`git push origin --delete feat/add-perf-checklist`。

---

## 5. 常见改动：必改清单

只改一处就提交，是 CI 变红和"文档与规则打架"的主要原因。按表逐项对：

| 改动 | 必改文件（缺一不可） |
|---|---|
| 改模板的固定 H2 章节名 | 模板本身 + `scripts/gamecheck.py` 的 `REQUIRED_SECTIONS` + `tests/test_gamecheck.py` + 引用该章节的 `references/` + `CHANGELOG.md` |
| 新增模板 | `templates/NN_名称.md` + `SKILL.md` 文件索引 + `README.md` 目录 + `gamecheck.py`（纳入校验时）+ 测试（纳入校验时）+ CHANGELOG |
| 删除/重命名模板 | 同"新增模板"全部位置 + 所有引用它的 `references/` + `gamecheck.py` 默认路径 |
| 新增闸门/检查项 | `gamecheck.py` + 测试（正例/反例/边界）+ `SKILL.md` 闸门命令表 + 对应 `references/` 闸门一节 + CHANGELOG |
| 改 references 的流程步骤 | 对应 references + 受影响的模板 + CHANGELOG（判据变化时） |
| 改示例数值（如跳跃高度） | `templates/06_数值表.csv` + 引用该数值的所有文档 + 测试断言 + CHANGELOG |
| 改安装/发布相关 | `README.md` + `docs/GitHub发布指南.md` + `AGENTS.md`（若影响 agent 行为）+ CHANGELOG |

---

## 6. 新增一个阶段（慎用）

8 条管线（P0–P7）是本 skill 的核心契约。**默认答案是"不新增"**：先证明现有管线的某一节装不下你的需求，再按下面七步走。

1. 开 issue，写明"为什么放进现有阶段会坏"，给出至少 1 个真实项目的例子。
2. 确定编号（P6 或插入式 P2.5）与闸门编号（G6），修改 `references/00-总览与协作.md` 的阶段表、mermaid 图、闸门总表。
3. 在 `SKILL.md` 的"阶段路由表"加一行，"文件索引"加一行。
4. 写新的 `references/NN-名称.md`，按固定九段结构：标题 / 引用块 / 这一阶段要回答的问题 / 输入 / 步骤 / 产出 / 闸门 / 反模式 / 检查清单。
5. 若该阶段有固定文档，写模板并登记到 `gamecheck.py` 的 `REQUIRED_SECTIONS`，补测试。
6. 同步 `docs/设计说明.md` 的"原始设想对照"一节。
7. CHANGELOG 记 `Added`；版本号至少 minor（`0.x` 阶段允许破坏性 minor）。

---

## 7. 新增一个模板

模板是给人**直接复制填写**的，不是教程。标准：

1. 文件命名 `templates/NN_名称.md`，`NN` 取下一个未使用的两位数，**不要跳号**。
2. 结构固定：H1 标题 → 一行引用块（`> 适用阶段：P? ｜ 何时加载：…… ｜ 上游：…… ｜ 下游：……`）→ 固定 H2 章节 → 末尾"变更记录"。
3. 占位符只用 `【待填】`；示例值标 `【示例】`；不写"根据实际情况填写"这类无法执行的提示。
4. 每个待填处给一行填写说明（如"填米，保留 1 位小数"），不写大段解释。
5. 篇幅 40–160 行；表格优先，单表不超过 12 行。
6. 至少在一个真实项目里从头填一遍，把填不下去的地方改掉再提交。

同步位置见第 5 节表格。

---

## 8. 新增一条校验规则

校验器只做**确定性判定**：字符串、数值、文件是否存在、章节是否齐全。它不判断"好不好玩、好不好看"。

1. 在 `scripts/gamecheck.py` 加检查函数，只用 Python 标准库；失败信息必须包含：`文件:行`、期望、实际、怎么修。
2. 退出码语义不变：`0` 通过、`1` 不通过、`2` 用法错误。
3. 在 `tests/test_gamecheck.py` 至少加三个用例：**正例、反例、边界**（空文件 / 缺文件 / 章节顺序颠倒）。
4. 容差写进常量并加注释，例如面数上限 `+5%`；不要把容差写死在正则里。
5. 规则先在 `references/` 对应闸门写清"判定项 + 不合格怎么办"，再实现。
6. 禁止为了让 CI 变绿而把规则降级成 warning、删测试、放宽容差。

---

## 9. 本地测试与自测

提交前必跑，四条全绿：

```powershell
python -m unittest discover -s tests -v
python scripts/gamecheck.py --help
git diff --check
git status
```

手动验收（改了闸门或 init 时必做）：在临时目录跑一遍初始化与各闸门，确认退出码符合预期。

```powershell
New-Item -ItemType Directory -Force D:\tmp\gc-test | Out-Null
python scripts/gamecheck.py init --dir D:\tmp\gc-test --name "测试项目"
python scripts/gamecheck.py doc check --stage 0 --root D:\tmp\gc-test
echo $LASTEXITCODE
```

CI 会在 push 与 PR 时跑 Windows + Ubuntu 两个平台（见 `.github/workflows/ci.yml`）。本地绿、CI 红，通常是路径分隔符、编码或大小写问题。

---

## 10. Review 清单

自己或他人合并前逐条勾：

- [ ] 模板的 H2 章节名与 `scripts/gamecheck.py` 的 `REQUIRED_SECTIONS` **逐字**一致（含全角标点）
- [ ] 非模板文件里没有遗留 `【待填】`；模板里的占位符是有意保留
- [ ] 所有命令能在 Windows PowerShell 直接复制执行，路径不依赖 Bash 语法
- [ ] 没有编造 UE / GitHub / Steam / Epic 的参数、价格、政策；不确定处写了"以官方文档为准"并给官方链接
- [ ] 每个新增判据带数字、阈值或链接，能回答"合格/不合格"
- [ ] 表格有说明，单表不超过 12 行
- [ ] 跨文件引用的相对路径全部存在（如 `references/04-引擎实现.md`）
- [ ] 数值示例自洽：改了一处数字，引用它的所有地方同步改
- [ ] `SKILL.md` 路由表、闸门命令表、文件索引已同步
- [ ] `CHANGELOG.md` 的 `[Unreleased]` 已加条目
- [ ] 新增/修改的检查项有测试，本地 `unittest` 全绿
- [ ] 没有提交 `__pycache__/`、`.venv/`、`sample/`、`out/`、`.gamecheck/`、`*.log`
- [ ] 没有大文件（单文件 < 10 MB）；没有把 UE 工程产物放进仓库

---

## 11. 发布流程（5 步）

1. **准备**：确认 `main` CI 绿；把 `CHANGELOG.md` 的 `[Unreleased]` 条目整理好，确认没有遗漏。
2. **改版本号**：在 `CHANGELOG.md` 把 `[Unreleased]` 内容移到 `## [0.x.0] - YYYY-MM-DD` 下，并重新留一个空的 `[Unreleased]` 段落；同步 README 徽章里的版本号与 `CHANGELOG` 链接。
3. **提交并推送**：`git add -A` → `git commit -m "chore: 发布 v0.x.0"` → `git push`。
4. **打 tag 并推送**：`git tag -a v0.x.0 -m "v0.x.0: 一句话说明"` → `git push origin v0.x.0`。
5. **建 Release**：GitHub 仓库页 → Releases → Draft a new release → 选 `v0.x.0` → 标题 `v0.x.0` → 说明从 CHANGELOG 复制 → Publish；发布后核对 Actions 绿、Release 页能下载源码 ZIP。

版本号怎么定见 `docs/GitHub发布指南.md` 第 5 节；完整发布与推送步骤见同一文件第 2–6 节。

---

## 12. 禁止

- 修改已发布 tag 指向的提交（使用者锁版本会拿到不同内容）。
- 对 `main` 执行 `git push --force`（唯一例外：误提交密钥/大文件后清理历史，且先 `git clone` 备份）。
- 把校验器改成依赖第三方库；它是"任何机器 `python` 就能跑"的底线。
- 为了让 CI 变绿而删测试、降级规则、放宽阈值。
- 在模板正文里写教程；教程属于 `references/`。
- 提交构建产物、缓存、`sample/`、`out/`、`.gamecheck/`。
- 用"更顺手 / 更统一 / 差不多 / 好看"作为合并理由。
