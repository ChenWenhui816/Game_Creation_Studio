# UE 资产导入脚本（scripts/ue_import_assets.py）

> 适用阶段：P3 资产管线 ｜ 何时加载：一批资产通过验收、准备进 UE 工程时 ｜ 上游：`docs/05_资产清单.csv`、`art/Export/` ｜ 下游：G3 资产合规、垂直切片。

把"手工在 Content Browser 里点导入"变成一条可重复的命令：读资产清单 → 校验路径与 note → 批量导入 FBX/GLB → 套材质、设碰撞、管 LOD → 输出 JSON 报告。没有 UE 的环境用 `--dry-run` 先校验清单，不 import unreal。

脚本位置：skill 仓库 `scripts/ue_import_assets.py`。可复制进游戏项目的 `scripts/` 后独立运行，也可直接用 skill 仓库的那份加 `--project-root` 指向项目。

---

## 1. 它解决什么问题

| 手工导入的毛病 | 脚本怎么处理 |
|---|---|
| 20 个资产点 20 次，漏 2 个没人知道 | 以清单为唯一来源，逐行处理并打印 `[OK]/[SKIP]/[FAIL]` |
| 路径、id、材质路径写错，导进去才发现 | `--dry-run` 在 1 秒内查完全部行，退出码 1 指出问题行 |
| 同一个 FBX 导两次，Content Browser 出现两个重名 | 导入前 `does_asset_exist`，默认跳过，`--force` 才覆盖 |
| 碰撞/LOD 靠记忆，不同批不一致 | note 列写死 `collision=...;lod=...`，脚本统一执行 |
| 出了问题不知道导了什么 | `--report` 输出 UTF-8 JSON，可存档进 `docs/07_交付单/` 作证据 |

**边界：脚本不判断美术品质，不重拓扑、不展 UV、不生成 LOD 美术质量。它只保证"清单写了什么，UE 里就按什么导入"。**

---

## 2. 前置条件

| 条件 | 怎么确认 |
|---|---|
| 项目根有 `docs/05_资产清单.csv`，表头 16 列一字不差 | 见 `templates/05_资产清单.csv`；脚本发现表头不对直接失败 |
| 清单行的 `file` 指向项目根内的 `.fbx` 或 `.glb` | `--dry-run` 逐行查存在性与 `..` 穿越 |
| 资产状态是 `已通过` 或 `已入库`（默认） | 其他状态被 `--include-status` 过滤成 `[SKIP]` |
| 已跑过 `gate assets` 且退出码 0 | `python scripts/gamecheck.py gate assets --root .` |
| UE 内模式：编辑器能打开项目、Python 插件已启用 | UE 5.8 默认带 Python 插件；Editor Scripting Utilities 也要启用 |
| UE 内模式：当前分支已 commit | `git status --short` 无未提交改动 |

---

## 3. 两种运行方式

| 模式 | 命令 | 需要 UE | 作用 |
|---|---|---|---|
| dry-run（先跑这个） | `python scripts/ue_import_assets.py --project-root . --dry-run` | 否 | 校验清单、文件、note、目标路径；不写任何资产 |
| UE 内导入 | 编辑器 Execute Python Script 或 `UnrealEditor-Cmd` | 是 | 真正导入，并设置材质/碰撞/LOD |

**顺序固定：先 `--dry-run` 全绿 → 再在分支上小批量导入 → 查报告 → 合入。** 跳过 dry-run 直接导入，等于把清单错误写进工程。

---

## 4. 资产清单约定

### 4.1 表头（16 列，顺序固定）

```text
id,type,name,usage,source,file,faces,textures,materials,animations,lod,collision,license,owner,status,note
```

脚本自带一份与 `templates/05_资产清单.csv` 相同的表头常量，不 import `gamecheck.py`；文件可单独复制进游戏项目。表头多一列、少一列、换顺序都判失败。

### 4.2 只处理哪些行

