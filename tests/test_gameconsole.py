#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gameconsole.py 单元测试：项目创建、保存版本、冻结/下一步、HTTP API。"""

import json
import os
import shutil
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import gameconsole  # noqa: E402

TMP_BASE = REPO_ROOT / "tests" / "_tmp" / "console"


def new_case_dir():
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    for index in range(10000):
        candidate = TMP_BASE / ("case-%d-%03d" % (os.getpid(), index))
        if not candidate.exists():
            candidate.mkdir()
            return candidate
    raise RuntimeError("无法创建测试目录")


def valid_brief(name="测试项目"):
    sections = [
        "一句话描述", "三个对标", "核心循环", "世界与角色",
        "规模与范围", "不做清单", "最大风险", "目标体验",
    ]
    lines = ["# 《%s》立项书" % name, "", "| 项目 | 内容 |", "|---|---|",
             "| 项目名 | %s |" % name, "", "## 一句话描述", "",
             "一句话。第二句。第三句。", ""]
    for section in sections[1:]:
        lines += ["## " + section, "", "内容。", ""]
    return "\n".join(lines)


class ConsoleBase(unittest.TestCase):
    def setUp(self):
        self.case = new_case_dir()
        self.root = self.case / "game"
        self.project = gameconsole.Project.create(
            self.root, "测试项目", "地下城病毒爆发，男孩逃向地面。", "Windows PC")

    def tearDown(self):
        shutil.rmtree(str(self.case), ignore_errors=True)


class ProjectTests(ConsoleBase):
    def test_create_layout(self):
        self.assertEqual(self.project.state["current_stage"], "P0")
        self.assertTrue((self.root / "docs" / "00_立项书.md").is_file())
        self.assertTrue((self.root / ".gameconsole" / "state.json").is_file())
        self.assertTrue((self.root / "stages" / "00_立项" / "README.md").is_file())
        for stage in gameconsole.STAGES:
            self.assertTrue((self.root / "stages" / stage["folder"]).is_dir())

    def test_save_creates_version(self):
        info = self.project.artifact_info("docs/00_立项书.md")
        self.assertTrue(info["exists"])
        first = len(info["versions"])
        self.project.save_artifact("docs/00_立项书.md", info["content"] + "\n", info["hash"])
        self.assertGreater(len(self.project.versions("docs/00_立项书.md")), first)
        self.assertGreaterEqual(first, 1)

    def test_conflict_on_external_edit(self):
        info = self.project.artifact_info("docs/00_立项书.md")
        path = self.root / "docs" / "00_立项书.md"
        path.write_text(info["content"] + "\nexternal", encoding="utf-8")
        with self.assertRaises(gameconsole.ConsoleError) as ctx:
            self.project.save_artifact("docs/00_立项书.md", "new", info["hash"])
        self.assertEqual(ctx.exception.status, 409)

    def test_gate_freeze_next(self):
        self.project.save_artifact("docs/00_立项书.md", valid_brief(), None)
        gate = self.project.run_gate("P0")
        self.assertEqual(gate["status"], "pass", gate.get("stdout_tail"))
        frozen = self.project.freeze("P0")
        self.assertTrue((self.root / frozen["snapshot"] / "freeze.json").is_file())
        self.assertEqual(self.project.state["stages"]["P0"]["status"], "frozen")
        with self.assertRaises(gameconsole.ConsoleError) as ctx:
            self.project.save_artifact("docs/00_立项书.md", "x", None)
        self.assertEqual(ctx.exception.status, 423)
        result = self.project.next_stage_action("P0")
        self.assertEqual(result["current_stage"], "P1")

    def test_next_requires_frozen(self):
        with self.assertRaises(gameconsole.ConsoleError) as ctx:
            self.project.next_stage_action("P0")
        self.assertEqual(ctx.exception.status, 409)

    def test_submission_lifecycle(self):
        sub = self.project.submit("P0", "立项初稿", "已附 3 个证据")
        self.assertEqual(self.project.state["stages"]["P0"]["status"], "review")
        resolved = self.project.resolve_submission(sub["id"], False, "缺证据")
        self.assertEqual(resolved["status"], "returned")
        self.assertEqual(self.project.state["stages"]["P0"]["status"], "drafting")

    def test_path_traversal_rejected(self):
        with self.assertRaises(gameconsole.ConsoleError):
            self.project.artifact_info("docs/../gamecheck.json")

    def test_list_fs(self):
        data = gameconsole.list_fs(str(self.root))
        self.assertEqual(data["path"], str(self.root.resolve()))
        self.assertTrue(any(item["name"] == "docs" for item in data["dirs"]))


