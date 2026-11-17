#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek Harness bridge: run a handoff prompt through DSH headless.

Uses the installed DeepSeek Harness CLI (Electron run-as-node) and a
headless-account profile so the current DSH account credentials are reused.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROFILE = "studio-headless"
DEFAULT_HOME = Path.home() / ".dsh"


def setup():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def dsh_home() -> Path:
    return Path(os.environ.get("DSH_HOME", DEFAULT_HOME)).expanduser()


def dsh_exe() -> Path:
    explicit = os.environ.get("DSH_EXE")
    if explicit:
        return Path(explicit)
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "DeepSeek Harness" / "DeepSeek Harness.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DeepSeek Harness" / "DeepSeek Harness.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise RuntimeError("找不到 DeepSeek Harness.exe；设置 DSH_EXE")


def dsh_bin() -> Path:
    explicit = os.environ.get("DSH_BIN")
    if explicit:
        return Path(explicit)
    asar = dsh_exe().parent / "resources" / "app.asar"
    path = asar / "dsh" / "node_modules" / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
    if asar.is_file():
        return path
    raise RuntimeError("找不到 DSH CLI bin.js；设置 DSH_BIN")


def ensure_profile() -> None:
    home = dsh_home()
    profiles = home / "profiles"
    target = profiles / PROFILE
    if target.is_dir():
        return
    source = profiles / "headless"
    if not source.is_dir():
        raise RuntimeError("找不到 DSH headless profile：%s" % source)
    shutil.copytree(source, target)
    patch = target / "cordis.patch.yml"
    patch.write_text(
        """# Studio headless: reuse DSH account credentials for one-shot tasks.
- id: credentials
  disabled: false
- id: authorization
  disabled: false
- id: deepseek-account
  disabled: false
- id: agent-default-model
  name: '@deepseek-ai/dsh-agent-default-model'
  config:
    provider: deepseek-account
    model: deepseek-flash
    reasoningEffort: max
""",
        encoding="utf-8",
    )


def build_command(project: Path, session_id: str = "", permission: str = "workspace-write") -> list:
    ensure_profile()
    cmd = [str(dsh_exe()), str(dsh_bin()), "--profile", PROFILE,
           "--permission-mode", permission, "--approval-policy", "never",
           "--add-dir", str(project)]
    if session_id:
        cmd += ["--session-id", session_id]
    cmd.append("-")
    return cmd


def run(prompt: str, project: Path, session_id: str = "", timeout: int = 1800) -> dict:
    project = project.expanduser().resolve()
    cmd = build_command(project, session_id)
    env = dict(os.environ, ELECTRON_RUN_AS_NODE="1")
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(project), input=prompt, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    return {"ok": proc.returncode == 0, "exit": proc.returncode,
            "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-12000:],
            "seconds": round(time.time() - started, 1)}


def main(argv=None):
    setup()
    parser = argparse.ArgumentParser(prog="dsh_bridge")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--project", default=".")
    p.add_argument("--prompt", default=None)
    p.add_argument("--handoff", default=None)
    p.add_argument("--session", default=os.environ.get("DSH_SESSION_ID", ""))
    p.add_argument("--print-command", action="store_true")
    args = parser.parse_args(argv)
    project = Path(args.project)
    prompt = args.prompt
    if args.handoff:
        prompt = Path(args.handoff).read_text(encoding="utf-8")
    if not prompt:
        print("需要 --prompt 或 --handoff")
        return 2
    if args.print_command:
        print(json.dumps(build_command(project, args.session), ensure_ascii=False, indent=2))
        return 0
    result = run(prompt, project, args.session)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