| 规则 | 说明 |
|---|---|
| 扩展名 | `file` 以 `.fbx` 或 `.glb` 结尾（不区分大小写）才处理；`.png`、`.wav`、`.uasset` 等行直接忽略，不计入 `total` |
| 状态 | `status` 必须在 `--include-status` 里，默认 `已通过,已入库`；否则 `[SKIP]` |
| 选择 | 传了 `--only id1,id2` 就只处理这些 id，其余 `[SKIP]` |
| 重复 | 同一批里 `id` 重复或 `file` 重复，后出现的行 `[FAIL]` |

### 4.3 type → UE 目标目录

| type | 子目录 | 目标资产路径 |
|---|---|---|
| `char` / `enemy` | Characters | `/Game/_Project/Characters/<id>` |
| `env` | Environment | `/Game/_Project/Environment/<id>` |
| `prop` | Props | `/Game/_Project/Props/<id>` |
| `fx` | VFX | `/Game/_Project/VFX/<id>` |
| `ui` | UI | `/Game/_Project/UI/<id>` |
| `anim` | Animations | `/Game/_Project/Animations/<id>` |
| `mat` | Materials | `/Game/_Project/Materials/<id>` |

`--content-dir` 改父目录，默认 `/Game/_Project`；必须以 `/Game/` 开头，否则退出码 2。

### 4.4 note 列：分号分隔的 key=value

```text
mat=/Game/_Project/Materials/M_hero;collision=use_complex_as_simple;lod=3;lod_count=3;scale=1.0
```

| key | 默认 | 允许值 | 作用 |
|---|---|---|---|
| `mat` | 空（不改材质） | 以 `/Game/` 开头的资产路径 | 导入后套到 StaticMesh / SkeletalMesh 的所有材质槽 |
| `collision` | `complex` | `none` / `simple` / `complex` / `use_complex_as_simple` | StaticMesh 碰撞策略，见 §7 |
| `lod` | `1` | 1–4 的整数 | 期望 LOD 级数；没写 `lod_count` 时复用它 |
| `lod_count` | 取 `lod` | 1–4 的整数 | 期望 LOD 级数；`--auto-lod` 时按它生成 |
| `scale` | `1.0` | 0.01–100 的数 | 导入缩放（`import_uniform_scale`），用于米/厘米单位差 |
| `import` | 空 | 任意字符串 | 保留键，当前版本解析后不生效，也不报错 |

**note 解析规则：**

1. 用 `;` 或 `；` 分段；每段按第一个 `=` 拆成 key 和 value。
2. 不含 `=` 的段视为备注文字，静默忽略。可以继续写"贴图 3 张；验收单 docs/08_验收单/x.md"。
3. 含 `=` 但 key 不在上表：记 `warning`，该行仍可通过。未知 key 不会让 `failed` 加 1。
4. 同一个 key 写两次：取最后一个值，不报警告。
5. `mat` 不以 `/Game/` 开头、`collision` 越界、`lod`/`lod_count`/`scale` 越界：该行 `[FAIL]`。

---

## 5. CLI 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--project-root` | UE 内取 `unreal.Paths.project_dir()`；无 UE 时必填 | 项目根目录 |
| `--manifest` | `<项目根>/docs/05_资产清单.csv` | 资产清单 CSV 路径 |
| `--content-dir` | `/Game/_Project` | UE 目标父目录，必须 `/Game/` 开头 |
| `--dry-run` | 关 | 只校验，不 import unreal、不写资产 |
| `--only` | 全部 | 逗号分隔的 id 白名单 |
| `--include-status` | `已通过,已入库` | 逗号分隔的状态白名单，未知状态退出码 2 |
| `--auto-lod` | 关 | 尝试自动生成 LOD；不开只检查 LOD 数 |
| `--force` | 关 | 目标已存在时覆盖；默认跳过 |
| `--report` | 不写 | JSON 报告输出路径（父目录自动创建，UTF-8） |
| `--json` | 关 | stdout 只输出 JSON；便于机器读与 CI |
| `--version` | — | 打印脚本版本 |

