# -*- coding: utf-8 -*-
"""PNGTuber / 帧序列 / 屏幕录制 / 3D 模型 -> 透明或循环 GIF 工具入口。

图形界面（无参数启动）:
    python main.py

命令行四种模式:
    1) PNGTuber 工程:
       python main.py --project <工程文件夹> --out <输出目录> [--fps 10]
    2) 图片 / 帧序列目录:
       python main.py --frames <帧目录> --out <输出目录> [--fps 10]
    3) 屏幕 / 窗口录屏:
       python main.py --record --duration 3 --region left,top,w,h --out <输出目录>
       python main.py --record --duration 3 --window "窗口标题关键词"
    4) VRM / glTF 3D 模型:
       python main.py --model <模型.vrm|模型.glb|模型.gltf> --out <输出目录>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pngtuber_exporter.capture import list_windows, primary_monitor, record
from pngtuber_exporter.detect import detect
from pngtuber_exporter.frames import load_project_images
from pngtuber_exporter.render import FORMAT_SUFFIX, RenderOptions, export_project, save_plain_gif
from pngtuber_exporter.sequence import load_sequence_images


def _setup_console() -> None:
    """重配标准流为 UTF-8 容错，避免 Windows GBK 控制台打印符号时崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def run_cli(project: Path, out_dir: Path, fps: int, max_edge: int, fmt: str = "gif") -> int:
    proj = detect(project, exclude_dirs=[out_dir])
    print(f"格式: {proj.source_format}  模型: {proj.model_name}")
    if proj.layered:
        print("分层工程当前版本待适配: " + proj.note)
        return 2
    if not proj.images:
        print("未识别到可用图片: " + (proj.note or ""))
        return 1

    assets = load_project_images(proj.images)
    result = export_project(
        assets, out_dir, RenderOptions(fps=fps, max_edge=max_edge),
        proj.model_meta, proj.model_name, fmt=fmt,
    )
    for w in result.warnings:
        print("⚠ " + w)
    if result.idle_gif:
        print(f"✓ 待机: {result.idle_gif}")
    if result.talk_gif:
        print(f"✓ 说话: {result.talk_gif}")
    for key, emo in result.emotion_gifs.items():
        print(f"✓ {key}: {emo}")
    return 0 if result.idle_gif else 1


def run_sequence(frames_dir: Path, out_dir: Path, fps: int, max_edge: int, fmt: str = "gif") -> int:
    frames = load_sequence_images(frames_dir, max_edge)
    suffix = FORMAT_SUFFIX.get(fmt, ".gif")
    out_path = out_dir / f"{frames_dir.name}_frames{suffix}"
    save_plain_gif(frames, out_path, fps, fmt=fmt)
    print(f"✓ 帧序列动画: {out_path}（{len(frames)} 帧）")
    return 0


def _resolve_region(args: argparse.Namespace) -> dict:
    if args.window:
        for win in list_windows():
            if args.window.lower() in win["title"].lower():
                print(f"目标窗口: {win['title']}  区域: {win['region']}")
                return win["region"]
        print("⚠ 未匹配到窗口，回退到全屏。")
    if args.region:
        parts = args.region.split(",")
        if len(parts) != 4:
            raise ValueError("自定义区域格式应为 left,top,w,h（如 100,100,600,500）")
        try:
            left, top, w, h = (int(x.strip()) for x in parts)
        except ValueError:
            raise ValueError("自定义区域坐标需为整数，格式 left,top,w,h")
        if w <= 0 or h <= 0:
            raise ValueError("区域宽高需为正整数（left,top,width,height）")
        return {"left": left, "top": top, "width": w, "height": h}
    return primary_monitor()


def run_model(model_path: Path, out_dir: Path, fps: int, frames: int, size: int, max_edge: int, fmt: str = "gif") -> int:
    from pngtuber_exporter.web_render import classify_model, render_model

    kind = classify_model(model_path)
    label = {"vrm": "3D 模型"}.get(kind, "未知")
    print(f"格式: {label}  模型: {model_path.name}")
    result = render_model(
        model_path,
        out_dir,
        fps=fps,
        frames=frames,
        size=size,
        max_edge=max_edge,
        fmt=fmt,
        log=print,
    )
    print(f"✓ 模型动画: {result.gif}（{result.frames} 帧）")
    return 0


def run_record(args: argparse.Namespace, out_dir: Path) -> int:
    region = _resolve_region(args)
    print(f"开始录制 {args.duration}s @ {args.fps}fps，区域 {region} …")
    frames = record(region, args.duration, args.fps)
    from pngtuber_exporter.render import normalize_frames

    frames = normalize_frames(frames, args.max_edge)
    suffix = FORMAT_SUFFIX.get(args.format, ".gif")
    out_path = out_dir / f"record{suffix}"
    save_plain_gif(frames, out_path, args.fps, fmt=args.format)
    print(f"✓ 录屏动画: {out_path}（{len(frames)} 帧）")
    return 0


def main() -> int:
    _setup_console()
    ap = argparse.ArgumentParser(description="PNGTuber / 帧序列 / 录屏 一键导出 GIF")
    ap.add_argument("--project", help="PNGTuber 工程文件夹")
    ap.add_argument("--frames", help="图片 / 帧序列目录")
    ap.add_argument("--model", help="3D 模型（.vrm/.glb/.gltf）或其所在目录；VRM 驱动表情，普通 glTF/GLB 静态渲染")
    ap.add_argument("--model-frames", type=int, default=12, help="模型渲染帧数，默认 12")
    ap.add_argument("--model-size", type=int, default=768, help="模型离屏画布边长，默认 768")
    ap.add_argument("--record", action="store_true", help="屏幕 / 窗口录屏模式")
    ap.add_argument("--out", help="GIF 输出目录")
    ap.add_argument("--fps", type=int, default=10, help="导出帧率，默认 10")
    ap.add_argument("--max-edge", type=int, default=1024, help="输出最长边，0 不限制")
    ap.add_argument("--duration", type=float, default=3.0, help="录屏时长（秒）")
    ap.add_argument("--region", help="录屏区域 left,top,w,h")
    ap.add_argument("--window", help="按标题关键词匹配要录制的窗口")
    ap.add_argument("--format", choices=("gif", "apng"), default="gif", help="输出格式：gif（1-bit 透明）或 apng（半透明），默认 gif")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else Path.cwd() / "output"
    fmt = args.format

    mode_count = sum(bool(x) for x in (args.project, args.frames, args.model, args.record))
    if mode_count > 1:
        print("⚠ 同时指定了多种模式参数；仅按 工程 → 帧序列 → 模型 → 录屏 的顺序执行第一个。")

    try:
        if args.project:
            return run_cli(Path(args.project), out_dir, args.fps, args.max_edge, fmt)
        if args.frames:
            return run_sequence(Path(args.frames), out_dir, args.fps, args.max_edge, fmt)
        if args.model:
            return run_model(
                Path(args.model), out_dir, args.fps, args.model_frames, args.model_size, args.max_edge, fmt
            )
        if args.record:
            return run_record(args, out_dir)
    except Exception as exc:  # noqa: BLE001 - CLI 顶层兜底，避免裸栈
        print("✗ 失败: " + str(exc))
        try:
            import traceback
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "_cli_error.log").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
        except OSError:
            pass
        return 1

    from pngtuber_exporter.gui import run
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
