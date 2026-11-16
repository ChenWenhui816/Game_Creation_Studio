# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：Personal_Game_Studio_UE 桌面版。

构建：
    python -m PyInstaller --noconfirm --clean build/desktop.spec
输出：
    dist/Personal_Game_Studio_UE/
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent
scripts = ROOT / "scripts"

datas = [
    (str(ROOT / "console_web"), "console_web"),
    (str(ROOT / "templates"), "templates"),
    (str(scripts), "scripts"),
    (str(ROOT / "references"), "references"),
    (str(ROOT / "docs"), "docs"),
    (str(ROOT / "mcp"), "mcp"),
    (str(ROOT / "schemas"), "schemas"),
]
for name in ("SKILL.md", "SKILL.en.md", "README.md", "README.en.md", "AGENTS.md",
             "CHANGELOG.md", "LICENSE"):
    path = ROOT / name
    if path.is_file():
        datas.append((str(path), "."))

hiddenimports = ["gameconsole", "version"]
binaries = []
try:
    wv_datas, wv_binaries, wv_hidden = collect_all("webview")
    datas += wv_datas
    binaries += wv_binaries
    hiddenimports += wv_hidden
except Exception:
    pass

a = Analysis(
    [str(scripts / "console_app.py")],
    pathex=[str(scripts), str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL", "tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Personal_Game_Studio_UE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Personal_Game_Studio_UE",
)
