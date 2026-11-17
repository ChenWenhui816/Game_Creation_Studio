#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Studio CLI：解释、检查与下一步建议（中英双语，中文为主）。

用法：
  python scripts/studio.py pipelines
  python scripts/studio.py explain 02
  python scripts/studio.py doctor --project D:\games\my-game
  python scripts/studio.py next --project D:\games\my-game
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import gameconsole
import version

ROOT = Path(__file__).resolve().parent.parent
PIPELINES = [
    ("00", "00_立项", "Concept & Scope", "P0"),
    ("01", "01_标准", "Standards & Docs", "P1"),
    ("02", "02_剧本", "Script & Narrative", "P2"),
    ("03", "03_概念与美术", "Whitebox & Tech", "P3"),
    ("04", "04_测试与技术", "Art & Video", "P4"),
    ("05", "05_音乐与音频", "Music & Audio", "P5"),
    ("06", "06_内容生产与视频", "Content Production", "P6"),
    ("07", "07_上线与发行", "Release & Publishing", "P7"),
]


def _setup():
    gameconsole._setup_stdout()


def cmd_pipelines():
    print("管线 / Pipelines")
    for code, folder, en, stage in PIPELINES:
        print("  %s  %-14s %-22s %s" % (code, folder, en, stage))
    print("\n用法 / Usage: python scripts/studio.py explain 02")



ROUTE_RULES = [
    ("P0", ["立项", "范围", "想法", "平台", "concept", "scope"], "00_立项"),
    ("P1", ["GDD", "标准", "数值", "技术方案", "art bible", "standards"], "01_标准"),
    ("P2", ["剧本", "故事", "角色", "台词", "场景", "镜头", "分镜", "script", "story", "storyboard"], "02_剧本"),
    ("P3", ["白模", "UE", "工程", "蓝图", "性能", "输入", "whitebox", "blueprint", "unreal"], "03_概念与美术"),
    ("P4", ["美术", "资产", "Blender", "贴图", "UI", "PV", "视频", "art", "asset", "video"], "04_测试与技术"),
    ("P5", ["音乐", "音效", "配音", "混音", "Wwise", "MetaSounds", "music", "audio", "voice"], "05_音乐与音频"),
    ("P6", ["关卡", "敌人", "Boss", "任务", "收集", "内容", "level", "enemy", "content"], "06_内容生产与视频"),
    ("P7", ["打包", "Steam", "主机", "商店", "认证", "发布", "release", "store", "console"], "07_上线与发行"),
]


def cmd_route(text, as_json=False):
    text = (text or "").lower()
    scores = []
    for order, (stage, keywords, folder) in enumerate(ROUTE_RULES):
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score:
            scores.append((score, stage, folder, order))
    scores.sort(key=lambda item: (-item[0], item[3]))
    if not scores:
        result = {"stage": "", "pipeline": "", "next": "需要澄清：这是哪条管线？"}
    else:
        score, stage, folder, order = scores[0]
        result = {
            "stage": stage,
            "pipeline": folder,
            "next": "先读 docs/管线/%s/README.md，再跑对应闸门" % folder,
        }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("请求 / Request:", text)
        print("管线 / Pipeline:", result.get("stage"), result.get("pipeline"))
        print("下一步 / Next:", result.get("next"))
    return 0

def _pipeline(code):
    for item in PIPELINES:
        if code in (item[0], item[1], item[2], item[3]):
            return item
    return None


def cmd_explain(code):
    item = _pipeline(code)
    if not item:
        print("未知管线 / Unknown pipeline:", code)
        return 2
    folder = item[1]
    path = ROOT / "docs" / "管线" / folder / "README.md"
    print("== %s / %s ==" % (folder, item[2]))
    print("File:", path)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        print(text[:4500])
    else:
        print("README 缺失；请检查 docs/管线/。")
    return 0


