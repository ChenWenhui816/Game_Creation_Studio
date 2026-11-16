#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""gameconsole.py — ue5-solo-game 本地制作控制台（v0.3.0）。

零第三方依赖的本地 Web 控制台，把 skill 的六阶段、闸门、交付单
变成可点击的状态机；项目文件仍然是本地文件，控制台只维护状态、版本与快照。

启动（新建项目）：
    python scripts/gameconsole.py serve
    浏览器打开启动日志里的地址，按“新建项目”向导走

启动（已有项目）：
    python scripts/gameconsole.py serve --project D:\games\my-game
    python scripts/gameconsole.py adopt --project D:\games\my-game

数据目录（都在项目内）：
    <project>/.gameconsole/state.json      阶段/闸门/当前阶段
    <project>/.gameconsole/audit.jsonl     追加审计
    <project>/.gameconsole/versions/       全项目版本索引
    <project>/stages/<环节>/versions/      每环节可直接阅读的版本副本
    <project>/stages/<环节>/frozen/        冻结快照

设计原则：
- 文档（docs/）是唯一真相源；控制台不复制正文，只记录状态。
- agent 只能提交，不能冻结/下一步；冻结与推进是用户的 D1/D3 决策。
- 冻结 = 闸门通过 + 快照 + 锁；解冻必须走变更单（v0.3 MVP 先留接口）。

退出码：0 成功；1 校验/状态不满足；2 用法错误。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONSOLE_VERSION = "0.3.0"
SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_ROOT / "templates"
GAMECHECK = SKILL_ROOT / "scripts" / "gamecheck.py"
WEB_ROOT = SKILL_ROOT / "console_web"
CONSOLE_DIR = ".gameconsole"
STAGE_ROOT = "stages"
MAX_BODY = 8 * 1024 * 1024

STAGES = [
    {
        "id": "P0", "name": "立项", "folder": "00_立项",
        "docs": ["docs/00_立项书.md"],
        "gate": ["doc", "check", "--stage", "0"],
        "gate_label": "G0 立项书可复述",
        "desc": "把一句话想法变成一页纸可判定立项书。",
    },
    {
        "id": "P1", "name": "标准与文档", "folder": "01_标准",
        "docs": ["docs/01_游戏设计文档.md", "docs/02_美术圣经.md",
                 "docs/03_技术方案.md", "docs/05_资产清单.csv", "docs/06_数值表.csv"],
        "gate": ["gate", "spec"],
        "gate_label": "G1 标准可判定",
        "desc": "GDD / 美术圣经 / 技术方案 / 资产清单 / 数值表冻结。",
    },
    {
        "id": "P2", "name": "技术底座 + 白模", "folder": "02_白模",
        "docs": ["docs/04_关卡设计", "docs/10_测试记录.md"],
        "gate": ["gate", "whitebox"],
        "gate_label": "G2 盲测通过",
        "desc": "工程能跑、角色能跑跳、1 关灰盒可玩。",
    },
    {
        "id": "P3", "name": "资产管线 + 垂直切片", "folder": "03_资产与切片",
        "docs": ["docs/07_交付单", "docs/08_验收单"],
        "gate": ["gate", "slice"],
        "gate_label": "G3 30 分钟入库",
        "desc": "资产工厂打通，1 关完整流程 + Boss + UI。",
    },
    {
        "id": "P4", "name": "内容生产", "folder": "04_内容生产",
        "docs": ["docs/04_关卡设计", "docs/11_周报"],
        "gate": ["gate", "content"],
        "gate_label": "G4 全流程通关",
        "desc": "全部关卡、敌人、剧情与收集内容。",
    },
    {
        "id": "P5", "name": "打磨 + Demo 上线", "folder": "05_上线",
        "docs": ["docs/12_Demo上线清单.md", "docs/13_多语言商店素材清单.md"],
        "gate": ["gate", "release"],
        "gate_label": "G5 上线清单",
        "desc": "性能、本地化、商店页、Demo 与发布。",
    },
]
STAGE_BY_ID = {item["id"]: item for item in STAGES}
STAGE_IDS = [item["id"] for item in STAGES]
DOC_STAGE = {
    "docs/00_立项书.md": "P0",
    "docs/01_游戏设计文档.md": "P1",
    "docs/02_美术圣经.md": "P1",
    "docs/03_技术方案.md": "P1",
    "docs/05_资产清单.csv": "P1",
    "docs/06_数值表.csv": "P1",
    "docs/10_测试记录.md": "P2",
    "docs/04_关卡设计": "P4",
    "docs/07_交付单": "P3",
    "docs/08_验收单": "P3",
    "docs/11_周报": "P4",
    "docs/12_Demo上线清单.md": "P5",
    "docs/13_多语言商店素材清单.md": "P5",
    "docs/09_变更单": None,
}
STATUSES = ("drafting", "review", "frozen", "blocked")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, data, atomic: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if atomic:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    else:
        path.write_text(text, encoding="utf-8")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def rel_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


