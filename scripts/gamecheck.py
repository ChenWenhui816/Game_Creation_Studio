#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gamecheck.py —— UE5 单人闯关游戏项目的文档 / 数值 / 资产清单校验器。

只依赖 Python 3.10+ 标准库。所有规则与 docs/维护规范.md §4 对齐：
改章节名必须同时改本文件、templates/ 与写作规范，否则校验与模板会互相打架。

常用命令：
  python scripts/gamecheck.py init --dir <项目目录> --name "项目名"
  python scripts/gamecheck.py doc check --stage 1 --root .
  python scripts/gamecheck.py gate spec --root .
  python scripts/gamecheck.py gate whitebox --root .
  python scripts/gamecheck.py gate assets --root .
  python scripts/gamecheck.py gate slice --root .
  python scripts/gamecheck.py gate content --root .
  python scripts/gamecheck.py gate release --root .
  python scripts/gamecheck.py numbers check --root .
  python scripts/gamecheck.py manifest check --root .
  python scripts/gamecheck.py check all --root .
  python scripts/gamecheck.py --show-rules

退出码：0 通过 / 1 校验失败 / 2 用法或内部错误。
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import shutil
import struct
import sys
from pathlib import Path

CONFIG_VERSION = "1.0"
CONFIG_FILE = "gamecheck.json"
AGENTS_FILE = "AGENTS.md"
DOCS_DIR = "docs"
ASSET_CSV = "05_资产清单.csv"
NUM_CSV = "06_数值表.csv"
CONTENT_MIN_ASSETS = 24
STORE_DIR = "store"
STORE_CAPSULES = {
    "header.png": (460, 215),
    "small.png": (231, 87),
    "main.png": (616, 353),
    "vertical.png": (374, 448),
    "library.png": (600, 900),
}
STORE_SCREENSHOT_SIZE = (1920, 1080)
STORE_SCREENSHOT_MIN = 5
STORE_TEXT_FILES = ("store_text_zh.md", "store_text_en.md")
STORE_SUBTITLE_FILES = ("trailer_zh.srt", "trailer_en.srt")
STORE_TRAILERS = ("trailer.mp4", "trailer.webm")
CHANGE_ID_PATTERN = re.compile(r"(?:CO|CR)-\d{3,}", re.IGNORECASE)
ASSET_ID_SCAN_PATTERN = re.compile(r"\b(?:char|enemy|env|prop|fx|ui|anim|mat)_[a-z0-9_]+\b")

STAGE_NAMES = {
    0: "立项",
    1: "标准",
    2: "白模",
    3: "资产管线与垂直切片",
    4: "内容生产",
    5: "打磨与 Demo 上线",
}

# ---------------------------------------------------------------------------
# 固定章节（必须与 docs/维护规范.md §4 一字不差）
# ---------------------------------------------------------------------------
REQUIRED_SECTIONS = {
    "00_立项书.md": [
        "一句话描述", "三个对标", "核心循环", "世界与角色",
        "规模与范围", "不做清单", "最大风险", "目标体验",
    ],
    "01_游戏设计文档.md": [
        "一句话与定位", "世界与故事", "核心循环", "操作与镜头", "角色状态机",
        "战斗与交互", "数值", "关卡总表", "UI 与引导", "音频", "存档与设置",
        "范围与不做", "验收标准", "变更记录",
    ],
    "02_美术圣经.md": [
        "风格定位", "视觉锚点", "色板", "比例与尺度", "材质与光照", "角色规范",
        "场景规范", "道具规范", "UI 规范", "特效规范", "动画规范", "命名与导入",
        "禁止项", "变更记录",
    ],
    "03_技术方案.md": [
        "引擎与平台", "插件与模块", "工程目录与命名", "角色与相机", "系统架构",
        "数据与存档", "关卡与流送", "测试与构建", "性能预算", "MCP 与自动化",
        "版本管理", "风险与回滚",
    ],
    "04_关卡设计.md": [
        "关卡目标", "节奏曲线", "空间尺规", "机制与教学", "敌人与遭遇",
        "检查点与存档", "收集与奖励", "演出与氛围", "性能预算", "验收清单",
    ],
    "07_交付单.md": [
        "目标", "改动", "证据", "自测", "已知问题", "偏离", "待决策", "下一步",
    ],
    "08_验收单.md": ["资产信息", "规格核对", "游戏内验证", "结论"],
    "09_变更单.md": [
        "基本信息", "现状", "变更内容", "原因", "影响评估", "选项", "决策", "执行清单",
    ],
    "10_测试记录.md": ["版本与环境", "测试范围", "用例与结果", "缺陷", "性能数据", "结论"],
    "11_周报.md": ["本周目标", "完成情况", "证据", "阻塞", "下周计划", "待决策"],
    "12_Demo上线清单.md": [
        "账号与资质", "商店页", "构建与认证", "商店素材", "法律与合规", "上线演练",
    ],
    "13_多语言商店素材清单.md": [
        "语言矩阵", "商店文案", "截图与预告片", "胶囊图与素材", "元数据与合规", "审核清单",
    ],
}

# 目录型文档 → 用哪套章节规则
DIR_SECTION_KEYS = {
    "04_关卡设计": "04_关卡设计.md",
    "07_交付单": "07_交付单.md",
    "08_验收单": "08_验收单.md",
    "11_周报": "11_周报.md",
}

# 阶段 → 新增的必需单文件 / 目录（累积）
_STAGE_SINGLE = {
    0: ["00_立项书.md"],
    1: ["01_游戏设计文档.md", "02_美术圣经.md", "03_技术方案.md", ASSET_CSV, NUM_CSV],
    2: [],
    3: [],
    4: ["10_测试记录.md"],
    5: ["12_Demo上线清单.md", "13_多语言商店素材清单.md"],
}
_STAGE_DIR = {
    0: [],
    1: [],
    2: [("04_关卡设计", 1)],
    3: [("07_交付单", 1), ("08_验收单", 1)],
    4: [("11_周报", 4)],
    5: [],
}

ASSET_HEADER = [
    "id", "type", "name", "usage", "source", "file", "faces", "textures",
    "materials", "animations", "lod", "collision", "license", "owner", "status", "note",
]
NUM_HEADER = ["category", "key", "value", "unit", "formula", "source", "note"]

TYPE_BUDGET = {
    "char": 80000,
    "enemy": 30000,
    "env": 5000,
    "prop": 5000,
    "fx": 0,
    "ui": 0,
    "anim": 0,
    "mat": 0,
}
TYPES = tuple(TYPE_BUDGET)
STATUSES = ("待做", "制作中", "待验收", "已通过", "已入库", "废弃")

ID_PATTERN = re.compile(r"^(char|enemy|env|prop|fx|ui|anim|mat)_[a-z0-9_]+$")
H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$")
NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
CHECKBOX_PATTERN = re.compile(r"^\s*[-*]\s+\[(?P<mark>[ xX])\]\s*(?P<text>\S.*)?$")
TEXTURE_EXTS = (".fbx", ".glb", ".png", ".wav")
PLACEHOLDER_TOKENS = ("【待填】", "TODO", "XXX", "???", "……")
NUMBER_TOLERANCE = 0.05
# 数值 key 规范：点号命名为主（与 references/02、templates/01 一致），下划线裸 key 作为别名兼容
NUM_KEY_ALIASES = {
    "height": ("move.jump.height", "jump_height"),
    "apex_time": ("move.jump.apex_time", "time_to_apex"),
    "gravity": ("move.gravity", "gravity"),
    "velocity": ("move.jump.velocity", "jump_velocity"),
}
NUM_ROLE_LABELS = {
    "height": "跳跃高度 h",
    "apex_time": "到顶点时间 t",
    "gravity": "重力 g",
    "velocity": "起跳速度 v",
}
REQUIRED_NUM_KEYS = tuple(aliases[0] for aliases in NUM_KEY_ALIASES.values())
NUM_ALIAS_HINT = "、".join(
    "%s（别名 %s）" % (aliases[0], " / ".join(aliases[1:]))
    for aliases in NUM_KEY_ALIASES.values()
)

# init 要复制的模板（全部 14 份；07/08 以 _模板_ 前缀放进项目，不计入闸门数量）
TEMPLATE_FILES = [
    "00_立项书.md", "01_游戏设计文档.md", "02_美术圣经.md", "03_技术方案.md",
    "04_关卡设计.md", ASSET_CSV, NUM_CSV, "07_交付单.md", "08_验收单.md",
    "09_变更单.md", "10_测试记录.md", "11_周报.md", "12_Demo上线清单.md",
    "13_多语言商店素材清单.md",
]
TEMPLATE_DEST = {
    "00_立项书.md": "docs/00_立项书.md",
    "01_游戏设计文档.md": "docs/01_游戏设计文档.md",
    "02_美术圣经.md": "docs/02_美术圣经.md",
    "03_技术方案.md": "docs/03_技术方案.md",
    "04_关卡设计.md": "docs/04_关卡设计/_模板_关卡设计.md",
    ASSET_CSV: "docs/" + ASSET_CSV,
    NUM_CSV: "docs/" + NUM_CSV,
    "07_交付单.md": "docs/07_交付单/_模板_交付单.md",
    "08_验收单.md": "docs/08_验收单/_模板_验收单.md",
    "09_变更单.md": "docs/09_变更单/_模板_变更单.md",
    "10_测试记录.md": "docs/10_测试记录.md",
    "11_周报.md": "docs/11_周报/_模板_周报.md",
    "12_Demo上线清单.md": "docs/12_Demo上线清单.md",
    "13_多语言商店素材清单.md": "docs/13_多语言商店素材清单.md",
}
INIT_DIRS = [
    "docs",
    "docs/04_关卡设计",
    "docs/07_交付单",
    "docs/08_验收单",
    "docs/09_变更单",
    "docs/11_周报",
    "art/Source",
    "art/Export",
    "art/Inbox",
    "assets",
    "game",
    "scripts",
    STORE_DIR,
]

