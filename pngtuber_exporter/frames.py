# -*- coding: utf-8 -*-
"""状态图加载：解码 PNG / GIF 帧为统一 RGBA 序列。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageSequence


@dataclass
class StateAsset:
    key: str
    path: Path
    frames: list[Image.Image]
    durations: list[int]  # 每帧毫秒
    is_animated: bool

    @property
    def first(self) -> Image.Image:
        return self.frames[0]


def load_asset(key: str, path: Path) -> StateAsset:
    frames: list[Image.Image] = []
    durations: list[int] = []
    try:
        im = Image.open(path)
        try:
            for frame in ImageSequence.Iterator(im):
                frames.append(frame.convert("RGBA"))
                durations.append(max(1, int(frame.info.get("duration", 100) or 100)))
        finally:
            im.close()
    except (OSError, Image.UnidentifiedImageError) as exc:
        raise ValueError(f"无法读取图片（文件损坏或格式不支持）: {path}") from exc

    if not frames:
        raise ValueError(f"无法读取图片: {path}")
    return StateAsset(
        key=key,
        path=path,
        frames=frames,
        durations=durations,
        is_animated=len(frames) > 1,
    )


def load_project_images(images: dict[str, Path]) -> dict[str, StateAsset]:
    out: dict[str, StateAsset] = {}
    for key, path in images.items():
        out[key] = load_asset(key, path)
    return out