class ConsoleError(Exception):
    def __init__(self, message: str, status: int = 400, detail=None):
        super().__init__(message)
        self.status = status
        self.detail = detail or {}


class Project:
    """一个游戏项目的控制台视图；文档本体仍在 docs/。"""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.console = self.root / CONSOLE_DIR
        self.state_path = self.console / "state.json"
        self.audit_path = self.console / "audit.jsonl"
        self.versions_index = self.console / "versions" / "index.json"
        self.state = read_json(self.state_path)
        if not isinstance(self.state, dict):
            raise ConsoleError("不是控制台项目：缺少 .gameconsole/state.json", 404)
        self._state_mtime = self.state_path.stat().st_mtime_ns if self.state_path.exists() else None
        self.ensure_layout()

    def reload(self) -> None:
        """外部进程（agent CLI）可能更新 state.json；请求前刷新。"""
        try:
            mtime = self.state_path.stat().st_mtime_ns
        except OSError:
            return
        if mtime != self._state_mtime:
            fresh = read_json(self.state_path)
            if isinstance(fresh, dict):
                self.state = fresh
                self._state_mtime = mtime

    @classmethod
    def create(cls, path: Path, name: str, idea: str, platform: str,
               scale: str = "小", engine: str = "5.8", force: bool = False) -> "Project":
        path = Path(path).expanduser().resolve()
        if path.exists() and any(path.iterdir()) and not force:
            raise ConsoleError("目标目录非空：%s" % path, 409,
                               {"hint": "换一个空目录，或勾选“允许覆盖”"})
        cmd = [sys.executable, str(GAMECHECK), "init", "--dir", str(path),
               "--name", name, "--engine", engine, "--scale", scale]
        if force:
            cmd.append("--force")
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
        if proc.returncode != 0:
            raise ConsoleError("创建项目骨架失败", 500,
                               {"stdout": proc.stdout[-3000:], "stderr": proc.stderr[-3000:]})
        cls._write_brief(path, name, idea, platform)
        project = cls._init_console(path, name, platform, scale, engine)
        project.audit("project.create", str(path), {"name": name, "idea": idea})
        project.snapshot_initial()
        return project

    @classmethod
    def adopt(cls, path: Path) -> "Project":
        path = Path(path).expanduser().resolve()
        if not (path / "gamecheck.json").is_file():
            raise ConsoleError("目录里没有 gamecheck.json：先跑 gamecheck.py init", 400)
        if (path / CONSOLE_DIR / "state.json").is_file():
            return cls(path)
        cfg = read_json(path / "gamecheck.json", {}) or {}
        project = cls._init_console(path, cfg.get("name", path.name), "",
                                    cfg.get("scale", "小"), cfg.get("engine", "5.8"))
        project.audit("project.adopt", str(path), {})
        project.snapshot_initial()
        return project

    @classmethod
    def _init_console(cls, path: Path, name: str, platform: str,
                      scale: str, engine: str) -> "Project":
        console = path / CONSOLE_DIR
        console.mkdir(parents=True, exist_ok=True)
        (console / "versions").mkdir(exist_ok=True)
        (console / "outbox").mkdir(exist_ok=True)
        (console / "inbox").mkdir(exist_ok=True)
        state = {
            "schema": 1,
            "console_version": CONSOLE_VERSION,
            "skill_version": CONSOLE_VERSION,
            "project": {
                "name": name,
                "path": str(path),
                "created": now_iso(),
                "platform": platform,
                "scale": scale,
                "engine": engine,
            },
            "current_stage": "P0",
            "stages": {sid: {"status": "drafting", "gate": None,
                             "frozen_at": None, "snapshot": None,
                             "updated_at": now_iso()} for sid in STAGE_IDS},
            "submissions": [],
        }
        write_json(console / "state.json", state)
        project = cls(path)
        for item in STAGES:
            project.stage_dir(item["id"]).mkdir(parents=True, exist_ok=True)
            (project.stage_dir(item["id"]) / "versions").mkdir(exist_ok=True)
            (project.stage_dir(item["id"]) / "frozen").mkdir(exist_ok=True)
        project.refresh_all_readmes()
        return project

    @classmethod
    def _write_brief(cls, path: Path, name: str, idea: str, platform: str) -> None:
        template = TEMPLATES / "00_立项书.md"
        text = read_text(template)
        text = text.replace("# 《【项目名】》立项书", "# 《%s》立项书" % name)
        text = text.replace("| 项目名 | 【待填】 |", "| 项目名 | %s |" % name)
        text = text.replace("| 日期 | 【待填】 |", "| 日期 | %s |" % datetime.now().strftime("%Y-%m-%d"))
        text = text.replace("| 负责人 | 【待填】 |", "| 负责人 | 你（需求 + 美术总监） |")
        text = text.replace("| 目标平台 | 【示例】Windows PC（Steam Demo），1080p 60 fps |",
                            "| 目标平台 | %s |" % (platform or "Windows PC（Steam Demo），1080p 60 fps"))
        text = text.replace("| 排期上限 | 【示例】16 周 |", "| 排期上限 | 20 周 |")
        text = text.replace("| 状态 | 草案 / 已确认（冻结） |", "| 状态 | 草案（控制台创建） |")
        sentences = [item.strip() for item in re.split(r"(?<=[。！？!?])", idea.strip()) if item.strip()]
        if not sentences:
            sentences = ["【待填】一句话描述。"]
        while len(sentences) < 3:
            sentences.append("【待填】补充第 %d 句。" % (len(sentences) + 1))
        rows = ["| 第 1 句 | %s | 世界背景 + 角色 + 突发事件 + 必须做的事 |" % sentences[0],
                "| 第 2 句 | %s | 得到什么 + 用来提升什么 + 继续做什么 |" % sentences[1],
                "| 第 3 句 | %s | 可验证终局：到达 / 关闭 / 救出 / 送出 |" % sentences[2]]
        text = re.sub(r"\| 第 1 句 \| 【待填】 \| 世界背景.*?\n\| 第 2 句 \| 【待填】 \| 得到什么.*?\n\| 第 3 句 \| 【待填】 \| 可验证终局.*?\n",
                      "\n".join(rows) + "\n", text, flags=re.S)
        brief = path / "docs" / "00_立项书.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text(text, encoding="utf-8")

    def save_state(self) -> None:
        self.state["updated_at"] = now_iso()
        write_json(self.state_path, self.state)
        try:
            self._state_mtime = self.state_path.stat().st_mtime_ns
        except OSError:
            self._state_mtime = None

    def audit(self, action: str, target: str = "", detail=None, actor: str = "user") -> None:
        entry = {"at": now_iso(), "actor": actor, "action": action,
                 "target": target, "detail": detail or {}}
        self.console.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def stage_dir(self, stage_id: str) -> Path:
        return self.root / STAGE_ROOT / STAGE_BY_ID[stage_id]["folder"]

    def ensure_layout(self) -> None:
        self.console.mkdir(parents=True, exist_ok=True)
        (self.console / "versions").mkdir(exist_ok=True)
        (self.console / "outbox").mkdir(exist_ok=True)
        (self.console / "inbox").mkdir(exist_ok=True)
        for item in STAGES:
            folder = self.stage_dir(item["id"])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "versions").mkdir(exist_ok=True)
            (folder / "frozen").mkdir(exist_ok=True)

    def stage_def(self, stage_id: str):
        if stage_id not in STAGE_BY_ID:
            raise ConsoleError("未知阶段：%s" % stage_id, 404)
        return STAGE_BY_ID[stage_id]

    def next_stage(self, stage_id: str):
        index = STAGE_IDS.index(stage_id)
        return STAGE_IDS[index + 1] if index + 1 < len(STAGE_IDS) else None

    def stage_status(self, stage_id: str) -> str:
        return self.state["stages"][stage_id].get("status", "drafting")

    def set_stage_status(self, stage_id: str, status: str) -> None:
        if status not in STATUSES:
            raise ConsoleError("非法状态：%s" % status, 400)
        self.state["stages"][stage_id]["status"] = status
        self.state["stages"][stage_id]["updated_at"] = now_iso()

    def docs_for_stage(self, stage_id: str):
        files = []
        for rel in STAGE_BY_ID[stage_id]["docs"]:
            path = self.root / rel
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(sorted(item for item in path.rglob("*.md")
                                    if item.is_file() and not item.name.startswith("_")))
        return files

    @staticmethod
    def stage_of_rel(rel: str):
        for prefix, stage in DOC_STAGE.items():
            if rel == prefix or rel.startswith(prefix + "/"):
                return stage
        return None

    def is_locked(self, rel: str) -> bool:
        stage = self.stage_of_rel(rel)
        if stage is None:
            return False
        return self.stage_status(stage) == "frozen"

    def _versions_index(self):
        data = read_json(self.versions_index, {"items": []})
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            data = {"items": []}
        return data

    def _save_versions_index(self, data) -> None:
        write_json(self.versions_index, data)

    def versions(self, rel: str):
        items = [item for item in self._versions_index()["items"] if item.get("file") == rel]
        return sorted(items, key=lambda item: item.get("at", ""), reverse=True)

    def _make_version(self, rel: str, content: str, note: str = "") -> dict:
        stage = self.stage_of_rel(rel) or self.state.get("current_stage", "P0")
        folder = self.stage_dir(stage) / "versions"
        folder.mkdir(parents=True, exist_ok=True)
        name = rel.split("/")[-1]
        base = "%s__%s" % (stamp(), name)
        path = folder / base
        counter = 2
        while path.exists():
            path = folder / ("%s_%d__%s" % (stamp(), counter, name))
            counter += 1
        path.write_text(content, encoding="utf-8")
        item = {"file": rel, "stage": stage, "version": path.name,
                "path": rel_posix(path, self.root), "hash": sha_text(content),
                "at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
                "note": note, "size": len(content.encode("utf-8"))}
        index = self._versions_index()
        index["items"].append(item)
        self._save_versions_index(index)
        return item

    def restore_version(self, rel: str, version: str) -> dict:
        items = [item for item in self._versions_index()["items"]
                 if item.get("file") == rel and item.get("version") == version]
        if not items:
            raise ConsoleError("找不到版本：%s" % version, 404)
        path = self.root / items[0]["path"]
        if not path.is_file():
            raise ConsoleError("版本文件已丢失：%s" % items[0]["path"], 404)
        content = read_text(path)
        self.save_artifact(rel, content, expected_hash=None, note="restore:" + version)
        return {"file": rel, "version": version, "hash": sha_text(content)}

    def snapshot_initial(self) -> None:
        for rel in ("docs/00_立项书.md",):
            path = self.root / rel
            if path.is_file():
                self._make_version(rel, read_text(path), "initial")
        self.save_state()

    def refresh_all_readmes(self) -> None:
        for item in STAGES:
            self.write_stage_readme(item["id"])

    def write_stage_readme(self, stage_id: str) -> None:
        item = self.stage_def(stage_id)
        folder = self.stage_dir(stage_id)
        state = self.state["stages"][stage_id]
        gate = state.get("gate") or {}
        lines = [
            "# %s %s · %s" % (item["id"], item["name"], state.get("status", "drafting")),
            "",
            "> 本文件夹由制作控制台生成，用于本地阅读；文档本体在 ../../docs/。",
            "",
            "## 本阶段文档",
            "",
        ]
        for rel in item["docs"]:
            path = self.root / rel
            if path.is_dir():
                lines.append("- %s/（目录）" % rel)
            elif path.is_file():
                lines.append("- [%s](../../%s)" % (rel, rel))
            else:
                lines.append("- %s（尚未创建）" % rel)
        lines += ["", "## 闸门", "",
                  "- 判定：%s" % item["gate_label"],
                  "- 命令：python scripts/gamecheck.py %s --root ." % " ".join(item["gate"]),
                  "- 最近结果：%s" % (gate.get("status", "未运行")),
                  "- 最近运行：%s" % (gate.get("ran_at", "—")),
                  "", "## 版本", "",
                  "- 本阶段版本副本：versions/",
                  "- 冻结快照：frozen/"]
        if state.get("frozen_at"):
            lines.append("- 冻结时间：%s" % state["frozen_at"])
        if state.get("snapshot"):
            lines.append("- 快照目录：%s" % state["snapshot"])
        lines += ["", "## 操作", "",
                  "在控制台打开本阶段，可保存 / 运行闸门 / 冻结 / 下一步。",
                  ""]
        (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")

    def _check_rel(self, rel: str) -> Path:
        if not rel or rel.startswith("/") or ".." in Path(rel).parts:
            raise ConsoleError("非法文档路径：%s" % rel, 400)
        path = (self.root / rel).resolve()
        docs = (self.root / "docs").resolve()
        try:
            path.relative_to(docs)
        except ValueError:
            raise ConsoleError("只允许修改 docs/ 下的文档", 400)
        return path

    def artifact_info(self, rel: str) -> dict:
        path = self._check_rel(rel)
        if not path.is_file():
            return {"path": rel, "exists": False, "content": "", "hash": "",
                    "locked": self.is_locked(rel), "stage": self.stage_of_rel(rel),
                    "versions": self.versions(rel)}
        content = read_text(path)
        return {"path": rel, "exists": True, "content": content, "hash": sha_text(content),
                "locked": self.is_locked(rel), "stage": self.stage_of_rel(rel),
                "versions": self.versions(rel), "size": len(content.encode("utf-8"))}

    def save_artifact(self, rel: str, content: str, expected_hash=None, note="") -> dict:
        path = self._check_rel(rel)
        if self.is_locked(rel):
            raise ConsoleError("该文档已随阶段冻结；修改需先开变更单", 423,
                               {"file": rel, "stage": self.stage_of_rel(rel)})
        old = read_text(path) if path.is_file() else ""
        if expected_hash and path.is_file() and sha_text(old) != expected_hash:
            raise ConsoleError("文件已在控制台外被修改，请刷新后重试", 409,
                               {"current_hash": sha_text(old)})
        if old and old != content:
            self._make_version(rel, old, note or "before-save")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self._make_version(rel, content, note or "save")
        stage = self.stage_of_rel(rel) or self.state.get("current_stage", "P0")
        if self.stage_status(stage) == "review":
            self.set_stage_status(stage, "drafting")
        self.audit("artifact.save", rel, {"size": len(content), "note": note})
        self.save_state()
        self.write_stage_readme(stage)
        return {"path": rel, "hash": sha_text(content), "stage": stage,
                "versions": self.versions(rel)}

    def run_gate(self, stage_id: str) -> dict:
        item = self.stage_def(stage_id)
        cmd = [sys.executable, str(GAMECHECK)] + list(item["gate"]) + [
            "--root", str(self.root), "--json"]
        started = time.time()
        proc = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        report = None
        try:
            report = json.loads(proc.stdout)
        except ValueError:
            start = proc.stdout.find("{")
            if start >= 0:
                try:
                    report = json.loads(proc.stdout[start:])
                except ValueError:
                    report = None
        status = "pass" if proc.returncode == 0 else "fail"
        gate = {
            "status": status,
            "exit_code": proc.returncode,
            "ran_at": now_iso(),
            "duration_ms": int((time.time() - started) * 1000),
            "command": " ".join(cmd[1:]),
            "report": report,
            "stdout_tail": proc.stdout[-6000:],
            "stderr_tail": proc.stderr[-3000:],
        }
        self.state["stages"][stage_id]["gate"] = gate
        self.state["stages"][stage_id]["updated_at"] = now_iso()
        self.audit("gate.run", stage_id, {"status": status, "exit_code": proc.returncode})
        self.save_state()
        self.write_stage_readme(stage_id)
        return gate

    def freeze(self, stage_id: str) -> dict:
        if stage_id != self.state.get("current_stage"):
            raise ConsoleError("只能冻结当前阶段", 400)
        gate = self.run_gate(stage_id)
        if gate["status"] != "pass":
            raise ConsoleError("闸门未通过，不能冻结", 409, {"gate": gate})
        folder = self.stage_dir(stage_id)
        snap = folder / "frozen" / stamp()
        snap.mkdir(parents=True, exist_ok=True)
        files = {}
        for path in self.docs_for_stage(stage_id):
            rel = rel_posix(path, self.root)
            dest = snap / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            files[rel] = sha_text(read_text(path))
        freeze_data = {"stage": stage_id, "frozen_at": now_iso(),
                       "skill_version": CONSOLE_VERSION, "gate": gate, "files": files}
        write_json(snap / "freeze.json", freeze_data)
        self.state["stages"][stage_id].update({
            "status": "frozen", "frozen_at": freeze_data["frozen_at"],
            "snapshot": rel_posix(snap, self.root), "gate": gate,
            "updated_at": now_iso(),
        })
        self.audit("stage.freeze", stage_id,
                   {"snapshot": rel_posix(snap, self.root), "files": len(files)})
        self.save_state()
        self.write_stage_readme(stage_id)
        return {"stage": stage_id, "snapshot": rel_posix(snap, self.root), "files": files,
                "frozen_at": freeze_data["frozen_at"]}

    def next_stage_action(self, stage_id: str) -> dict:
        if stage_id != self.state.get("current_stage"):
            raise ConsoleError("只能推进当前阶段", 400)
        if self.stage_status(stage_id) != "frozen":
            raise ConsoleError("当前阶段未冻结，不能进入下一步", 409)
        nxt = self.next_stage(stage_id)
        if not nxt:
            raise ConsoleError("已经是最后一个阶段", 409)
        self.state["current_stage"] = nxt
        if self.state["stages"][nxt].get("status") != "frozen":
            self.state["stages"][nxt]["status"] = "drafting"
        self.state["stages"][nxt]["updated_at"] = now_iso()
        self.audit("stage.next", "%s -> %s" % (stage_id, nxt), {})
        self.save_state()
        self.refresh_all_readmes()
        return {"current_stage": nxt}

    def reject(self, stage_id: str, reason: str = "") -> dict:
        if self.stage_status(stage_id) == "frozen":
            raise ConsoleError("已冻结阶段需走变更单解冻", 409)
        self.set_stage_status(stage_id, "drafting")
        self.audit("stage.reject", stage_id, {"reason": reason})
        self.save_state()
        self.write_stage_readme(stage_id)
        return {"stage": stage_id, "status": "drafting"}

    def submit(self, stage_id: str, title: str, note: str = "", evidence=None) -> dict:
        self.stage_def(stage_id)
        sub = {
            "id": "S-" + secrets.token_hex(4).upper(),
            "stage": stage_id,
            "title": title,
            "note": note,
            "evidence": evidence or [],
            "status": "pending",
            "at": now_iso(),
        }
        write_json(self.console / "outbox" / (sub["id"] + ".json"), sub)
        self.state.setdefault("submissions", []).append(sub)
        if self.stage_status(stage_id) == "drafting":
            self.set_stage_status(stage_id, "review")
        self.audit("submission.create", sub["id"], {"stage": stage_id, "title": title})
        self.save_state()
        return sub

    def resolve_submission(self, sub_id: str, accepted: bool, reason: str = "") -> dict:
        subs = self.state.setdefault("submissions", [])
        sub = next((item for item in subs if item["id"] == sub_id), None)
        if not sub:
            raise ConsoleError("找不到交付单：%s" % sub_id, 404)
        sub["status"] = "accepted" if accepted else "returned"
        sub["resolved_at"] = now_iso()
        sub["reason"] = reason
        if accepted:
            self.set_stage_status(sub["stage"], "review")
        else:
            self.set_stage_status(sub["stage"], "drafting")
        self.audit("submission.resolve", sub_id, {"accepted": accepted, "reason": reason})
        self.save_state()
        self.write_stage_readme(sub["stage"])
        return sub

    def summary(self) -> dict:
        stages = []
        for item in STAGES:
            state = self.state["stages"].get(item["id"], {})
            docs = []
            for rel in item["docs"]:
                path = self.root / rel
                if path.is_file():
                    docs.append({"path": rel, "exists": True,
                                 "size": path.stat().st_size,
                                 "locked": self.is_locked(rel)})
                elif path.is_dir():
                    files = sorted(p for p in path.rglob("*.md")
                                   if p.is_file() and not p.name.startswith("_"))
                    docs.append({"path": rel, "exists": bool(files),
                                 "files": len(files), "locked": self.is_locked(rel)})
                else:
                    docs.append({"path": rel, "exists": False, "locked": False})
            gate = state.get("gate") or {}
            stages.append({
                "id": item["id"], "name": item["name"], "folder": item["folder"],
                "desc": item["desc"], "gate_label": item["gate_label"],
                "status": state.get("status", "drafting"),
                "gate_status": gate.get("status"), "gate_ran_at": gate.get("ran_at"),
                "frozen_at": state.get("frozen_at"),
                "snapshot": state.get("snapshot"),
                "docs": docs,
            })
        pending = [s for s in self.state.get("submissions", []) if s.get("status") == "pending"]
        return {
            "project": self.state.get("project", {}),
            "current_stage": self.state.get("current_stage", "P0"),
            "stages": stages,
            "pending_submissions": len(pending),
            "submissions": self.state.get("submissions", []),
            "console_version": CONSOLE_VERSION,
            "root": str(self.root),
        }

    def stage_detail(self, stage_id: str) -> dict:
        item = self.stage_def(stage_id)
        state = self.state["stages"][stage_id]
        docs = []
        for rel in item["docs"]:
            path = self.root / rel
            if path.is_file():
                docs.append({"path": rel, "exists": True, "name": path.name,
                             "size": path.stat().st_size,
                             "hash": sha_text(read_text(path)),
                             "locked": self.is_locked(rel),
                             "versions": len(self.versions(rel))})
            elif path.is_dir():
                for child in sorted(p for p in path.rglob("*.md")
                                    if p.is_file() and not p.name.startswith("_")):
                    child_rel = rel_posix(child, self.root)
                    docs.append({"path": child_rel, "exists": True, "name": child.name,
                                 "size": child.stat().st_size,
                                 "hash": sha_text(read_text(child)),
                                 "locked": self.is_locked(child_rel),
                                 "versions": len(self.versions(child_rel))})
            else:
                docs.append({"path": rel, "exists": False, "name": rel.split("/")[-1],
                             "locked": False, "versions": 0})
        gate = state.get("gate") or {}
        return {
            "stage": item, "status": state.get("status", "drafting"),
            "gate": gate, "frozen_at": state.get("frozen_at"),
            "snapshot": state.get("snapshot"), "docs": docs,
            "folder": item["folder"],
            "next_stage": self.next_stage(stage_id),
        }

    def audit_tail(self, limit: int = 80):
        if not self.audit_path.is_file():
            return []
        lines = self.audit_path.read_text(encoding="utf-8").splitlines()[-limit:]
        items = []
        for line in lines:
            try:
                items.append(json.loads(line))
            except ValueError:
                continue
        return list(reversed(items))


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, project=None):
        super().__init__(address, Handler)
        self.project = project