EXAMPLES = """示例：
  python scripts/gamecheck.py init --dir ../MyGame --name "代号：山径"
  python scripts/gamecheck.py doc check --stage 2 --root ../MyGame
  python scripts/gamecheck.py numbers check --root ../MyGame --json
  python scripts/gamecheck.py gate slice --root ../MyGame
  python scripts/gamecheck.py gate content --root ../MyGame --min-assets 24
  python scripts/gamecheck.py change check --root ../MyGame
  python scripts/gamecheck.py gate release --root ../MyGame --store-dir store
  python scripts/gamecheck.py check all --root ../MyGame"""


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def _setup_stdout() -> None:
    """Windows 控制台默认编码可能是 GBK，统一改成 UTF-8 避免中文输出乱码/报错。"""
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


def rel_label(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return path.as_posix()


def count_lines(text: str) -> int:
    return len(text.splitlines())


def parse_h2(text: str) -> list:
    headings = []
    for line in text.splitlines():
        match = H2_PATTERN.match(line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def find_placeholders(text: str) -> list:
    """返回 [(行号, 记号)]；含【示例】的行整行豁免（示例值是规范允许的）。"""
    hits = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if "【示例】" in line:
            continue
        for token in PLACEHOLDER_TOKENS:
            if token in line:
                hits.append((line_no, token))
                break
    return hits


def parse_number(value: str):
    text = (value or "").strip()
    if not text or not NUMBER_PATTERN.match(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: str):
    text = (value or "").strip()
    if not re.fullmatch(r"[+-]?\d+", text):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def norm_rel(value: str) -> str:
    text = (value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def requirements_for(stage: int):
    singles = []
    dirs = []
    for level in range(0, stage + 1):
        for name in _STAGE_SINGLE.get(level, []):
            if name not in singles:
                singles.append(name)
        for item in _STAGE_DIR.get(level, []):
            if item not in dirs:
                dirs.append(item)
    return singles, dirs


def section_lines(text: str, name: str) -> list:
    """返回指定 H2 章节内的 [(行号, 行内容)]。"""
    body = []
    inside = False
    for line_no, line in enumerate(text.splitlines(), 1):
        match = H2_PATTERN.match(line)
        if match:
            title = match.group(1).strip()
            if inside and title != name:
                break
            inside = title == name
            continue
        if inside:
            body.append((line_no, line))
    return body


def extract_section(text: str, name: str) -> str:
    return "\n".join(line for _, line in section_lines(text, name)).strip()


def header_hint(header, expected) -> str:
    missing = [col for col in expected if col not in header]
    extra = [col for col in header if col not in expected]
    parts = []
    if missing:
        parts.append("缺少列：" + "、".join(missing))
    if extra:
        parts.append("多余列：" + "、".join(extra))
    if not parts:
        parts.append("列顺序不对")
    return "表头必须严格为 " + ",".join(expected) + "；" + "；".join(parts)


def parse_csv(path: Path):
    """返回 (header, rows, error)。rows = [(行号, cells)]，行号为近似值（已过滤空行与 # 注释行）。"""
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


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
class Report:
    def __init__(self):
        self.items = []
        self.passed = 0
        self.failed = 0
        self.warned = 0

    def _add(self, level: str, message: str, hint: str = "") -> None:
        item = {"level": level, "message": message}
        if hint:
            item["hint"] = hint
        self.items.append(item)
        if level == "FAIL":
            self.failed += 1
        elif level == "PASS":
            self.passed += 1
        else:
            self.warned += 1

    def ok(self, message: str, hint: str = "") -> None:
        self._add("PASS", message, hint)

    def fail(self, message: str, hint: str = "") -> None:
        self._add("FAIL", message, hint)

    def warn(self, message: str, hint: str = "") -> None:
        self._add("WARN", message, hint)

    def summary_text(self) -> str:
        return "%d 通过 / %d 失败 / %d 警告" % (self.passed, self.failed, self.warned)


def finish(report: Report, args, command: str, root=None, extra=None) -> int:
    if getattr(args, "json_out", False):
        data = {
            "command": command,
            "root": str(root) if root is not None else "",
            "ok": report.failed == 0,
            "passed": report.passed,
            "failed": report.failed,
            "warned": report.warned,
            "summary": report.summary_text(),
            "items": report.items,
        }
        if extra:
            for key, value in extra.items():
                data.setdefault(key, value)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        header = "== %s" % command
        if root is not None:
            header += " ｜ %s" % root
        print(header + " ==")
        for item in report.items:
            print("[%s] %s" % (item["level"], item["message"]))
            hint = item.get("hint")
            if hint:
                print("        建议：%s" % hint)
        print(report.summary_text())
    return 0 if report.failed == 0 else 1


# ---------------------------------------------------------------------------
# 文档检查
# ---------------------------------------------------------------------------
def check_placeholders_only(report: Report, text: str, label: str) -> None:
    hits = find_placeholders(text)
    if hits:
        tokens = "、".join(sorted({token for _, token in hits}))
        report.fail(
            "%s 有 %d 处占位符（含 %s，首个在第 %d 行）" % (label, len(hits), tokens, hits[0][0]),
            hint="把【待填】/TODO/XXX/???/…… 换成可判定内容；示例值必须标【示例】才会被豁免",
        )
    else:
        report.ok("%s 无占位符" % label)


def check_md_document(report: Report, path: Path, key: str, label: str,
                      skip_placeholders: bool = False) -> None:
    try:
        text = read_text(path)
    except OSError as exc:
        report.fail("%s 读取失败：%s" % (label, exc))
        return
    if not text.strip():
        report.fail("%s 是空文件" % label, hint="复制模板后至少保留 H2 章节标题与一行填写说明")
        return
    required = REQUIRED_SECTIONS[key]
    headings = parse_h2(text)
    missing = [section for section in required if section not in headings]
    if missing:
        report.fail(
            "%s 缺少章节：%s" % (label, "、".join(missing)),
            hint="按 docs/维护规范.md §4 用 H2（## 标题）补齐，一字不差；模板见 templates/%s" % key,
        )
    else:
        report.ok("%s 章节齐全（%d 项）" % (label, len(required)))
    if not skip_placeholders:
        check_placeholders_only(report, text, label)


def check_documents(root: Path, report: Report, stage: int,
                    skip_placeholders=frozenset()) -> None:
    docs = root / DOCS_DIR
    report.ok("阶段 P%d（%s）：检查必需文档、H2 章节与占位符" % (stage, STAGE_NAMES.get(stage, "?")))
    if not docs.is_dir():
        report.fail(
            "缺少 docs 目录：%s" % docs,
            hint="先初始化项目：python scripts/gamecheck.py init --dir <目录> --name \"项目名\"",
        )
        return
    singles, dirs = requirements_for(stage)
    for name in singles:
        path = docs / name
        label = "%s/%s" % (DOCS_DIR, name)
        if not path.is_file():
            report.fail("%s 缺失" % label, hint="把 templates/%s 复制到 docs/ 后填写" % name)
            continue
        try:
            text = read_text(path)
        except OSError as exc:
            report.fail("%s 读取失败：%s" % (label, exc))
            continue
        if not text.strip():
            report.fail("%s 是空文件" % label, hint="复制模板后至少保留章节标题")
            continue
        if path.suffix.lower() == ".md":
            check_md_document(report, path, name, label,
                              skip_placeholders=name in skip_placeholders)
        else:
            report.ok("%s 存在（%d 行）" % (label, count_lines(text)))
            if name not in skip_placeholders:
                check_placeholders_only(report, text, label)
    for dirname, minimum in dirs:
        folder = docs / dirname
        label = "%s/%s/" % (DOCS_DIR, dirname)
        files = []
        if folder.is_dir():
            files = sorted(
                item for item in folder.glob("*.md")
                if item.is_file() and not item.name.startswith("_")
            )
        for path in files:
            check_md_document(report, path, DIR_SECTION_KEYS[dirname], label + path.name)
        if len(files) < minimum:
            report.fail(
                "%s 只有 %d 份 .md（要求 ≥%d 份）" % (label, len(files), minimum),
                hint="用 templates/%s 新建文档，文件名不要以 _ 开头（_模板_* 不计入数量）"
                     % DIR_SECTION_KEYS[dirname],
            )
        else:
            report.ok("%s 共 %d 份（要求 ≥%d 份）" % (label, len(files), minimum))


# ---------------------------------------------------------------------------
# 数值检查
# ---------------------------------------------------------------------------
def check_numbers(root: Path, report: Report) -> None:
    path = root / DOCS_DIR / NUM_CSV
    label = "%s/%s" % (DOCS_DIR, NUM_CSV)
    if not path.is_file():
        report.fail("%s 缺失" % label, hint="把 templates/%s 复制到 docs/ 后填写" % NUM_CSV)
        return
    header, rows, error = parse_csv(path)
    if error:
        report.fail("%s 无法解析：%s" % (label, error))
        return
    if header != NUM_HEADER:
        report.fail("%s 表头不符" % label, hint=header_hint(header, NUM_HEADER))
        return
    report.ok("%s 表头正确（%d 列，%d 条数据）" % (label, len(header), len(rows)))
    index = {name: position for position, name in enumerate(header)}
    values = {}
    for line_no, cells in rows:
        key = cell(cells, index, "key")
        if not key:
            report.warn("第 %d 行 key 为空，已跳过" % line_no)
            continue
        if key in values:
            report.warn("key「%s」重复（第 %d 行），只取第 %d 行" % (key, line_no, values[key][2]))
            continue
        values[key] = (cell(cells, index, "value"), cell(cells, index, "unit"), line_no)
    resolved = {}
    conflicts = []
    for role, aliases in NUM_KEY_ALIASES.items():
        found = [(alias, values[alias]) for alias in aliases if alias in values]
        if found:
            resolved[role] = found[0]
            if len(found) > 1:
                conflicts.append(
                    "%s 同时存在 %s，取点号 key"
                    % (NUM_ROLE_LABELS[role], " / ".join(alias for alias, _ in found))
                )
    for note in conflicts:
        report.warn(note, hint="模板统一用点号 key；裸 key 只是兼容旧数据，不要两套并写")

    missing = [aliases[0] for role, aliases in NUM_KEY_ALIASES.items() if role not in resolved]
    if missing:
        report.fail(
            "%s 缺少 key：%s" % (label, "、".join(missing)),
            hint="必需 4 个 key，点号为主、裸 key 兼容：" + NUM_ALIAS_HINT,
        )
    if resolved:
        report.ok("解析到数值 key：%s" % "、".join(
            "%s(%s)" % (resolved[role][0], role) for role in resolved
        ))

    numbers = {}
    for role in NUM_KEY_ALIASES:
        if role not in resolved:
            continue
        alias, (raw_value, unit, line_no) = resolved[role]
        parsed = parse_number(raw_value)
        if parsed is None:
            report.fail("%s 的 %s 不是数字：「%s」" % (label, alias, raw_value),
                        hint="value 列只写数字，单位写到 unit 列")
            continue
        numbers[role] = parsed
    height = numbers.get("height")
    apex = numbers.get("apex_time")
    if height is None or apex is None:
        return
    key_h, key_t = resolved["height"][0], resolved["apex_time"][0]
    if height <= 0:
        report.fail("%s 的 %s 必须 > 0（当前 %s）" % (label, key_h, height))
        return
    if apex <= 0:
        report.fail("%s 的 %s 必须 > 0（当前 %s）" % (label, key_t, apex))
        return
    expected_gravity = 2.0 * height / (apex * apex)
    expected_velocity = 2.0 * height / apex
    unit_h = resolved["height"][1][1]
    unit_t = resolved["apex_time"][1][1]
    report.ok(
        "公式自洽：%s=%g%s %s=%g%s ⇒ g=2h/t²=%.2f，v=2h/t=%.2f"
        % (key_h, height, unit_h, key_t, apex, unit_t, expected_gravity, expected_velocity)
    )
    for role, expected in (("gravity", expected_gravity), ("velocity", expected_velocity)):
        if role not in numbers:
            continue
        alias, (_, unit, _line_no) = resolved[role]
        actual = numbers[role]
        if expected == 0:
            continue
        deviation = (actual - expected) / expected
        percent = deviation * 100.0
        message = "%s（%s）：实际 %g%s，期望 %.2f%s，偏差 %+.2f%%（容差 ±5%%）" % (
            alias, NUM_ROLE_LABELS[role], actual, unit, expected, unit, percent)
        if abs(deviation) <= NUMBER_TOLERANCE:
            report.ok(message)
        else:
            report.fail(
                message,
                hint="三者必须自洽：只改 %s / %s 使其等于 2h/t²、2h/t，或改 %s / %s 让它们一致；单位不做换算，h 用 m 则 g 用 m/s²"
                     % (NUM_KEY_ALIASES["gravity"][0], NUM_KEY_ALIASES["velocity"][0], key_h, key_t),
            )


# ---------------------------------------------------------------------------
# 资产清单检查
# ---------------------------------------------------------------------------
def check_texture(value: str):
    """返回 (是否合规, 说明)。允许 2048x2048 / 4K / 2048；2 的幂且 ≤4096。"""
    raw = (value or "").strip()
    if raw in ("-", "无", "—", "N/A", "NA", "n/a"):
        return True, "无贴图"
    text = raw.replace(" ", "").upper()
    match = re.fullmatch(r"(\d+)[X×*](\d+)", text)
    if match:
        width, height = int(match.group(1)), int(match.group(2))
        for size in (width, height):
            if not is_power_of_two(size):
                return False, "「%s」的边长 %d 不是 2 的幂（允许 256/512/1024/2048/4096）" % (raw, size)
            if size > 4096:
                return False, "「%s」的边长 %d 超过 4096" % (raw, size)
        return True, raw
    match = re.fullmatch(r"(\d+)K", text)
    if match:
        size = int(match.group(1)) * 1024
        if size > 4096:
            return False, "「%s」= %d 超过 4096" % (raw, size)
        if not is_power_of_two(size):
            return False, "「%s」= %d 不是 2 的幂" % (raw, size)
        return True, "%s=%d" % (raw, size)
    match = re.fullmatch(r"(\d+)", text)
    if match:
        size = int(match.group(1))
        if size == 0:
            return True, "无贴图"
        if not is_power_of_two(size):
            return False, "「%s」不是 2 的幂（允许 256/512/1024/2048/4096）" % raw
        if size > 4096:
            return False, "「%s」超过 4096" % raw
        return True, raw
    return False, "「%s」格式不对（写 2048x2048 / 4K / 2048，无贴图写 -）" % raw


def check_asset_header(root: Path, report: Report) -> bool:
    path = root / DOCS_DIR / ASSET_CSV
    label = "%s/%s" % (DOCS_DIR, ASSET_CSV)
    if not path.is_file():
        report.fail("%s 缺失" % label, hint="把 templates/%s 复制到 docs/" % ASSET_CSV)
        return False
    header, rows, error = parse_csv(path)
    if error:
        report.fail("%s 无法解析：%s" % (label, error))
        return False
    if header != ASSET_HEADER:
        report.fail("%s 表头不符" % label, hint=header_hint(header, ASSET_HEADER))
        return False
    report.ok("%s 表头正确（16 列，%d 条数据）" % (label, len(rows)))
    return True


def check_manifest(root: Path, report: Report) -> None:
    path = root / DOCS_DIR / ASSET_CSV
    label = "%s/%s" % (DOCS_DIR, ASSET_CSV)
    if not path.is_file():
        report.fail("%s 缺失" % label, hint="把 templates/%s 复制到 docs/ 后逐行登记" % ASSET_CSV)
        return
    header, rows, error = parse_csv(path)
    if error:
        report.fail("%s 无法解析：%s" % (label, error))
        return
    if header != ASSET_HEADER:
        report.fail("%s 表头不符" % label, hint=header_hint(header, ASSET_HEADER))
        return
    report.ok("%s 表头正确（16 列，%d 条数据）" % (label, len(rows)))
    index = {name: position for position, name in enumerate(header)}
    seen_ids = {}
    seen_files = {}
    registered = set()

    if not rows:
        report.warn("%s 没有任何数据行" % label,
                    hint="至少登记 1 个资产；垂直切片要求已入库 ≥10 条，内容生产按关卡数×8")

    for line_no, cells in rows:
        issues = []
        hints = []
        if len(cells) != len(header):
            issues.append("列数 %d，期望 %d" % (len(cells), len(header)))
            hints.append("对照表头补齐 16 列，空值也要留逗号占位")
        row_id = cell(cells, index, "id")
        row_type = cell(cells, index, "type")
        row_file = norm_rel(cell(cells, index, "file"))
        faces_text = cell(cells, index, "faces")
        textures_text = cell(cells, index, "textures")
        materials_text = cell(cells, index, "materials")
        lod_text = cell(cells, index, "lod")
        license_text = cell(cells, index, "license")
        owner_text = cell(cells, index, "owner")
        status_text = cell(cells, index, "status")

        if not row_id:
            issues.append("id 为空")
            hints.append("id 形如 char_hero / env_rock_01 / mat_stone")
        elif not ID_PATTERN.match(row_id):
            issues.append("id「%s」不符合 ^(char|enemy|env|prop|fx|ui|anim|mat)_[a-z0-9_]+$" % row_id)
            hints.append("id 只用小写字母、数字、下划线，并以类型前缀开头")
        else:
            if row_id in seen_ids:
                issues.append("id 重复（第 %d 行已出现）" % seen_ids[row_id])
            else:
                seen_ids[row_id] = line_no

        if row_type not in TYPE_BUDGET:
            issues.append("type「%s」不在 %s" % (row_type, "/".join(TYPES)))
            hints.append("type 只能是 char/enemy/env/prop/fx/ui/anim/mat")
        elif row_id and ID_PATTERN.match(row_id) and not row_id.startswith(row_type + "_"):
            report.warn(
                "第 %d 行：id「%s」前缀与 type「%s」不一致" % (line_no, row_id, row_type),
                hint="建议 id 用 <type>_ 开头，方便按类型检索",
            )

        if not row_file:
            issues.append("file 为空")
            hints.append("file 写项目相对路径，例如 assets/char_hero.fbx")
        else:
            lower_file = row_file.lower()
            if lower_file in seen_files:
                issues.append("file 重复（第 %d 行已出现）" % seen_files[lower_file])
            else:
                seen_files[lower_file] = line_no
            registered.add(lower_file)
            if not (lower_file.startswith("assets/") or lower_file.startswith("art/export/")):
                issues.append("file「%s」不在 assets/ 或 art/Export/ 下" % row_file)
                hints.append("只有 assets/ 与 art/Export/ 下的文件允许登记；源工程放 art/Source/")
            target = root / row_file
            if not target.exists():
                issues.append("file 不存在：%s" % row_file)
                hints.append("先把导出件放进对应目录，或改 file 列指向真实文件")
            elif not target.is_file():
                issues.append("file 不是文件：%s" % row_file)

        faces = parse_int(faces_text)
        if faces is None:
            issues.append("faces「%s」不是整数" % faces_text)
            hints.append("faces 只写整数，例如 45000；没有网格写 0")
        elif row_type in TYPE_BUDGET:
            budget = TYPE_BUDGET[row_type]
            if faces < 0:
                issues.append("faces 不能为负")
            elif faces > budget:
                issues.append("faces %d 超 %s 预算 %d" % (faces, row_type, budget))
                hints.append("减面或拆分资产；预算见 --show-rules")

        texture_ok, texture_note = check_texture(textures_text)
        if not texture_ok:
            issues.append("textures %s" % texture_note)
            hints.append("贴图边长必须是 2 的幂且 ≤4096；无贴图写 -")

        materials = parse_int(materials_text)
        if materials is None:
            issues.append("materials「%s」不是整数" % materials_text)
        elif not 1 <= materials <= 4:
            issues.append("materials %d 不在 1..4" % materials)
            hints.append("单个资产材质槽不超过 4 个；超出就合并或拆分")

        lod = parse_int(lod_text)
        if lod is None:
            issues.append("lod「%s」不是整数" % lod_text)
        elif not 0 <= lod <= 4:
            issues.append("lod %d 不在 0..4" % lod)
            hints.append("LOD 层级最多 4 级（0 为最高模）")

        if not license_text:
            issues.append("license 为空")
            hints.append("写清授权来源：自有 / CC0 / 商用授权编号；不明来源不许入库")
        if not owner_text:
            issues.append("owner 为空")
            hints.append("owner 写负责人或生成工具，便于追责")
        if status_text not in STATUSES:
            issues.append("status「%s」不在 %s" % (status_text, "/".join(STATUSES)))
            hints.append("status 只能从待做/制作中/待验收/已通过/已入库/废弃 中选")

        head = row_id or "(空 id)"
        if issues:
            report.fail(
                "第 %d 行 %s：%s" % (line_no, head, "；".join(issues)),
                hint="；".join(dict.fromkeys(hints)) if hints
                     else "按 templates/%s 的列含义修正" % ASSET_CSV,
            )
        else:
            report.ok("第 %d 行 %s：合规（%s，faces %d ≤ %d）"
                      % (line_no, head, row_type, faces, TYPE_BUDGET.get(row_type, 0)))

    assets_dir = root / "assets"
    if assets_dir.is_dir():
        found = set()
        for item in assets_dir.rglob("*"):
            if item.is_file() and item.suffix.lower() in TEXTURE_EXTS:
                found.add(rel_label(item, root).lower())
        unregistered = sorted(found - registered)
        if unregistered:
            shown = "、".join(unregistered[:10])
            more = "" if len(unregistered) <= 10 else " 等 %d 个" % len(unregistered)
            report.fail(
                "assets/ 下有 %d 个文件未登记：%s%s" % (len(unregistered), shown, more),
                hint="要么在 docs/%s 登记（id/type/file 等 16 列），要么从 assets/ 移走" % ASSET_CSV,
            )
        else:
            report.ok("assets/ 下 %d 个 .fbx/.glb/.png/.wav 均已登记" % len(found))
    else:
        report.warn("assets/ 目录不存在", hint="init 应创建 assets/；手工建项目时补上")


# ---------------------------------------------------------------------------
# 闸门专用检查
# ---------------------------------------------------------------------------
def check_table_count(root: Path, report: Report, name: str, minimum: int = 3) -> None:
    path = root / DOCS_DIR / name
    label = "%s/%s" % (DOCS_DIR, name)
    if not path.is_file():
        report.fail("%s 缺失" % label, hint="把 templates/%s 复制到 docs/ 后填写" % name)
        return
    text = read_text(path)
    pipe_lines = sum(1 for line in text.splitlines() if line.strip().startswith("|"))
    blocks = 0
    previous_pipe = False
    for line in text.splitlines():
        is_pipe = line.strip().startswith("|")
        if is_pipe and not previous_pipe:
            blocks += 1
        previous_pipe = is_pipe
    if pipe_lines >= minimum:
        report.ok("%s 表格行 %d 行（%d 个表格，要求 ≥%d 行）" % (label, pipe_lines, blocks, minimum))
    else:
        report.fail(
            "%s 表格行只有 %d 行（要求 ≥%d 行）" % (label, pipe_lines, minimum),
            hint="标准书的关键内容用表格写：表头 / 分隔 / 至少 1 行数据，共 3 行以 | 开头",
        )


def check_test_record_placeholders(root: Path, report: Report,
                                   silent_if_missing: bool = False) -> None:
    path = root / DOCS_DIR / "10_测试记录.md"
    if not path.is_file():
        if not silent_if_missing:
            report.fail("%s/10_测试记录.md 缺失" % DOCS_DIR,
                        hint="把 templates/10_测试记录.md 复制到 docs/ 后填写")
        return
    try:
        text = read_text(path)
    except OSError as exc:
        report.fail("docs/10_测试记录.md 读取失败：%s" % exc)
        return
    hits = find_placeholders(text)
    if hits:
        report.fail(
            "docs/10_测试记录.md 有 %d 处占位符（首个在第 %d 行）" % (len(hits), hits[0][0]),
            hint="填入真实版本号、用例、缺陷、性能数据；示例值标【示例】",
        )
    else:
        report.ok("docs/10_测试记录.md 无占位符")


def check_blind_test_evidence(root: Path, report: Report) -> None:
    path = root / DOCS_DIR / "10_测试记录.md"
    if not path.is_file():
        report.fail("docs/10_测试记录.md 缺失（白模闸门必须有盲测记录）",
                    hint="把 templates/10_测试记录.md 复制到 docs/ 后填写盲测结论")
        return
    try:
        text = read_text(path)
    except OSError as exc:
        report.fail("docs/10_测试记录.md 读取失败：%s" % exc)
        return
    if "盲测" in text:
        report.ok("docs/10_测试记录.md 含“盲测”证据")
    else:
        report.fail(
            "docs/10_测试记录.md 未出现“盲测”",
            hint="找 1 名没参与开发的人试玩 1 关，记录人数、时长、卡点、结论，再重跑",
        )
    check_test_record_placeholders(root, report, silent_if_missing=True)
    report.ok("说明：脚本只验证证据齐备，不判定“好不好玩”；好玩与否由 D3 验收决策与盲测结论决定")


def count_status(root: Path, report: Report, wanted: str = "已入库"):
    path = root / DOCS_DIR / ASSET_CSV
    if not path.is_file():
        report.fail("docs/%s 缺失，无法统计状态" % ASSET_CSV)
        return None
    header, rows, error = parse_csv(path)
    if error:
        report.fail("docs/%s 无法解析：%s" % (ASSET_CSV, error))
        return None
    if header != ASSET_HEADER:
        report.fail("docs/%s 表头不符，无法统计状态" % ASSET_CSV,
                    hint=header_hint(header, ASSET_HEADER))
        return None
    index = {name: position for position, name in enumerate(header)}
    return sum(1 for _, cells in rows if cell(cells, index, "status") == wanted)


def find_accepted_receipts(root: Path):
    folder = root / DOCS_DIR / "08_验收单"
    passed = []
    if not folder.is_dir():
        return passed
    for path in sorted(folder.glob("*.md")):
        if not path.is_file() or path.name.startswith("_"):
            continue
        try:
            text = read_text(path)
        except OSError:
            continue
        conclusion = extract_section(text, "结论")
        if not conclusion:
            continue
        if any(word in conclusion for word in ("不通过", "未通过", "待定", "驳回", "返工")):
            continue
        if "通过" in conclusion:
            passed.append(rel_label(path, root))
    return passed


def list_level_docs(root: Path):
    folder = root / DOCS_DIR / "04_关卡设计"
    if not folder.is_dir():
        return []
    return sorted(
        item for item in folder.glob("*.md")
        if item.is_file() and not item.name.startswith("_")
    )


def check_level_acceptance(root: Path, report: Report) -> int:
    folder = root / DOCS_DIR / "04_关卡设计"
    label = "%s/04_关卡设计/" % DOCS_DIR
    files = list_level_docs(root)
    if not folder.is_dir():
        report.fail("%s 目录缺失" % label, hint="每关一份文档，例如 docs/04_关卡设计/01_第一关.md")
        return 0
    if not files:
        report.fail("%s 没有关卡文档" % label, hint="每关一份 <关卡名>.md，从 templates/04_关卡设计.md 复制")
        return 0
    for path in files:
        file_label = label + path.name
        try:
            text = read_text(path)
        except OSError as exc:
            report.fail("%s 读取失败：%s" % (file_label, exc))
            continue
        lines = section_lines(text, "验收清单")
        if not lines:
            report.fail("%s 缺少「## 验收清单」章节或章节为空" % file_label,
                        hint="在关卡文档末尾补 ## 验收清单，逐条写 - [ ] 可判定的验收项")
            continue
        total = 0
        unchecked = []
        for line_no, line in lines:
            match = CHECKBOX_PATTERN.match(line)
            if not match:
                continue
            total += 1
            if match.group("mark") == " ":
                unchecked.append((line_no, (match.group("text") or "").strip()))
        if total == 0:
            report.fail("%s 的「验收清单」没有勾选项（- [ ] / - [x]）" % file_label,
                        hint="每条写成「- [ ] 具体验收项 + 判定标准」，做完改 - [x]")
        elif unchecked:
            sample = "；".join("第 %d 行「%s」" % (line_no, text[:20]) for line_no, text in unchecked[:5])
            report.fail(
                "%s 的「验收清单」还有 %d 项未勾选（共 %d 项）：%s"
                % (file_label, len(unchecked), total, sample),
                hint="关卡验收项不勾完不算做完：完成并改 - [x]，或写明理由后删除该项",
            )
        else:
            report.ok("%s 的「验收清单」%d 项全部已勾选" % (file_label, total))
    return len(files)


def check_content_stock(root: Path, report: Report, level_count=None, override=None) -> None:
    count = count_status(root, report, "已入库")
    if count is None:
        return
    if override is not None:
        threshold = override
        basis = "--min-assets %d（手动覆盖）" % override
    else:
        computed = (level_count or 0) * 8
        threshold = max(computed, CONTENT_MIN_ASSETS)
        basis = "关卡数 %d×8=%d，默认下限 %d" % (level_count or 0, computed, CONTENT_MIN_ASSETS)
    if count >= threshold:
        report.ok("docs/%s 已入库 %d 条 ≥ 阈值 %d（%s）" % (ASSET_CSV, count, threshold, basis))
    else:
        report.fail(
            "docs/%s 已入库只有 %d 条，阈值 %d（%s）" % (ASSET_CSV, count, threshold, basis),
            hint="把通过验收的资产 status 改为 已入库；不够就先补资产或减少关卡数（改范围要走变更单）",
        )


def _track(report: Report, tips, label: str, func, tip: str) -> None:
    before = report.failed
    func()
    if report.failed > before:
        tips.append("%s未通过 → %s" % (label, tip))


# ---------------------------------------------------------------------------
# 各命令实现
# ---------------------------------------------------------------------------
def build_agents_md(skill_rel: str, script_rel: str) -> str:
    return f"""# 项目规则（AGENTS.md）

本文件由 gamecheck.py init 生成，Codex / DSH 等工具会自动读取。项目内文件是唯一真相源，本文件只做入口与命令索引。

## 先读

| 文件 | 用途 |
|---|---|
| {skill_rel}/SKILL.md | 技能入口：先读它，再按阶段加载对应 references 文档 |
| docs/01_游戏设计文档.md | 玩法唯一真相源（数值改这里） |
| docs/02_美术圣经.md | 美术唯一真相源（风格/色板/规范） |
| docs/03_技术方案.md | 技术唯一真相源（架构/性能预算/构建） |

## 硬性规则

- 改数值先改 docs/06_数值表.csv，再跑 numbers check：g=2h/t²、v=2h/t，容差 5%。
- 新增资产先登记 docs/05_资产清单.csv，再放文件到 assets/，然后跑 manifest check。
- 不编造 UE / Steam / Epic 的 API、价格、政策；不确定就写“以官方文档为准”并给官方链接。
- 每个任务交一份交付单：从 docs/07_交付单/_模板_交付单.md 复制到 docs/07_交付单/<编号>.md。
- 资产验收从 docs/08_验收单/_模板_验收单.md 复制到 docs/08_验收单/<资产名>.md。
- 资产导入先 dry-run：python {skill_rel}/scripts/ue_import_assets.py --project-root . --dry-run
- 每天生成截图巡览：python {skill_rel}/scripts/daily_gallery.py --src game/Saved/Screenshots --out gallery

## 常用命令

| 场景 | 命令 |
|---|---|
| 看当前阶段缺什么 | python {script_rel} doc check --stage 2 --root . |
| 数值自洽 | python {script_rel} numbers check --root . |
| 资产清单 | python {script_rel} manifest check --root . |
| 变更单联动 | python {script_rel} change check --root . |
| 上线闸门 | python {script_rel} gate release --root . --store-dir store |
| 全部检查 | python {script_rel} check all --root . |
| 看校验规则 | python {script_rel} --show-rules |

## 完成定义

- 退出码 0 = 该闸门通过；1 = 有 [FAIL]，按提示修；2 = 用法错误。
- 验收单的「结论」只能写“通过”或“不通过”，写“待定”不算通过。
"""


def cmd_init(args) -> int:
    report = Report()
    name = (args.name or "").strip()
    engine = (args.engine or "5.8").strip()
    scale = (args.scale or "小").strip()
    if not name:
        report.fail("--name 不能为空", hint="示例：--name \"代号：山径\"")
        return finish(report, args, "init")
    if not re.match(r"^\d+\.\d+", engine):
        report.warn("--engine「%s」不像 UE 版本号（示例：5.4 / 5.5 / 5.8），已原样写入 gamecheck.json" % engine)

    try:
        target = Path(args.dir).expanduser().resolve()
    except OSError:
        target = Path(args.dir).expanduser().absolute()

    templates = args.templates
    if templates:
        templates_path = Path(templates).expanduser()
    else:
        templates_path = Path(__file__).resolve().parent.parent / "templates"
    try:
        templates_path = templates_path.resolve()
    except OSError:
        templates_path = templates_path.absolute()

    if target.exists() and not target.is_dir():
        report.fail("--dir 指向的不是目录：%s" % target, hint="换一个目录路径")
        return finish(report, args, "init", target)
    overwrite_existing = False
    if target.exists():
        try:
            existing = list(target.iterdir())
        except OSError as exc:
            report.fail("无法读取目标目录 %s：%s" % (target, exc))
            return finish(report, args, "init", target)
        if existing and not args.force:
            report.fail(
                "目标目录非空：%s（%d 个条目）" % (target, len(existing)),
                hint="换一个空目录；确认要覆盖时加 --force（只覆盖本脚本生成的同名文件，不删除其他文件）",
            )
            return finish(report, args, "init", target)
        overwrite_existing = bool(existing)
    else:
        try:
            target.mkdir(parents=True)
        except OSError as exc:
            report.fail("无法创建目录 %s：%s" % (target, exc))
            return finish(report, args, "init", target)

    if not templates_path.is_dir():
        report.fail("模板目录不存在：%s" % templates_path,
                    hint="用 --templates 指定 skill 仓库的 templates 目录")
        return finish(report, args, "init", target)
    missing = [item for item in TEMPLATE_FILES if not (templates_path / item).is_file()]
    if missing:
        report.fail(
            "模板缺失 %d 个：%s" % (len(missing), "、".join(missing)),
            hint="确认 templates/ 完整后重跑，或用 --templates 指向完整目录",
        )
        return finish(report, args, "init", target)
    report.ok("模板目录：%s（%d 个模板）" % (templates_path, len(TEMPLATE_FILES)))

    for relative in INIT_DIRS:
        folder = target / relative
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            report.fail("无法创建目录 %s：%s" % (relative, exc))
            continue
        report.ok("目录 %s/" % relative)

    for template_name in TEMPLATE_FILES:
        source = templates_path / template_name
        dest_rel = TEMPLATE_DEST[template_name]
        dest = target / dest_rel
        existed = dest.exists()
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        except OSError as exc:
            report.fail("复制失败 %s：%s" % (dest_rel, exc))
            continue
        if existed and overwrite_existing:
            report.warn("%s 已存在，已被模板覆盖（--force）" % dest_rel)
        report.ok("写入 %s" % dest_rel)

    config_path = target / CONFIG_FILE
    existed = config_path.exists()
    config = {
        "name": name,
        "engine": engine,
        "scale": scale,
        "created": datetime.date.today().isoformat(),
        "version": CONFIG_VERSION,
    }
    try:
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    except OSError as exc:
        report.fail("写入 %s 失败：%s" % (CONFIG_FILE, exc))
    else:
        if existed and overwrite_existing:
            report.warn("%s 已存在，已被覆盖（--force）" % CONFIG_FILE)
        report.ok("写入 %s（name=%s engine=%s scale=%s）" % (CONFIG_FILE, name, engine, scale))

    try:
        script_path = Path(__file__).resolve()
        skill_root = script_path.parent.parent
        script_rel = Path(os.path.relpath(script_path, target)).as_posix()
        skill_rel = Path(os.path.relpath(skill_root, target)).as_posix()
    except (ValueError, OSError):
        script_rel = Path(__file__).resolve().as_posix()
        skill_rel = Path(__file__).resolve().parent.parent.as_posix()
    agents_path = target / AGENTS_FILE
    existed = agents_path.exists()
    try:
        agents_path.write_text(build_agents_md(skill_rel, "scripts/gamecheck.py"), encoding="utf-8")
    except OSError as exc:
        report.fail("写入 %s 失败：%s" % (AGENTS_FILE, exc))
    else:
        if existed and overwrite_existing:
            report.warn("%s 已存在，已被覆盖（--force）" % AGENTS_FILE)
        report.ok("写入 %s（指向 %s/SKILL.md）" % (AGENTS_FILE, skill_rel))

    checker_src = Path(__file__).resolve()
    checker_dest = target / "scripts" / "gamecheck.py"
    existed = checker_dest.exists()
    try:
        shutil.copyfile(checker_src, checker_dest)
    except OSError as exc:
        report.fail("复制 scripts/gamecheck.py 失败：%s" % exc)
    else:
        if existed and overwrite_existing:
            report.warn("scripts/gamecheck.py 已存在，已被覆盖（--force）")
        report.ok("写入 scripts/gamecheck.py（项目内可直接运行）")

    if report.failed == 0:
        report.ok(
            "项目初始化完成：%s" % target,
            hint="下一步：填 docs/00_立项书.md，然后跑 doc check --stage 0",
        )
    return finish(report, args, "init", target,
                  {"name": name, "engine": engine, "scale": scale})


def cmd_doc_check(args, root: Path) -> int:
    report = Report()
    check_documents(root, report, args.stage)
    return finish(report, args, "doc check --stage %d" % args.stage, root, {"stage": args.stage})


def cmd_numbers(args, root: Path) -> int:
    report = Report()
    check_numbers(root, report)
    return finish(report, args, "numbers check", root)


def cmd_manifest(args, root: Path) -> int:
    report = Report()
    check_manifest(root, report)
    return finish(report, args, "manifest check", root)


def cmd_change(args, root: Path) -> int:
    report = Report()
    check_changes(root, report)
    return finish(report, args, "change check", root)


def cmd_check_all(args, root: Path) -> int:
    report = Report()
    report.ok("组合检查：doc stage 5 + numbers check + manifest check + change check（不早停）")
    check_documents(root, report, 5)
    check_numbers(root, report)
    check_manifest(root, report)
    check_changes(root, report)
    if report.failed:
        report.warn("修复建议：先按上面 [FAIL] 逐条修（文档 → 数值 → 清单），再重跑本命令；各闸门命令会再逐项复查")
    return finish(report, args, "check all", root)


def cmd_gate(args, root: Path) -> int:
    gate = args.gate_cmd
    report = Report()
    tips = []

    if gate == "content":
        override = getattr(args, "min_assets", None)
        if override is not None and override < 1:
            report.fail("--min-assets 必须是正整数，收到 %d" % override,
                        hint="示例：--min-assets 24")
            finish(report, args, "gate content", root)
            return 2
        report.ok("闸门 content：内容生产（阶段 P4）——文档阶段 4 + 每关验收清单全勾选 + 测试记录无占位符 + 已入库 ≥ 关卡数×8（默认下限 24）")
        _track(report, tips, "文档阶段 4",
               lambda: check_documents(root, report, 4, {"10_测试记录.md"}),
               "补齐 docs/00–04、07/08、10 与 11_周报 ≥4 份及其章节")
        level_count = {}

        def run_levels():
            level_count["count"] = check_level_acceptance(root, report)

        _track(report, tips, "关卡验收清单", run_levels,
               "把 docs/04_关卡设计/*.md 的「## 验收清单」全部勾成 - [x]")
        _track(report, tips, "测试记录",
               lambda: check_test_record_placeholders(root, report, True),
               "把 docs/10_测试记录.md 的占位符换成真实版本/用例/缺陷/性能数据")
        _track(report, tips, "已入库数量",
               lambda: check_content_stock(root, report, level_count.get("count"), override),
               "把通过验收的资产 status 改为 已入库，或按关卡数补足；默认下限 24 条")
        _track(report, tips, "变更单联动",
               lambda: check_changes(root, report),
               "每张变更单写 CO- 编号与影响资产；清单 source/note 引用的编号必须存在")
        if report.failed:
            report.warn("G4 内容生产闸门看“量 + 证据”：关卡数×8 是资产产能下限，验收清单是逐关判定依据")
    elif gate == "spec":
        report.ok("闸门 spec：规格锁定（阶段 P1）——文档阶段 1 + 数值自洽 + 资产清单表头 + 标准书表格")
        _track(report, tips, "文档阶段 1",
               lambda: check_documents(root, report, 1),
               "补齐 docs/00、01、02、03、05、06 及其 H2 章节")
        _track(report, tips, "数值自洽",
               lambda: check_numbers(root, report),
               "按 g=2h/t²、v=2h/t 修正 docs/06_数值表.csv 的三处数值")
        _track(report, tips, "资产清单表头",
               lambda: check_asset_header(root, report),
               "把 docs/05_资产清单.csv 表头改成 templates/05_资产清单.csv 的 16 列")
        for name in ("01_游戏设计文档.md", "02_美术圣经.md", "03_技术方案.md"):
            _track(report, tips, "%s 表格" % name,
                   lambda n=name: check_table_count(root, report, n),
                   "在 docs/%s 补表格（至少 3 行以 | 开头：表头/分隔/1 行数据）" % name)
        if report.failed:
            report.warn("G1 不通过时不要进入 P2 白模；标准书改完重跑本闸门")
    elif gate == "whitebox":
        report.ok("闸门 whitebox：白模可玩（阶段 P2）——文档阶段 2 + 数值自洽 + 盲测证据")
        _track(report, tips, "文档阶段 2",
               lambda: check_documents(root, report, 2),
               "补齐 docs/00–03、04_关卡设计/ 至少 1 份关卡文档、05/06")
        _track(report, tips, "数值自洽",
               lambda: check_numbers(root, report),
               "按 g=2h/t²、v=2h/t 修正 docs/06_数值表.csv")
        _track(report, tips, "盲测证据",
               lambda: check_blind_test_evidence(root, report),
               "把盲测人数/时长/卡点/结论写进 docs/10_测试记录.md，并清掉占位符")
        if report.failed:
            report.warn("白模闸门只看证据齐备；好不好玩由 D3 验收决策判定，不在脚本里自动判")
    elif gate == "assets":
        report.ok("闸门 assets：资产管线（阶段 P3）——文档阶段 1 + 资产清单逐行校验")
        _track(report, tips, "文档阶段 1",
               lambda: check_documents(root, report, 1),
               "补齐 docs/00–03、05、06 及其章节")
        _track(report, tips, "资产清单",
               lambda: check_manifest(root, report),
               "按行修正 id/type/file/faces/textures/materials/lod/license/owner/status，并登记 assets/ 下所有文件")
        if report.failed:
            report.warn("资产清单不通过时先不导入 UE：清单是资产工厂的输入，改完重跑本闸门")
    elif gate == "slice":
        report.ok("闸门 slice：垂直切片（阶段 P3）——文档阶段 3 + 验收结论通过 + 已入库 ≥10 条")
        _track(report, tips, "文档阶段 3",
               lambda: check_documents(root, report, 3),
               "补齐 04_关卡设计/、07_交付单/、08_验收单/ 至少各 1 份并填齐章节")
        _track(report, tips, "验收结论",
               lambda: check_accepted_receipt(root, report),
               "在 docs/08_验收单/<资产名>.md 的 ## 结论 写“通过：…”，不要写待定/不通过")
        _track(report, tips, "已入库数量",
               lambda: check_stock_count(root, report),
               "把通过验收的资产 status 改为 已入库，凑够 10 条")
        if report.failed:
            report.warn("切片闸门证明“管线可复现”：1 个完整关卡 + 核心系统 + 成品美术，缺一不可")
    elif gate == "release":
        report.ok("闸门 release：Demo 上线（阶段 P5）——文档阶段 5 + 12/13 清单全勾选 + 双输入 + 商店素材 + 变更联动")
        _track(report, tips, "文档阶段 5",
               lambda: check_documents(root, report, 5, {"10_测试记录.md"}),
               "补齐 P0–P5 全部文档与 H2 章节")
        _track(report, tips, "Demo 上线清单勾选",
               lambda: check_release_checkboxes(root, report, "12_Demo上线清单.md"),
               "逐项完成并改成 - [x]；不做的项写明理由后从清单删除")
        _track(report, tips, "多语言商店清单与双输入",
               lambda: check_release_localization(root, report),
               "13 清单全勾；测试记录/ GDD /技术方案同时覆盖键鼠与手柄；中英商店文案齐备")
        _track(report, tips, "测试记录",
               lambda: check_test_record_placeholders(root, report, True),
               "把 docs/10_测试记录.md 的占位符换成真实版本/用例/缺陷/性能数据")
        _track(report, tips, "商店素材",
               lambda: check_store_assets(root, report, getattr(args, "store_dir", STORE_DIR)),
               "按 templates/13 的命名与尺寸放 5 张胶囊图、双语截图、文案、预告片与字幕")
        _track(report, tips, "变更单联动",
               lambda: check_changes(root, report),
               "每张变更单写 CO- 编号与影响资产；清单 source/note 引用的编号必须存在")
        if report.failed:
            report.warn("上线闸门不允许“基本完成”：任何未勾选项、缺图或未验证输入都算不通过")
    else:
        report.fail("未知闸门：%s" % gate, hint="可选：spec / whitebox / assets / slice / content / release")
        return finish(report, args, "gate %s" % gate, root)

    for tip in tips:
        report.warn("修复建议：%s" % tip)
    return finish(report, args, "gate %s" % gate, root)


def check_accepted_receipt(root: Path, report: Report) -> None:
    folder = root / DOCS_DIR / "08_验收单"
    label = "docs/08_验收单/"
    if not folder.is_dir():
        report.fail("%s 目录缺失" % label, hint="先建目录并至少写 1 份验收单")
        return
    passed = find_accepted_receipts(root)
    total = [item for item in folder.glob("*.md")
             if item.is_file() and not item.name.startswith("_")]
    if passed:
        report.ok("%s 有 %d 份验收单结论为“通过”（共 %d 份）：%s"
                  % (label, len(passed), len(total), "、".join(passed[:5])))
    else:
        report.fail(
            "%s 没有一份验收单的「结论」为通过（共 %d 份）" % (label, len(total)),
            hint="在每份验收单的 ## 结论 下写“通过：满足验收标准”，不可写待定/不通过；待定不算通过",
        )


def check_stock_count(root: Path, report: Report) -> None:
    count = count_status(root, report, "已入库")
    if count is None:
        return
    if count >= 10:
        report.ok("docs/%s 已入库 %d 条（要求 ≥10 条）" % (ASSET_CSV, count))
    else:
        report.fail(
            "docs/%s 已入库只有 %d 条（要求 ≥10 条）" % (ASSET_CSV, count),
            hint="把通过验收的资产 status 改为 已入库；未验收的留在 待验收，不要提前改",
        )



def read_png_size(path: Path):
    """读取 PNG 的 (宽, 高)；非 PNG 或损坏返回 None。"""
    try:
        with path.open("rb") as handle:
            head = handle.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return int(width), int(height)


def split_sections(text: str):
    """按 H2 切分，返回 {章节名: 正文}（同名章节后出现的覆盖前面的）。"""
    sections = {}
    current = None
    buffer = []
    for line in text.splitlines():
        match = H2_PATTERN.match(line)
        if match:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = match.group(1).strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def check_release_checkboxes(root: Path, report: Report,
                             filename: str = "12_Demo上线清单.md") -> None:
    path = root / DOCS_DIR / filename
    label = "%s/%s" % (DOCS_DIR, filename)
    if not path.is_file():
        report.fail("%s 缺失" % label, hint="把 templates/%s 复制到 docs/ 后逐项勾选" % filename)
        return
    text = read_text(path)
    unchecked = []
    checked = 0
    total = 0
    for line_no, line in enumerate(text.splitlines(), 1):
        match = CHECKBOX_PATTERN.match(line)
        if not match:
            continue
        total += 1
        if match.group("mark") == " ":
            unchecked.append((line_no, (match.group("text") or "").strip()))
        else:
            checked += 1
    if total == 0:
        report.fail(
            "%s 没有找到勾选项（- [ ] / - [x]）" % label,
            hint="每个上线条目写成「- [ ] 具体事项 + 完成标准」，完成后改成 - [x]",
        )
        return
    if unchecked:
        sample = "；".join("第 %d 行「%s」" % (line_no, text[:20]) for line_no, text in unchecked[:5])
        report.fail(
            "%s 还有 %d 项未勾选（共 %d 项，已勾 %d 项）：%s"
            % (label, len(unchecked), total, checked, sample),
            hint="未完成项不许上线：完成并改 - [x]；确实不做的项写明理由后从清单删除",
        )
    else:
        report.ok("%s %d 项全部已勾选" % (label, total))


def check_store_assets(root: Path, report: Report, store_rel: str = STORE_DIR) -> None:
    """检查 store/ 下的胶囊图、双语截图、商店文案、预告片与字幕。"""
    store = root / store_rel
    label = store_rel.rstrip("/") + "/"
    if not store.is_dir():
        report.fail(
            "%s 目录缺失" % label,
            hint="按 templates/13_多语言商店素材清单.md 建 store/，放 5 张胶囊图、双语截图、文案、预告片与字幕",
        )
        return
    for name, expected in STORE_CAPSULES.items():
        path = store / name
        if not path.is_file():
            report.fail("%s%s 缺失（应为 %dx%d PNG）" % (label, name, expected[0], expected[1]),
                        hint="按 templates/13 的尺寸表导出；文件名不要改")
            continue
        actual = read_png_size(path)
        if actual is None:
            report.fail("%s%s 不是有效 PNG" % (label, name), hint="导出 PNG（不要改扩展名）后重试")
        elif actual != expected:
            report.fail(
                "%s%s 尺寸 %dx%d，要求 %dx%d" % (label, name, actual[0], actual[1], expected[0], expected[1]),
                hint="按 templates/13 的尺寸表重新导出",
            )
        else:
            report.ok("%s%s 尺寸正确 %dx%d" % (label, name, expected[0], expected[1]))

    for lang in ("zh", "en"):
        shots = sorted(store.glob("screenshot_%s_*.png" % lang))
        if len(shots) < STORE_SCREENSHOT_MIN:
            report.fail(
                "%s 语言 %s 的截图只有 %d 张（要求 ≥%d 张）" % (label, lang, len(shots), STORE_SCREENSHOT_MIN),
                hint="按 templates/13 命名 screenshot_%s_01.png …；每张 1920x1080" % lang,
            )
            continue
        bad = []
        for shot in shots:
            size = read_png_size(shot)
            if size != STORE_SCREENSHOT_SIZE:
                bad.append("%s=%s" % (shot.name, size))
        if bad:
            report.fail("%s 语言 %s 截图尺寸不符：%s" % (label, lang, "、".join(bad[:3])),
                        hint="统一导出 1920x1080 PNG")
        else:
            report.ok("%s 语言 %s 截图 %d 张，均为 1920x1080" % (label, lang, len(shots)))

    for filename in STORE_TEXT_FILES:
        path = store / filename
        if not path.is_file():
            report.fail("%s%s 缺失" % (label, filename), hint="写中文/English 商店文案（各 500 字/300 词以上）")
            continue
        text = read_text(path)
        if len(text.strip()) < 200:
            report.fail("%s%s 内容过短（%d 字符，要求 ≥200）" % (label, filename, len(text.strip())),
                        hint="补一句话卖点、长描述、标签、系统需求、FAQ")
        elif find_placeholders(text):
            report.fail("%s%s 仍有占位符" % (label, filename), hint="清掉【待填】/TODO 后再跑")
        else:
            report.ok("%s%s 已填写（%d 字符）" % (label, filename, len(text.strip())))

    for filename in STORE_SUBTITLE_FILES:
        path = store / filename
        if not path.is_file() or len(read_text(path).strip()) < 20:
            report.fail("%s%s 缺失或过短" % (label, filename), hint="导出与预告片时间轴对齐的 UTF-8 SRT")
        else:
            report.ok("%s%s 已填写" % (label, filename))

    trailer_ok = False
    for filename in STORE_TRAILERS:
        path = store / filename
        if path.is_file() and path.stat().st_size > 100 * 1024:
            report.ok("%s%s 存在（%.1f MB）" % (label, filename, path.stat().st_size / 1048576.0))
            trailer_ok = True
            break
    if not trailer_ok:
        report.fail("%s 预告片缺失或小于 100 KB" % label,
                    hint="放 trailer.mp4 或 trailer.webm（30–60 s，H.264，1080p）")


def check_release_localization(root: Path, report: Report) -> None:
    """G5：双输入（键鼠+手柄）+ 双语商店/界面 + 13 清单勾选。"""
    check_release_checkboxes(root, report, "13_多语言商店素材清单.md")
    checks = (
        ("10_测试记录.md", ("键鼠", "手柄"), "测试记录必须分别记录键鼠与手柄全流程"),
        ("01_游戏设计文档.md", ("键鼠", "手柄"), "GDD 操作表必须同时覆盖键鼠与手柄"),
        ("03_技术方案.md", ("输入映射", "手柄"), "技术方案必须有键鼠+手柄输入映射"),
    )
    for filename, needles, hint in checks:
        path = root / DOCS_DIR / filename
        if not path.is_file():
            report.fail("docs/%s 缺失，无法验证双输入" % filename, hint="补齐文档后再跑")
            continue
        text = read_text(path)
        missing = [needle for needle in needles if needle not in text]
        if missing:
            report.fail(
                "docs/%s 缺少双输入证据：%s" % (filename, "、".join(missing)),
                hint=hint,
            )
        else:
            report.ok("docs/%s 含双输入证据（%s）" % (filename, "、".join(needles)))
    text13_path = root / DOCS_DIR / "13_多语言商店素材清单.md"
    if text13_path.is_file():
        text13 = read_text(text13_path)
        missing = [token for token in ("中文", "English") if token not in text13]
        if missing:
            report.fail("docs/13 缺少语言声明：%s" % "、".join(missing),
                        hint="语言矩阵必须同时写中文与 English")
        else:
            report.ok("docs/13 声明了中文与 English")


def check_changes(root: Path, report: Report) -> None:
    """变更单 ↔ 资产清单联动校验。

    规则：
    1) 每张变更单必须有 CO-/CR- 编号，且「影响评估」列出资产 ID 或写“无资产影响”；
    2) 变更单引用的资产 ID 必须存在于 05_资产清单.csv；
    3) 资产清单 source/note 里引用的 CO-/CR- 编号必须有对应变更单；
    4) 决策栏写“待定”给 warning，不阻断（允许先做后批，但会提示）。
    """
    orders_dir = root / DOCS_DIR / "09_变更单"
    orders = []
    if orders_dir.is_dir():
        orders = sorted(item for item in orders_dir.glob("*.md")
                        if item.is_file() and not item.name.startswith("_"))
    if not orders:
        report.ok("docs/09_变更单/ 无变更单（仍会检查资产清单里的 CO-/CR- 引用）")

    manifest_path = root / DOCS_DIR / ASSET_CSV
    asset_ids = set()
    manifest_rows = []
    if manifest_path.is_file():
        header, rows, error = parse_csv(manifest_path)
        if not error and header == ASSET_HEADER:
            index = {name: pos for pos, name in enumerate(header)}
            for _, cells in rows:
                asset_ids.add(cell(cells, index, "id"))
                manifest_rows.append((cell(cells, index, "id"), cells, index))
    known_order_ids = set()
    order_assets = {}
    for path in orders:
        label = "docs/09_变更单/" + path.name
        check_md_document(report, path, "09_变更单.md", label)
        text = read_text(path)
        match = CHANGE_ID_PATTERN.search(path.stem) or CHANGE_ID_PATTERN.search(text)
        if not match:
            report.fail("%s 缺少变更单编号（CO-001 / CR-001）" % label,
                        hint="在编号行写 CO-<数字>，例如 CO-001")
            continue
        change_id = match.group(0).upper()
        known_order_ids.add(change_id)
        sections = split_sections(text)
        impact = sections.get("影响评估", "")
        ids = sorted(set(ASSET_ID_SCAN_PATTERN.findall(impact)))
        if not ids and "无资产影响" not in impact:
            report.fail("%s 的「影响评估」没有资产 ID，也没有写“无资产影响”" % label,
                        hint="加一张影响资产表（资产 ID/变更类型/变更后状态/验收单），或明确写“无资产影响”")
        missing = [asset_id for asset_id in ids if asset_id not in asset_ids]
        if missing:
            report.fail("%s 引用了资产清单里不存在的资产：%s" % (label, "、".join(missing)),
                        hint="先在 docs/05_资产清单.csv 登记该资产，或修正变更单里的 ID")
        order_assets[change_id] = set(ids)
        if ids:
            report.ok("%s 关联 %d 个资产：%s" % (label, len(ids), "、".join(ids[:5])))
        decision = sections.get("决策", "")
        if "待定" in decision or not any(word in decision for word in ("批准", "通过", "驳回", "已批", "已拒")):
            report.warn("%s 的「决策」还没有明确结论（批准/驳回/待定）" % label)

    for asset_id, cells, index in manifest_rows:
        combined = (cell(cells, index, "source") + " " + cell(cells, index, "note"))
        refs = sorted(set(ref.upper() for ref in CHANGE_ID_PATTERN.findall(combined)))
        for ref in refs:
            if ref not in known_order_ids:
                report.fail("资产 %s 引用了不存在的变更单 %s" % (asset_id, ref),
                            hint="补 docs/09_变更单/%s_*.md，或修正 source/note" % ref)
    linked = sum(1 for refs in order_assets.values() if refs)
    if orders:
        report.ok("变更单联动：%d 张变更单，%d 张关联资产，清单中资产 %d 条"
                  % (len(orders), linked, len(asset_ids)))


# ---------------------------------------------------------------------------
# 规则输出
# ---------------------------------------------------------------------------
def rules_data():
    data = {
        "version": CONFIG_VERSION,
        "stages": {},
        "sections": {},
        "gates": {
            "spec": "doc stage 1 + numbers check + 05 表头 + 01/02/03 各 ≥3 行表格",
            "whitebox": "doc stage 2 + numbers check + 10_测试记录含“盲测”且无占位符",
            "assets": "doc stage 1 + manifest check",
            "slice": "doc stage 3 + ≥1 份验收单结论=通过 + 05 已入库 ≥10 条",
            "content": "doc stage 4 + 每关「验收清单」全勾选 + 10_测试记录无占位符 + 05 已入库 ≥ 关卡数×8（默认下限 24，--min-assets 覆盖）+ change check",
            "release": "doc stage 5 + 12/13 清单无未勾选 + 10_测试记录无占位符 + 双输入 + 商店素材 + change check",
        },
        "placeholders": {
            "forbidden": list(PLACEHOLDER_TOKENS),
            "allowed": "带【示例】的行整行豁免",
        },
        "numbers": {
            "file": "docs/" + NUM_CSV,
            "keys": list(REQUIRED_NUM_KEYS),
            "key_aliases": {role: list(aliases) for role, aliases in NUM_KEY_ALIASES.items()},
            "formulas": ["g = 2h/t²", "v = 2h/t"],
            "tolerance_percent": NUMBER_TOLERANCE * 100,
        },
        "assets": {
            "file": "docs/" + ASSET_CSV,
            "header": list(ASSET_HEADER),
            "types": {name: TYPE_BUDGET[name] for name in TYPES},
            "statuses": list(STATUSES),
            "id_pattern": ID_PATTERN.pattern,
            "textures": "2 的幂且 ≤4096，形如 2048x2048 / 4K / 2048；无贴图写 -",
            "materials": "1..4",
            "lod": "0..4",
            "reverse_scan": "assets/ 下 .fbx/.glb/.png/.wav 必须全部登记；art/Export 与 art/Source 不反向查",
        },
        "exit_codes": {"0": "通过", "1": "校验失败", "2": "用法或内部错误"},
        "source": "docs/维护规范.md §4（章节名一字不差）",
    }
    for stage in range(0, 6):
        singles, dirs = requirements_for(stage)
        data["stages"][str(stage)] = {
            "name": STAGE_NAMES[stage],
            "files": singles,
            "directories": ["%s/ ≥%d 份" % (name, minimum) for name, minimum in dirs],
        }
    data["sections"] = {name: list(sections) for name, sections in REQUIRED_SECTIONS.items()}
    return data


def print_rules(json_out: bool = False) -> None:
    data = rules_data()
    if json_out:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print("gamecheck.py 规则（v%s）" % data["version"])
    print("规则来源：%s；改章节名要同时改这里、templates/ 与规范。" % data["source"])
    print("")
    print("== 阶段与累积必需文档 ==")
    for stage in range(0, 6):
        entry = data["stages"][str(stage)]
        files = "、".join(entry["files"]) if entry["files"] else "（无新增单文件）"
        dirs = "；".join(entry["directories"]) if entry["directories"] else ""
        print("P%d %s：%s%s" % (stage, entry["name"], files, ("；" + dirs) if dirs else ""))
    print("")
    print("== 固定 H2 章节（一字不差）==")
    for name, sections in REQUIRED_SECTIONS.items():
        print("%s：%s" % (name, " / ".join(sections)))
    print("")
    print("== 占位符 ==")
    print("失败记号：%s；整行含【示例】时豁免该行。" % "、".join(PLACEHOLDER_TOKENS))
    print("")
    print("== 数值自洽（docs/%s）==" % NUM_CSV)
    print("必需 key：%s；g=2h/t²、v=2h/t，容差 ±%d%%。"
          % ("、".join(REQUIRED_NUM_KEYS), int(NUMBER_TOLERANCE * 100)))
    print("裸 key 别名（兼容旧数据，不因缺别名 FAIL）：%s" % NUM_ALIAS_HINT)
    print("单位不做换算：h 用 m 则 g 用 m/s²、v 用 m/s；同时出现点号与裸 key 时取点号并告警。")
    print("")
    print("== 资产清单（docs/%s）==" % ASSET_CSV)
    print("16 列表头：%s" % ",".join(ASSET_HEADER))
    print("type 面数预算：%s" % "、".join("%s=%d" % (name, TYPE_BUDGET[name]) for name in TYPES))
    print("贴图：2 的幂且 ≤4096（2048x2048 / 4K / 2048；无贴图写 -）；材质槽 1..4；lod 0..4。")
    print("id 正则：%s" % ID_PATTERN.pattern)
    print("status：%s" % "/".join(STATUSES))
    print("反向检查：%s" % data["assets"]["reverse_scan"])
    print("")
    print("== 闸门 ==")
    for name in ("spec", "whitebox", "assets", "slice", "content", "release"):
        print("%s：%s" % (name, data["gates"][name]))
    print("")
    print("== 退出码 ==")
    print("0 通过 / 1 校验失败 / 2 用法或内部错误")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
class _Parser(argparse.ArgumentParser):
    def error(self, message):
        if "--json" in sys.argv:
            payload = {
                "command": "usage",
                "root": "",
                "ok": False,
                "passed": 0,
                "failed": 1,
                "warned": 0,
                "summary": "0 通过 / 1 失败 / 0 警告",
                "items": [{"level": "FAIL", "message": "用法错误：%s" % message}],
                "error": message,
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            sys.stderr.write("用法错误：%s\n" % message)
            self.print_usage(sys.stderr)
            sys.stderr.write("退出码 2 = 用法错误。示例：python scripts/gamecheck.py doc check --stage 1 --root .\n")
        sys.exit(2)


def _stage_type(value):
    text = str(value).strip()
    if re.fullmatch(r"[Pp]?[0-5]", text):
        return int(text[-1])
    raise argparse.ArgumentTypeError("--stage 只接受 0..5 或 P0..P5，收到：%s" % value)


def _common_parent():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", default=argparse.SUPPRESS,
                        help="项目根目录（默认当前目录，含 docs/ 的那一层）")
    parser.add_argument("--json", dest="json_out", action="store_true", default=argparse.SUPPRESS,
                        help="输出 JSON 报告（stdout 只有 JSON）")
    return parser


def build_parser():
    common = _common_parent()
    parser = _Parser(
        prog="gamecheck.py",
        description="UE5 单人闯关游戏项目校验器：文档 / 数值 / 资产清单 / 闸门。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )
    parser.add_argument("--root", default=".", help="项目根目录（默认当前目录）")
    parser.add_argument("--json", dest="json_out", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--show-rules", action="store_true", help="打印校验规则（章节名/预算/阶段要求/闸门）")
    sub = parser.add_subparsers(dest="cmd", metavar="<命令>")

    p_init = sub.add_parser("init", parents=[common], help="初始化项目骨架")
    p_init.add_argument("--dir", required=True, help="项目目录（不存在则创建）")
    p_init.add_argument("--name", required=True, help="项目名")
    p_init.add_argument("--engine", default="5.8", help="UE 版本（默认 5.8）")
    p_init.add_argument("--scale", default="小", help="项目规模：小/中/大（默认 小）")
    p_init.add_argument("--templates", default=None, help="模板目录（默认 脚本所在目录/../templates）")
    p_init.add_argument("--force", action="store_true", help="目标目录非空时仍然初始化（覆盖同名文件）")

    p_doc = sub.add_parser("doc", parents=[common], help="文档检查")
    doc_sub = p_doc.add_subparsers(dest="doc_cmd", metavar="<动作>", required=True)
    p_doc_check = doc_sub.add_parser("check", parents=[common], help="按阶段检查必需文档")
    p_doc_check.add_argument("--stage", type=_stage_type, required=True, help="阶段 0..5（也接受 P0..P5）")

    p_gate = sub.add_parser("gate", parents=[common], help="闸门检查")
    gate_sub = p_gate.add_subparsers(dest="gate_cmd", metavar="<闸门>", required=True)
    gate_help = {
        "spec": "G1 规格锁定：文档阶段 1 + 数值 + 表头 + 标准书表格",
        "whitebox": "G2 白模可玩：文档阶段 2 + 数值 + 盲测证据",
        "assets": "G3 资产管线：文档阶段 1 + 资产清单逐行校验",
        "slice": "G3 垂直切片：文档阶段 3 + 验收通过 + 已入库 ≥10",
        "content": "G4 内容生产：文档阶段 4 + 每关验收清单全勾选 + 已入库 ≥ 关卡数×8",
        "release": "G5 Demo 上线：文档阶段 5 + 12/13 清单全勾选 + 双输入 + 商店素材 + 变更联动",
    }
    gate_parsers = {}
    for gate_name, help_text in gate_help.items():
        gate_parsers[gate_name] = gate_sub.add_parser(gate_name, parents=[common], help=help_text)
    gate_parsers["content"].add_argument(
        "--min-assets", type=int, default=None,
        help="覆盖已入库数量下限（默认 max(关卡数×8, 24)）",
    )
    gate_parsers["release"].add_argument(
        "--store-dir", default=STORE_DIR,
        help="商店素材目录（默认 store/）",
    )

    p_change = sub.add_parser("change", parents=[common], help="变更单联动检查")
    change_sub = p_change.add_subparsers(dest="change_cmd", metavar="<动作>", required=True)
    change_sub.add_parser("check", parents=[common], help="校验变更单与资产清单的双向引用")

    p_numbers = sub.add_parser("numbers", parents=[common], help="数值表检查")
    numbers_sub = p_numbers.add_subparsers(dest="num_cmd", metavar="<动作>", required=True)
    numbers_sub.add_parser("check", parents=[common], help="校验 06_数值表.csv 的 g/v 自洽")

    p_manifest = sub.add_parser("manifest", parents=[common], help="资产清单检查")
    manifest_sub = p_manifest.add_subparsers(dest="man_cmd", metavar="<动作>", required=True)
    manifest_sub.add_parser("check", parents=[common], help="校验 05_资产清单.csv 全字段与预算")

    p_check = sub.add_parser("check", parents=[common], help="组合检查")
    check_sub = p_check.add_subparsers(dest="check_cmd", metavar="<动作>", required=True)
    check_sub.add_parser("all", parents=[common], help="doc stage 5 + numbers + manifest，不早停")

    sub.add_parser("rules", parents=[common], help="打印校验规则（同 --show-rules）")
    return parser


def dispatch(args) -> int:
    if args.cmd == "init":
        return cmd_init(args)
    root = resolve_root(getattr(args, "root", "."))
    if not root.is_dir():
        report = Report()
        report.fail(
            "根目录不存在或不是目录：%s" % root,
            hint="用 --root 指向项目根（包含 docs/ 的那一层），默认当前目录",
        )
        return finish(report, args, "root", root)
    if args.cmd == "doc":
        if not 0 <= args.stage <= 5:
            report = Report()
            report.fail("--stage 只接受 0..5，收到 %d" % args.stage,
                        hint="P0..P5 对应 --stage 0..5")
            finish(report, args, "doc check", root)
            return 2
        return cmd_doc_check(args, root)
    if args.cmd == "gate":
        return cmd_gate(args, root)
    if args.cmd == "change":
        return cmd_change(args, root)
    if args.cmd == "numbers":
        return cmd_numbers(args, root)
    if args.cmd == "manifest":
        return cmd_manifest(args, root)
    if args.cmd == "check":
        return cmd_check_all(args, root)
    report = Report()
    report.fail("未知命令：%s" % args.cmd)
    finish(report, args, "unknown", root)
    return 2


def main(argv=None) -> int:
    _setup_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "show_rules", False) or args.cmd == "rules":
        print_rules(bool(getattr(args, "json_out", False)))
        return 0
    if args.cmd is None:
        parser.print_help()
        return 2
    try:
        return dispatch(args)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        return 2
    except Exception as exc:  # noqa: BLE001 —— 绝不向用户抛 traceback
        report = Report()
        report.fail(
            "内部错误：%s: %s" % (type(exc).__name__, exc),
            hint="请附上完整命令与 --json 输出反馈给 skill 维护者",
        )
        try:
            root = resolve_root(getattr(args, "root", "."))
        except Exception:
            root = None
        finish(report, args, "internal", root)
        return 2


if __name__ == "__main__":
    sys.exit(main())
