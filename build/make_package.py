#!/usr/bin/env python3
"""构建 Windows onedir 成品。

前置：
    python -m pip install -r requirements.txt -r requirements-build.txt
    cd web && npm ci

用法：
    python build/make_package.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
STAGING = ROOT / "build" / "staging"
WORK = ROOT / "build" / "work"
DIST = ROOT / "dist"
APP_NAME = "PNGTuber-GIF-Exporter"

IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
    "models",
    "_frames*",
    ".cache",
    "*.test.mjs",
    "download-*.mjs",
)


def main() -> int:
    if not (WEB / "node_modules").is_dir():
        print("[error] web/node_modules 不存在；先在 web/ 目录执行 npm ci", file=sys.stderr)
        return 2

    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    shutil.copytree(WEB, STAGING / "web", ignore=IGNORE)

    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        print("[error] 未安装 PyInstaller；pip install -r requirements-build.txt", file=sys.stderr)
        return 2

    pyinstaller.run(
        [
            str(ROOT / "main.py"),
            "--name",
            APP_NAME,
            "--onedir",
            "--console",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST),
            "--workpath",
            str(WORK),
            "--specpath",
            str(ROOT / "build"),
            "--add-data",
            f"{STAGING / 'web'};web",
            "--version-file",
            str(ROOT / "build" / "version_info.txt"),
        ]
    )

    app_dir = DIST / APP_NAME
    exe = app_dir / f"{APP_NAME}.exe"
    if not exe.is_file():
        print(f"[error] 未生成 {exe}", file=sys.stderr)
        return 1

    # 把项目许可与第三方声明放到成品根目录，避免只在源码树里可见。
    for doc in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        src = ROOT / doc
        if not src.is_file():
            print(f"[error] 缺少 {doc}", file=sys.stderr)
            return 1
        shutil.copy2(src, app_dir / doc)

    licenses_src = ROOT / "THIRD_PARTY_LICENSES"
    if not licenses_src.is_dir():
        print("[error] 缺少 THIRD_PARTY_LICENSES 目录", file=sys.stderr)
        return 1
    licenses_dst = app_dir / "THIRD_PARTY_LICENSES"
    if licenses_dst.exists():
        shutil.rmtree(licenses_dst)
    shutil.copytree(licenses_src, licenses_dst)

    print(exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
