#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/ue_import_assets.py 的单元测试。

约定：
- 全部用 sys.executable 调 CLI，贴近真实用法；fixture 现场生成，不读仓库模板。
- 不需要 UE：所有用例只跑 --dry-run；真导入需要 UE 编辑器，放手工验收。
- 临时目录落在仓库 tmp/ue_import（已 gitignore），跑完由 tearDownModule 删除；
  不用 tests/_tmp：其他测试模块的 tearDownModule 会清空 tests/_tmp，并行跑时会误删。
- 可在 Windows / Linux 直接跑：python -m unittest tests.test_ue_import_assets -v
"""

import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

# 让 unittest 的中文输出按 UTF-8 写，Windows 控制台/CI 都不乱码。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "ue_import_assets.py"
# 用仓库根 tmp/（已 gitignore）：tests/_tmp 会被其他测试模块整体清空。
# 目录带 PID：多个进程同时跑测试时，各自只清自己的目录，互不误删。
TMP_BASE = Path(os.environ.get("UE_IMPORT_TEST_TMP")
                or (REPO_ROOT / "tmp" / ("ue_import_tests-%d" % os.getpid())))

# 测试自己写一份表头，不 import 被测脚本的常量：脚本改坏表头时测试必须红。
HEADER = [
    "id", "type", "name", "usage", "source", "file", "faces", "textures",
    "materials", "animations", "lod", "collision", "license", "owner", "status", "note",
]
DEFAULT_STATUS = "已入库"


def new_case_dir() -> Path:
    """在 TMP_BASE 下建唯一目录。

    不用 tempfile.mkdtemp：它在 Windows 沙箱下用 0o700 建目录，再建子目录会 WinError 5。
    """
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    prefix = "case-%d-" % os.getpid()
    for index in range(10000):
        candidate = TMP_BASE / (prefix + "%03d" % index)
        if candidate.exists():
            continue
        candidate.mkdir()
        return candidate
    raise RuntimeError("无法在 %s 下创建测试目录" % TMP_BASE)


def run(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(arg) for arg in args],
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def run_json(args, cwd=None):
    proc = run(args, cwd)
    try:
        return proc, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc, None


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_manifest(root: Path, rows, header=None, rel="docs/05_资产清单.csv") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header if header is not None else HEADER)
        for row in rows:
            writer.writerow(row)
    return path


def make_row(row_id, row_type="char", file=None, status=DEFAULT_STATUS, note=""):
    """生成一行 16 列的资产清单，默认 file 落在 art/Export/<id>/<id>.fbx。"""
    file_value = file if file is not None else ("art/Export/%s/%s.fbx" % (row_id, row_id))
    return [
        row_id, row_type, "名称", "用途", "来源", file_value,
        "100", "512x512", "1", "0", "1", "UCX", "商业可用", "你", status, note,
    ]


def create_assets(root: Path, rows) -> None:
    for row in rows:
        file_value = row[HEADER.index("file")]
        if not file_value or not file_value.lower().endswith((".fbx", ".glb")):
            continue
        path = root / file_value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"dummy")


def valid_rows():
    return [
        make_row(
            "char_hero", "char",
            note="mat=/Game/_Project/Materials/M_hero;collision=complex;lod=3;lod_count=3;scale=1.0",
        ),
        make_row(
            "env_ruins_wall", "env",
            file="art/Export/env_ruins_wall/SM_env_ruins_wall.glb",
            note="collision=complex",
        ),
    ]


def build_case(rows=None, create=True, header=None):
    """建一个项目根：docs/05_资产清单.csv + 资产文件。返回 (case, rows)。"""
    case = new_case_dir()
    rows = valid_rows() if rows is None else rows
    write_manifest(case, rows, header=header)
    if create:
        create_assets(case, rows)
    return case, rows


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.case = new_case_dir()

    def make_project(self, rows=None, create=True, header=None):
        rows = valid_rows() if rows is None else rows
        write_manifest(self.case, rows, header=header)
        if create:
            create_assets(self.case, rows)
        return rows

    def run_dry(self, *extra):
        return run(["--project-root", str(self.case), "--dry-run"] + list(extra), cwd=self.case)

    def run_dry_json(self, *extra):
        return run_json(["--project-root", str(self.case), "--dry-run", "--json"] + list(extra),
                        cwd=self.case)


class DryRunPassTests(TempDirCase):
    def test_all_valid_rows_pass(self):
        self.make_project()
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIsNotNone(data)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["ok"], 2)
        self.assertEqual(data["failed"], 0)
        self.assertTrue(data["dry_run"])
        hero = data["items"][0]
        self.assertEqual(hero["id"], "char_hero")
        self.assertEqual(hero["dest"], "/Game/_Project/Characters/char_hero")
        self.assertEqual(hero["material"], "/Game/_Project/Materials/M_hero")
        self.assertEqual(hero["collision"], "complex")
        self.assertEqual(hero["lods"], 3)
        self.assertEqual(hero["scale"], 1.0)
        self.assertEqual(hero["result"], "validated")
        env = data["items"][1]
        self.assertEqual(env["dest"], "/Game/_Project/Environment/env_ruins_wall")

    def test_default_note_values(self):
        self.make_project([make_row("prop_crate")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        item = data["items"][0]
        self.assertEqual(item["material"], "")
        self.assertEqual(item["collision"], "complex")
        self.assertEqual(item["lods"], 1)
        self.assertEqual(item["scale"], 1.0)
        self.assertEqual(item["result"], "validated")

    def test_text_output_marks_ok(self):
        self.make_project([make_row("prop_crate")])
        proc = self.run_dry()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[OK] prop_crate", proc.stdout)
        self.assertIn("dry-run", proc.stdout)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)

    def test_glb_extension_supported(self):
        self.make_project([make_row("env_pillar", "env", file="art/Export/env_pillar/pillar.GLB")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["result"], "validated")

    def test_unsupported_extension_ignored(self):
        rows = [
            make_row("prop_crate", "prop"),
            make_row("fx_spark", "fx", file="art/Export/fx_spark/spark.png"),
        ]
        self.make_project(rows)
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["id"], "prop_crate")

    def test_unknown_note_key_warns_but_passes(self):
        self.make_project([make_row("prop_crate", note="foo=bar;scale=2")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        item = data["items"][0]
        self.assertEqual(item["result"], "validated")
        self.assertTrue(any("未知 note 键" in text for text in item["warnings"]), item["warnings"])
        self.assertEqual(item["scale"], 2.0)

    def test_prose_note_ignored(self):
        note = "贴图 3 张；验收单 docs/08_验收单/char_hero.md；粗糙度 0.65-0.75"
        self.make_project([make_row("char_hero", note=note)])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["items"][0]["warnings"], [])

    def test_custom_content_dir(self):
        self.make_project([make_row("char_hero")])
        proc, data = self.run_dry_json("--content-dir", "/Game/MyGame")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["content_dir"], "/Game/MyGame")
        self.assertEqual(data["items"][0]["dest"], "/Game/MyGame/Characters/char_hero")

    def test_auto_lod_flag_accepted_in_dry_run(self):
        self.make_project([make_row("char_hero")])
        proc = self.run_dry("--auto-lod")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)



class ValidationFailureTests(TempDirCase):
    def test_missing_file_fails(self):
        self.make_project([make_row("prop_crate")], create=False)
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(data["failed"], 1)
        item = data["items"][0]
        self.assertEqual(item["result"], "failed")
        self.assertTrue(any("file 不存在" in text for text in item["errors"]), item["errors"])
        self.assertIn("[FAIL]", self.run_dry().stdout)

    def test_bad_header_fails(self):
        self.make_project([], create=False, header=HEADER[:-1])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(data["failed"], 1)
        self.assertTrue(any("表头" in text for text in data["errors"]), data["errors"])

    def test_bad_mat_fails(self):
        self.make_project([make_row("prop_crate", note="mat=Materials/M_crate")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("mat 必须以 /Game/ 开头" in text
                            for text in data["items"][0]["errors"]))

    def test_bad_collision_fails(self):
        self.make_project([make_row("prop_crate", note="collision=box")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("collision 只接受" in text
                            for text in data["items"][0]["errors"]))

    def test_bad_lod_fails(self):
        self.make_project([make_row("prop_crate", note="lod=5")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("lod 必须是" in text for text in data["items"][0]["errors"]))

    def test_bad_lod_count_fails(self):
        self.make_project([make_row("prop_crate", note="lod_count=0")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("lod_count 必须是" in text for text in data["items"][0]["errors"]))

    def test_bad_scale_fails(self):
        self.make_project([make_row("prop_crate", note="scale=0")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("scale 必须是" in text for text in data["items"][0]["errors"]))

    def test_duplicate_id_fails(self):
        rows = [
            make_row("char_hero"),
            make_row("char_hero", file="art/Export/char_hero/alt.fbx"),
        ]
        self.make_project(rows)
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(data["ok"], 1)
        self.assertEqual(data["failed"], 1)
        self.assertTrue(any("id 重复" in text for text in data["items"][1]["errors"]))

    def test_duplicate_file_fails(self):
        rows = [
            make_row("char_hero", file="art/Export/shared/mesh.fbx"),
            make_row("env_wall", "env", file="art/Export/shared/mesh.fbx"),
        ]
        self.make_project(rows)
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("file 重复" in text for text in data["items"][1]["errors"]))

    def test_path_traversal_fails(self):
        outside_name = self.case.name + "-outside.fbx"
        row = make_row("prop_crate", "prop", file="../" + outside_name)
        self.make_project([row])
        self.assertTrue((TMP_BASE / outside_name).is_file(), "fixture 没建到 project-root 外")
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("禁止 .. 穿越" in text for text in data["items"][0]["errors"]))

    def test_unknown_type_fails(self):
        self.make_project([make_row("weapon_sword", "weapon")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("未知 type" in text for text in data["items"][0]["errors"]))

    def test_illegal_id_fails(self):
        self.make_project([make_row("char hero")])
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(any("id 只能含" in text for text in data["items"][0]["errors"]))


class FilterTests(TempDirCase):
    def test_only_keeps_selected_id(self):
        self.make_project()
        proc, data = self.run_dry_json("--only", "char_hero")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["ok"], 1)
        self.assertEqual(data["skipped"], 1)
        self.assertEqual([item["id"] for item in data["items"]], ["char_hero", "env_ruins_wall"])
        skipped = data["items"][1]
        self.assertEqual(skipped["result"], "skipped")
        self.assertTrue(any("不在 --only" in text for text in skipped["warnings"]))

    def test_only_unknown_id_warns(self):
        self.make_project()
        proc, data = self.run_dry_json("--only", "ghost_id")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["ok"], 0)
        self.assertEqual(data["skipped"], 2)
        self.assertTrue(any("--only" in text for text in data["warnings"]), data["warnings"])

    def test_include_status_default_skips_not_ready(self):
        rows = [
            make_row("char_hero", status="已通过"),
            make_row("prop_crate", "prop", status="待验收"),
        ]
        self.make_project(rows)
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["ok"], 1)
        self.assertEqual(data["skipped"], 1)
        self.assertEqual(data["items"][1]["result"], "skipped")

        proc, data = self.run_dry_json("--include-status", "已通过,待验收")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["ok"], 2)
        self.assertEqual(data["skipped"], 0)

    def test_include_status_unknown_is_usage_error(self):
        self.make_project()
        proc = self.run_dry("--include-status", "已入库,瞎写")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("未知状态", proc.stdout + proc.stderr)

    def test_empty_only_is_usage_error(self):
        self.make_project()
        proc = self.run_dry("--only", "")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_bad_content_dir_is_usage_error(self):
        self.make_project()
        proc = self.run_dry("--content-dir", "Game/Project")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("--content-dir", proc.stdout + proc.stderr)


class OutputTests(TempDirCase):
    def test_json_report_is_parsable(self):
        self.make_project()
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIsNotNone(data)
        for key in ("root", "manifest", "dry_run", "total", "ok", "skipped", "failed", "items"):
            self.assertIn(key, data)
        expected_item_keys = {
            "id", "file", "dest", "status", "material", "collision", "lods",
            "scale", "result", "errors", "warnings",
        }
        self.assertEqual(set(data["items"][0]), expected_item_keys)

    def test_report_file_written_on_failure(self):
        self.make_project([make_row("prop_crate")], create=False)
        proc = run(["--project-root", str(self.case), "--dry-run",
                    "--report", "out/import-report.json"], cwd=self.case)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report_path = self.case / "out" / "import-report.json"
        self.assertTrue(report_path.is_file())
        data = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(data["failed"], 1)
        self.assertEqual(data["items"][0]["result"], "failed")
        self.assertIn("报告：", proc.stdout)

    def test_help_does_not_require_unreal(self):
        proc = run(["--help"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("--dry-run", proc.stdout)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)

        spec = importlib.util.spec_from_file_location("ue_import_assets_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(hasattr(module, "unreal"), "import 时不应加载 unreal")
        self.assertEqual(module.ASSET_HEADER, HEADER)
        self.assertTrue(callable(module.build_parser))

    @unittest.skipIf(importlib.util.find_spec("unreal") is not None,
                     "当前环境可导入 unreal，跳过无 UE 断言")
    def test_non_dry_run_without_unreal_is_usage_error(self):
        self.make_project()
        proc = run(["--project-root", str(self.case)], cwd=self.case)
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 2, combined)
        self.assertIn("unreal", combined.lower())
        self.assertNotIn("Traceback", combined)

    def test_missing_manifest_fails(self):
        write(self.case / "README.md", "# 空项目\n")
        proc, data = self.run_dry_json()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(data["failed"], 1)
        self.assertTrue(data["manifest"].endswith("05_资产清单.csv"))
        self.assertEqual(data["items"], [])
        text_proc = self.run_dry()
        self.assertEqual(text_proc.returncode, 1, text_proc.stdout + text_proc.stderr)
        self.assertIn("[FAIL]", text_proc.stdout)

    def test_missing_project_root_is_usage_error(self):
        proc = run(["--project-root", str(self.case / "nope"), "--dry-run"])
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("项目根不存在", proc.stdout + proc.stderr)

    def test_usage_error_json_is_parsable(self):
        self.make_project()
        proc, data = run_json(["--project-root", str(self.case), "--dry-run",
                               "--only", "", "--json"], cwd=self.case)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIsNotNone(data)
        self.assertEqual(data["failed"], 1)
        self.assertTrue(any("用法错误" in text for text in data["errors"]))

    def test_version_flag(self):
        proc = run(["--version"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("0.2.0", proc.stdout)


def tearDownModule():
    shutil.rmtree(TMP_BASE, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
