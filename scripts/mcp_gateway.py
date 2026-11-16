#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Studio MCP Gateway（POC）：配置、发现、调用、权限与审计。

只依赖 Python 标准库。支持 stdio 与 Streamable HTTP MCP（POC）。
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import version

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "mcp" / "servers.example.json"
PERMISSIONS = ROOT / "mcp" / "permissions.json"


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def config_path(project=None, explicit=None):
    if explicit:
        return Path(explicit)
    if project:
        candidate = Path(project).expanduser() / "mcp" / "servers.json"
        if candidate.is_file():
            return candidate
    return DEFAULT_CONFIG


class MCPError(Exception):
    pass


class StdioMCP:
    def __init__(self, command, env=None, timeout=20.0):
        self.timeout = timeout
        self.proc = subprocess.Popen(
            [str(x) for x in command],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            env=dict(os.environ, **(env or {})),
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        self.lines = queue.Queue()
        self.stderr = []
        self._id = 0
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            line = line.strip()
            if line:
                self.lines.put(line)
        self.lines.put(None)

    def _read_err(self):
        for line in self.proc.stderr:
            self.stderr.append(line.rstrip())

    def _send(self, payload):
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params=None):
        self._id += 1
        req_id = self._id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                line = self.lines.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if line is None:
                raise MCPError("MCP server 已退出：" + " | ".join(self.stderr[-5:]))
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if data.get("id") == req_id:
                if "error" in data:
                    raise MCPError(str(data["error"]))
                return data.get("result", {})
        raise MCPError("MCP 请求超时：%s" % method)

    def initialize(self):
        result = self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "studio-mcp-gateway", "version": version.VERSION},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return result

    def tools(self):
        return self.request("tools/list", {}).get("tools", [])

    def call(self, name, args):
        return self.request("tools/call", {"name": name, "arguments": args or {}})

    def close(self):
        try:
            self.proc.terminate()
        except OSError:
            pass



class HttpMCP:
    """最小 Streamable HTTP MCP 客户端：POST JSON-RPC，兼容 application/json 与 text/event-stream。"""

    def __init__(self, url, headers=None, timeout=30.0):
        self.url = url
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.session_id = None
        self._id = 0

    def _post(self, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = dict(self.headers)
        headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "studio-mcp-gateway/" + version.VERSION,
        })
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            sid = response.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            body = response.read().decode("utf-8", "replace")
            ctype = (response.headers.get("Content-Type") or "").lower()
        if not body:
            return None
        if "text/event-stream" in ctype:
            events = []
            for line in body.splitlines():
                if line.startswith("data:"):
                    try:
                        events.append(json.loads(line[5:].strip()))
                    except ValueError:
                        continue
            return events[-1] if events else None
        try:
            return json.loads(body)
        except ValueError as exc:
            raise MCPError("HTTP MCP 返回不是 JSON：" + body[:200]) from exc

    def request(self, method, params=None):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        data = self._post(payload)
        if not data:
            raise MCPError("HTTP MCP 无响应：%s" % method)
        if data.get("id") != self._id:
            raise MCPError("HTTP MCP 响应 id 不匹配：%s" % method)
        if "error" in data:
            raise MCPError(str(data["error"]))
        return data.get("result", {})

    def initialize(self):
        result = self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "studio-mcp-gateway", "version": version.VERSION},
        })
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        except Exception:  # noqa: BLE001
            pass
        return result

    def tools(self):
        return self.request("tools/list", {}).get("tools", [])

    def call(self, name, args):
        return self.request("tools/call", {"name": name, "arguments": args or {}})

    def close(self):
        return None


def _server_command(server):
    command = server.get("command") or []
    if not command:
        raise MCPError("stdio server 缺少 command")
    exe = shutil.which(str(command[0]))
    if not exe:
        raise MCPError("找不到命令：%s" % command[0])
    return [exe] + [str(x) for x in command[1:]]


def _permission(tool, perms, yes):
    if tool in (perms.get("deny_tools") or []):
        return "deny"
    if tool in (perms.get("approval_required") or []) and not yes:
        return "approval"
    return "ok"


