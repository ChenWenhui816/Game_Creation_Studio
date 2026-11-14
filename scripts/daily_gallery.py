#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日截图巡览生成器。

把 UE 每日截图整理成可浏览的 HTML/Markdown 巡览页：
- 递归扫描 --src 下的图片，按日期分组（父目录名 YYYY-MM-DD 优先，否则用 mtime 的本地日期）；
- 日期降序、同日内 mtime 升序；
- 生成自包含 out/index.html（无外链 CSS、无 JS 依赖）与 out/index.md；
- --days 以最新截图为基准保留最近 N 天，--compare 生成两栏对比，--json 输出机器可读汇总。

用法：
    python scripts/daily_gallery.py --src <截图目录> [--out <输出目录>] [--title <标题>]
        [--days N] [--compare YYYY-MM-DD,YYYY-MM-DD] [--ext png,jpg,jpeg] [--json]

退出码：0 成功；1 无截图或参数错误；2 用法错误。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

VERSION = "0.2.0"
DEFAULT_TITLE = "每日截图巡览"
DEFAULT_EXTS = ("png", "jpg", "jpeg")
HTML_NAME = "index.html"
MD_NAME = "index.md"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

EXAMPLES = """示例：
  python scripts/daily_gallery.py --src "D:/Game/Saved/Screenshots" --title "第 3 周巡览"
  python scripts/daily_gallery.py --src Saved/Screenshots --days 7 --out docs/gallery
  python scripts/daily_gallery.py --src Saved/Screenshots --compare 2026-11-10,2026-11-14
  python scripts/daily_gallery.py --src Saved/Screenshots --json > gallery.json

退出码：0 成功；1 无截图或参数错误；2 用法错误。
默认输出目录：当前目录/gallery。"""


class GalleryError(Exception):
    """可预期的参数或环境错误，统一按退出码 1 处理。"""


@dataclass
class Shot:
    """一张通过扩展名筛选的截图。"""

    path: Path
    rel: str          # 相对 src 的 posix 路径，用于显示与 JSON
    mtime: float      # 文件修改时间戳
    when: datetime    # 本地时间，用于排序与显示
    size: int         # 字节数
    day: date         # 分组日期（父目录名优先）


@dataclass
class DayGroup:
    """同一天的一组截图。"""

    day: date
    shots: list = field(default_factory=list)


