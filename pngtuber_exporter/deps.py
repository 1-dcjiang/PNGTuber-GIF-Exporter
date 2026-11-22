# -*- coding: utf-8 -*-
"""运行依赖探测：Node.js 与本机浏览器（Chrome / Edge）。

提供：
- 依赖状态探测（是否安装、版本、路径）；
- 官方 / 镜像下载入口 URL；
- 便携版 Node 自动下载解压到程序目录 ``runtime/node``，免安装补齐。

模型渲染模式（模式 4）依赖本机 Node 18+ 与 Chrome/Edge；其余三种模式不依赖。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

# 浏览器候选路径（名称, 路径）
BROWSER_CANDIDATES: list[tuple[str, str]] = [
    ("Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ("Chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ("Edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ("Edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

BROWSER_URLS = {
    "Chrome": "https://www.google.com/chrome/",
    "Edge": "https://www.microsoft.com/edge",
}

NODE_DOWNLOAD_PAGE = "https://nodejs.org/en/download"
# 便携 Node 二进制镜像（先国内镜像，回退官方）
NODE_DIST_MIRRORS = [
    "https://registry.npmmirror.com/-/binary/node",
    "https://nodejs.org/dist",
]
NODE_INDEX_URL = "https://nodejs.org/dist/index.json"
NODE_SHASUMS_URL = "https://nodejs.org/dist/{version}/SHASUMS256.txt"
NODE_MIN = (18, 0, 0)

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class DepStatus:
    key: str
    label: str
    ok: bool
    detail: str = ""
    path: str = ""
    version: str = ""
    download_url: str = ""


def runtime_dir() -> Path:
    """便携运行时目录（exe / 解释器旁侧 ``runtime``），可写。"""
    base = Path(sys.executable).resolve().parent
    return base / "runtime"


def portable_node_dir() -> Path:
    return runtime_dir() / "node"


def _node_candidates() -> list[str]:
    """Node 可执行文件候选：本地便携版 → PATH → 常见安装目录。"""
    cands: list[str] = []
    local = portable_node_dir() / "node.exe"
    if local.exists():
        cands.append(str(local))
    found = shutil.which("node")
    if found:
        cands.append(found)
    cands += [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs" / "node.exe"),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _parse_version(text: str) -> tuple[int, ...]:
    m = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", text or "")
    if not m:
        return (0,)
    return tuple(int(g) if g else 0 for g in m.groups())


def _node_version(exe: str) -> str:
    try:
        proc = subprocess.run(
            [exe, "-v"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=_CREATE_NO_WINDOW,
        )
        return proc.stdout.strip().lstrip("v")
    except (OSError, subprocess.SubprocessError):
        # TimeoutExpired 属于 SubprocessError，不是 OSError 子类，需一并兜住
        return ""


def detect_node() -> DepStatus:
    for exe in _node_candidates():
        if Path(exe).exists():
            ver = _node_version(exe)
            ver_tuple = _parse_version(ver)
            ok = ver_tuple >= NODE_MIN
            detail = f"Node {ver or '未知版本'} @ {exe}"
            if not ok:
                detail += f"（版本低于 {NODE_MIN[0]}，请升级）"
            return DepStatus(
                key="node",
                label="Node.js 18+",
                ok=ok,
                detail=detail,
                path=exe,
                version=ver,
                download_url=NODE_DOWNLOAD_PAGE,
            )
    return DepStatus(
        key="node",
        label="Node.js 18+",
        ok=False,
        detail="未检测到 Node.js，模型渲染模式不可用（可一键下载便携版）",
        download_url=NODE_DOWNLOAD_PAGE,
    )


def detect_browser() -> DepStatus:
    candidates = list(BROWSER_CANDIDATES)
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates += [
            ("Chrome", str(Path(local_app) / "Google" / "Chrome" / "Application" / "chrome.exe")),
            ("Edge", str(Path(local_app) / "Microsoft" / "Edge" / "Application" / "msedge.exe")),
        ]
    for name, path in candidates:
        if Path(path).exists():
            return DepStatus(
                key="browser",
                label=f"{name} 浏览器",
                ok=True,
                detail=f"{name} @ {path}",
                path=path,
                download_url=BROWSER_URLS[name],
            )
    return DepStatus(
        key="browser",
        label="Chrome / Edge",
        ok=False,
        detail="未检测到 Chrome 或 Edge，模型渲染模式不可用",
        download_url=BROWSER_URLS["Chrome"],
    )


@lru_cache(maxsize=1)
def detect_ffmpeg() -> Optional[str]:
    """探测本机 ffmpeg 可执行文件，返回路径；未安装返回 None。

    ffmpeg 用于以两阶段调色板生成高质量 GIF（色彩/边缘显著优于纯 Python 量化）。
    进程内结果缓存，避免每次导出都重新扫描 PATH 与 WinGet 目录。
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = [
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local.exists():
        candidates += [str(p) for p in local.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe")]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def detect_all() -> list[DepStatus]:
    return [detect_node(), detect_browser()]


def missing() -> list[DepStatus]:
    return [d for d in detect_all() if not d.ok]


# ---------- 便携 Node 自动下载补齐 ----------

def _http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pngtuber-exporter"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _expected_sha256(shasums: str, filename: str) -> str:
    """从 Node 官方 ``SHASUMS256.txt`` 中取指定文件的 sha256。"""
    for line in shasums.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*") == filename:
            digest = parts[0].lower()
            if re.fullmatch(r"[0-9a-f]{64}", digest):
                return digest
    raise RuntimeError(f"Node 官方校验文件中没有 {filename} 的 sha256")


def _fetch_node_sha256(version: str, filename: str) -> str:
    """只从 nodejs.org 取校验值，镜像只用于下载加速，不能同时提供校验值。"""
    url = NODE_SHASUMS_URL.format(version=version)
    return _expected_sha256(_http_get(url, timeout=30).decode("utf-8"), filename)


def _sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def latest_lts_version() -> str:
    """取 Node 最新 LTS 版本号（含 v 前缀）；先国内镜像，回退官方源。"""
    index_urls = [f"{mirror}/index.json" for mirror in NODE_DIST_MIRRORS] + [NODE_INDEX_URL]
    last_err: Optional[Exception] = None
    for url in index_urls:
        try:
            data = json.loads(_http_get(url, timeout=20).decode("utf-8"))
            for entry in data:
                if entry.get("lts"):
                    return str(entry["version"])
        except Exception as exc:  # noqa: BLE001 - 尝试下一镜像
            last_err = exc
    raise RuntimeError(f"未能从 Node 源获取 LTS 版本列表: {last_err}")


def portable_node_zip_urls(version: str) -> list[str]:
    name = f"node-{version}-win-x64.zip"
    return [f"{mirror}/{version}/{name}" for mirror in NODE_DIST_MIRRORS]


def install_portable_node(
    progress: Optional[Callable[[str, float], None]] = None,
) -> Path:
    """下载并解压便携 Node 到 ``runtime/node``，返回 node.exe 路径。

    progress(message, ratio) 回调用于上报进度（0~1）。已存在可用 node.exe 时直接返回。
    """
    existing = portable_node_dir() / "node.exe"
    if existing.exists():
        return existing

    def report(msg: str, ratio: float) -> None:
        if progress:
            progress(msg, ratio)

    report("获取 Node LTS 版本号…", 0.05)
    version = latest_lts_version()
    filename = f"node-{version}-win-x64.zip"
    urls = portable_node_zip_urls(version)

    last_err: Optional[Exception] = None
    blob: Optional[bytes] = None
    for url in urls:
        try:
            report(f"下载 Node {version}（镜像）…", 0.2)
            blob = _http_get(url, timeout=120)
            break
        except Exception as exc:  # noqa: BLE001 - 尝试下一镜像
            last_err = exc

    if blob is None:
        raise RuntimeError(f"便携 Node 下载失败: {last_err}")

    # 镜像只负责加速下载；校验值必须来自 nodejs.org 官方 SHASUMS256.txt。
    report("校验 Node 压缩包…", 0.45)
    expected = _fetch_node_sha256(version, filename)
    actual = _sha256_bytes(blob)
    if not hmac.compare_digest(actual, expected):
        raise RuntimeError(
            f"Node 压缩包 sha256 校验失败: 期望 {expected}，实际 {actual}；"
            "已中止解压，请重试或改用官方安装包"
        )

    target = portable_node_dir()
    tmp = runtime_dir() / f".node-{version}-tmp"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    zip_path = runtime_dir() / filename
    report("解压中…", 0.7)
    zip_path.write_bytes(blob)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            corrupt = zf.testzip()
            if corrupt:
                raise RuntimeError(f"Node 压缩包损坏: {corrupt}")
            tgt = tmp.resolve()
            for member in zf.infolist():
                # 防 zip-slip：条目 resolve 后必须仍位于临时目录内
                member_path = (tmp / member.filename).resolve()
                try:
                    member_path.relative_to(tgt)
                except ValueError:
                    raise RuntimeError(f"Node 压缩包含越界路径条目，已中止: {member.filename}")
            zf.extractall(tmp)

        # zip 内顶层目录为 node-vXX-win-x64/，拍平到临时目录根
        sub = next((p for p in tmp.iterdir() if p.is_dir()), None)
        if sub is not None:
            for child in sub.iterdir():
                shutil.move(str(child), str(tmp / child.name))
            shutil.rmtree(sub, ignore_errors=True)

        node_exe = tmp / "node.exe"
        if not node_exe.exists():
            raise RuntimeError("便携 Node 解压后未找到 node.exe")
        ver = _node_version(str(node_exe))
        if _parse_version(ver) < NODE_MIN:
            raise RuntimeError(f"便携 Node 版本不可用: {ver or '未知版本'}")

        # 只有全部校验通过后才替换正式目录，避免半成品 runtime/node 被复用。
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(tmp), str(target))
    finally:
        zip_path.unlink(missing_ok=True)
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)

    report("Node 就绪", 1.0)
    return target / "node.exe"