class Handler(BaseHTTPRequestHandler):
    server_version = "GameConsole/" + CONSOLE_VERSION

    def log_message(self, fmt, *args):
        return

    def _send(self, status: int, body: bytes, content_type: str, extra=None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _ok(self, payload) -> None:
        self._json(200, {"ok": True, "data": payload})

    def _fail(self, error) -> None:
        if isinstance(error, ConsoleError):
            self._json(error.status, {"ok": False, "error": str(error), "detail": error.detail})
        else:
            self._json(500, {"ok": False, "error": "内部错误：%s" % error})

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ConsoleError("请求体过大", 413)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ConsoleError("请求体不是合法 JSON", 400)

    def _project(self):
        project = getattr(self.server, "project", None)
        if project is None:
            raise ConsoleError("尚未创建项目；先走新建项目向导", 400)
        project.reload()
        return project

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def _static(self, rel: str):
        rel = urllib.parse.unquote(rel)
        if not rel or ".." in Path(rel).parts:
            raise ConsoleError("非法静态路径", 400)
        path = (WEB_ROOT / rel).resolve()
        try:
            path.relative_to(WEB_ROOT.resolve())
        except ValueError:
            raise ConsoleError("非法静态路径", 400)
        if not path.is_file():
            raise ConsoleError("文件不存在", 404)
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        if path.suffix in (".html", ".css", ".svg"):
            ctype += "; charset=utf-8" if "charset" not in ctype else ""
        self._send(200, path.read_bytes(), ctype)

    def do_GET(self):
        if not self._host_ok():
            self._json(403, {"ok": False, "error": "只允许本机访问"})
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                self._static("index.html")
            elif path.startswith("/static/"):
                self._static(path[len("/static/"):])
            elif path == "/api/health":
                self._ok({"console": CONSOLE_VERSION, "project": bool(getattr(self.server, "project", None))})
            elif path == "/api/state":
                project = getattr(self.server, "project", None)
                if project is None:
                    self._ok({"needs_project": True, "console_version": CONSOLE_VERSION})
                else:
                    project.reload()
                    self._ok(project.summary())
            elif path == "/api/fs":
                self._ok(list_fs(query.get("path", [""])[0]))
            elif path == "/api/artifact":
                self._ok(self._project().artifact_info(query.get("path", [""])[0]))
            elif path == "/api/versions":
                rel = query.get("path", [""])[0]
                self._ok({"path": rel, "versions": self._project().versions(rel)})
            elif path == "/api/audit":
                self._ok({"items": self._project().audit_tail(80)})
            elif path == "/api/stage":
                self._ok(self._project().stage_detail(query.get("id", ["P0"])[0]))
            elif path == "/api/config":
                self._project()
                self._ok({"root": str(self.server.project.root),
                          "stage_root": STAGE_ROOT,
                          "console_dir": CONSOLE_DIR,
                          "version": CONSOLE_VERSION})
            else:
                self._json(404, {"ok": False, "error": "未知接口：%s" % path})
        except ConsoleError as exc:
            self._fail(exc)
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)

    def do_POST(self):
        if not self._host_ok():
            self._json(403, {"ok": False, "error": "只允许本机访问"})
            return
        try:
            payload = self._body()
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/project":
                root = payload.get("path", "").strip()
                name = payload.get("name", "").strip()
                if not root or not name:
                    raise ConsoleError("项目名与路径不能为空", 400)
                project = Project.create(
                    Path(root), name, payload.get("idea", ""),
                    payload.get("platform", "Windows PC（Steam Demo），1080p 60 fps"),
                    payload.get("scale", "小"), payload.get("engine", "5.8"),
                    bool(payload.get("force")))
                self.server.project = project
                self._ok(project.summary())
            elif path == "/api/adopt":
                project = Project.adopt(Path(payload.get("path", "")))
                self.server.project = project
                self._ok(project.summary())
            elif path == "/api/save":
                project = self._project()
                result = project.save_artifact(
                    payload.get("path", ""), payload.get("content", ""),
                    payload.get("expected_hash"), payload.get("note", ""))
                self._ok(result)
            elif path == "/api/restore":
                project = self._project()
                self._ok(project.restore_version(payload.get("path", ""),
                                                 payload.get("version", "")))
            elif path == "/api/gate":
                project = self._project()
                self._ok(project.run_gate(payload.get("stage", "")))
            elif path == "/api/freeze":
                project = self._project()
                self._ok(project.freeze(payload.get("stage", "")))
            elif path == "/api/next":
                project = self._project()
                self._ok(project.next_stage_action(payload.get("stage", "")))
            elif path == "/api/reject":
                project = self._project()
                self._ok(project.reject(payload.get("stage", ""), payload.get("reason", "")))
            elif path == "/api/submit":
                project = self._project()
                self._ok(project.submit(payload.get("stage", ""), payload.get("title", ""),
                                        payload.get("note", ""), payload.get("evidence", [])))
            elif path == "/api/submission/resolve":
                project = self._project()
                self._ok(project.resolve_submission(
                    payload.get("id", ""), bool(payload.get("accepted")),
                    payload.get("reason", "")))
            else:
                self._json(404, {"ok": False, "error": "未知接口：%s" % path})
        except ConsoleError as exc:
            self._fail(exc)
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)