### 退出码

| 退出码 | 含义 | 下一步 |
|---|---|---|
| 0 | 全部成功或跳过 | 把报告存进交付单，进入下一步 |
| 1 | 至少一条失败；或清单/表头读不了 | 读 `[FAIL]` 行与 `errors`，修清单或文件后重跑 |
| 2 | 用法错误或环境不满足（无 UE 却没加 `--dry-run`、`--content-dir` 非法等） | 按 stderr 提示改命令 |

**任何模式下都不向用户抛 traceback**；单条导入失败不中断整批。读退出码，不读日志猜。

---

## 6. dry-run 用法

### 6.1 最小流程（【示例】）

项目根：

```text
【示例】D:/games/my-game/
├─ docs/05_资产清单.csv
├─ art/Export/char_hero/SK_char_hero.fbx
├─ art/Export/env_ruins_wall/SM_env_ruins_wall.glb
└─ scripts/ue_import_assets.py      # 从 skill 仓库复制过来
```

清单里两行（`【示例】`）：

```csv
【示例】char_hero,char,提灯少年,玩家可操作角色,SDXL + Tripo3D,art/Export/char_hero/SK_char_hero.fbx,38400,2048x2048,3,8,3,胶囊,商业可用,你,已入库,mat=/Game/_Project/Materials/M_hero;collision=use_complex_as_simple;lod=3;lod_count=3;scale=1.0
【示例】env_ruins_wall,env,废墟墙模块,场景模块,Flux + Meshy,art/Export/env_ruins_wall/SM_env_ruins_wall.glb,2400,2048x2048,1,0,3,UCX 盒 x1,商业可用,你,已通过,collision=simple;lod=2;lod_count=2;贴图 2 张
```

运行：

```powershell
cd D:\games\my-game
python scripts/ue_import_assets.py --project-root . --dry-run
```

输出（【示例】）：

```text
== ue_import_assets.py ｜ dry-run 校验 ==
项目根：D:\games\my-game
清单：D:\games\my-game\docs\05_资产清单.csv
目标目录：/Game/_Project
[OK] char_hero -> /Game/_Project/Characters/char_hero（dry-run 校验通过）
[OK] env_ruins_wall -> /Game/_Project/Environment/env_ruins_wall（dry-run 校验通过）
2 成功 / 0 跳过 / 0 失败（清单候选 2 条）
结论：通过。
```

### 6.2 加机器可读报告（【示例】）

```powershell
python scripts/ue_import_assets.py --project-root . --dry-run --json --report out/import-dry-run.json
```

`--json` 时 stdout 只有 JSON；`--report` 同时写文件。失败也写报告，退出码仍为 1。

### 6.3 只看这一批（【示例】）

```powershell
python scripts/ue_import_assets.py --project-root . --dry-run --only char_hero,prop_crate
```

### 6.4 正例与反例

| 类型 | 写在哪里 | 内容 | dry-run 结果 |
|---|---|---|---|
| 正例 | note 列 | `mat=/Game/_Project/Materials/M_hero;collision=use_complex_as_simple;lod=3;lod_count=3;scale=1.0` | `[OK]`，材质/碰撞/LOD/缩放全部记录 |
| 反例 1 | note 列 | `mat=Materials/M_hero` | `[FAIL]`：`mat 必须以 /Game/ 开头` |
| 反例 2 | note 列 | `collision=box;lod=5;scale=0` | 3 条错误：collision 越界、lod 越界、scale 越界 |
| 反例 3 | file 列 | `../art/SK_x.fbx` | `[FAIL]`：`file 越出 project-root（禁止 .. 穿越）` |
| 反例 4 | 两行 note 列 | 两个不同 id 的 file 都指向 `art/Export/shared/mesh.fbx` | 后一行 `[FAIL]`：`file 重复` |

