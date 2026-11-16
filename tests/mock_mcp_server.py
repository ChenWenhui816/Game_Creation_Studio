#!/usr/bin/env python3
"""极简 MCP stdio server，仅用于 gateway 测试。"""
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
    except ValueError:
        continue
    method = req.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "mock", "version": "0.1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "project.get_status", "description": "mock status"},
                            {"name": "python.execute", "description": "unsafe"}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": json.dumps({"ok": True, "name": req.get("params", {}).get("name")})}]}
    else:
        result = {}
    if "id" in req:
        print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
