#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UE5 资产批量导入脚本（skill v0.2.0）。

做什么
    读项目 docs/05_资产清单.csv，把 file 列是 .fbx/.glb 的资产批量导入 UE5，
    并按 note 列的 key=value 设置材质、碰撞、LOD、缩放；没有 UE 的环境用
    --dry-run 只做清单与路径校验。

两种运行方式
    1) 无 UE 环境（先做这一种，验收只看它）：
       python scripts/ue_import_assets.py --project-root <项目根> --dry-run
    2) UE5 编辑器内（真正导入）：
       a. 编辑器菜单 Tools > Execute Python Script... 选本文件；或
       b. 命令行：
          UnrealEditor-Cmd.exe <工程>.uproject -run=pythonscript -script="<绝对路径>/scripts/ue_import_assets.py"
       编辑器内运行时不会经过普通命令行参数，用环境变量 UE_IMPORT_ARGS 传参：
          $env:UE_IMPORT_ARGS = "--project-root D:/games/my-game --report D:/games/my-game/out/import.json"
       也可以直接改下面的 EDITOR_ARGS 常量。

注意
    - 先 --dry-run，再在 Git 分支上跑小批量（一次 <= 12 个资产），确认后合入。
    - 导入前先 commit，保证能 git checkout 回滚。
    - UE 5.8 的 Python API 仍可能随引擎版本变化：import unreal 之后所有 API
      调用都包在 try/except 里，并先用 hasattr 探测；API 不存在时降级为
      warning，不中断整批导入。具体签名以官方 Python API 文档为准：
      https://dev.epicgames.com/documentation/unreal-engine/python-api/
    - 本文件被 import 时不依赖 unreal；只有非 --dry-run 才 import unreal。

退出码
    0 全部成功/跳过；1 有失败；2 用法错误或环境不满足（如无 UE 却未加 --dry-run）。
"""

import argparse
import csv
import json
import os
import posixpath
import re
import shlex
import sys
from pathlib import Path

SCRIPT_VERSION = "0.2.0"

# 与 templates/05_资产清单.csv 的表头一字不差。故意自己定义，不 import gamecheck，
# 这样脚本可以单独复制进游戏项目运行。
ASSET_HEADER = [
    "id", "type", "name", "usage", "source", "file", "faces", "textures",
    "materials", "animations", "lod", "collision", "license", "owner", "status", "note",
]

# type -> /Game/_Project/<子目录>
TYPE_DIRS = {
    "char": "Characters",
    "enemy": "Characters",
    "env": "Environment",
    "prop": "Props",
    "fx": "VFX",
    "ui": "UI",
    "anim": "Animations",
    "mat": "Materials",
}

VALID_COLLISIONS = ("none", "simple", "complex", "use_complex_as_simple")
DEFAULT_COLLISION = "complex"
DEFAULT_LOD = 1
DEFAULT_LOD_COUNT = None  # 未写 lod_count 时取 lod
DEFAULT_SCALE = 1.0
SCALE_MIN = 0.01
SCALE_MAX = 100.0
LOD_MIN = 1
LOD_MAX = 4
STATUSES = ("待做", "制作中", "待验收", "已通过", "已入库", "废弃")
DEFAULT_INCLUDE_STATUS = "已通过,已入库"
NOTE_KEYS = ("mat", "collision", "lod", "lod_count", "scale", "import")
SUPPORTED_EXTS = (".fbx", ".glb")
MAX_BATCH = 12
DEFAULT_CONTENT_DIR = "/Game/_Project"
DEFAULT_MANIFEST_PARTS = ("docs", "05_资产清单.csv")

# 在 UE 编辑器里用 Execute Python Script 直接运行时，可把参数写进这里；
# 环境变量 UE_IMPORT_ARGS 优先于本常量。
EDITOR_ARGS = ""

NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

EXAMPLES = """示例：
  python scripts/ue_import_assets.py --project-root . --dry-run
  python scripts/ue_import_assets.py --project-root . --dry-run --only char_hero,env_ruins_wall
  python scripts/ue_import_assets.py --project-root . --dry-run --include-status 已通过,已入库 --json
  python scripts/ue_import_assets.py --project-root . --report out/import.json
  python scripts/ue_import_assets.py --project-root . --auto-lod --force"""


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def _setup_stdout() -> None:
    """Windows 控制台默认编码可能是 GBK，统一改成 UTF-8，避免中文输出乱码/报错。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def resolve_root(value) -> Path:
    try:
        return Path(value).expanduser().resolve()
    except OSError:
        return Path(value).expanduser().absolute()