**反例的正确修法是改清单，不是给脚本加白名单。** 闸门只能靠修内容变绿。

---

## 7. UE 内运行

### 7.1 方式 A：Execute Python Script（不用命令行）

1. 先 commit，再开分支：
   ```powershell
   git status --short
   git checkout -b asset/import-batch-01
   ```
2. 先跑 `--dry-run` 全绿（见 §6）。
3. （可选）打开脚本顶部，把参数写进 `EDITOR_ARGS`；不传参数也能跑，自动取当前工程目录、默认目标目录与默认状态，但没有报告文件：
   ```python
   EDITOR_ARGS = "--project-root D:/games/my-game --report D:/games/my-game/out/import.json"
   ```
   或者不编辑脚本，用环境变量 `UE_IMPORT_ARGS`（优先级更高）：
   ```powershell
   $env:UE_IMPORT_ARGS = "--project-root D:/games/my-game --report D:/games/my-game/out/import.json"
   ```
   编辑器启动后再设环境变量不生效：从设好变量的 PowerShell 里启动 UE，或直接改 `EDITOR_ARGS`。
4. UE 编辑器菜单 **Tools > Execute Python Script...**，选 `scripts/ue_import_assets.py`。
5. 看 Output Log 的 Python 区：逐条 `[OK]/[SKIP]/[FAIL]`，最后一行是汇总。
6. 打开 `--report` 指向的 JSON，确认 `failed` 为 0；有失败按 §10 处理。

节省参数：UE 内省略 `--project-root` 时脚本取 `unreal.Paths.project_dir()`，即当前工程目录。清单仍在工程根的 `docs/05_资产清单.csv`。项目工程通常在 `<项目根>/game/`，此时显式写 `--project-root` 指到真正的项目根。

### 7.2 方式 B：UnrealEditor-Cmd（可进 CI 脚本，【示例】）

```powershell
$env:UE_IMPORT_ARGS = "--project-root D:/games/my-game --include-status 已通过,已入库 --report D:/games/my-game/out/import.json"
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
  "D:\games\my-game\game\MyGame.uproject" `
  -run=pythonscript `
  -script="D:\games\my-game\scripts\ue_import_assets.py"
```

路径按本机 UE 安装位置改；UE 5.8 的安装目录与 `UnrealEditor-Cmd.exe` 名称以官方文档为准。命令结束看进程退出码与 `--report` 报告，不要只看 Output Log。

### 7.3 一批资产的推荐顺序

```text
1. git status --short          无未提交改动
2. git checkout -b asset/import-batch-NN
3. gamecheck.py gate assets    退出码 0
4. ue_import_assets.py --dry-run   全绿
5. ue_import_assets.py         一次 <= 12 个资产
6. 打开编辑器抽查 3 个资产：材质槽、碰撞、LOD
7. 报告存 docs/07_交付单/，commit
```

### 7.4 UE 模式输出（【示例】）

```text
== ue_import_assets.py ｜ UE 导入 ==
项目根：D:\games\my-game
清单：D:\games\my-game\docs\05_资产清单.csv
目标目录：/Game/_Project
[OK] char_hero -> /Game/_Project/Characters/char_hero（已导入）
[SKIP] prop_old -> /Game/_Project/Props/prop_old（跳过）
        警告：目标资产已存在，默认跳过（--force 才覆盖）：/Game/_Project/Props/prop_old
1 成功 / 1 跳过 / 0 失败（清单候选 2 条）
结论：通过。
报告：D:\games\my-game\out\import.json
```

---

## 8. 材质、碰撞、LOD、缩放怎么设

### 8.1 材质（note 的 `mat`）

