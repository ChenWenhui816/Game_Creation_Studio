#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单一版本源：桌面版、skill、GitHub 发布共用。"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import urllib.request
from pathlib import Path

VERSION = "0.7.0"
SKILL_NAME = "ue5-solo-game"
APP_NAME = "Personal_Game_Studio_UE"
REPO_OWNER = "ChenWenhui816"
REPO_NAME = "Personal_Game_Studio_UE"
REPO_URL = "https://github.com/%s/%s" % (REPO_OWNER, REPO_NAME)
RELEASES_URL = REPO_URL + "/releases"
LATEST_RELEASE_API = "https://api.github.com/repos/%s/%s/releases/latest" % (REPO_OWNER, REPO_NAME)


def parse_version(text: str):
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def is_newer(latest: str, current: str = VERSION) -> bool:
    left, right = parse_version(latest), parse_version(current)
    if not left or not right:
        return False
    return left > right


def check_latest(timeout: float = 8.0) -> dict:
    """查询 GitHub 最新 release；失败时返回 ok=False，不影响本地使用。"""
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={"User-Agent": "Personal_Game_Studio_UE/" + VERSION,
                 "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
        tag = data.get("tag_name", "")
        assets = []
        for item in data.get("assets", []) or []:
            assets.append({
                "name": item.get("name", ""),
                "size": item.get("size", 0),
                "download_url": item.get("browser_download_url", ""),
                "digest": item.get("digest") or "",
            })
        asset = next((a for a in assets if a["name"].lower().endswith(".zip")), assets[0] if assets else None)
        return {
            "ok": True,
            "current": VERSION,
            "latest": tag.lstrip("v"),
            "tag": tag,
            "url": data.get("html_url", RELEASES_URL),
            "update_available": is_newer(tag),
            "published_at": data.get("published_at"),
            "assets": assets,
            "asset": asset,
        }
    except Exception as exc:  # noqa: BLE001 —— 更新检查不能影响启动
        return {"ok": False, "current": VERSION, "error": str(exc), "url": RELEASES_URL}


def download_update(asset: dict, dest_dir=None, timeout: float = 60.0) -> str:
    """下载发布包到本地，校验大小与 sha256 digest（若 GitHub 提供）。"""
    if not asset or not asset.get("download_url"):
        raise RuntimeError("发布包没有下载地址")
    folder = Path(dest_dir) if dest_dir else Path(tempfile.gettempdir()) / APP_NAME
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (asset.get("name") or ("update-%s.zip" % VERSION))
    request = urllib.request.Request(
        asset["download_url"],
        headers={"User-Agent": APP_NAME + "/" + VERSION, "Accept": "application/octet-stream"},
    )
    hasher = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=timeout) as response, target.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 128)
            if not chunk:
                break
            handle.write(chunk)
            hasher.update(chunk)
            total += len(chunk)
    if asset.get("size") and total != int(asset["size"]):
        raise RuntimeError("下载大小不符：%s != %s" % (total, asset["size"]))
    digest = (asset.get("digest") or "").lower()
    if digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1]
        if hasher.hexdigest().lower() != expected:
            raise RuntimeError("SHA-256 校验失败")
    return str(target)