def read_text(path: Path) -> str:
    """按 UTF-8 读，失败退化到 GB18030；再不行用替换字符，绝不抛 UnicodeDecodeError。"""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def norm_rel(value: str) -> str:
    text = (value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def rel_label(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return path.as_posix()


def parse_csv(path: Path):
    """返回 (header, rows, error)。rows = [(行号, cells)]，行号为近似值（已过滤空行与 # 注释）。"""
    try:
        text = read_text(path)
    except OSError as exc:
        return None, None, "读取失败：%s" % exc
    lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    if not lines:
        return None, None, "文件为空"
    try:
        raw_rows = [row for row in csv.reader(lines) if row and any(cell.strip() for cell in row)]
    except csv.Error as exc:
        return None, None, "CSV 解析失败：%s" % exc
    if not raw_rows:
        return None, None, "没有表头"
    header = [cell.strip() for cell in raw_rows[0]]
    rows = [(index + 2, row) for index, row in enumerate(raw_rows[1:])]
    return header, rows, None


def cell(cells, index, name) -> str:
    position = index.get(name)
    if position is None or position >= len(cells):
        return ""
    return cells[position].strip()


def header_hint(header) -> str:
    missing = [col for col in ASSET_HEADER if col not in header]
    extra = [col for col in header if col not in ASSET_HEADER]
    parts = []
    if missing:
        parts.append("缺少列：" + "、".join(missing))
    if extra:
        parts.append("多余列：" + "、".join(extra))
    if not parts:
        parts.append("列顺序不对")
    return "表头必须严格为 " + ",".join(ASSET_HEADER) + "；" + "；".join(parts)


def parse_int(value: str):
    text = (value or "").strip()
    if not re.fullmatch(r"[+-]?\d+", text):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_float(value: str):
    text = (value or "").strip()
    if not NUMBER_PATTERN.match(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_content_dir(value: str):
    """--content-dir 必须是 /Game/ 下的路径。返回规范化结果，非法返回 None。"""
    text = (value or "").strip().replace("\\", "/").rstrip("/")
    if not text.startswith("/Game/"):
        return None
    parts = text.split("/")
    if ".." in parts or "." in parts[1:]:
        return None
    return text


def parse_note(note: str):
    """解析 note 列：分号分隔的 key=value。

    返回 (parsed, warnings)：
    - parsed 是 dict，重复 key 取最后一个；
    - 不含 "=" 的分号片段视为备注文字，静默忽略（清单 note 常写验收单路径等）；
    - 含 "=" 但 key 不在 NOTE_KEYS 的片段记 warning，不失败。
    """
    parsed = {}
    warnings = []
    for segment in re.split(r"[;；]", note or ""):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key:
            continue
        if key not in NOTE_KEYS:
            warnings.append(
                "未知 note 键「%s」（已忽略）；允许的键：%s" % (key, "、".join(NOTE_KEYS))
            )
            continue
        parsed[key] = value
    return parsed, warnings


def _split_list(value: str):
    return [part.strip() for part in re.split(r"[,，]", value or "") if part.strip()]


def _is_engine_argv(argv) -> bool:
    """判断是不是被 UE 编辑器/命令行拉起的 argv（不是本脚本的 CLI 参数）。"""
    for arg in argv:
        text = str(arg)
        if "UnrealEditor" in text or text.endswith(".uproject"):
            return True
        if text.startswith("-run=") or text.startswith("-script="):
            return True
    return False


def resolve_argv(argv=None):
    """CLI 参数解析入口：显式 argv > UE_IMPORT_ARGS 环境变量 > EDITOR_ARGS 常量 > sys.argv。"""
    if argv is not None:
        return list(argv)
    env_args = os.environ.get("UE_IMPORT_ARGS", "").strip()
    if env_args:
        try:
            return shlex.split(env_args)
        except ValueError:
            return []
    raw = sys.argv[1:]
    if _is_engine_argv(raw):
        if not EDITOR_ARGS.strip():
            return []
        try:
            return shlex.split(EDITOR_ARGS)
        except ValueError:
            return []
    return list(raw)



# ---------------------------------------------------------------------------
# 清单校验（dry-run 与 UE 模式共用）
# ---------------------------------------------------------------------------
def new_item(line_no) -> dict:
    return {
        "id": "",
        "file": "",
        "dest": "",
        "status": "",
        "material": "",
        "collision": DEFAULT_COLLISION,
        "lods": DEFAULT_LOD,
        "scale": DEFAULT_SCALE,
        "result": "pending",
        "errors": [],
        "warnings": [],
        "_line": line_no,
    }


def validate_item(item, cells, index, root, content_dir, seen_ids, seen_files) -> None:
    """校验一行，结果写回 item；不抛异常。"""
    line_no = item["_line"]
    row_id = cell(cells, index, "id")
    row_type = cell(cells, index, "type").lower()
    raw_file = norm_rel(cell(cells, index, "file"))
    item["id"] = row_id
    item["file"] = raw_file

    if not row_id:
        item["errors"].append("id 为空")
    elif not ID_PATTERN.match(row_id):
        item["errors"].append("id 只能含字母、数字、下划线：%s" % row_id)

    if not row_type:
        item["errors"].append("type 为空")
    elif row_type not in TYPE_DIRS:
        item["errors"].append("未知 type「%s」；只接受：%s" % (row_type, "、".join(TYPE_DIRS)))
    else:
        item["dest"] = "%s/%s/%s" % (content_dir, TYPE_DIRS[row_type], row_id)

    if row_id:
        first = seen_ids.get(row_id)
        if first is not None:
            item["errors"].append("id 重复：%s（首次出现在第 %d 行）" % (row_id, first))
        else:
            seen_ids[row_id] = line_no

    if not raw_file:
        item["errors"].append("file 为空")
    else:
        target = (root / raw_file).resolve()
        try:
            rel = target.relative_to(root)
        except ValueError:
            item["errors"].append("file 越出 project-root（禁止 .. 穿越）：%s" % raw_file)
        else:
            key = os.path.normcase(rel.as_posix())
            first = seen_files.get(key)
            if first is not None:
                item["errors"].append("file 重复：%s（首次出现在第 %d 行）" % (raw_file, first))
            else:
                seen_files[key] = line_no
            if not target.is_file():
                item["errors"].append("file 不存在：%s（相对 project-root）" % raw_file)

    parsed, note_warnings = parse_note(cell(cells, index, "note"))
    item["warnings"].extend(note_warnings)

    material = (parsed.get("mat") or "").strip()
    item["material"] = material
    if material and not material.startswith("/Game/"):
        item["errors"].append("mat 必须以 /Game/ 开头：%s" % material)

    collision = (parsed.get("collision") or DEFAULT_COLLISION).strip().lower()
    if collision not in VALID_COLLISIONS:
        item["errors"].append(
            "collision 只接受 %s，收到：%s" % (" / ".join(VALID_COLLISIONS), collision)
        )
    item["collision"] = collision

    lod = DEFAULT_LOD
    if "lod" in parsed:
        parsed_lod = parse_int(parsed["lod"])
        if parsed_lod is None or not LOD_MIN <= parsed_lod <= LOD_MAX:
            item["errors"].append(
                "lod 必须是 %d-%d 的整数，收到：%s" % (LOD_MIN, LOD_MAX, parsed["lod"])
            )
        else:
            lod = parsed_lod

    lod_count = lod
    if "lod_count" in parsed:
        parsed_count = parse_int(parsed["lod_count"])
        if parsed_count is None or not LOD_MIN <= parsed_count <= LOD_MAX:
            item["errors"].append(
                "lod_count 必须是 %d-%d 的整数，收到：%s"
                % (LOD_MIN, LOD_MAX, parsed["lod_count"])
            )
        else:
            lod_count = parsed_count
    item["lods"] = lod_count

    scale = DEFAULT_SCALE
    if "scale" in parsed:
        parsed_scale = parse_float(parsed["scale"])
        if parsed_scale is None or not SCALE_MIN <= parsed_scale <= SCALE_MAX:
            item["errors"].append(
                "scale 必须是 %s-%s 之间的数，收到：%s"
                % (SCALE_MIN, SCALE_MAX, parsed["scale"])
            )
        else:
            scale = parsed_scale
    item["scale"] = scale

    item["result"] = "failed" if item["errors"] else "pending"


def build_items(root: Path, manifest: Path, content_dir: str,
                include_status, only_ids):
    """读清单并产出 items 与全局 errors/warnings；不抛异常。"""
    items = []
    global_errors = []
    global_warnings = []

    header, rows, error = parse_csv(manifest)
    if error:
        global_errors.append("读取清单失败：%s" % error)
        return items, global_errors, global_warnings
    if header != ASSET_HEADER:
        global_errors.append("表头不符合资产清单规范：" + header_hint(header))
        return items, global_errors, global_warnings

    index = {name: position for position, name in enumerate(header)}
    candidates = []
    for line_no, cells in rows:
        file_value = norm_rel(cell(cells, index, "file"))
        if file_value and file_value.lower().endswith(SUPPORTED_EXTS):
            candidates.append((line_no, cells))

    if not candidates:
        global_warnings.append("清单里没有 .fbx/.glb 行；本脚本只处理这两种扩展名")

    if only_ids is not None:
        known = {cell(cells, index, "id") for _, cells in candidates}
        missing = sorted(only_ids - known)
        if missing:
            global_warnings.append("--only 里的 id 在清单中不存在：%s" % "、".join(missing))

    if len(candidates) > MAX_BATCH:
        global_warnings.append(
            "本次候选 %d 个，超过单批建议上限 %d 个；建议拆分后再导入（不阻止执行）"
            % (len(candidates), MAX_BATCH)
        )

    seen_ids = {}
    seen_files = {}
    for line_no, cells in candidates:
        item = new_item(line_no)
        row_id = cell(cells, index, "id")
        status = cell(cells, index, "status")
        item["id"] = row_id
        item["status"] = status
        item["file"] = norm_rel(cell(cells, index, "file"))

        if status not in include_status:
            item["result"] = "skipped"
            item["warnings"].append(
                "状态「%s」不在 --include-status，跳过" % (status or "空")
            )
            items.append(item)
            continue
        if only_ids is not None and row_id not in only_ids:
            item["result"] = "skipped"
            item["warnings"].append("不在 --only 列表，跳过")
            items.append(item)
            continue

        validate_item(item, cells, index, root, content_dir, seen_ids, seen_files)
        items.append(item)

    return items, global_errors, global_warnings


def mark_dry_run(items) -> None:
    for item in items:
        if item["result"] == "pending":
            item["result"] = "validated"


def summarize(items, global_errors) -> dict:
    ok = sum(1 for item in items if item["result"] in ("validated", "imported"))
    skipped = sum(1 for item in items if item["result"] == "skipped")
    failed_items = sum(1 for item in items if item["result"] == "failed")
    return {
        "total": len(items),
        "ok": ok,
        "skipped": skipped,
        "failed": failed_items + len(global_errors),
    }


def public_item(item) -> dict:
    keys = ("id", "file", "dest", "status", "material", "collision", "lods",
            "scale", "result", "errors", "warnings")
    return {key: item[key] for key in keys}


def build_report(root: Path, manifest: Path, content_dir: str, dry_run: bool,
                 items, global_errors, global_warnings) -> dict:
    counts = summarize(items, global_errors)
    return {
        "script": "ue_import_assets.py",
        "version": SCRIPT_VERSION,
        "root": str(root),
        "manifest": str(manifest),
        "content_dir": content_dir,
        "dry_run": bool(dry_run),
        "total": counts["total"],
        "ok": counts["ok"],
        "skipped": counts["skipped"],
        "failed": counts["failed"],
        "errors": list(global_errors),
        "warnings": list(global_warnings),
        "items": [public_item(item) for item in items],
    }


def write_report(path: Path, data: dict) -> str:
    """写 --report JSON（UTF-8，无 BOM）。成功返回空串，失败返回错误文案。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        return ""
    except OSError as exc:
        return "写报告失败：%s" % exc



# ---------------------------------------------------------------------------
# UE 内模式：所有 unreal 调用都 try/except + hasattr，单条失败继续
# ---------------------------------------------------------------------------
def _load_unreal():
    """真正进入 UE 导入模式时才 import unreal；import 失败返回 None。"""
    try:
        import unreal  # noqa: F401 —— 只有非 --dry-run 才走到这里
    except Exception:
        return None
    return unreal


def _call_ue(owner, name, args, item, label):
    """调用可选的 UE API：不存在或抛异常都降级为 warning，返回 None。"""
    func = getattr(owner, name, None)
    if not callable(func):
        item["warnings"].append("UE API 不存在：%s（已降级跳过）" % label)
        return None
    try:
        return func(*args)
    except Exception as exc:  # noqa: BLE001 —— UE 版本差异不中断整批
        item["warnings"].append("调用 %s 失败：%s（已降级跳过）" % (label, exc))
        return None


def _is_static_mesh(unreal, asset) -> bool:
    try:
        if hasattr(unreal, "StaticMesh") and isinstance(asset, unreal.StaticMesh):
            return True
    except Exception:
        pass
    try:
        return asset.get_class().get_name() == "StaticMesh"
    except Exception:
        return False


def _static_mesh_library(unreal):
    return getattr(unreal, "EditorStaticMeshLibrary", None)


def _get_body_setup(asset):
    getter = getattr(asset, "get_editor_property", None)
    if not callable(getter):
        return None
    for name in ("body_setup", "BodySetup"):
        try:
            return getter(name)
        except Exception:
            continue
    return None


def _trace_flag(unreal, enum_name):
    for enum_attr in ("CollisionTraceFlag", "BodySetupCollisionTraceFlag"):
        enum = getattr(unreal, enum_attr, None)
        flag = getattr(enum, enum_name, None) if enum is not None else None
        if flag is not None:
            return flag
    return None


def _set_collision_trace_flag(unreal, asset, enum_name, item) -> None:
    flag = _trace_flag(unreal, enum_name)
    if flag is None:
        item["warnings"].append(
            "CollisionTraceFlag.%s 不可用（UE 版本差异），跳过碰撞追踪标记" % enum_name
        )
        return
    targets = [asset]
    body_setup = _get_body_setup(asset)
    if body_setup is not None:
        targets.append(body_setup)
    for target in targets:
        setter = getattr(target, "set_editor_property", None)
        if not callable(setter):
            continue
        for prop_name in ("collision_trace_flag", "CollisionTraceFlag"):
            try:
                setter(prop_name, flag)
                return
            except Exception:
                continue
    item["warnings"].append("无法在 StaticMesh 上设置 CollisionTraceFlag（API 可能已变化），跳过")


def _apply_material(unreal, asset, item) -> None:
    """把 note 的 mat 应用到 StaticMesh / SkeletalMesh 的所有材质槽。"""
    if not hasattr(asset, "set_material"):
        item["warnings"].append("资产不支持 set_material，跳过材质设置")
        return
    editor_lib = getattr(unreal, "EditorAssetLibrary", None)
    loader = getattr(editor_lib, "load_asset", None) if editor_lib is not None else None
    if not callable(loader):
        item["warnings"].append("EditorAssetLibrary.load_asset 不可用，跳过材质设置")
        return
    try:
        material = loader(item["material"])
    except Exception as exc:  # noqa: BLE001
        item["errors"].append("加载材质失败：%s（%s）" % (item["material"], exc))
        return
    if material is None:
        item["errors"].append("材质资产不存在：%s" % item["material"])
        return

    slots = 1
    getter = getattr(asset, "get_num_materials", None)
    if callable(getter):
        try:
            slots = max(1, int(getter()))
        except Exception as exc:  # noqa: BLE001
            item["warnings"].append("get_num_materials 调用失败，按 1 个槽位处理：%s" % exc)
    applied = 0
    for slot in range(slots):
        try:
            asset.set_material(slot, material)
            applied += 1
        except Exception as exc:  # noqa: BLE001
            item["warnings"].append("set_material(%d) 失败：%s" % (slot, exc))
    if applied == 0:
        item["warnings"].append("材质未应用到任何槽位")


def _apply_collision(unreal, asset, item) -> None:
    """按 note 的 collision 设置 StaticMesh 碰撞。"""
    if not _is_static_mesh(unreal, asset):
        item["warnings"].append("非 StaticMesh，跳过碰撞设置（保留导入自带碰撞）")
        return
    lib = _static_mesh_library(unreal)
    if lib is None:
        item["warnings"].append("EditorStaticMeshLibrary 不可用，跳过碰撞设置")
        return
    mode = item["collision"]
    if mode == "none":
        _call_ue(lib, "remove_collisions", (asset,), item, "remove_collisions")
        return
    if mode == "simple":
        _call_ue(lib, "remove_collisions", (asset,), item, "remove_collisions")
        shape_enum = getattr(unreal, "ScriptingCollisionShapeType", None)
        box = getattr(shape_enum, "BOX", None) if shape_enum is not None else None
        if box is None:
            item["warnings"].append(
                "ScriptingCollisionShapeType.BOX 不可用，跳过 add_simple_collisions"
            )
        else:
            _call_ue(lib, "add_simple_collisions", (asset, box), item,
                     "add_simple_collisions")
        _set_collision_trace_flag(unreal, asset, "CTF_USE_SIMPLE_AS_COMPLEX", item)
        return
    if mode == "use_complex_as_simple":
        _set_collision_trace_flag(unreal, asset, "CTF_USE_COMPLEX_AS_SIMPLE", item)
        return
    # complex：保留 FBX 自带的复杂碰撞，只把追踪标记复位
    _set_collision_trace_flag(unreal, asset, "CTF_USE_DEFAULT", item)


def _build_lod_settings(unreal, wanted, item):
    cls = getattr(unreal, "EditorStaticMeshLODReductionSettings", None)
    if cls is None:
        cls = getattr(unreal, "StaticMeshLODReductionSettings", None)
    if cls is None:
        item["warnings"].append(
            "LOD 缩减设置类不可用（UE 版本差异），跳过 set_lod_reduction_settings"
        )
        return []
    settings = []
    try:
        for _ in range(max(0, int(wanted) - 1)):
            settings.append(cls())
    except Exception as exc:  # noqa: BLE001
        item["warnings"].append("创建 LOD 缩减设置失败：%s" % exc)
        return []
    return settings


def _apply_lods(unreal, asset, item, auto_lod: bool) -> None:
    """--auto-lod 时尝试自动生成 LOD；否则只检查 LOD 数，不足记 warning。"""
    if not _is_static_mesh(unreal, asset):
        item["warnings"].append("非 StaticMesh，跳过 LOD 设置")
        return
    lib = _static_mesh_library(unreal)
    if lib is None:
        item["warnings"].append("EditorStaticMeshLibrary 不可用，跳过 LOD 设置")
        return
    wanted = int(item["lods"])
    if auto_lod:
        reduction = getattr(lib, "set_lod_reduction_settings", None)
        if callable(reduction):
            settings = _build_lod_settings(unreal, wanted, item)
            if settings:
                _call_ue(lib, "set_lod_reduction_settings", (asset, settings), item,
                         "set_lod_reduction_settings")
        else:
            item["warnings"].append(
                "set_lod_reduction_settings 不可用（UE 版本差异），跳过 LOD 缩减"
            )
        if callable(getattr(lib, "set_num_lods", None)):
            _call_ue(lib, "set_num_lods", (asset, wanted), item, "set_num_lods")
        else:
            item["warnings"].append("set_num_lods 不可用，跳过自动 LOD 数量设置")
        return

    getter = getattr(lib, "get_lod_count", None)
    if not callable(getter):
        item["warnings"].append("get_lod_count 不可用，跳过 LOD 数量检查")
        return
    try:
        count = int(getter(asset))
    except Exception as exc:  # noqa: BLE001
        item["warnings"].append("get_lod_count 调用失败：%s" % exc)
        return
    if count < wanted:
        item["warnings"].append(
            "当前 LOD 数 %d 少于清单 lods=%d；未启用 --auto-lod，未自动生成"
            % (count, wanted)
        )


def _configure_import_task(unreal, item, abs_file):
    """构造 AssetImportTask；关键属性失败记 error，可选属性失败记 warning。"""
    task = unreal.AssetImportTask()
    essential = (
        ("filename", abs_file),
        ("destination_path", posixpath.dirname(item["dest"])),
        ("destination_name", posixpath.basename(item["dest"])),
        ("automated", True),
        ("save", False),
    )
    for name, value in essential:
        try:
            task.set_editor_property(name, value)
        except Exception as exc:  # noqa: BLE001
            item["errors"].append("配置 AssetImportTask.%s 失败：%s" % (name, exc))

    force = bool(item.get("_force"))
    for name, value in (("replace_existing", force),
                        ("replace_existing_settings", force)):
        try:
            task.set_editor_property(name, value)
        except Exception as exc:  # noqa: BLE001
            item["warnings"].append("AssetImportTask.%s 不可用：%s" % (name, exc))

    if abs(float(item["scale"]) - 1.0) > 1e-9:
        try:
            task.set_editor_property("import_uniform_scale", float(item["scale"]))
        except Exception as exc:  # noqa: BLE001
            item["warnings"].append("import_uniform_scale 不可用（scale 未应用）：%s" % exc)
    return task


def _import_one(unreal, root: Path, item, force: bool, auto_lod: bool) -> None:
    """导入单个资产并设置材质/碰撞/LOD；结果写回 item。"""
    item["_force"] = force
    asset_path = item["dest"]
    if not asset_path:
        item["errors"].append("目标路径为空，无法导入")
        item["result"] = "failed"
        return

    editor_lib = getattr(unreal, "EditorAssetLibrary", None)
    exists = False
    checker = getattr(editor_lib, "does_asset_exist", None) if editor_lib is not None else None
    if callable(checker):
        try:
            exists = bool(checker(asset_path))
        except Exception as exc:  # noqa: BLE001
            item["warnings"].append("does_asset_exist 调用失败：%s" % exc)
    else:
        item["warnings"].append("EditorAssetLibrary.does_asset_exist 不可用，无法判断是否已存在")
    if exists and not force:
        item["result"] = "skipped"
        item["warnings"].append(
            "目标资产已存在，默认跳过（--force 才覆盖）：%s" % asset_path
        )
        return

    abs_file = str((root / item["file"]).resolve())
    task = _configure_import_task(unreal, item, abs_file)
    if item["errors"]:
        item["result"] = "failed"
        return

    helpers = getattr(unreal, "AssetToolsHelpers", None)
    getter = getattr(helpers, "get_asset_tools", None) if helpers is not None else None
    if not callable(getter):
        item["errors"].append("AssetToolsHelpers.get_asset_tools 不可用，无法导入")
        item["result"] = "failed"
        return
    try:
        asset_tools = getter()
        asset_tools.import_asset_tasks([task])
    except Exception as exc:  # noqa: BLE001
        item["errors"].append("import_asset_tasks 失败：%s: %s" % (type(exc).__name__, exc))
        item["result"] = "failed"
        return

    asset = None
    loader = getattr(editor_lib, "load_asset", None) if editor_lib is not None else None
    if callable(loader):
        try:
            asset = loader(asset_path)
        except Exception as exc:  # noqa: BLE001
            item["warnings"].append("load_asset 失败：%s" % exc)
    if asset is None:
        item["errors"].append("导入后找不到资产：%s" % asset_path)
        item["result"] = "failed"
        return

    if item["material"]:
        _apply_material(unreal, asset, item)
    _apply_collision(unreal, asset, item)
    _apply_lods(unreal, asset, item, auto_lod)

    saver = getattr(editor_lib, "save_loaded_asset", None) if editor_lib is not None else None
    if callable(saver):
        try:
            saver(asset)
        except Exception as exc:  # noqa: BLE001
            item["errors"].append("保存资产失败：%s" % exc)
    else:
        item["warnings"].append("save_loaded_asset 不可用，资产未显式保存")

    item["result"] = "failed" if item["errors"] else "imported"


def import_unreal(root: Path, items, force: bool, auto_lod: bool):
    """执行 UE 导入。返回 unreal 模块；无 unreal 环境返回 None。"""
    unreal = _load_unreal()
    if unreal is None:
        return None
    for item in items:
        if item["result"] != "pending":
            continue
        try:
            _import_one(unreal, root, item, force, auto_lod)
        except Exception as exc:  # noqa: BLE001 —— 单条失败继续
            item["errors"].append("导入异常：%s: %s" % (type(exc).__name__, exc))
            item["result"] = "failed"
    return unreal



# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
RESULT_TAGS = {
    "validated": "OK",
    "imported": "OK",
    "skipped": "SKIP",
    "failed": "FAIL",
}


def print_text(data: dict, report_path=None) -> None:
    mode = "dry-run 校验" if data["dry_run"] else "UE 导入"
    print("== ue_import_assets.py ｜ %s ==" % mode)
    print("项目根：%s" % data["root"])
    print("清单：%s" % data["manifest"])
    print("目标目录：%s" % data["content_dir"])
    for error in data["errors"]:
        print("[FAIL] %s" % error)
    for warning in data["warnings"]:
        print("[WARN] %s" % warning)

    for item in data["items"]:
        tag = RESULT_TAGS.get(item["result"], "FAIL")
        line = "[%s] %s" % (tag, item["id"] or "<无 id>")
        if item["dest"]:
            line += " -> " + item["dest"]
        if item["result"] == "validated":
            line += "（dry-run 校验通过）"
        elif item["result"] == "imported":
            line += "（已导入）"
        elif item["result"] == "skipped":
            line += "（跳过）"
        print(line)
        for warning in item["warnings"]:
            print("        警告：%s" % warning)
        for error in item["errors"]:
            print("        错误：%s" % error)

    print("%d 成功 / %d 跳过 / %d 失败（清单候选 %d 条）"
          % (data["ok"], data["skipped"], data["failed"], data["total"]))
    if data["failed"]:
        print("结论：有失败项。按上面的错误修清单或文件后重跑，不要跳过失败行。")
    else:
        print("结论：通过。")
    if report_path is not None:
        print("报告：%s" % report_path)


def usage_error(message: str, json_out: bool = False) -> int:
    text = "用法错误：%s" % message
    if json_out:
        payload = {
            "script": "ue_import_assets.py",
            "version": SCRIPT_VERSION,
            "dry_run": False,
            "total": 0,
            "ok": 0,
            "skipped": 0,
            "failed": 1,
            "errors": [text],
            "warnings": [],
            "items": [],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        sys.stderr.write(text + "\n")
        sys.stderr.write("退出码 2 = 用法错误。先跑 --dry-run 校验清单。\n")
    return 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
class _Parser(argparse.ArgumentParser):
    def error(self, message):
        if "--json" in sys.argv:
            payload = {
                "script": "ue_import_assets.py",
                "version": SCRIPT_VERSION,
                "dry_run": False,
                "total": 0,
                "ok": 0,
                "skipped": 0,
                "failed": 1,
                "errors": ["用法错误：%s" % message],
                "warnings": [],
                "items": [],
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            sys.stderr.write("用法错误：%s\n" % message)
            self.print_usage(sys.stderr)
            sys.stderr.write(
                "退出码 2 = 用法错误。示例：python scripts/ue_import_assets.py --project-root . --dry-run\n"
            )
        sys.exit(2)


def build_parser():
    parser = _Parser(
        prog="ue_import_assets.py",
        description="UE5 资产批量导入：读 docs/05_资产清单.csv，导入 FBX/GLB 并设置材质/碰撞/LOD。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + SCRIPT_VERSION)
    parser.add_argument(
        "--project-root", default=None,
        help="项目根目录（含 docs/05_资产清单.csv；UE 编辑器内省略时取 unreal.Paths.project_dir()）",
    )
    parser.add_argument("--manifest", default=None,
                        help="资产清单 CSV 路径（默认 <项目根>/docs/05_资产清单.csv；相对路径按当前工作目录解析）")
    parser.add_argument("--content-dir", default=DEFAULT_CONTENT_DIR,
                        help="UE 目标内容目录，必须以 /Game/ 开头（默认 /Game/_Project）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只校验清单与路径，不 import unreal、不写 UE 资产")
    parser.add_argument("--only", default=None,
                        help="只处理这些 id，逗号分隔，例如 char_hero,env_ruins_wall")
    parser.add_argument("--include-status", default=DEFAULT_INCLUDE_STATUS,
                        help="允许导入的状态，逗号分隔（默认 已通过,已入库）")
    parser.add_argument("--auto-lod", action="store_true",
                        help="尝试自动生成 LOD（默认只检查 LOD 数）")
    parser.add_argument("--force", action="store_true",
                        help="目标资产已存在时覆盖；默认跳过")
    parser.add_argument("--report", default=None,
                        help="把 JSON 报告写到该路径（UTF-8）")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="stdout 只输出 JSON 报告")
    return parser


def _project_root_from_ue():
    """UE 编辑器内省略 --project-root 时，用当前工程目录兜底。"""
    unreal = _load_unreal()
    if unreal is None:
        return None
    try:
        return unreal.Paths.project_dir()
    except Exception:  # noqa: BLE001
        return None


def run(args) -> int:
    json_out = bool(getattr(args, "json_out", False))

    content_dir = normalize_content_dir(args.content_dir)
    if content_dir is None:
        return usage_error("--content-dir 必须是 /Game/ 下的路径，例如 /Game/_Project", json_out)

    include_status = _split_list(args.include_status)
    if not include_status:
        return usage_error(
            "--include-status 至少给一个状态；可选：%s" % "、".join(STATUSES), json_out
        )
    unknown_status = [status for status in include_status if status not in STATUSES]
    if unknown_status:
        return usage_error(
            "--include-status 含未知状态：%s；可选：%s"
            % ("、".join(unknown_status), "、".join(STATUSES)),
            json_out,
        )

    only_ids = None
    if args.only is not None:
        only_ids = set(_split_list(args.only))
        if not only_ids:
            return usage_error(
                "--only 至少给一个 id，例如 --only char_hero,env_ruins_wall", json_out
            )

    root_value = args.project_root
    if root_value is None:
        root_value = _project_root_from_ue()
        if root_value is None:
            return usage_error(
                "缺少 --project-root；无 UE 环境请显式指定项目根并加 --dry-run", json_out
            )
    root = resolve_root(root_value)
    if not root.is_dir():
        return usage_error("项目根不存在或不是目录：%s" % root, json_out)

    manifest = resolve_root(args.manifest) if args.manifest else root.joinpath(*DEFAULT_MANIFEST_PARTS)

    if not args.dry_run and _load_unreal() is None:
        return usage_error(
            "未检测到 unreal 模块，无法执行 UE 导入；无 UE 环境请加 --dry-run", json_out
        )

    items, global_errors, global_warnings = build_items(
        root, manifest, content_dir, set(include_status), only_ids
    )

    if args.dry_run:
        mark_dry_run(items)
    else:
        unreal = import_unreal(root, items, bool(args.force), bool(args.auto_lod))
        if unreal is None:
            global_errors.append(
                "未检测到 unreal 模块，未执行导入；无 UE 环境请加 --dry-run"
            )

    dry_run = bool(args.dry_run)
    data = build_report(root, manifest, content_dir, dry_run, items,
                        global_errors, global_warnings)

    report_path = resolve_root(args.report) if args.report else None
    if report_path is not None:
        report_error = write_report(report_path, data)
        if report_error:
            global_errors.append(report_error)
            data = build_report(root, manifest, content_dir, dry_run, items,
                                global_errors, global_warnings)

    if json_out:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_text(data, report_path)

    return 0 if data["failed"] == 0 else 1


def main(argv=None) -> int:
    _setup_stdout()
    parser = build_parser()
    args = parser.parse_args(resolve_argv(argv))
    try:
        return run(args)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        return 2
    except Exception as exc:  # noqa: BLE001 —— 任何模式下都不向用户抛 traceback
        message = "内部错误：%s: %s" % (type(exc).__name__, exc)
        if getattr(args, "json_out", False):
            print(json.dumps({
                "script": "ue_import_assets.py",
                "version": SCRIPT_VERSION,
                "dry_run": bool(getattr(args, "dry_run", False)),
                "total": 0,
                "ok": 0,
                "skipped": 0,
                "failed": 1,
                "errors": [message],
                "warnings": [],
                "items": [],
            }, ensure_ascii=False, indent=2))
        else:
            sys.stderr.write(message + "\n")
            sys.stderr.write("提示：请附完整命令与 --json 输出反馈给 skill 维护者。\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
