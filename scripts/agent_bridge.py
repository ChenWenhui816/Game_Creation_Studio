#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""监听工作室交接包，调用外部 agent CLI。

示例：
  python scripts/agent_bridge.py watch --project D:\games\my-game ^
    --command "claude -p @HANDOFF_FILE@"

命令里的 @HANDOFF_FILE@ 会替换成交接包路径；没有占位符时追加路径。
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path


def setup():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def handoff_files(project: Path):
    folder = project / ".gameconsole" / "handoff"
    return sorted(folder.glob("*.md"), key=lambda p: p.stat().st_mtime) if folder.is_dir() else []


def run_once(project: Path, command: str, processed_path: Path, log_path: Path):
    processed = set(load_json(processed_path, {"files": []}).get("files", []))
    for path in handoff_files(project):
        if path.name in processed:
            continue
        parts = shlex.split(command)
        parts = [item.replace("@HANDOFF_FILE@", str(path)).replace("{file}", str(path)) for item in parts]
        if not any(str(path) in item for item in parts):
            parts.append(str(path))
        env = dict(os.environ, STUDIO_PROJECT=str(project), STUDIO_HANDOFF_FILE=str(path))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write("\n=== %s ===\n%s\n" % (path.name, command))
            log.flush()
            try:
                proc = subprocess.run(parts, cwd=str(project), env=env, stdout=log, stderr=log, timeout=3600)
                log.write("\n[exit %s]\n" % proc.returncode)
            except Exception as exc:  # noqa: BLE001
                log.write("\n[error] %s\n" % exc)
        processed.add(path.name)
        save_json(processed_path, {"files": sorted(processed)})
        print("dispatched", path)
        return True
    return False


def main(argv=None):
    setup()
    parser = argparse.ArgumentParser(prog="agent_bridge", description="工作室交接包 → agent CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("watch")
    p.add_argument("--project", default=".")
    p.add_argument("--command", required=True, help="外部 agent 命令；用 @HANDOFF_FILE@ 传交接包路径")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    processed = project / ".gameconsole" / "handoff" / ".processed.json"
    log = project / ".gameconsole" / "agent-bridge.log"
    print("watching", project / ".gameconsole" / "handoff")
    while True:
        run_once(project, args.command, processed, log)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
