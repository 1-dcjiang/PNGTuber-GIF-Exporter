# -*- coding: utf-8 -*-
"""通用图片 / 帧序列目录加载：按文件名自然排序，GIF 展开为多帧。"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from .render import normalize_frames

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _nat_key(path: Path) -> list[object]:
    """自然排序键：把文件名里的数字段按数值比较（frame_2 排在 frame_10 前）。"""
    parts = re.split(r"(\d+)", path.stem.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def load_sequence_images(directory: str | Path, max_edge: int = 0) -> list[Image.Image]:
    """读取目录内有序图片为 RGBA 帧序列；GIF 素材会展开其全部帧。"""
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        raise ValueError("目录不存在或不是文件夹")

    files = sorted(
        (p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES),
        key=_nat_key,
    )
    frames: list[Image.Image] = []
    for p in files:
        im = Image.open(p)
        try:
            # 按手机 / 相机 EXIF 方向校正，避免 JPG 竖图被横着读入
            im = ImageOps.exif_transpose(im)
            for frame in ImageSequence.Iterator(im):
                frames.append(frame.convert("RGBA"))
        finally:
            im.close()

    if not frames:
        raise ValueError("目录内没有可读取的图片（支持 PNG/JPG/WebP/GIF）")

    return normalize_frames(frames, max_edge)
