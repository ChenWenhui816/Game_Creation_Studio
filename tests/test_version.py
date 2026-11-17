#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""version.py 单元测试：版本解析与更新比较。"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import version  # noqa: E402


class VersionTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(version.parse_version("v1.2.3"), (1, 2, 3))
        self.assertIsNone(version.parse_version("dev"))

    def test_newer(self):
        self.assertTrue(version.is_newer("0.4.1", "0.4.0"))
        self.assertFalse(version.is_newer("0.4.0", "0.4.0"))
        self.assertFalse(version.is_newer("0.3.9", "0.4.0"))

    def test_repo_name(self):
        self.assertEqual(version.REPO_NAME, "Game_Creation_Studio")


if __name__ == "__main__":
    unittest.main()
