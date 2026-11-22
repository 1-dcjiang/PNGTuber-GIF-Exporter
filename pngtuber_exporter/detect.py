# -*- coding: utf-8 -*-
"""PNGTuber 工程探测与状态图识别。

支持的扁平来源:
  - simple_package: 根目录 model.json（model_type=pngtuber，图片在 pngtuber.*_image）
  - loose_images:   目录内散图，按文件名关键词归类 idle/talking/blink/...

分层来源（识别后标记为待适配，第一版不做图层合成）:
  - pngtuber_plus_save:   *.save
  - pngtube_remix_pngremix: *.pngRemix
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

IMAGE_SUFFIXES = {".png", ".gif", ".jpg", ".jpeg", ".webp"}

# model.json 字段 -> 标准状态 key
MODEL_FIELD_MAP = {
    "idle_image": "idle",
    "talking_image": "talking",
    "blink_image": "blink",
    "blink_talking_image": "blink_talking",
    "happy_image": "happy",
    "sad_image": "sad",
    "angry_image": "angry",
    "surprised_image": "surprised",
    "click_image": "click",
    "drag_image": "drag",
}

# 文件名关键词 -> 标准状态 key（顺序即优先级，越具体的越靠前）
# 每项: (key, [关键词...])
NAME_PATTERNS: list[tuple[str, list[str]]] = [
    ("blink_talking", ["blink-talking", "blink_talking", "blinktalk", "open-closed", "open_closed"]),
    ("blink", ["blink", "closed-closed", "closed_closed", "eyes-closed", "eye-closed", "eyelid"]),
    ("talking", ["talking", "talk", "mouth-open", "mouth_open", "open-mouth", "open-open", "open_open"]),
    ("happy", ["happy"]),
    ("sad", ["sad"]),
    ("angry", ["angry"]),
    ("surprised", ["surprised", "surprise"]),
    ("click", ["click"]),
    ("drag", ["drag"]),
    ("idle", ["idle", "neutral", "closed-open", "closed_open", "still", "base"]),
]

STATE_LABELS = {
    "idle": "待机（嘴闭 / 眼睁）",
    "talking": "说话（嘴张 / 眼睁）",
    "blink": "眨眼（嘴闭 / 眼闭）",
    "blink_talking": "眨眼说话（嘴张 / 眼闭）",
    "happy": "开心",
    "sad": "难过",
    "angry": "生气",
    "surprised": "惊讶",
    "click": "点击",
    "drag": "拖拽",
}


@dataclass
class Project:
    source_format: str
    root: Path
    model_name: str = "avatar"
    images: dict[str, Path] = field(default_factory=dict)
    model_meta: dict = field(default_factory=dict)
    layered: bool = False
    note: str = ""

    def state_keys(self) -> list[str]:
        return list(self.images.keys())

    def has(self, key: str) -> bool:
        return key in self.images


def _norm_name(path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def _is_inside(root: Path, path: Path) -> bool:
    """路径 resolve 后是否仍位于 root 目录内，拒绝 ../ 越界引用。"""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _match_state_key(path: Path) -> Optional[str]:
    stem = _norm_name(path)
    for key, keywords in NAME_PATTERNS:
        for kw in keywords:
            kw_norm = re.sub(r"[^a-z0-9]+", "-", kw).strip("-")
            if kw_norm in stem:
                return key
    return None


def _load_model_json(root: Path) -> Optional[dict]:
    model_path = root / "model.json"
    if not model_path.exists():
        return None
    try:
        data = json.loads(model_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("model_type") and data.get("model_type") != "pngtuber":
        return None
    return data


def detect(project_dir: str | Path, exclude_dirs: Optional[list[Path]] = None) -> Project:
    root = Path(project_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return Project(source_format="unknown", root=root, note="目录不存在或不是文件夹")

    excluded = [p.resolve() for p in (exclude_dirs or [])]

    def _excluded(path: Path) -> bool:
        return any(_is_inside(e, path) for e in excluded)

    # 1) model.json 扁平包
    data = _load_model_json(root)
    if data is not None:
        png = data.get("pngtuber") if isinstance(data.get("pngtuber"), dict) else data
        images: dict[str, Path] = {}
        for field_name, key in MODEL_FIELD_MAP.items():
            rel = png.get(field_name)
            if not rel:
                continue
            candidate = (root / str(rel)).resolve()
            if not _is_inside(root, candidate):
                continue
            if candidate.exists():
                images[key] = candidate
            else:
                # 容忍文件名仅给了 basename
                hit = next((h for h in root.rglob(Path(str(rel)).name) if not _excluded(h)), None)
                if hit is not None:
                    images[key] = hit
        meta = {
            k: png.get(k)
            for k in ("scale", "offset_x", "offset_y", "mobile_scale", "mobile_offset_x", "mobile_offset_y", "mirror", "source_type")
            if k in png
        }
        return Project(
            source_format="simple_package",
            root=root,
            model_name=str(data.get("name") or root.name),
            images=images,
            model_meta=meta,
            layered=False,
            note="" if images else "model.json 中未解析到可用图片",
        )

    # 2) 分层工程探测（待适配）
    save_files = sorted(root.rglob("*.save"))
    if save_files:
        return Project(
            source_format="pngtuber_plus_save",
            root=root,
            model_name=root.name,
            layered=True,
            note="检测到 PNGTuber Plus .save 分层工程；当前版本尚未做图层合成，请提供样本以适配。",
        )

    remix_files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".pngremix"
    )
    if remix_files:
        return Project(
            source_format="pngtube_remix_pngremix",
            root=root,
            model_name=root.name,
            layered=True,
            note="检测到 PNGTube Remix .pngRemix 分层工程；当前版本尚未做 Godot Variant 图层合成，请提供样本以适配。",
        )

    # 3) 散图回退
    images = {}
    unknown: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if p.parent.name in {"layers"}:
            continue
        if _excluded(p):
            continue
        key = _match_state_key(p)
        if key and key not in images:
            images[key] = p
        elif key is None:
            unknown.append(p)

    if not images and not unknown:
        return Project(source_format="unknown", root=root, note="未找到任何图片或工程文件")

    return Project(
        source_format="loose_images",
        root=root,
        model_name=root.name,
        images=images,
        model_meta={},
        layered=False,
        note="未能按文件名归类的图片: " + ", ".join(p.name for p in unknown) if unknown else "",
    )
