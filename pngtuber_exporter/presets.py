# -*- coding: utf-8 -*-
"""导出预设档位与「AI 自动调参」本地规则。

- 三档预设：流畅优先 / 清晰优先 / 小体积优先，供小白用户一键套用；
- ``recommend`` 依据素材信息（帧数、分辨率、是否含透明、时长）与目标倾向，
  用本地规则给出推荐参数与可解释理由；不调用外部服务、不需要 API Key。

专业用户可在高级视图里逐项覆盖这里给出的任意参数。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------- 三档预设（跨模式通用基线） ----------

PRESET_ORDER = ("smooth", "sharp", "small")

PRESETS: dict[str, dict] = {
    "smooth": {
        "label": "流畅优先",
        "desc": "动作更顺滑、画质优先，体积相对偏大",
        "fps": 12,
        "frames": 12,
        "size": 768,
        "max_edge": 1024,
        "fmt": "apng",
        "blink_interval": 30,
        "blink_frames": 2,
        "talk_hold": 6,
        "idle_hold": 4,
        "duration": 3.0,
        "dither": True,
    },
    "sharp": {
        "label": "清晰优先",
        "desc": "分辨率与细节优先，适合静态或慢动作素材",
        "fps": 10,
        "frames": 12,
        "size": 768,
        "max_edge": 1024,
        "fmt": "gif",
        "blink_interval": 30,
        "blink_frames": 2,
        "talk_hold": 6,
        "idle_hold": 4,
        "duration": 3.0,
        "dither": False,
    },
    "small": {
        "label": "小体积优先",
        "desc": "优先压缩体积，适合聊天窗口 / 网页快速加载",
        "fps": 8,
        "frames": 10,
        "size": 512,
        "max_edge": 512,
        "fmt": "gif",
        "blink_interval": 30,
        "blink_frames": 2,
        "talk_hold": 6,
        "idle_hold": 4,
        "duration": 3.0,
        "dither": False,
    },
}

DEFAULT_PRESET = "sharp"

# 各模式真正读取的字段（便于统一套用预设）
MODE_FIELDS: dict[str, tuple[str, ...]] = {
    "project": ("fps", "blink_interval", "blink_frames", "talk_hold", "idle_hold", "max_edge", "fmt"),
    "sequence": ("fps", "max_edge", "fmt"),
    "record": ("duration", "fps", "max_edge", "fmt"),
    "model": ("fps", "frames", "size", "max_edge", "fmt"),
}


def preset_names() -> list[str]:
    return list(PRESET_ORDER)


def preset_label(key: str) -> str:
    return PRESETS.get(key, PRESETS[DEFAULT_PRESET])["label"]


def preset_for_mode(mode: str, preset_key: str) -> dict:
    """取某模式在指定档位下的参数子集（只保留该模式读取的字段）。"""
    base = PRESETS.get(preset_key, PRESETS[DEFAULT_PRESET])
    fields = MODE_FIELDS.get(mode, ())
    return {k: base[k] for k in fields if k in base}


@dataclass
class Recommendation:
    params: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def recommend(
    mode: str,
    info: Optional[dict] = None,
    goal: Optional[str] = None,
) -> Recommendation:
    """按素材信息给出推荐参数与理由（本地规则，可逐条解释）。

    参数:
        mode: project / sequence / record / model
        info: 可选素材信息，可含 ``frames``(帧数)、``width/height``(像素)、
              ``has_alpha``(是否含半透明)、``duration``(秒)。
        goal: smooth / sharp / small / None（None 表示按素材自动权衡）。
    """
    info = info or {}
    reasons: list[str] = []

    # 1) 先选基线档位
    if goal in PRESETS:
        base_key = goal
    elif info.get("has_alpha"):
        # 带透明边缘的素材，无损格式更能保住边缘
        base_key = "smooth"
        reasons.append("素材含透明边缘，已优先选用 APNG 无损格式以避免边缘被量化出锯齿。")
    elif (info.get("frames") or 0) > 30 or (info.get("duration") or 0) > 5:
        base_key = "small"
        reasons.append("帧数 / 时长较长，已适当降低帧率与边长以控制最终体积。")
    else:
        base_key = DEFAULT_PRESET

    params = preset_for_mode(mode, base_key)
    reasons.insert(0, f"套用「{preset_label(base_key)}」基线预设。")

    # 2) 依据分辨率收敛边长上限
    w = info.get("width") or 0
    h = info.get("height") or 0
    if w and h:
        if max(w, h) <= 512:
            params["max_edge"] = 512
            reasons.append("素材本身分辨率不高，边长上限设为 512，避免放大模糊。")
        elif max(w, h) >= 1500:
            params["max_edge"] = 1024
            reasons.append("素材分辨率较高，边长上限保留 1024 以保住细节。")

    # 3) PNGTuber 立绘：细节与半透明边缘多，优先 APNG 无损以保住线条与渐变
    if mode == "project" and not goal:
        params["fmt"] = "apng"
        reasons.append(
            "立绘的线条、发丝与半透明边缘较多，已选用 APNG 无损格式，画面最接近原图；"
            "若需兼容只支持 GIF 的老播放器，可在高级设置里改回 GIF。"
        )

    # 4) 动作幅度大的素材保帧率（规则占位：后续可结合帧间差判定）
    if info.get("busy"):
        params["fps"] = max(params.get("fps", 10), 12)
        reasons.append("画面动作较频繁，已提高帧率以减少卡顿感。")

    return Recommendation(params=params, reasons=reasons)
