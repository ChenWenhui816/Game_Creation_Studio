#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资产注册表 POC：扫描本地资产，生成可重建索引。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = {
    ".fbx": "model", ".glb": "model", ".gltf": "model", ".obj": "model", ".blend": "model",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".tga": "image",
    ".exr": "texture", ".psd": "texture",
    ".wav": "audio", ".ogg": "audio", ".mp3": "audio",
    ".mp4": "video", ".webm": "video", ".mov": "video",
    ".umap": "level", ".uasset": "data", ".json": "data", ".csv": "data", ".md": "other",
}
SCAN_DIRS = ("assets", "art/Export", "art/Source")


def setup():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def index_path(project: Path) -> Path:
    return project / ".gameconsole" / "assets.json"


def load_index(project: Path):
    try:
        data = json.loads(index_path(project).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"items": []}
    except (OSError, ValueError):
        return {"items": []}


def scan(project: Path, dry_run=False):
    project = project.expanduser().resolve()
    old = {item.get("path"): item for item in load_index(project).get("items", []) if item.get("path")}
    items = []
    for rel_dir in SCAN_DIRS:
        folder = project / rel_dir
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(project).as_posix()
            ext = path.suffix.lower()
            digest = sha256(path)
            previous = old.get(rel, {})
            item = {
                "id": previous.get("id") or digest[:16],
                "path": rel,
                "name": path.name,
                "kind": KINDS.get(ext, "other"),
                "sha256": digest,
                "size": path.stat().st_size,
                "status": previous.get("status", "untracked"),
                "license": previous.get("license", ""),
                "source": previous.get("source", ""),
                "provenance": previous.get("provenance", {}),
                "stage": previous.get("stage", ""),
                "owner": previous.get("owner", ""),
                "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }
            items.append(item)
    data = {"schema": 1, "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "items": items}
    if not dry_run:
        target = index_path(project)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def validate(project: Path):
    data = load_index(project)
    errors = []
    seen = set()
    for item in data.get("items", []):
        for key in ("id", "path", "kind", "sha256", "size", "status"):
            if key not in item:
                errors.append("缺少 %s：%s" % (key, item.get("path")))
        if item.get("path") in seen:
            errors.append("重复 path：%s" % item.get("path"))
        seen.add(item.get("path"))
    if errors:
        for error in errors:
            print("[FAIL]", error)
        return 1
    print("[OK] %d 条资产卡" % len(data.get("items", [])))
    return 0


def main(argv=None):
    setup()
    parser = argparse.ArgumentParser(prog="asset_registry")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "validate", "list"):
        p = sub.add_parser(name)
        p.add_argument("--project", default=".")
        if name == "scan":
            p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    project = Path(args.project)
    if args.cmd == "scan":
        data = scan(project, args.dry_run)
        print("assets:", len(data["items"]), "dry_run:", args.dry_run)
        return 0
    if args.cmd == "validate":
        return validate(project)
    data = load_index(project)
    for item in data.get("items", []):
        print("%-40s %-8s %-10s %s" % (item.get("path"), item.get("kind"), item.get("status"), item.get("license") or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