def list_fs(raw: str) -> dict:
    if not raw:
        drives = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            path = Path(letter + ":\\")
            if path.exists():
                drives.append({"name": letter + ":", "path": str(path)})
        return {"path": "", "parent": None, "dirs": drives, "drives": drives}
    path = Path(raw).expanduser()
    try:
        path = path.resolve()
    except OSError:
        raise ConsoleError("路径无法解析：%s" % raw, 400)
    if not path.is_dir():
        raise ConsoleError("不是目录：%s" % path, 400)
    children = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and not child.name.startswith("."):
                children.append({"name": child.name, "path": str(child)})
    except OSError as exc:
        raise ConsoleError("无法读取目录：%s" % exc, 400)
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "dirs": children}


def serve(project_path=None, host="127.0.0.1", port=8765, open_browser=True):
    project = None
    if project_path:
        project = Project(Path(project_path))
    elif (Path.cwd() / "gamecheck.json").is_file():
        try:
            project = Project.adopt(Path.cwd())
        except ConsoleError:
            project = None
    server = None
    chosen = None
    for candidate in range(port, port + 20):
        try:
            server = ConsoleServer((host, candidate), project)
            chosen = candidate
            break
        except OSError:
            continue
    if server is None:
        raise ConsoleError("端口 %d-%d 都被占用" % (port, port + 19), 500)
    url = "http://%s:%d/" % (host, chosen)
    print("=" * 62)
    print("  ue5-solo-game 制作控制台 v%s" % CONSOLE_VERSION)
    print("  项目：%s" % (project.root if project else "尚未创建（进入新建向导）"))
    print("  地址：%s" % url)
    print("  退出：Ctrl+C")
    print("=" * 62)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


