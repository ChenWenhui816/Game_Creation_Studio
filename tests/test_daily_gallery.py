#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daily_gallery.py 的单元测试。

约定：
- 全部用 sys.executable 调 CLI，贴近真实用法；图片是空壳文件，只关心扩展名与 mtime。
- 临时目录默认 tests/_tmp（已 gitignore），环境变量 DAILY_GALLERY_TEST_TMP 可改。
- 可在 Windows / Linux 直接跑：python -m unittest tests.test_daily_gallery -v
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "daily_gallery.py"
# 与 test_gamecheck.py 相同：Windows 文件沙箱下不用 tempfile，落在仓库 tests/_tmp。
TMP_BASE = Path(os.environ.get("DAILY_GALLERY_TEST_TMP") or (REPO_ROOT / "tests" / "_tmp" / "gallery"))
PNG_BYTES = b"\x89PNG\r\n\x1a\n"


def new_case_dir():
    """在 TMP_BASE 下建唯一目录；用默认权限 mkdir，避开沙箱 ACL 问题。"""
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    prefix = "gallery-%d-" % os.getpid()
    for index in range(10000):
        candidate = TMP_BASE / (prefix + "%03d" % index)
        if candidate.exists():
            continue
        candidate.mkdir()
        return candidate
    raise RuntimeError("无法在 %s 下创建测试目录" % TMP_BASE)


def timestamp(year, month, day, hour=12, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second).timestamp()