class HttpTests(ConsoleBase):
    def setUp(self):
        super().setUp()
        self.server = gameconsole.ConsoleServer(("127.0.0.1", 0), self.project)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def request(self, method, path, data=None):
        url = "http://127.0.0.1:%d%s" % (self.port, path)
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def test_state_and_stage(self):
        status, payload = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["project"]["name"], "测试项目")
        status, payload = self.request("GET", "/api/stage?id=P0")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["stage"]["id"], "P0")

    def test_artifact_save(self):
        path = "/api/artifact?path=" + urllib.parse.quote("docs/00_立项书.md")
        status, payload = self.request("GET", path)
        info = payload["data"]
        status, payload = self.request("POST", "/api/save", {
            "path": "docs/00_立项书.md", "content": info["content"] + "\n",
            "expected_hash": info["hash"]})
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["path"], "docs/00_立项书.md")

    def test_static_index(self):
        with urllib.request.urlopen("http://127.0.0.1:%d/" % self.port, timeout=20) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn(b"ue5-solo-game", resp.read())

    def test_wizard_create(self):
        server = gameconsole.ConsoleServer(("127.0.0.1", 0), None)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            target = self.case / "wizard-game"
            body = json.dumps({"name": "向导项目", "idea": "一句话。", "path": str(target)}).encode()
            req = urllib.request.Request("http://127.0.0.1:%d/api/project" % port, data=body,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode())
            self.assertEqual(payload["data"]["project"]["name"], "向导项目")
            self.assertTrue((target / "docs" / "00_立项书.md").is_file())
        finally:
            server.shutdown()
            server.server_close()


    def test_change_order_unlocks_and_applies(self):
        self.project.save_artifact("docs/00_立项书.md", valid_brief(), None)
        self.assertTrue(self.project.run_gate("P0")["status"] == "pass")
        self.project.freeze("P0")
        change = self.project.create_change("P0", "补充双输入", "新增手柄验收")
        self.assertEqual(change["status"], "pending")
        self.project.approve_change(change["id"])
        self.assertEqual(self.project.state["stages"]["P0"]["status"], "change")
        self.assertFalse(self.project.is_locked("docs/00_立项书.md"))
        self.project.save_artifact("docs/00_立项书.md", valid_brief() + "\n\n## 双输入\n\n手柄已验收。\n", None)
        self.project.freeze("P0")
        applied = next(item for item in self.project.state["changes"] if item["id"] == change["id"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(self.project.state["stages"]["P0"]["status"], "frozen")

    def test_evidence_wall(self):
        folder = self.root / "docs" / "evidence"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "shot.png").write_bytes(b"png-data")
        data = self.project.evidence()
        self.assertEqual(len(data["items"]), 1)
        content, ctype = self.project.evidence_file("docs/evidence/shot.png")
        self.assertEqual(content, b"png-data")
        self.assertIn("image/png", ctype)
        with self.assertRaises(gameconsole.ConsoleError):
            self.project.evidence_file("docs/../gamecheck.json")


class V06Tests(ConsoleBase):
    def test_time_tracking(self):
        first = self.project.time_start("P0", "测试")
        self.assertEqual(first["active"]["stage"], "P0")
        stopped = self.project.time_stop("完成")
        self.assertIsNone(stopped["active"])
        self.assertGreaterEqual(len(stopped["entries"]), 1)
        self.assertIn("P0", stopped["per_stage"])

    def test_stage_diff_and_insight(self):
        self.project.save_artifact("docs/00_立项书.md", valid_brief() + "\n\n## 玩法变化\n\n新增双输入与关卡。\n", None)
        diff = self.project.stage_diff("P0")
        self.assertGreaterEqual(diff["changed"], 1)
        insight = self.project.stage_insight("P0")
        self.assertTrue(any(item["stage"] == "P2" for item in insight["suggestions"]), insight)

    def test_change_diff(self):
        self.project.save_artifact("docs/00_立项书.md", valid_brief(), None)
        self.project.freeze("P0")
        change = self.project.create_change("P0", "玩法调整", "新增关卡", ["docs/00_立项书.md"])
        self.project.approve_change(change["id"])
        self.project.save_artifact("docs/00_立项书.md", valid_brief() + "\n\n## 新章节\n\n内容。\n", None)
        diff = self.project.diff_change(change["id"])
        self.assertGreaterEqual(diff["changed"], 1)
        self.assertIn("+## 新章节", diff["docs"][0]["diff"])

    def test_evidence_upload(self):
        result = self.project.save_evidence("test.txt", "aGVsbG8=", "P0")
        self.assertEqual(result["name"], "test.txt")
        items = self.project.evidence()["items"]
        self.assertTrue(any(item["name"] == "test.txt" for item in items))
        data, _ = self.project.evidence_file("docs/evidence/test.txt")
        self.assertEqual(data, b"hello")


if __name__ == "__main__":
    unittest.main()
