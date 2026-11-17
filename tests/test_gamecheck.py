#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gamecheck.py 的单元测试。

约定：
- 全部用 sys.executable 调 CLI，贴近真实用法；不依赖仓库 templates/（fixture 内联生成）。
- 只有 test_templates_have_required_sections 读仓库模板；模板还没写完时 skip。
- 可在 Windows / Linux 直接跑：python -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "gamecheck.py"
TEMPLATES = REPO_ROOT / "templates"
# 有些沙箱/CI 的 系统临时目录不允许再建子目录；默认落在仓库 tests/_tmp 下，跑完即删。
# 想换位置设环境变量 GAMECHECK_TEST_TMP。
TMP_BASE = Path(os.environ.get("GAMECHECK_TEST_TMP") or (REPO_ROOT / "tests" / "_tmp" / "gamecheck"))


def new_case_dir():
    """在 TMP_BASE 下建唯一目录。

    不用 tempfile.mkdtemp/TemporaryDirectory：它们用 os.mkdir(path, 0o700) 建目录，
    在 Windows 文件沙箱下这种目录 ACL 异常，往里面再建子目录会 WinError 5。
    这里用默认权限 mkdir（0o777），沙箱与 CI 都正常。
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

TABLE = "\n| 项 | 值 |\n|---|---|\n| 示例 | 1 |\n"


def load_module():
    spec = importlib.util.spec_from_file_location("gamecheck_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gamecheck = load_module()
REQ = gamecheck.REQUIRED_SECTIONS
ASSET_HEADER = gamecheck.ASSET_HEADER
NUM_HEADER = gamecheck.NUM_HEADER


def run(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


def run_json(args, cwd=None):
    proc = run(args, cwd)
    try:
        return proc, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc, None


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def md_text(key, missing=None, placeholder=False, extra="",
            conclusion="通过：满足验收标准。", checks=None):
    lines = ["# " + key, ""]
    for section in REQ[key]:
        if section == missing:
            continue
        lines.append("## " + section)
        lines.append("")
        if section == "结论" and key == "08_验收单.md":
            lines.append(conclusion)
        elif section == "验收清单" and key == "04_关卡设计.md" and checks is not None:
            for index in range(checks):
                lines.append("- [x] 验收项 %d：通过" % (index + 1))
        else:
            lines.append("内容。")
        lines.append("")
    if placeholder:
        lines.append("这里是【待填】。")
    if extra:
        lines.append(extra)
    return "\n".join(lines) + "\n"


def make_templates(base):
    mapping = {
        "00_立项书.md": "00_立项书.md",
        "01_游戏设计文档.md": "01_游戏设计文档.md",
        "02_美术圣经.md": "02_美术圣经.md",
        "03_技术方案.md": "03_技术方案.md",
        "04_关卡设计.md": "04_关卡设计.md",
        "07_交付单.md": "07_交付单.md",
        "08_验收单.md": "08_验收单.md",
        "09_变更单.md": "09_变更单.md",
        "10_测试记录.md": "10_测试记录.md",
        "11_周报.md": "11_周报.md",
        "12_Demo上线清单.md": "12_Demo上线清单.md",
        "13_多语言商店素材清单.md": "13_多语言商店素材清单.md",
        "14_剧本圣经.md": "14_剧本圣经.md",
        "15_分镜与镜头表.md": "15_分镜与镜头表.md",
        "16_音乐音频设计.md": "16_音乐音频设计.md",
        "17_视频PV制作单.md": "17_视频PV制作单.md",
    }
    base.mkdir(parents=True, exist_ok=True)
    for filename, key in mapping.items():
        extras = TABLE if key in ("01_游戏设计文档.md", "02_美术圣经.md", "03_技术方案.md") else ""
        write(base / filename, md_text(key, extra=extras, checks=2 if key == "04_关卡设计.md" else None))
    write(base / "05_资产清单.csv", ",".join(ASSET_HEADER) + "\n")
    write(base / "06_数值表.csv", ",".join(NUM_HEADER) + "\n")
    return base


def write_numbers(root, height=2.2, apex=0.4, gravity=27.5, velocity=11.0, missing=()):
    rows = [
        ("move.jump", "move.jump.height", height, "m", "", "GDD", "最高点"),
        ("move.jump", "move.jump.apex_time", apex, "s", "", "GDD", "到顶点"),
        ("move", "move.gravity", gravity, "m/s^2", "2*move.jump.height/move.jump.apex_time^2", "GDD", "重力"),
        ("move.jump", "move.jump.velocity", velocity, "m/s", "2*move.jump.height/move.jump.apex_time", "GDD", "起跳"),
    ]
    lines = [",".join(NUM_HEADER)]
    for row in rows:
        if row[1] in missing:
            continue
        lines.append(",".join(str(item) for item in row))
    write(root / "docs" / "06_数值表.csv", "\n".join(lines) + "\n")


def asset(row_id, row_type, **overrides):
    row = {
        "id": row_id,
        "type": row_type,
        "name": "示例",
        "usage": "角色",
        "source": "Blender",
        "file": "",
        "faces": "0",
        "textures": "2048x2048",
        "materials": "1",
        "animations": "0",
        "lod": "0",
        "collision": "无",
        "license": "自有",
        "owner": "我",
        "status": "已入库",
        "note": "【示例】",
    }
    row.update(overrides)
    return row


def default_asset_rows(env_count=8):
    rows = [
        asset("char_hero", "char", name="主角", usage="角色", file="assets/char_hero.fbx",
              faces="45000", textures="2048x2048", materials="2", animations="6", lod="1", collision="胶囊"),
        asset("enemy_grunt", "enemy", name="杂兵", usage="敌人", file="assets/enemy_grunt.fbx",
              faces="12000", textures="1024x1024", materials="1", animations="3", lod="2", collision="胶囊"),
    ]
    for index in range(1, env_count + 1):
        rows.append(asset("env_rock_%02d" % index, "env", name="岩石%d" % index, usage="环境",
                          file="assets/env_rock_%02d.fbx" % index, faces="3000", textures="2048",
                          materials="1", lod="2", collision="凸包"))
    rows.append(asset("mat_stone", "mat", name="岩石材质", usage="材质", file="assets/mat_stone.png",
                      faces="0", textures="-", materials="1", lod="0"))
    rows.append(asset("prop_crate_01", "prop", name="木箱", usage="道具", file="assets/prop_crate_01.fbx",
                      faces="500", textures="512x512", materials="1", lod="1", status="制作中"))
    return rows


def write_assets(root, rows):
    lines = [",".join(ASSET_HEADER)]
    for row in rows:
        lines.append(",".join(str(row.get(column, "")) for column in ASSET_HEADER))
    write(root / "docs" / "05_资产清单.csv", "\n".join(lines) + "\n")
    for row in rows:
        file_rel = str(row.get("file", "")).strip()
        if file_rel.startswith("assets/") or file_rel.startswith("art/Export/"):
            target = root / file_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")


def build_checklist(filename, checked, unchecked, extra_text=""):
    lines = ["# " + filename, ""]
    if extra_text:
        lines.append(extra_text)
        lines.append("")
    for section in REQ[filename]:
        lines.append("## " + section)
        lines.append("")
    for index in range(checked):
        lines.append("- [x] 已完成事项 %d：构建与认证通过" % (index + 1))
    for index in range(unchecked):
        lines.append("- [ ] 未完成事项 %d：等待商店审核" % (index + 1))
    return "\n".join(lines) + "\n"


def png_bytes(width, height):
    """只写 PNG 签名 + IHDR，足够让 read_png_size 读出尺寸（测试用）。"""
    return (b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13) + b"IHDR"
            + struct.pack(">II", width, height)
            + b"\x08\x06\x00\x00\x00" + b"\x00\x00\x00\x00")


def write_store_assets(root):
    store = root / "store"
    store.mkdir(parents=True, exist_ok=True)
    for name, (width, height) in gamecheck.STORE_CAPSULES.items():
        write(store / name, "")
        (store / name).write_bytes(png_bytes(width, height))
    for lang in ("zh", "en"):
        for index in range(1, 6):
            path = store / ("screenshot_%s_%02d.png" % (lang, index))
            path.write_bytes(png_bytes(1920, 1080))
    write(store / "store_text_zh.md", "一句话卖点。长描述。" + "这是一段可判定的中文商店文案。" * 20)
    write(store / "store_text_en.md", "One-liner. Long description. " + "This is a deterministic English store copy. " * 20)
    write(store / "trailer_zh.srt", "1\n00:00:00,000 --> 00:00:02,000\n玩法画面\n")
    write(store / "trailer_en.srt", "1\n00:00:00,000 --> 00:00:02,000\nGameplay\n")
    (store / "trailer.mp4").write_bytes(b"0" * 110000)


def write_change(root, change_id="CO-001", impact="char_hero", decision="批准", filename=None):
    lines = ["# 变更单 — 测试", ""]
    for section in REQ["09_变更单.md"]:
        lines.append("## " + section)
        lines.append("")
        if section == "影响评估":
            lines.append("| 资产 ID | 变更类型 |")
            lines.append("|---|---|")
            lines.append("| %s | 改规格 |" % impact)
        elif section == "决策":
            lines.append(decision)
        else:
            lines.append("内容。")
        lines.append("")
    path = root / "docs" / "09_变更单" / (filename or (change_id + "_测试.md"))
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, "\n".join(lines) + "\n")
    return path


def build_project(root, asset_rows=None, numbers=None, weeks=4, checked=2, unchecked=0,
                  accepted=True, level_checks=2, blind_test=True,
                  checked13=2, unchecked13=0):
    for name in ("00_立项书.md", "01_游戏设计文档.md", "02_美术圣经.md", "03_技术方案.md"):
        extra = TABLE
        if name in ("01_游戏设计文档.md", "03_技术方案.md"):
            extra = TABLE + "\n键鼠 手柄 输入映射"
        write(root / "docs" / name, md_text(name, extra=extra))
    write_numbers(root, **(numbers or {}))
    write_assets(root, default_asset_rows() if asset_rows is None else asset_rows)
    write(root / "docs" / "04_关卡设计" / "01_第一关.md",
          md_text("04_关卡设计.md", checks=level_checks))
    write(root / "docs" / "07_交付单" / "001_开局.md", md_text("07_交付单.md"))
    write(root / "docs" / "08_验收单" / "char_hero.md",
          md_text("08_验收单.md",
                  conclusion="通过：满足验收标准。" if accepted else "待定：等待复验。"))
    write(root / "docs" / "10_测试记录.md",
          md_text("10_测试记录.md",
                  extra=("盲测：3 人各 20 分钟，卡点 2 处。键鼠全流程通过，手柄全流程通过。" if blind_test else "键鼠 手柄")))
    for index in range(weeks):
        write(root / "docs" / "11_周报" / ("2026-W%02d.md" % (index + 1)), md_text("11_周报.md"))
    write(root / "docs" / "17_视频PV制作单.md",
          md_text("17_视频PV制作单.md", extra=TABLE))
    write(root / "docs" / "12_Demo上线清单.md",
          build_checklist("12_Demo上线清单.md", checked, unchecked))
    write(root / "docs" / "13_多语言商店素材清单.md",
          build_checklist("13_多语言商店素材清单.md", checked13, unchecked13,
                          extra_text="语言矩阵：中文 + English"))
    write_store_assets(root)
    return root


def tearDownModule():
    shutil.rmtree(str(TMP_BASE), ignore_errors=True)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = new_case_dir()
        self.root = self.tmp / "proj"

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)


class InitTests(TempDirCase):
    def test_init_creates_project_skeleton(self):
        templates = make_templates(self.tmp / "templates")
        target = self.tmp / "game"
        proc = run(["init", "--dir", str(target), "--name", "测试项目",
                    "--templates", str(templates)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        expected = [
            "docs/00_立项书.md", "docs/01_游戏设计文档.md", "docs/02_美术圣经.md",
            "docs/03_技术方案.md", "docs/04_关卡设计", "docs/05_资产清单.csv",
            "docs/06_数值表.csv", "docs/07_交付单", "docs/08_验收单", "docs/09_变更单",
            "docs/10_测试记录.md", "docs/11_周报", "docs/12_Demo上线清单.md",
            "docs/13_多语言商店素材清单.md", "store",
            "art/Source", "art/Export", "art/Inbox", "assets", "game", "scripts",
            "gamecheck.json", "AGENTS.md", "scripts/gamecheck.py",
        ]
        for relative in expected:
            self.assertTrue((target / relative).exists(), "缺少 " + relative)
        config = json.loads((target / "gamecheck.json").read_text(encoding="utf-8"))
        for key in ("name", "engine", "scale", "created", "version"):
            self.assertIn(key, config)
        self.assertEqual(config["name"], "测试项目")
        agents_text = (target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("SKILL.md", agents_text)
        self.assertIn("scripts/gamecheck.py", agents_text)
        self.assertTrue((target / "docs" / "07_交付单" / "_模板_交付单.md").is_file())
        self.assertTrue((target / "docs" / "08_验收单" / "_模板_验收单.md").is_file())

    def test_init_refuses_non_empty_directory(self):
        templates = make_templates(self.tmp / "templates")
        target = self.tmp / "game"
        target.mkdir()
        write(target / "keep.txt", "用户文件")
        proc = run(["init", "--dir", str(target), "--name", "x", "--templates", str(templates)])
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("非空", proc.stdout)
        self.assertFalse((target / "docs").exists())

    def test_init_force_overwrites(self):
        templates = make_templates(self.tmp / "templates")
        target = self.tmp / "game"
        self.assertEqual(run(["init", "--dir", str(target), "--name", "x",
                              "--templates", str(templates)]).returncode, 0)
        write(target / "docs" / "00_立项书.md", "手改过的内容")
        proc = run(["init", "--dir", str(target), "--name", "y",
                    "--templates", str(templates), "--force"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("覆盖", proc.stdout)
        self.assertNotIn("手改过的内容", (target / "docs" / "00_立项书.md").read_text(encoding="utf-8"))

    def test_init_missing_templates_fails(self):
        empty = self.tmp / "empty-templates"
        empty.mkdir()
        proc = run(["init", "--dir", str(self.tmp / "game"), "--name", "x",
                    "--templates", str(empty)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("模板缺失", proc.stdout)

    def test_init_missing_name_is_usage_error(self):
        proc = run(["init", "--dir", str(self.tmp / "game")])
        self.assertEqual(proc.returncode, 2)


class DocCheckTests(TempDirCase):
    def test_stage0_minimal_passes(self):
        write(self.root / "docs" / "00_立项书.md", md_text("00_立项书.md"))
        proc = run(["doc", "check", "--stage", "0", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("[PASS]", proc.stdout)

    def test_missing_document_fails(self):
        (self.root / "docs").mkdir(parents=True)
        proc = run(["doc", "check", "--stage", "0", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("缺失", proc.stdout)

    def test_missing_section_fails(self):
        write(self.root / "docs" / "00_立项书.md", md_text("00_立项书.md", missing="核心循环"))
        proc = run(["doc", "check", "--stage", "0", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("核心循环", proc.stdout)
        self.assertIn("缺少章节", proc.stdout)

    def test_placeholder_fails(self):
        write(self.root / "docs" / "00_立项书.md", md_text("00_立项书.md", placeholder=True))
        proc = run(["doc", "check", "--stage", "0", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("占位符", proc.stdout)
        self.assertIn("【待填】", proc.stdout)

    def test_example_marker_not_flagged(self):
        write(self.root / "docs" / "00_立项书.md",
              md_text("00_立项书.md", extra="- 跳跃高度 2.2 m（【示例】……）"))
        proc = run(["doc", "check", "--stage", "0", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("[FAIL]", proc.stdout)

    def test_stage4_requires_four_weeklies(self):
        build_project(self.root, weeks=3)
        proc = run(["doc", "check", "--stage", "4", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("11_周报", proc.stdout)


class NumberTests(TempDirCase):
    def test_dotted_keys_passes(self):
        build_project(self.root)
        proc = run(["numbers", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("move.jump.height", proc.stdout)
        self.assertIn("[PASS]", proc.stdout)

    def test_bare_key_aliases_pass(self):
        build_project(self.root)
        lines = [",".join(NUM_HEADER)]
        for key, value, unit in (("jump_height", "2.2", "m"), ("time_to_apex", "0.4", "s"),
                                 ("gravity", "27.5", "m/s^2"), ("jump_velocity", "11", "m/s")):
            lines.append(",".join(["move", key, value, unit, "", "GDD", "旧数据"]))
        write(self.root / "docs" / "06_数值表.csv", "\n".join(lines) + "\n")
        proc = run(["numbers", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_inconsistent_values_fail(self):
        build_project(self.root)
        write_numbers(self.root, gravity=40.0)
        proc = run(["numbers", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("偏差", proc.stdout)
        self.assertIn("move.gravity", proc.stdout)

    def test_missing_key_fails(self):
        build_project(self.root)
        write_numbers(self.root, missing=("move.jump.velocity",))
        proc = run(["numbers", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("缺少 key", proc.stdout)
        self.assertIn("move.jump.velocity", proc.stdout)


class ManifestTests(TempDirCase):
    def test_manifest_passes(self):
        build_project(self.root)
        proc = run(["manifest", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_missing_file_fails(self):
        build_project(self.root)
        (self.root / "assets" / "char_hero.fbx").unlink()
        proc = run(["manifest", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("不存在", proc.stdout)

    def test_bad_id_fails(self):
        rows = default_asset_rows()
        rows[0]["id"] = "hero"
        build_project(self.root, asset_rows=rows)
        proc = run(["manifest", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("不符合", proc.stdout)

    def test_over_budget_faces_fail(self):
        rows = default_asset_rows()
        rows[0]["faces"] = "90000"
        build_project(self.root, asset_rows=rows)
        proc = run(["manifest", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("预算", proc.stdout)

    def test_bad_texture_fails(self):
        rows = default_asset_rows()
        rows[2]["textures"] = "3000x3000"
        build_project(self.root, asset_rows=rows)
        proc = run(["manifest", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("2 的幂", proc.stdout)

    def test_unregistered_asset_fails(self):
        build_project(self.root)
        (self.root / "assets" / "stray.png").write_bytes(b"")
        proc = run(["manifest", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("未登记", proc.stdout)

    def test_duplicate_id_fails(self):
        rows = default_asset_rows()
        rows.append(dict(rows[0]))
        build_project(self.root, asset_rows=rows)
        proc = run(["manifest", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("重复", proc.stdout)

    def test_bad_header_fails(self):
        build_project(self.root)
        header = [column for column in ASSET_HEADER if column != "note"]
        write(self.root / "docs" / "05_资产清单.csv", ",".join(header) + "\n")
        proc = run(["manifest", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("表头", proc.stdout)


class GateTests(TempDirCase):
    def test_gate_spec_passes(self):
        build_project(self.root)
        proc = run(["gate", "spec", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_gate_spec_requires_tables(self):
        build_project(self.root)
        write(self.root / "docs" / "02_美术圣经.md", md_text("02_美术圣经.md"))
        proc = run(["gate", "spec", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("表格", proc.stdout)

    def test_gate_whitebox_requires_blind_test(self):
        build_project(self.root, blind_test=False)
        proc = run(["gate", "whitebox", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("盲测", proc.stdout)

    def test_gate_slice_requires_accepted_conclusion(self):
        build_project(self.root, accepted=False)
        proc = run(["gate", "slice", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("验收单", proc.stdout)

    def test_gate_content_default_threshold(self):
        build_project(self.root)
        proc = run(["gate", "content", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("24", proc.stdout)
        self.assertIn("已入库", proc.stdout)

    def test_gate_content_passes_with_override(self):
        build_project(self.root)
        proc = run(["gate", "content", "--root", str(self.root), "--min-assets", "10"])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_gate_content_requires_level_checklists(self):
        build_project(self.root, level_checks=0)
        proc = run(["gate", "content", "--root", str(self.root), "--min-assets", "10"])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("验收清单", proc.stdout)

    def test_gate_release_unchecked_fails(self):
        build_project(self.root, unchecked=1)
        proc = run(["gate", "release", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("未勾选", proc.stdout)

    def test_gate_release_all_checked_passes(self):
        build_project(self.root)
        proc = run(["gate", "release", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_check_all_does_not_early_stop(self):
        build_project(self.root)
        write_numbers(self.root, gravity=80.0)
        (self.root / "assets" / "char_hero.fbx").unlink()
        proc = run(["check", "all", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("move.gravity", proc.stdout)
        self.assertIn("不存在", proc.stdout)


class ChangeOrderTests(TempDirCase):
    def test_no_change_orders_passes(self):
        build_project(self.root)
        proc = run(["change", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_change_links_asset_passes(self):
        rows = default_asset_rows()
        rows[0]["note"] = "CO-001"
        build_project(self.root, asset_rows=rows)
        write_change(self.root, "CO-001", "char_hero")
        proc = run(["change", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_change_missing_asset_fails(self):
        build_project(self.root)
        write_change(self.root, "CO-001", "char_missing")
        proc = run(["change", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("不存在", proc.stdout)

    def test_manifest_ref_missing_order_fails(self):
        rows = default_asset_rows()
        rows[0]["note"] = "CO-999"
        build_project(self.root, asset_rows=rows)
        proc = run(["change", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("CO-999", proc.stdout)

    def test_change_without_asset_impact_fails(self):
        build_project(self.root)
        path = self.root / "docs" / "09_变更单" / "CO-002_无影响.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# 变更单 — 无影响", ""]
        for section in REQ["09_变更单.md"]:
            lines.append("## " + section)
            lines.append("")
            lines.append("内容。")
            lines.append("")
        write(path, "\n".join(lines) + "\n")
        proc = run(["change", "check", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("影响评估", proc.stdout)


class ReleaseStoreTests(TempDirCase):
    def test_release_missing_store_file_fails(self):
        build_project(self.root)
        (self.root / "store" / "header.png").unlink()
        proc = run(["gate", "release", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("header.png", proc.stdout)

    def test_release_bad_screenshot_size_fails(self):
        build_project(self.root)
        (self.root / "store" / "screenshot_zh_01.png").write_bytes(png_bytes(1280, 720))
        proc = run(["gate", "release", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("1920x1080", proc.stdout)

    def test_release_missing_dual_input_fails(self):
        build_project(self.root)
        text = (self.root / "docs" / "10_测试记录.md").read_text(encoding="utf-8")
        write(self.root / "docs" / "10_测试记录.md", text.replace("手柄", "Xbox"))
        proc = run(["gate", "release", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("手柄", proc.stdout)

    def test_release_13_unchecked_fails(self):
        build_project(self.root, checked13=1, unchecked13=1)
        proc = run(["gate", "release", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("13_多语言商店素材清单", proc.stdout)


class OutputTests(TempDirCase):
    def test_json_report_is_parsable(self):
        build_project(self.root)
        proc, data = run_json(["check", "all", "--json", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIsNotNone(data, proc.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["failed"], 0)
        self.assertGreater(len(data["items"]), 0)
        for item in data["items"]:
            self.assertIn(item["level"], ("PASS", "FAIL", "WARN"))

    def test_json_report_on_failure(self):
        build_project(self.root)
        write_numbers(self.root, missing=("move.gravity",))
        proc, data = run_json(["manifest", "check", "--json", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        proc, data = run_json(["numbers", "check", "--json", "--root", str(self.root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIsNotNone(data)
        self.assertFalse(data["ok"])
        self.assertGreater(data["failed"], 0)

    def test_show_rules_lists_rules(self):
        proc = run(["--show-rules"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("80000", proc.stdout)
        self.assertIn("move.jump.height", proc.stdout)
        self.assertIn("content：doc stage 4", proc.stdout)
        self.assertIn("关卡数×8", proc.stdout)
        self.assertIn("退出码", proc.stdout)

    def test_help_lists_subcommands(self):
        proc = run(["--help"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for token in ("init", "doc", "gate", "numbers", "manifest", "change", "check"):
            self.assertIn(token, proc.stdout)


class SpecConsistencyTests(unittest.TestCase):
    def test_skill_frontmatter(self):
        path = REPO_ROOT / "SKILL.md"
        self.assertTrue(path.is_file(), "SKILL.md 必须存在")
        text = path.read_text(encoding="utf-8-sig")
        self.assertTrue(text.startswith("---"), "SKILL.md 必须以 YAML frontmatter 开头")
        frontmatter = text.split("---", 2)[1]
        self.assertIn("name:", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertIn("ue5-solo-game", frontmatter)

    def test_required_sections_match_spec_anchors(self):
        self.assertIn("结论", REQ["08_验收单.md"])
        self.assertIn("关卡目标", REQ["04_关卡设计.md"])
        self.assertIn("MCP 与自动化", REQ["03_技术方案.md"])
        self.assertIn("语言矩阵", REQ["13_多语言商店素材清单.md"])
        self.assertEqual(len(ASSET_HEADER), 16)
        self.assertEqual(len(NUM_HEADER), 7)
        self.assertEqual(REQ["11_周报.md"],
                         ["本周目标", "完成情况", "证据", "阻塞", "下周计划", "待决策"])

    def test_templates_have_required_sections(self):
        if not TEMPLATES.is_dir():
            self.skipTest("templates/ 尚未生成（由其他成员并行编写）")
        mapping = {
            "00_立项书.md": "00_立项书.md",
            "01_游戏设计文档.md": "01_游戏设计文档.md",
            "02_美术圣经.md": "02_美术圣经.md",
            "03_技术方案.md": "03_技术方案.md",
            "04_关卡设计.md": "04_关卡设计.md",
            "07_交付单.md": "07_交付单.md",
            "08_验收单.md": "08_验收单.md",
            "09_变更单.md": "09_变更单.md",
            "10_测试记录.md": "10_测试记录.md",
            "11_周报.md": "11_周报.md",
            "12_Demo上线清单.md": "12_Demo上线清单.md",
            "13_多语言商店素材清单.md": "13_多语言商店素材清单.md",
        }
        for filename, key in mapping.items():
            path = TEMPLATES / filename
            if not path.is_file():
                self.skipTest("templates/" + filename + " 尚未生成（由其他成员并行编写）")
            text = path.read_text(encoding="utf-8-sig")
            headings = gamecheck.parse_h2(text)
            missing = [section for section in REQ[key] if section not in headings]
            self.assertFalse(missing, filename + " 缺少 H2 章节：" + "、".join(missing))
        for filename, header in (("05_资产清单.csv", ASSET_HEADER), ("06_数值表.csv", NUM_HEADER)):
            path = TEMPLATES / filename
            if not path.is_file():
                self.skipTest("templates/" + filename + " 尚未生成")
            text = path.read_text(encoding="utf-8-sig")
            first_line = next(line for line in text.splitlines() if line.strip())
            self.assertEqual([cell.strip() for cell in first_line.split(",")], header,
                             filename + " 表头与校验器不一致")


if __name__ == "__main__":
    unittest.main()