def cmd_init(args):
    project = Project.create(Path(args.project), args.name, args.idea,
                             args.platform, args.scale, args.engine, args.force)
    print("项目已创建：%s" % project.root)
    print("控制台启动：python scripts/gameconsole.py serve --project %s" % project.root)
    return 0


def cmd_adopt(args):
    project = Project.adopt(Path(args.project))
    print("项目已接管：%s" % project.root)
    return 0


def cmd_status(args):
    project = Project(Path(args.project))
    data = project.summary()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("%s · 当前阶段 %s" % (data["project"].get("name"), data["current_stage"]))
        for stage in data["stages"]:
            print("  %s %-10s %-8s gate=%s" % (
                stage["id"], stage["name"], stage["status"],
                stage["gate_status"] or "-"))
    return 0


def cmd_gate(args):
    project = Project(Path(args.project))
    gate = project.run_gate(args.stage)
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0 if gate["status"] == "pass" else 1


def cmd_freeze(args):
    project = Project(Path(args.project))
    result = project.freeze(args.stage)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_next(args):
    project = Project(Path(args.project))
    print(json.dumps(project.next_stage_action(args.stage), ensure_ascii=False, indent=2))
    return 0


def cmd_submit(args):
    project = Project(Path(args.project))
    sub = project.submit(args.stage, args.title, args.note or "", args.evidence or [])
    print(json.dumps(sub, ensure_ascii=False, indent=2))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gameconsole.py",
        description="ue5-solo-game 本地制作控制台（零依赖，只监听本机）。")
    parser.add_argument("--version", action="version", version=CONSOLE_VERSION)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("serve", help="启动本地控制台")
    p.add_argument("--project", default=None, help="已有项目路径；不填则进入新建向导")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=lambda a: serve(a.project, a.host, a.port, not a.no_browser))

    p = sub.add_parser("init", help="无界面创建项目")
    p.add_argument("--project", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--idea", default="")
    p.add_argument("--platform", default="Windows PC（Steam Demo），1080p 60 fps")
    p.add_argument("--scale", default="小")
    p.add_argument("--engine", default="5.8")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("adopt", help="接管已有 gamecheck 项目")
    p.add_argument("--project", required=True)
    p.set_defaults(func=cmd_adopt)

    p = sub.add_parser("status", help="打印项目状态")
    p.add_argument("--project", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("gate", help="运行某阶段闸门")
    p.add_argument("--project", required=True)
    p.add_argument("--stage", required=True, choices=STAGE_IDS)
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("freeze", help="冻结当前阶段（需闸门通过）")
    p.add_argument("--project", required=True)
    p.add_argument("--stage", required=True, choices=STAGE_IDS)
    p.set_defaults(func=cmd_freeze)

    p = sub.add_parser("next", help="进入下一阶段")
    p.add_argument("--project", required=True)
    p.add_argument("--stage", required=True, choices=STAGE_IDS)
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("submit", help="提交 agent 交付单")
    p.add_argument("--project", required=True)
    p.add_argument("--stage", required=True, choices=STAGE_IDS)
    p.add_argument("--title", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--evidence", action="append", default=[])
    p.set_defaults(func=cmd_submit)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConsoleError as exc:
        print("错误：%s" % exc, file=sys.stderr)
        if exc.detail:
            print(json.dumps(exc.detail, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 2


if __name__ == "__main__":
    sys.exit(main())