def add_shot(path, when, payload=None):
    """写一张空壳图片并设置 mtime。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload if payload is not None else PNG_BYTES)
    os.utime(str(path), (when, when))
    return path


def run(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(item) for item in args],
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


class DailyGalleryTest(unittest.TestCase):
    def setUp(self):
        self.case = new_case_dir()
        self.src = self.case / "src"
        self.src.mkdir()
        self.out = self.case / "out"

    def tearDown(self):
        shutil.rmtree(str(self.case), ignore_errors=True)

    def generate(self, *extra, cwd=None):
        return run(["--src", self.src, "--out", self.out] + list(extra), cwd=cwd)

    def read_html(self):
        return (self.out / "index.html").read_text(encoding="utf-8")

    def read_md(self):
        return (self.out / "index.md").read_text(encoding="utf-8")

    # ---------- 1. CLI 与空目录 ----------

    def test_help_available(self):
        proc = run(["--help"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for flag in ("--src", "--out", "--title", "--days", "--compare", "--ext", "--json"):
            self.assertIn(flag, proc.stdout)

    def test_empty_dir_returns_1(self):
        proc = self.generate()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("没有找到图片", proc.stderr)
        self.assertFalse((self.out / "index.html").exists())

    # ---------- 2. 分组与排序 ----------

    def test_groups_sorted_and_mtime_ascending(self):
        add_shot(self.src / "2026-03-02" / "b.png", timestamp(2026, 3, 2, 10))
        add_shot(self.src / "2026-03-01" / "c.png", timestamp(2026, 3, 1, 9, 30))
        add_shot(self.src / "2026-03-01" / "a.png", timestamp(2026, 3, 1, 9, 0))
        add_shot(self.src / "loose" / "d.jpg", timestamp(2026, 2, 28, 8))
        proc = self.generate()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.read_html()
        dates = re.findall(r"<h2>(\d{4}-\d{2}-\d{2})</h2>", page)
        self.assertEqual(dates, ["2026-03-02", "2026-03-01", "2026-02-28"])
        self.assertLess(page.index("a.png"), page.index("c.png"))
        self.assertIn("共 2 张", page)
        self.assertIn("## 2026-03-01（2 张）", self.read_md())

    def test_parent_folder_date_overrides_mtime(self):
        add_shot(self.src / "2026-07-15" / "x.png", timestamp(2020, 1, 1))
        proc = self.generate()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.read_html()
        self.assertIn("<h2>2026-07-15</h2>", page)
        self.assertNotIn("<h2>2020-01-01</h2>", page)

    # ---------- 3. --days ----------

    def test_days_relative_to_newest_not_today(self):
        for day in (1, 2, 3):
            add_shot(self.src / ("2026-01-0%d" % day) / "shot.png", timestamp(2026, 1, day))
        add_shot(self.src / "2025-12-20" / "old.png", timestamp(2025, 12, 20))
        proc = self.generate("--days", "2", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["total"], 2)
        self.assertEqual([item["date"] for item in payload["dates"]], ["2026-01-03", "2026-01-02"])
        # 若错误地按“今天”过滤，2026-01 的图会全被砍掉；--days 999 应保留全部。
        proc_all = self.generate("--days", "999", "--json")
        self.assertEqual(json.loads(proc_all.stdout)["total"], 4)

    # ---------- 4. --compare ----------

    def test_compare_block_is_two_columns(self):
        add_shot(self.src / "2026-11-10" / "a.png", timestamp(2026, 11, 10, 9))
        add_shot(self.src / "2026-11-10" / "b.png", timestamp(2026, 11, 10, 10))
        add_shot(self.src / "2026-11-14" / "c.png", timestamp(2026, 11, 14, 9))
        proc = self.generate("--compare", "2026-11-10,2026-11-14")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.read_html()
        self.assertIn('class="compare-grid"', page)
        self.assertIn("对比：2026-11-10 ↔ 2026-11-14", page)
        self.assertIn('class="compare-col"', page)
        self.assertIn("## 对比：2026-11-10 ↔ 2026-11-14", self.read_md())

    def test_compare_missing_date_shows_hint(self):
        add_shot(self.src / "2026-11-10" / "a.png", timestamp(2026, 11, 10, 9))
        proc = self.generate("--compare", "2026-11-10,2026-11-12")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.read_html()
        self.assertIn("该日期没有截图：2026-11-12", page)
        self.assertIn("提示", proc.stderr)
        self.assertIn("该日期没有截图。", self.read_md())

    # ---------- 5. HTML 转义与相对路径 ----------

    def test_title_and_filename_are_escaped(self):
        add_shot(self.src / "2026-06-01" / "a&b.png", timestamp(2026, 6, 1))
        title = '<script>alert("x")</script> & 标题'
        proc = self.generate("--title", title)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.read_html()
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("&amp; 标题", page)
        self.assertIn("a&amp;b.png", page)
        self.assertIn("<title>&lt;script&gt;", page)

    def test_image_links_are_relative(self):
        add_shot(self.src / "2026-05-01" / "a.png", timestamp(2026, 5, 1))
        proc = self.generate()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.read_html()
        self.assertIn('../src/2026-05-01/a.png', page)
        self.assertNotIn(str(self.case), page)
        self.assertIn("(../src/2026-05-01/a.png)", self.read_md())

    # ---------- 6. Markdown 与 JSON ----------

    def test_index_md_has_dates_and_links(self):
        add_shot(self.src / "2026-05-02" / "a.png", timestamp(2026, 5, 2, 9))
        add_shot(self.src / "2026-05-02" / "b.png", timestamp(2026, 5, 2, 10))
        proc = self.generate("--title", "R3 巡览")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        md = self.read_md()
        self.assertTrue(md.startswith("# R3 巡览"))
        self.assertIn("## 2026-05-02（2 张）", md)
        self.assertIn("[a.png](../src/2026-05-02/a.png)", md)

    def test_json_output_is_parseable(self):
        add_shot(self.src / "2026-04-01" / "a.png", timestamp(2026, 4, 1, 9))
        add_shot(self.src / "2026-04-02" / "b.jpg", timestamp(2026, 4, 2, 9))
        proc = self.generate("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.lstrip().startswith("{"))
        self.assertNotIn("已生成巡览", proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["total"], 2)
        self.assertIsNone(payload["days"])
        self.assertEqual([item["date"] for item in payload["dates"]], ["2026-04-02", "2026-04-01"])
        self.assertEqual(payload["dates"][0]["count"], 1)
        self.assertEqual(payload["dates"][1]["files"], ["2026-04-01/a.png"])
        self.assertEqual(payload["src"], str(self.src))
        self.assertEqual(payload["out"], str(self.out))

    # ---------- 7. out 在 src 内 ----------

    def test_out_inside_src_is_not_scanned(self):
        add_shot(self.src / "2026-01-01" / "a.png", timestamp(2026, 1, 1))
        gallery = self.src / "gallery"
        add_shot(gallery / "2026-01-01" / "old.png", timestamp(2026, 1, 1))
        proc = run(["--src", self.src, "--out", gallery, "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["total"], 1)
        self.assertNotIn("old.png", (gallery / "index.html").read_text(encoding="utf-8"))
        # 再跑一次，index.html/index.md 不应被当成图片或导致重复。
        proc_again = run(["--src", self.src, "--out", gallery, "--json"])
        self.assertEqual(proc_again.returncode, 0, proc_again.stderr)
        self.assertEqual(json.loads(proc_again.stdout)["total"], 1)

    # ---------- 8. 扩展名、默认目录、自包含 ----------

    def test_ext_filter(self):
        add_shot(self.src / "2026-02-01" / "a.png", timestamp(2026, 2, 1))
        add_shot(self.src / "2026-02-01" / "b.jpg", timestamp(2026, 2, 1))
        add_shot(self.src / "2026-02-01" / "notes.txt", timestamp(2026, 2, 1))
        proc = self.generate("--ext", "png", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["total"], 1)
        proc_default = self.generate("--json")
        self.assertEqual(json.loads(proc_default.stdout)["total"], 2)

    def test_default_out_is_gallery_in_cwd(self):
        add_shot(self.src / "2026-08-01" / "a.png", timestamp(2026, 8, 1))
        proc = run(["--src", "src"], cwd=self.case)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.case / "gallery" / "index.html").is_file())
        self.assertTrue((self.case / "gallery" / "index.md").is_file())

    def test_html_is_self_contained(self):
        add_shot(self.src / "2026-09-01" / "a.png", timestamp(2026, 9, 1))
        proc = self.generate()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.read_html()
        self.assertIn("<style>", page)
        self.assertIn('name="viewport"', page)
        self.assertNotIn("<script", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn('src="file:', page)

    # ---------- 9. 参数错误 ----------

    def test_invalid_days_and_compare_return_1(self):
        add_shot(self.src / "2026-10-01" / "a.png", timestamp(2026, 10, 1))
        cases = (
            ("--days", "0"),
            ("--days", "abc"),
            ("--compare", "2026-10-01"),
            ("--compare", "2026-13-01,2026-10-01"),
        )
        for extra in cases:
            with self.subTest(extra=extra):
                proc = run(["--src", self.src, "--out", self.out] + list(extra))
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn("错误：", proc.stderr)

    def test_out_equal_src_returns_1(self):
        add_shot(self.src / "2026-10-02" / "a.png", timestamp(2026, 10, 2))
        proc = run(["--src", self.src, "--out", self.src])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--out 不能等于 --src", proc.stderr)


if __name__ == "__main__":
    unittest.main()
