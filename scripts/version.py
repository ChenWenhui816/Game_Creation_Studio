#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单一版本源：桌面版、skill、GitHub 发布共用。"""

from __future__ import annotations

import json
import re
import urllib.request

VERSION = "0.4.0"
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
        return {
            "ok": True,
            "current": VERSION,
            "latest": tag.lstrip("v"),
            "tag": tag,
            "url": data.get("html_url", RELEASES_URL),
            "update_available": is_newer(tag),
            "published_at": data.get("published_at"),
        }
    except Exception as exc:  # noqa: BLE001 —— 更新检查不能影响启动
        return {"ok": False, "current": VERSION, "error": str(exc), "url": RELEASES_URL}