| 步骤 | API | 失败时 |
|---|---|---|
| 加载材质 | `unreal.EditorAssetLibrary.load_asset(mat_path)` | 材质不存在记 error，该行 `[FAIL]`；需先建好材质资产 |
| 判断能力 | `hasattr(asset, "set_material")` | 不支持记 warning，跳过材质 |
| 取槽位数 | `asset.get_num_materials()` | 调用失败按 1 个槽位处理，记 warning |
| 套材质 | `asset.set_material(i, material)` 逐槽调用 | 单槽失败记 warning，继续下一槽 |

**注意：** `mat` 指向的资产必须在导入前已经存在。脚本不自动创建材质，也不改材质参数。一个材质套全部槽位是默认行为；多材质资产需要在导入后手工调整，或在后续版本扩展 note 语法。

### 8.2 碰撞（note 的 `collision`，只对 StaticMesh）

| 值 | 脚本动作 | 适用 |
|---|---|---|
| `none` | `remove_collisions` | 纯装饰、不需要碰撞的资产 |
| `simple` | 先 `remove_collisions`，再 `add_simple_collisions`（BOX 形状），并把追踪标记设为 simple | 白模、可走地面、方块道具 |
| `complex` | 保留 FBX 自带复杂碰撞，只复位追踪标记 | 默认值；精确碰撞、可用复杂碰撞的资产 |
| `use_complex_as_simple` | 保留复杂碰撞，追踪标记设为 complex as simple | 静态场景、要精确又不想补简单碰撞的模块 |

`simple` 用 BOX 占位，不是最终形状；人物胶囊、楼梯、斜坡这类资产导入后要人工补 UCX 或换碰撞。SkeletalMesh 不做碰撞设置，脚本记 warning 后继续。

### 8.3 LOD（note 的 `lod` / `lod_count`，只对 StaticMesh）

| 模式 | 脚本动作 | 结果 |
|---|---|---|
| 默认（不加 `--auto-lod`） | `get_lod_count` 读当前 LOD 数；少于 note 的 `lods` 记 warning | 不自动生成；warning 提示需要补 LOD 或开 `--auto-lod` |
| `--auto-lod` | 有 `set_lod_reduction_settings` 就尝试设缩减，有 `set_num_lods` 就设级数 | 自动生成质量由引擎决定，导入后要人工抽查 |
| 非 StaticMesh | 记 warning 跳过 | SkeletalMesh 的 LOD 导入后手工处理 |

LOD 数是"期望值"不是"保证值"：UE 5.8 的自动 LOD 参数与 API 可能变化，脚本用 `hasattr` 探测、失败降级为 warning。以官方 Python API 文档为准。

### 8.4 缩放（note 的 `scale`）

通过 `AssetImportTask.import_uniform_scale` 应用。资产是"厘米建、米用"还是相反，在美术圣经的"比例与尺度"章节定死，写进 note；不要每次导入时临时改。API 不存在时记 warning，导入后按 0.01–100 的范围人工缩放并复查尺寸。

---

## 9. 报告字段（--report JSON）

| 字段 | 类型 | 说明 |
|---|---|---|
| `script` / `version` | string | 脚本名与版本，v0.2 起始为 `0.2.0` |
| `root` | string | 项目根绝对路径 |
| `manifest` | string | 实际读取的清单绝对路径 |
| `content_dir` | string | UE 目标父目录 |
| `dry_run` | bool | true = 只校验 |
| `total` | int | 清单候选行数（只计 .fbx/.glb） |
| `ok` | int | dry-run 校验通过 + UE 导入成功 |
| `skipped` | int | 状态过滤 / --only 过滤 / 目标已存在 |
| `failed` | int | 失败行数 + 全局错误数 |
| `errors` | string[] | 全局错误（清单缺失、表头不对、内部错误等） |
| `warnings` | string[] | 全局警告（--only 未命中、单批超 12 个等） |
| `items[]` | object[] | 逐行明细，见下表 |

