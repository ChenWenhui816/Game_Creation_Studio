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
import subprocess
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
    names = ["console_web", "templates", "references", "docs", "scripts", "mcp", "schemas"]
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
    # 启动时不再自动打开上次项目；用户先在开始页选择。
    if force_new or not explicit:
        return None
    return Path(explicit).expanduser().resolve()


def remember_project(project) -> None:
    settings = load_settings()
    root = str(project.root)
    recent = [item for item in settings.get("recent_projects", []) if item != root]
    recent.insert(0, root)
    settings["last_project"] = root
    settings["recent_projects"] = recent[:8]
    save_settings(settings)


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
    global _WINDOW
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
        _WINDOW = window
        webview.start(debug=False, private_mode=False)
        _WINDOW = None
    except Exception as exc:  # noqa: BLE001 —— WebView2 缺失时退回浏览器
        show_error("桌面窗口启动失败：%s\n改用系统浏览器：%s" % (exc, url))
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return



_WINDOW = None
_SERVER = None


def updates_dir() -> Path:
    path = local_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_app_update() -> dict:
    info = version.check_latest()
    if not info.get("ok"):
        raise RuntimeError("检查更新失败：%s" % info.get("error", "网络不可用"))
    if not info.get("update_available"):
        raise RuntimeError("当前已是最新版本 %s" % version.VERSION)
    asset = info.get("asset")
    if not asset:
        raise RuntimeError("最新 Release 没有可下载的 zip")
    target = version.download_update(asset, updates_dir())
    return {"ok": True, "version": info.get("latest"), "zip": target,
            "size": asset.get("size"), "url": info.get("url")}


def _apply_update_script(source: Path, target: Path, exe: Path, pid: int, script: Path) -> None:
    content = (
        "param()\r\n"
        "$ErrorActionPreference = 'Stop'\r\n"
        "Wait-Process -Id %d -Timeout 60 -ErrorAction SilentlyContinue\r\n"
        "Start-Sleep -Milliseconds 800\r\n"
        "Copy-Item -Path (Join-Path '%s' '*') -Destination '%s' -Recurse -Force\r\n"
        "Start-Process -FilePath '%s'\r\n"
    ) % (pid, str(source).replace("'", "''"), str(target).replace("'", "''"),
         str(exe).replace("'", "''"))
    script.write_text(content, encoding="utf-8-sig")


def apply_app_update() -> dict:
    zips = sorted(updates_dir().glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        raise RuntimeError("没有已下载的更新包，请先点“下载并安装”")
    zip_path = zips[0]
    staging = updates_dir() / "staging"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    import zipfile
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(staging)
    source = staging / version.APP_NAME
    if not source.is_dir():
        children = [item for item in staging.iterdir() if item.is_dir()]
        source = children[0] if children else staging
    target = Path(sys.executable).resolve().parent
    exe = target / (version.APP_NAME + ".exe")
    script = updates_dir() / "apply_update.ps1"
    _apply_update_script(source, target, exe, os.getpid(), script)
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                      "-WindowStyle", "Hidden", "-File", str(script)],
                     creationflags=flags, close_fds=True)
    threading.Timer(0.8, _shutdown_for_update).start()
    return {"ok": True, "restarting": True, "version": version.VERSION}


def _shutdown_for_update() -> None:
    global _WINDOW, _SERVER
    try:
        if _WINDOW is not None:
            _WINDOW.destroy()
    except Exception:  # noqa: BLE001
        pass
    try:
        if _SERVER is not None:
            _SERVER.shutdown()
            _SERVER.server_close()
    except Exception:  # noqa: BLE001
        pass
    os._exit(0)




def refresh_desktop_shortcut() -> None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    try:
        desktop = Path.home() / "Desktop"
        link = desktop / (version.APP_NAME + ".lnk")
        if not link.is_file():
            return
        exe = Path(sys.executable).resolve()
        script = (
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
            "$s.TargetPath='%s';$s.WorkingDirectory='%s';$s.IconLocation='%s,0';$s.Save()"
        ) % (str(link).replace("'", "''"), str(exe).replace("'", "''"),
             str(exe.parent).replace("'", "''"), str(exe).replace("'", "''"))
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-Command", script], capture_output=True, timeout=15,
                       creationflags=0x08000000)
    except Exception:  # noqa: BLE001
        pass

def start_agent_bridge(project) -> None:
    if project is None:
        return
    config_path = project.root / ".gameconsole" / "agent.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    command = (config.get("command") or "").strip()
    if not command:
        return
    try:
        import agent_bridge
    except ImportError:
        return
    processed = project.root / ".gameconsole" / "handoff" / ".processed.json"
    log = project.root / ".gameconsole" / "agent-bridge.log"

    def loop():
        while True:
            try:
                agent_bridge.run_once(project.root, command, processed, log)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)

    threading.Thread(target=loop, daemon=True).start()
    print("Agent bridge: watching", project.root / ".gameconsole" / "handoff")

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
        remember_project(project)

    global _SERVER
    server = gameconsole.ConsoleServer(("127.0.0.1", args.port), project)
    server.on_project_open = remember_project
    settings = load_settings()
    recent = list(settings.get("recent_projects", []))
    last = settings.get("last_project")
    if last and last not in recent and (Path(last) / ".gameconsole" / "state.json").is_file():
        recent.insert(0, last)
    server.recent_projects = recent[:8]
    _SERVER = server
    server.update_download = download_app_update
    server.update_apply = apply_app_update
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
    start_agent_bridge(project)
    refresh_desktop_shortcut()
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