def configure_stdio() -> None:
    """Windows 控制台/CI 重定向时统一 UTF-8，避免中文标题写不出去。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _norm_path(value) -> str:
    """用于判断目录包含关系的规范化绝对路径。"""
    return os.path.normcase(os.path.abspath(os.path.expanduser(str(value))))


def is_within(child, parent) -> bool:
    """child 是否等于 parent 或位于 parent 之下（大小写按平台处理）。"""
    child_norm = _norm_path(child)
    parent_norm = _norm_path(parent)
    if child_norm == parent_norm:
        return True
    try:
        return os.path.commonpath([child_norm, parent_norm]) == parent_norm
    except ValueError:
        # Windows 上不同盘符无法比较，直接判否。
        return False


def parse_day(text: str):
    """把 YYYY-MM-DD 解析成 date；不合法返回 None。"""
    value = str(text).strip()
    if not DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parent_day(path: Path):
    """父目录名是合法 YYYY-MM-DD 时返回该日期，否则返回 None。"""
    return parse_day(path.parent.name)


def parse_exts(raw: str):
    """解析 --ext：逗号分隔、大小写不敏感、自动去掉点。"""
    items = []
    for chunk in str(raw).replace(";", ",").split(","):
        ext = chunk.strip().lower().lstrip(".")
        if not ext:
            continue
        if not re.fullmatch(r"[a-z0-9]+", ext):
            raise GalleryError("--ext 只接受字母或数字扩展名，收到：%s（示例：--ext png,jpg）" % chunk.strip())
        if ext not in items:
            items.append(ext)
    if not items:
        raise GalleryError("--ext 不能为空（示例：--ext png,jpg,jpeg）")
    return tuple(items)


def parse_days(raw):
    """解析 --days：正整数；未传返回 None。"""
    if raw is None or str(raw).strip() == "":
        return None
    text = str(raw).strip()
    try:
        value = int(text)
    except ValueError:
        raise GalleryError("--days 必须是正整数，收到：%s" % text)
    if value < 1:
        raise GalleryError("--days 必须 >= 1，收到：%s" % text)
    return value


def parse_compare(raw):
    """解析 --compare A,B：两个真实存在的 YYYY-MM-DD 日期。"""
    if raw is None or str(raw).strip() == "":
        return None
    parts = [part.strip() for part in str(raw).split(",")]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise GalleryError("--compare 需要两个日期，格式：--compare 2026-11-10,2026-11-14")
    first = parse_day(parts[0])
    second = parse_day(parts[1])
    if first is None or second is None:
        raise GalleryError("--compare 的日期必须是真实存在的 YYYY-MM-DD，收到：%s" % str(raw).strip())
    return first, second


def collect_shots(src: Path, out: Path, exts) -> list:
    """递归扫描 src；out 位于 src 内时跳过 out 整棵子树。"""
    shots = []
    skip_out = is_within(out, src)
    for dirpath, dirnames, filenames in os.walk(str(src), followlinks=False):
        current = Path(dirpath)
        if skip_out:
            if is_within(current, out):
                dirnames[:] = []
                continue
            dirnames[:] = [name for name in dirnames if not is_within(current / name, out)]
        for name in filenames:
            path = current / name
            ext = path.suffix.lower().lstrip(".")
            if ext not in exts:
                continue
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            when = datetime.fromtimestamp(stat.st_mtime)
            day = parent_day(path) or when.date()
            try:
                rel = path.relative_to(src).as_posix()
            except ValueError:
                rel = path.name
            shots.append(Shot(path=path, rel=rel, mtime=stat.st_mtime,
                              when=when, size=stat.st_size, day=day))
    return shots


def group_shots(shots) -> list:
    """按日期分组：日期降序，同日内 mtime 升序（相同 mtime 按文件名）。"""
    buckets = {}
    for shot in shots:
        buckets.setdefault(shot.day, []).append(shot)
    groups = []
    for day in sorted(buckets, reverse=True):
        items = sorted(buckets[day], key=lambda item: (item.mtime, item.path.name))
        groups.append(DayGroup(day=day, shots=items))
    return groups


def filter_days(groups, days) -> list:
    """保留最近 N 个自然日；基准是最新截图的日期，不是今天。"""
    if days is None or not groups:
        return list(groups)
    newest = groups[0].day
    cutoff = newest - timedelta(days=days - 1)
    return [group for group in groups if group.day >= cutoff]


def human_size(size: int) -> str:
    """把字节数转成 B/KB/MB/GB 的短文本。"""
    value = float(size)
    if value < 1024:
        return "%d B" % int(value)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024:
            return "%.1f %s" % (value, unit)
    return "%.1f PB" % value


def relative_link(path: Path, out_dir: Path) -> str:
    """生成从 out 指向图片的相对链接；失败时退化为绝对路径。"""
    try:
        rel = os.path.relpath(str(path), str(out_dir))
    except ValueError:
        rel = str(path)
    return quote(Path(rel).as_posix(), safe="/")


CSS = """
:root {
  color-scheme: light dark;
  --bg: #f4f5f7;
  --card: #ffffff;
  --text: #1f2328;
  --muted: #6b7280;
  --line: #d8dee4;
  --accent: #2563eb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111318;
    --card: #1a1d24;
    --text: #e6e8eb;
    --muted: #9aa4b2;
    --line: #2c313a;
    --accent: #60a5fa;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei",
    "Noto Sans CJK SC", "PingFang SC", sans-serif;
  line-height: 1.5;
}
header.page { max-width: 1440px; margin: 0 auto; padding: 20px 16px 8px; }
h1 { margin: 0 0 4px; font-size: clamp(20px, 2.4vw, 30px); }
.meta { margin: 2px 0; color: var(--muted); font-size: 13px; }
main { max-width: 1440px; margin: 0 auto; padding: 8px 16px 32px; }
.compare {
  margin: 12px 0 20px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--card);
}
.compare h2 { margin: 0 0 8px; font-size: 18px; }
.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.compare-col h3 { margin: 0 0 6px; font-size: 16px; }
.compare-col .count { color: var(--muted); font-size: 13px; font-weight: normal; }
.missing {
  margin: 0;
  padding: 16px;
  border: 1px dashed var(--line);
  border-radius: 8px;
  color: var(--muted);
  font-size: 14px;
}
.day { margin: 22px 0; }
.day > header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--line);
}
.day h2 { margin: 0; font-size: 18px; font-variant-numeric: tabular-nums; }
.count { color: var(--muted); font-size: 13px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.shot {
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--card);
}
.shot a { display: block; }
.shot img {
  display: block;
  width: 100%;
  height: auto;
  aspect-ratio: 16 / 9;
  object-fit: contain;
  background: #000000;
}
.shot figcaption { display: flex; flex-direction: column; gap: 2px; padding: 6px 8px; font-size: 12px; }
.shot .name { font-weight: 600; overflow-wrap: anywhere; }
.shot .time, .shot .size { color: var(--muted); }
footer { max-width: 1440px; margin: 0 auto; padding: 0 16px 24px; color: var(--muted); font-size: 12px; }
@media (max-width: 640px) {
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .compare-grid { grid-template-columns: 1fr; }
  .shot .name { font-size: 11px; }
  header.page, main, footer { padding-left: 12px; padding-right: 12px; }
}
@media print {
  body { background: #ffffff; }
  .shot { break-inside: avoid; }
}
"""


def _esc(value) -> str:
    """HTML 转义：文本节点与属性值共用。"""
    return html.escape(str(value), quote=True)


def _figure(shot: Shot, out_dir: Path) -> str:
    """单张截图卡片：缩略图 + 文件名/时间/大小。"""
    link = _esc(relative_link(shot.path, out_dir))
    name = _esc(shot.path.name)
    return (
        '<figure class="shot">'
        '<a href="%s" target="_blank" rel="noopener"><img src="%s" alt="%s" loading="lazy"></a>'
        '<figcaption><span class="name">%s</span><span class="time">%s</span>'
        '<span class="size">%s</span></figcaption>'
        "</figure>"
    ) % (link, link, name, name, _esc(shot.when.strftime("%Y-%m-%d %H:%M:%S")), _esc(human_size(shot.size)))


def _grid(shots, out_dir: Path) -> str:
    return '<div class="grid">' + "".join(_figure(shot, out_dir) for shot in shots) + "</div>"


def build_html(title: str, groups, compare_rows, total: int, generated_at: str, out_dir: Path) -> str:
    """生成自包含 index.html：样式内联、无脚本、无外链。"""
    compare_html = ""
    if compare_rows:
        columns = []
        for day, group in compare_rows:
            count = len(group.shots) if group else 0
            head = "<h3>%s <span class=\"count\">共 %d 张</span></h3>" % (_esc(day.isoformat()), count)
            if group is None:
                body = '<p class="missing">该日期没有截图：%s（检查 --src、父目录日期或截图日期）</p>' % _esc(day.isoformat())
            else:
                body = _grid(group.shots, out_dir)
            columns.append('<div class="compare-col">%s%s</div>' % (head, body))
        label = " ↔ ".join(_esc(day.isoformat()) for day, _group in compare_rows)
        compare_html = (
            '<section class="compare" id="compare"><h2>对比：%s</h2>'
            '<div class="compare-grid">%s</div></section>'
        ) % (label, "".join(columns))

    day_blocks = []
    for group in groups:
        day_blocks.append(
            '<section class="day" id="d-%s"><header><h2>%s</h2>'
            '<span class="count">共 %d 张</span></header>%s</section>'
            % (_esc(group.day.isoformat()), _esc(group.day.isoformat()),
               len(group.shots), _grid(group.shots, out_dir))
        )

    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="generator" content="daily_gallery.py %s">' % VERSION,
        "<title>%s</title>" % _esc(title),
        "<style>%s</style>" % CSS,
        "</head>",
        "<body>",
        '<header class="page">',
        "<h1>%s</h1>" % _esc(title),
        '<p class="meta">共 %d 张截图 ｜ %d 天 ｜ 生成于 %s</p>' % (total, len(groups), _esc(generated_at)),
        "</header>",
        "<main>",
        compare_html,
        "".join(day_blocks),
        "</main>",
        '<footer>由 scripts/daily_gallery.py 生成；图片使用相对路径，移动目录后请重新生成。</footer>',
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(parts)


def _md_escape(text: str) -> str:
    """转义 Markdown 链接文字里的方括号与反斜杠。"""
    return re.sub(r"([\\\[\]()])", r"\\\1", text)


def build_markdown(title: str, groups, compare_rows, total: int, generated_at: str, out_dir: Path) -> str:
    """生成 index.md：日期 + 图片相对链接。"""
    lines = ["# " + title, "",
             "- 共 %d 张截图 ｜ %d 天" % (total, len(groups)),
             "- 生成时间：%s" % generated_at, ""]
    if compare_rows:
        label = " ↔ ".join(day.isoformat() for day, _group in compare_rows)
        lines += ["## 对比：%s" % label, ""]
        for day, group in compare_rows:
            count = len(group.shots) if group else 0
            lines += ["### %s（%d 张）" % (day.isoformat(), count), ""]
            if group is None:
                lines += ["- 该日期没有截图。", ""]
                continue
            for shot in group.shots:
                link = relative_link(shot.path, out_dir)
                lines.append("- [%s](%s) — %s · %s" % (
                    _md_escape(shot.path.name), link,
                    shot.when.strftime("%H:%M:%S"), human_size(shot.size)))
            lines.append("")
    for group in groups:
        lines += ["## %s（%d 张）" % (group.day.isoformat(), len(group.shots)), ""]
        for shot in group.shots:
            link = relative_link(shot.path, out_dir)
            lines.append("- [%s](%s) — %s · %s" % (
                _md_escape(shot.path.name), link,
                shot.when.strftime("%H:%M:%S"), human_size(shot.size)))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_text_file(path: Path, text: str) -> None:
    """统一 UTF-8、LF 换行写入，避免 Windows 下 CRLF 污染 diff。"""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def run(args) -> int:
    """执行一次生成；所有可预期错误抛 GalleryError（退出码 1）。"""
    src = Path(os.path.abspath(os.path.expanduser(str(args.src))))
    if not src.is_dir():
        raise GalleryError("截图目录不存在或不是目录：%s" % src)

    if args.out:
        out = Path(os.path.abspath(os.path.expanduser(str(args.out))))
    else:
        out = Path(os.path.abspath(str(Path.cwd() / "gallery")))
    if _norm_path(src) == _norm_path(out):
        raise GalleryError("--out 不能等于 --src：输出页要写在截图目录之外，避免把 index.html 当成截图扫描。")

    exts = parse_exts(args.ext)
    days = parse_days(args.days)
    compare = parse_compare(args.compare)
    title = str(args.title or "").strip() or DEFAULT_TITLE

    shots = collect_shots(src, out, exts)
    if not shots:
        raise GalleryError("在 %s 下没有找到图片（扩展名：%s）。检查路径，或用 --ext 指定扩展名。"
                           % (src, ",".join(exts)))

    all_groups = group_shots(shots)
    groups = filter_days(all_groups, days)
    by_day = {group.day: group for group in all_groups}
    compare_rows = [(day, by_day.get(day)) for day in compare] if compare else []

    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GalleryError("无法创建输出目录 %s：%s" % (out, exc))

    total = sum(len(group.shots) for group in groups)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html_path = out / HTML_NAME
    md_path = out / MD_NAME
    try:
        write_text_file(html_path, build_html(title, groups, compare_rows, total, generated_at, out))
        write_text_file(md_path, build_markdown(title, groups, compare_rows, total, generated_at, out))
    except OSError as exc:
        raise GalleryError("写入输出文件失败：%s" % exc)

    if compare_rows:
        missing = [day.isoformat() for day, group in compare_rows if group is None]
        if missing:
            sys.stderr.write("提示：以下对比日期没有截图：%s\n" % "、".join(missing))

    if args.json_out:
        payload = {
            "src": str(src),
            "out": str(out),
            "days": days,
            "total": total,
            "dates": [
                {"date": group.day.isoformat(),
                 "count": len(group.shots),
                 "files": [shot.rel for shot in group.shots]}
                for group in groups
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("已生成巡览：%s" % html_path)
        print("            %s" % md_path)
        suffix = ""
        if days is not None:
            suffix = "（--days %d，以最新截图 %s 为基准）" % (days, all_groups[0].day.isoformat())
        print("截图 %d 张 / %d 天%s" % (total, len(groups), suffix))
        if compare_rows:
            print("对比：%s" % " / ".join(day.isoformat() for day, _group in compare_rows))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily_gallery.py",
        description="把 UE 每日截图整理成可浏览的 HTML/Markdown 巡览页（Python 标准库，无第三方依赖）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )
    parser.add_argument("--src", required=True,
                        help="截图目录（递归扫描；必需）")
    parser.add_argument("--out", default=None,
                        help="输出目录（默认：当前目录/gallery）")
    parser.add_argument("--title", default=None,
                        help="巡览页标题（默认：%s）" % DEFAULT_TITLE)
    parser.add_argument("--days", default=None, metavar="N",
                        help="只保留最近 N 个自然日；基准是最新截图的日期，不是今天")
    parser.add_argument("--compare", default=None, metavar="A,B",
                        help="生成两栏对比：--compare 2026-11-10,2026-11-14（左 A 右 B）")
    parser.add_argument("--ext", default=",".join(DEFAULT_EXTS),
                        help="图片扩展名，逗号分隔（默认：png,jpg,jpeg）")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="stdout 只输出 JSON 汇总")
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    return parser


def main(argv=None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except GalleryError as exc:
        sys.stderr.write("错误：%s\n" % exc)
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        return 2
    except Exception as exc:  # noqa: BLE001 —— 不向用户抛 traceback
        sys.stderr.write("内部错误：%s: %s\n" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
