#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""studio CLI 与 MCP Gateway POC 测试。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(*args, cwd=ROOT):
    return subprocess.run([PY] + list(args), cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60)


class StudioTests(unittest.TestCase):
    def test_pipelines(self):
        result = run(str(ROOT / "scripts" / "studio.py"), "pipelines")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for token in ("00_立项", "02_剧本", "07_上线与发行"):
            self.assertIn(token, result.stdout)

    def test_explain(self):
        result = run(str(ROOT / "scripts" / "studio.py"), "explain", "02")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("剧本", result.stdout)

    def test_asset_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "game"
            (project / "assets").mkdir(parents=True)
            (project / "assets" / "hero.fbx").write_bytes(b"fbx")
            result = run(str(ROOT / "scripts" / "asset_registry.py"), "scan", "--project", str(project))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((project / ".gameconsole" / "assets.json").is_file())
            result = run(str(ROOT / "scripts" / "asset_registry.py"), "validate", "--project", str(project))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class GatewayTests(unittest.TestCase):
    def test_tools_and_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock = Path(tmp) / "mock_mcp.py"
            mock.write_text(Path(ROOT / "tests" / "mock_mcp_server.py").read_text(encoding="utf-8"), encoding="utf-8")
            config = Path(tmp) / "servers.json"
            config.write_text(json.dumps({"servers": {"mock": {
                "transport": "stdio", "command": [PY, str(mock)], "scopes": ["read"]
            }}}), encoding="utf-8")
            result = run(str(ROOT / "scripts" / "mcp_gateway.py"), "--config", str(config), "tools", "mock")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("project.get_status", result.stdout)
            result = run(str(ROOT / "scripts" / "mcp_gateway.py"), "--config", str(config),
                         "call", "mock", "project.get_status", "--args", "{}")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ok", result.stdout)
            result = run(str(ROOT / "scripts" / "mcp_gateway.py"), "--config", str(config),
                         "call", "mock", "python.execute", "--args", "{}", "--yes")
            self.assertEqual(result.returncode, 2)

    def test_http_tools_and_call(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                if "id" not in req:
                    self.send_response(202)
                    self.end_headers()
                    return
                method = req.get("method")
                if method == "initialize":
                    result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                              "serverInfo": {"name": "http-mock", "version": "0.1"}}
                elif method == "tools/list":
                    result = {"tools": [{"name": "project.get_status"}]}
                elif method == "tools/call":
                    result = {"content": [{"type": "text", "text": "http-ok"}]}
                else:
                    result = {}
                body = json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp) / "servers.json"
                config.write_text(json.dumps({"servers": {"httpmock": {
                    "transport": "http",
                    "url": "http://127.0.0.1:%d/mcp" % server.server_address[1],
                }}}), encoding="utf-8")
                result = run(str(ROOT / "scripts" / "mcp_gateway.py"), "--config", str(config),
                             "tools", "httpmock")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("project.get_status", result.stdout)
                result = run(str(ROOT / "scripts" / "mcp_gateway.py"), "--config", str(config),
                             "call", "httpmock", "project.get_status", "--args", "{}")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("http-ok", result.stdout)
        finally:
            server.shutdown()
            server.server_close()