`items[]` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 清单 id |
| `file` | string | 清单里的相对路径（已规范化为 `/`） |
| `dest` | string | UE 目标资产路径；被过滤的行可能为空 |
| `status` | string | 清单状态 |
| `material` | string | note 的 mat，空表示不改 |
| `collision` | string | 生效的碰撞值 |
| `lods` | int | 生效的 LOD 级数 |
| `scale` | number | 生效的缩放 |
| `result` | string | `validated` / `imported` / `skipped` / `failed` |
| `errors` | string[] | 该行错误 |
| `warnings` | string[] | 该行警告 |

报告里 `failed` 大于 0 时，退出码是 1；报告文件仍会写出来，方便定位。

---

## 10. 失败处理

| 输出 | 原因 | 动作 |
|---|---|---|
| `[FAIL] ... file 不存在` | 清单写了导出文件，但 `art/Export/` 里没有 | 补导出；确认 FBX 已进版本库 |
| `[FAIL] ... file 越出 project-root` | `file` 用了 `..` 或绝对路径 | 改成项目内相对路径 |
| `[FAIL] ... 表头不符合资产清单规范` | 表头缺列/多列/换序 | 用 `templates/05_资产清单.csv` 的表头重建 |
| `[FAIL] ... mat 必须以 /Game/ 开头` | 材质路径写成了相对路径 | 改成 `/Game/_Project/Materials/M_xxx` |
| `[FAIL] ... 材质资产不存在` | UE 里还没建材质 | 先建材质，再重跑 |
| `[FAIL] ... import_asset_tasks 失败` | FBX 损坏、插件未开、路径不可读 | 用编辑器手工导一次同文件定位；修好再重跑 |
| `[SKIP] ... 目标资产已存在` | 之前导过 | 确认旧资产可替换后再加 `--force`；不确定就保留跳过 |
| `warning: 未知 note 键` | note 拼写错 | 按 §4.4 的 key 表改；warning 不会让整批失败 |
| `warning: 当前 LOD 数 N 少于` | 资产本身没 LOD | 补 LOD 或加 `--auto-lod`，导入后抽查 |
| `warning: UE API 不存在` | UE 版本差异 | 手工补对应设置，把版本与 API 名记进交付单 |
| 退出码 2 | 命令/环境不对 | 按 stderr 改命令，不要改脚本绕过 |

**一条失败不中断整批**：先让整批跑完，拿到完整失败清单，再一次性修。不要边跑边改清单。

---

## 11. 回滚

导入是**写工程资产**的操作，必须能撤回。按顺序做：

1. 立刻停止后续批次，不要继续用 `--force` 覆盖。
2. `git status --short` 看改动范围；记录 `--report` 里 `result=imported` 的 `dest` 列表。
3. 已跟踪文件的改动：`git restore -- game/Content`（工程目录以实际路径为准）。
4. 未跟踪的新资产：先 `git clean -nd game/Content` 预览，确认只删本批导入的 `.uasset`，再 `git clean -fd game/Content`。
5. 编辑器里关闭未保存的关卡/蓝图，避免把回滚前的内存状态再存回去。
6. 重新打开工程，跑一次 `gate assets`，退出码 0 才算回到干净状态。
7. 把失败原因、回滚范围写进 `docs/07_交付单/`；涉及改标准时另开变更单。

**没有 commit 就不允许开始批量导入**（SKILL.md 铁律 7）。回滚点永远是上一个 commit。

---

## 12. 已知限制

