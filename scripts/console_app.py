#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""桌面入口：本地服务 + pywebview/WebView2 窗口。

开发运行：
    python scripts/console_app.py --project D:\games\my-game

打包后：
    Personal_Game_Studio_UE.exe
    Personal_Game_Studio_UE.exe --project D:\games\my-game

无窗口调试：
    python scripts/console_app.py --serve-only
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import gameconsole
import version


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def local_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    candidates = [
        Path(base) / version.APP_NAME,
        Path(sys.executable).resolve().parent / "appdata" if getattr(sys, "frozen", False) else None,
        Path.home() / ("." + version.APP_NAME),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    raise RuntimeError("没有可写的本地数据目录")


def settings_path() -> Path:
    return local_dir() / "settings.json"


def load_settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    try:
        settings_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def export_skill(root: Path) -> Path:
    if not getattr(sys, "frozen", False):
        return root
    target = local_dir() / "skill" / version.VERSION
    if (target / "SKILL.md").is_file():
        return target
    target.mkdir(parents=True, exist_ok=True)
    names = ["console_web", "templates", "references", "docs", "scripts"]
    for name in names:
        source = root / name
        if source.is_dir():
            shutil.copytree(source, target / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("SKILL.md", "README.md", "AGENTS.md", "CHANGELOG.md", "LICENSE"):
        source = root / name
        if source.is_file():
            shutil.copyfile(source, target / name)
    return target


def acquire_single_instance():
    if os.name != "nt":
        return True
    try:
        import ctypes
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\" + version.APP_NAME)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return None
        return handle
    except Exception:  # noqa: BLE001
        return True


def find_project(explicit, force_new: bool):
    if force_new:
        return None
    if explicit:
        return Path(explicit).expanduser().resolve()
    settings = load_settings()
    last = settings.get("last_project")
    if last and (Path(last) / ".gameconsole" / "state.json").is_file():
        return Path(last)
    return None


def wait_health(url: str, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    return False


def open_window(url: str) -> None:
    try:
        import webview  # type: ignore
    except ImportError:
        show_error("未安装 pywebview，改用系统浏览器打开：\n" + url)
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return
    try:
        window = webview.create_window(
            version.APP_NAME,
            url,
            width=1440,
            height=940,
            min_size=(1100, 700),
            text_select=True,
        )
        webview.start(debug=False, private_mode=False)
    except Exception as exc:  # noqa: BLE001 —— WebView2 缺失时退回浏览器
        show_error("桌面窗口启动失败：%s\n改用系统浏览器：%s" % (exc, url))
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return


def show_error(text: str) -> None:
    try:
        print(text)
    except Exception:  # noqa: BLE001
        pass
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, version.APP_NAME, 0x10)
        except Exception:  # noqa: BLE001
            pass


def main(argv=None) -> int:
    gameconsole._setup_stdout()
    parser = argparse.ArgumentParser(prog=version.APP_NAME,
                                     description="UE5 单机游戏制作控制台（桌面版）")
    parser.add_argument("--version", action="version", version=version.VERSION)
    parser.add_argument("--project", default=None, help="已有项目路径")
    parser.add_argument("--new", action="store_true", help="强制进入新建项目向导")
    parser.add_argument("--port", type=int, default=0, help="端口（默认自动选择）")
    parser.add_argument("--serve-only", action="store_true", help="只启动本地服务，不开窗口")
    parser.add_argument("--no-single", action="store_true", help="跳过单实例检查（调试/多开）")
    parser.add_argument("--check-update", action="store_true", help="检查 GitHub 最新版本")
    args = parser.parse_args(argv)

    if args.check_update:
        print(json.dumps(version.check_latest(), ensure_ascii=False, indent=2))
        return 0

    root = export_skill(bundle_root())
    gameconsole.configure(skill_root=root, web_root=root / "console_web")
    mutex = None if args.no_single else acquire_single_instance()
    if mutex is None and not args.no_single:
        print("控制台已经在运行。")
        return 0

    project_path = find_project(args.project, args.new)
    project = None
    if project_path is not None:
        try:
            project = gameconsole.Project(project_path)
        except gameconsole.ConsoleError:
            project = None
    if project is not None:
        settings = load_settings()
        settings["last_project"] = str(project.root)
        save_settings(settings)

    server = gameconsole.ConsoleServer(("127.0.0.1", args.port), project)
    port = server.server_address[1]
    url = "http://127.0.0.1:%d/" % port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if not wait_health(url):
        server.shutdown()
        print("本地服务启动失败。")
        return 1
    print("%s v%s" % (version.APP_NAME, version.VERSION))
    print("项目：%s" % (project.root if project else "新建项目向导"))
    print("地址：%s" % url)
    if args.serve_only:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        open_window(url)
    server.shutdown()
    server.server_close()
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # noqa: BLE001
        import traceback
        show_error("启动失败：\n" + traceback.format_exc())
        code = 1
    sys.exit(code)