def audit(project, event):
    folder = Path(project).expanduser() / ".gameconsole" if project else ROOT / "mcp"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "mcp-audit.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def cmd_doctor(project, explicit):
    path = config_path(project, explicit)
    data = load_json(path)
    print("MCP Gateway / Doctor")
    print("config:", path)
    if not data or not isinstance(data.get("servers"), dict):
        print("[FAIL] 配置不存在或缺少 servers")
        return 1
    failed = False
    for name, server in data["servers"].items():
        transport = server.get("transport", "stdio")
        if transport == "stdio":
            try:
                command = _server_command(server)
                print("  [OK] %-14s stdio %s" % (name, command[0]))
            except MCPError as exc:
                failed = True
                print("  [!!] %-14s %s" % (name, exc))
        else:
            url = server.get("url", "")
            print("  [--] %-14s %s %s（HTTP/POST；需要 session/headers 时在配置里补）" % (name, transport, url))
    perms = load_json(PERMISSIONS, {})
    print("  [%s] permissions: deny=%d approval=%d" % (
        "OK" if perms else "!!", len(perms.get("deny_tools") or []), len(perms.get("approval_required") or [])))
    return 1 if failed else 0


def cmd_list(project, explicit):
    path = config_path(project, explicit)
    data = load_json(path, {})
    for name, server in (data.get("servers") or {}).items():
        print("%-14s %-8s scopes=%s  %s" % (
            name, server.get("transport", "stdio"), ",".join(server.get("scopes", [])),
            server.get("note", "")))
    return 0


def _connect(server):
    if server.get("transport", "stdio") == "http":
        client = HttpMCP(server.get("url", ""), server.get("headers"), float(server.get("timeout", 30)))
        client.initialize()
        return client
    client = StdioMCP(_server_command(server), server.get("env"))
    client.initialize()
    return client


def cmd_tools(project, explicit, name):
    data = load_json(config_path(project, explicit), {})
    server = (data.get("servers") or {}).get(name)
    if not server:
        print("未知 MCP server：%s" % name)
        return 2
    client = _connect(server)
    try:
        tools = client.tools()
        print("tools:", len(tools))
        for tool in tools:
            print("  %-40s %s" % (tool.get("name", ""), (tool.get("description") or "")[:100]))
    finally:
        client.close()
    return 0


def cmd_call(project, explicit, name, tool, args_json, yes):
    data = load_json(config_path(project, explicit), {})
    server = (data.get("servers") or {}).get(name)
    if not server:
        print("未知 MCP server：%s" % name)
        return 2
    perms = load_json(PERMISSIONS, {})
    decision = _permission(tool, perms, yes)
    if decision == "deny":
        print("权限拒绝 / denied:", tool)
        return 2
    if decision == "approval":
        print("该工具需要人工审批 / approval required：加 --yes 再执行")
        return 2
    try:
        args = json.loads(args_json or "{}")
    except ValueError:
        print("--args 不是合法 JSON")
        return 2
    client = _connect(server)
    try:
        result = client.call(tool, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        audit(project, {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "server": name,
                        "tool": tool, "args": args, "result": result})
    finally:
        client.close()
    return 0


def main(argv=None):
    gameconsole_setup()
    parser = argparse.ArgumentParser(prog="mcp_gateway", description="Studio MCP Gateway（POC）")
    parser.add_argument("--version", action="version", version=version.VERSION)
    parser.add_argument("--project", default=None)
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("list")
    p_tools = sub.add_parser("tools")
    p_tools.add_argument("server")
    p_call = sub.add_parser("call")
    p_call.add_argument("server")
    p_call.add_argument("tool")
    p_call.add_argument("--args", default="{}")
    p_call.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        return cmd_doctor(args.project, args.config)
    if args.cmd == "list":
        return cmd_list(args.project, args.config)
    if args.cmd == "tools":
        return cmd_tools(args.project, args.config, args.server)
    if args.cmd == "call":
        return cmd_call(args.project, args.config, args.server, args.tool, args.args, args.yes)
    return 2


def gameconsole_setup():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


if __name__ == "__main__":
    sys.exit(main())
