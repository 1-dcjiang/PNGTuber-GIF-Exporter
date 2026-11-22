# -*- coding: utf-8 -*-
"""VRM / glTF 模型 -> 序列帧 -> GIF 的 Web 渲染桥接。

链路：本机 Node 无头脚本调用系统 Chrome/Edge 加载模型，逐帧截 PNG 到临时目录，
再交回本包既有的帧序列管线打包透明循环 GIF。不内嵌浏览器内核、不内嵌 Node。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path

from . import deps
from .render import FORMAT_SUFFIX, save_plain_gif
from .sequence import load_sequence_images

VRM_SUFFIXES = {".vrm", ".glb", ".gltf"}

ENTRY_PRIORITY = (".vrm", ".glb", ".gltf")


def resolve_model_entry(path: str | Path) -> Path | None:
    """若给定目录，递归识别其中首个模型入口文件；文件则原样返回。"""
    p = Path(path)
    if p.is_file():
        return p
    if not p.is_dir():
        return None
    by_ext: dict[str, Path] = {}
    for child in p.rglob("*"):
        if not child.is_file():
            continue
        suf = child.suffix.lower()
        if suf in VRM_SUFFIXES:
            by_ext.setdefault(suf, child)
    for ext in ENTRY_PRIORITY:
        if ext in by_ext:
            return by_ext[ext]
    return None


def classify_model(path: str | Path) -> str | None:
    """返回 'vrm'；无法识别返回 None。"""
    p = Path(path)
    if p.suffix.lower() in VRM_SUFFIXES:
        return "vrm"
    return None


def web_root() -> Path:
    """定位随程序分发的 web/ 资源目录。

    兼容：开发态包根 / onefile 解压目录(_MEIPASS) / onedir 的 _internal 与旁侧 web/。
    """
    meipass = getattr(sys, "_MEIPASS", None)
    exe_dir = Path(sys.executable).resolve().parent
    candidates: list[Path] = []
    if meipass:
        candidates.append(Path(meipass) / "web")
    candidates += [
        exe_dir / "web",
        exe_dir / "_internal" / "web",
        Path(__file__).resolve().parent.parent / "web",
    ]
    for c in candidates:
        if c.is_dir() and (c / "render-vrm.mjs").exists():
            return c
    raise FileNotFoundError("未找到 web 渲染资源目录（render-vrm.mjs 缺失）。")


def detect_node() -> str:
    """探测本机 Node 可执行文件（含本地便携版 runtime/node）。"""
    status = deps.detect_node()
    if not status.ok:
        raise FileNotFoundError(
            "未检测到 Node.js 18+。模型渲染依赖本机 Node 运行无头采集脚本，"
            "可在界面的环境状态区一键下载便携版，或访问 " + status.download_url
        )
    return status.path


def detect_browser() -> str:
    """探测本机 Chrome / Edge 可执行文件。"""
    status = deps.detect_browser()
    if not status.ok:
        raise FileNotFoundError(
            "未检测到 Chrome 或 Edge。无头采集需要本机浏览器内核，下载页: " + status.download_url
        )
    return status.path


@dataclass
class RenderResult:
    gif: Path
    frames: int
    frame_dir: Path


def render_model(
    model_path: str | Path,
    out_dir: str | Path,
    fps: int = 10,
    frames: int = 12,
    size: int = 768,
    max_edge: int = 1024,
    keep_frames: bool = False,
    fmt: str = "gif",
    dither: bool = True,
    log=print,
) -> RenderResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_dir = None
    slog = (out_dir / "_web_render.log").open("w", encoding="utf-8")

    def w(msg: str) -> None:
        slog.write(msg + "\n")
        slog.flush()
        try:
            log(msg)
        except Exception:
            pass

    try:
        model = Path(model_path).resolve()
        if model.is_dir():
            entry = resolve_model_entry(model)
            if entry is None:
                raise FileNotFoundError(f"目录内未找到模型入口（.vrm/.glb/.gltf）: {model}")
            model = entry
            w(f"目录自动识别入口: {model}")
        w(f"模型路径: {model}  存在={model.exists()}")
        if not model.exists():
            raise FileNotFoundError(f"模型文件不存在: {model}")

        kind = classify_model(model)
        w(f"识别格式: {kind}")
        if kind is None:
            raise ValueError("不支持的模型格式（支持 .vrm/.glb/.gltf）。")

        root = web_root()
        w(f"web 资源目录: {root}")
        node = detect_node()
        w(f"node 可执行: {node}")
        browser = detect_browser()
        w(f"浏览器: {browser}")
        script = root / "render-vrm.mjs"

        frame_dir = Path(tempfile.mkdtemp(prefix="lgif_frames_"))
        ext_url = f"/external/{model.name}"
        cmd = [
            node,
            str(script),
            "--model",
            ext_url,
            "--model-dir",
            str(model.parent),
            "--out",
            str(frame_dir),
            "--frames",
            str(frames),
            "--fps",
            str(fps),
            "--size",
            str(size),
            "--browser",
            str(browser),
        ]
        w("命令: " + " ".join(cmd))

        env = dict(os.environ)
        # 本地 127.0.0.1 桥接，不关闭 Node 证书校验
        # GUI 程序下不弹出子进程控制台窗口
        creationflags = 0x08000000 if sys.platform == "win32" else 0

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=creationflags,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "无头渲染超时（180s）：浏览器加载模型或逐帧采集卡住，"
                "可减少渲染帧数、检查模型文件完整性后重试。"
            )
        if proc.stdout:
            for line in proc.stdout.splitlines():
                if line.strip():
                    w("[browser] " + line.strip())
        w(f"采集退出码: {proc.returncode}")
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "未知错误").strip()
            raise RuntimeError(f"无头采集失败（退出码 {proc.returncode}）:\n{err}")

        images = load_sequence_images(frame_dir, max_edge)
        if not images:
            raise RuntimeError("采集完成但未读取到有效帧。")

        suffix = FORMAT_SUFFIX.get(fmt, ".gif")
        base = model.stem
        out_path = out_dir / f"{base}{suffix}"
        save_plain_gif(images, out_path, fps, fmt=fmt, dither=dither)

        kept = frame_dir if keep_frames else Path("")
        w(f"✓ 模型 GIF: {out_path}（{len(images)} 帧）")
        return RenderResult(gif=out_path, frames=len(images), frame_dir=kept)
    except Exception:
        w(traceback.format_exc())
        raise
    finally:
        # 无论成功还是异常，未要求保留帧时都清理临时帧目录，避免泄漏
        if frame_dir is not None and not keep_frames:
            shutil.rmtree(frame_dir, ignore_errors=True)
        slog.close()