def cmd_doctor(project=None):
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    add("Python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0])
    add("版本 version.py", (ROOT / "scripts" / "version.py").is_file(), version.VERSION)
    add("gamecheck", (ROOT / "scripts" / "gamecheck.py").is_file())
    add("gameconsole", (ROOT / "scripts" / "gameconsole.py").is_file())
    add("8 管线目录", all((ROOT / "docs" / "管线" / x[1]).is_dir() for x in PIPELINES))
    add("MCP 示例配置", (ROOT / "mcp" / "servers.example.json").is_file())
    if project:
        root = Path(project).expanduser().resolve()
        add("项目 gamecheck.json", (root / "gamecheck.json").is_file(), str(root))
        add("项目 docs/", (root / "docs").is_dir())
        add("项目 .gameconsole/", (root / ".gameconsole" / "state.json").is_file())
    print("Studio Doctor / 环境检查")
    for name, ok, detail in checks:
        print("  [%s] %-24s %s" % ("OK" if ok else "!!", name, detail))
    if project and (Path(project).expanduser() / ".gameconsole" / "state.json").is_file():
        try:
            project_obj = gameconsole.Project(Path(project))
            summary = project_obj.summary()
            print("\n项目 / Project: %s" % summary["project"].get("name", ""))
            print("当前阶段 / Current: %s" % summary["current_stage"])
        except Exception as exc:  # noqa: BLE001
            print("项目读取失败 / Project error:", exc)
    print("\n结论 / Verdict:", "PASS" if all(ok for _, ok, _ in checks) else "CHECK")
    return 0 if all(ok for _, ok, _ in checks) else 1


def cmd_next(project):
    root = Path(project).expanduser().resolve()
    try:
        proj = gameconsole.Project(root)
    except Exception as exc:  # noqa: BLE001
        print("无法打开项目 / Cannot open project:", exc)
        return 1
    summary = proj.summary()
    stage = summary["current_stage"]
    detail = proj.stage_detail(stage)
    pipe = _pipeline(stage)
    print("项目 / Project:", summary["project"].get("name", root.name))
    print("当前阶段 / Stage:", stage, pipe[1] if pipe else "")
    print("状态 / Status:", detail.get("status"))
    gate = detail.get("gate") or {}
    print("闸门 / Gate:", gate.get("status") or "未运行")
    if gate.get("status") == "frozen" or detail.get("status") == "frozen":
        print("下一步 / Next: 冻结已完成；进入下一阶段（控制台点“下一步”）。")
    elif gate.get("status") == "pass":
        print("下一步 / Next: 闸门已通过；人工验收后点“冻结”。")
    else:
        print("下一步 / Next: 运行闸门，按失败项修复；说明见 docs/管线/%s/README.md" % (pipe[1] if pipe else ""))
    if detail.get("active_change"):
        print("变更单进行中 / Open change:", detail["active_change"].get("id"))
    return 0


def main(argv=None):
    _setup()
    parser = argparse.ArgumentParser(prog="studio", description="UE5 一人工作室 CLI")
    parser.add_argument("--version", action="version", version=version.VERSION)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("pipelines", help="列出 8 条管线")
    p_route = sub.add_parser("route", help="按请求路由到管线")
    p_route.add_argument("text")
    p_route.add_argument("--json", action="store_true")
    p_explain = sub.add_parser("explain", help="解释某条管线")
    p_explain.add_argument("code")
    p_doctor = sub.add_parser("doctor", help="检查环境")
    p_doctor.add_argument("--project", default=None)
    p_next = sub.add_parser("next", help="当前阶段下一步")
    p_next.add_argument("--project", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "pipelines":
        cmd_pipelines()
        return 0
    if args.cmd == "route":
        return cmd_route(args.text, args.json)
    if args.cmd == "explain":
        return cmd_explain(args.code)
    if args.cmd == "doctor":
        return cmd_doctor(args.project)
    if args.cmd == "next":
        return cmd_next(args.project)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