| 限制 | 现状 | 规避 |
|---|---|---|
| UE 5.8 Python API 可能变 | 所有调用包在 `try/except` + `hasattr`，不存在则 warning 降级 | 首次跑小批量看 warning；把版本与 warning 记进交付单 |
| `set_lod_reduction_settings` 签名不确定 | 参数按"LOD 缩减设置列表"构造，失败降级 | 自动 LOD 失败时用编辑器 LOD 面板手工加；或导入后 `set_num_lods` |
| CollisionTraceFlag 挂在哪不确定 | 先试 StaticMesh 属性，再试 `body_setup`；都失败记 warning | 导入后在 StaticMesh Editor 的 Collision 面板手工确认 |
| GLB 依赖 glTF 导入插件 | 插件没开时导入失败 | 在 `docs/03_技术方案.md` 的"插件与模块"里确认已启用 |
| 不检查材质是否存在 | dry-run 只看路径格式，不看 UE 资产 | UE 模式失败会报"材质资产不存在"；批量前先建材质 |
| 简单碰撞是 BOX 占位 | 不是最终形状 | 人物、楼梯、斜坡导入后人工补 UCX |
| SkeletalMesh 的 LOD/碰撞不处理 | 只记 warning | 动画与角色资产导入后手工设置 |
| 不导入贴图/不建材质实例 | 只导入 FBX/GLB 网格 | 贴图在材质里引用；按 `references/03-美术资产管线.md` 的贴图约定执行 |
| 单批超过 12 个只警告不阻止 | 方便排查，不代替纪律 | 安全边界见 §13；超批拆开跑 |
| 报告不记录引擎版本 | 只记录脚本版本 | 在交付单里写 UE 版本 |

---

## 13. 安全边界

1. **一次最多 12 个资产。** 脚本超过 12 个只记 warning，不替你踩刹车；SKILL.md 禁止未经确认批量生成超过 12 个资产。
2. **先 commit，再开分支。** 没有可回滚版本不开始导入。
3. **先 dry-run，再 UE 导入。** dry-run 未全绿不进编辑器。
4. **默认不覆盖。** `--force` 只在确认旧资产可替换、且已 commit 时用。
5. **不导到 `/Game/` 根目录。** 用 `--content-dir /Game/_Project`，保持目录约定。
6. **不动别人的文件。** 一批只处理 `--only` 列出的 id，避免顺手重导导致引用变化。
7. **报告进交付单。** `--report` 的 JSON 是证据，和截图一起进 `docs/07_交付单/<编号>.md`。

---

## 14. 检查清单

- [ ] `git status --short` 干净，当前在 `asset/import-batch-NN` 分支
- [ ] `docs/05_资产清单.csv` 表头 16 列与模板一致
- [ ] 本批资产都通过 `docs/08_验收单/`，状态是 `已通过` 或 `已入库`
- [ ] 每个 `file` 在项目根内，扩展名是 `.fbx` 或 `.glb`
- [ ] 每个 id 唯一，没有两个 id 指向同一个文件
- [ ] note 的 `mat` 以 `/Game/` 开头，材质资产已存在
- [ ] note 的 `collision` 在四个允许值内
- [ ] note 的 `lod`/`lod_count` 在 1–4，`scale` 在 0.01–100
- [ ] `gate assets` 退出码 0
- [ ] `--dry-run` 退出码 0，`failed` 为 0
- [ ] 本批不超过 12 个资产
- [ ] UE 导入后抽查 3 个资产：材质槽、碰撞、LOD
- [ ] `--report` JSON 已存档，`failed` 为 0
- [ ] 已 commit，提交信息写明批次与资产数量

---

## 15. 相关文件

| 文件 | 用途 |
|---|---|
| `scripts/ue_import_assets.py` | 本脚本本体 |
| `tests/test_ue_import_assets.py` | 单元测试（35 条，dry-run 为主） |
| `templates/05_资产清单.csv` | 清单模板与表头来源 |
| `references/03-美术资产管线.md` | 导出、命名、贴图、验收流程 |
| `references/04-引擎实现.md` | UE 工程目录、插件、碰撞与 LOD 的引擎侧说明 |
| `scripts/gamecheck.py` | `gate assets` / `manifest check` 闸门 |

**正例**：清单 note 写全 `mat/collision/lod/lod_count/scale`，先 dry-run 再小批量导入，报告进交付单，一次 commit 可回滚。
**反例**：不 commit 直接 `--force` 覆盖 30 个资产，失败后既不知道导了什么，也回不到干净状态。
