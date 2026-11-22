# -*- coding: utf-8 -*-
"""帧序列编排与透明 GIF 导出。"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import Image, ImageChops, ImageFilter, ImageOps

from .frames import StateAsset


@dataclass
class RenderOptions:
    fps: int = 10
    blink_interval: int = 30      # 待机状态下每隔多少帧出现一次眨眼
    blink_frames: int = 2         # 每次眨眼持续帧数
    talk_hold: int = 6            # 说话段嘴张停留帧数
    idle_hold: int = 4            # 说话段嘴闭停留帧数
    max_edge: int = 1024          # 输出边长上限（0 不限制）
    dither: bool = False          # GIF 是否启用 Floyd–Steinberg 抖动（平涂立绘建议关闭，避免网点脏色）
    bg_color: Optional[tuple[int, int, int, int]] = None  # 不透明底色；None 保留透明背景

    def __post_init__(self) -> None:
        # 帧计数 / 帧率下限钳制，避免 0 或负值把眨眼、说话段编排成异常次数
        self.fps = max(1, int(self.fps))
        self.blink_interval = max(1, int(self.blink_interval))
        self.blink_frames = max(1, int(self.blink_frames))
        self.talk_hold = max(1, int(self.talk_hold))
        self.idle_hold = max(1, int(self.idle_hold))


def _fit_size(w: int, h: int, max_edge: int) -> tuple[int, int]:
    if max_edge and max(w, h) > max_edge:
        scale = max_edge / max(w, h)
        return max(1, round(w * scale)), max(1, round(h * scale))
    return w, h


def _clean_alpha_edges(rgba: Image.Image, lo: int = 16, hi: int = 240) -> Image.Image:
    """清理半透明边缘，避免脏色 / 色散进入 GIF 调色板。

    - alpha 软阈值：极透明归全透、接近不透明归全不透明，中间保留；
    - 半透明边缘像素的颜色用主体轻微模糊后的颜色回填，去除边缘杂色。
    """
    rgba = rgba.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda v: 0 if v < lo else (255 if v > hi else v))
    edge_mask = alpha.point(lambda v: 255 if 0 < v < 255 else 0)
    if edge_mask.getbbox():
        # 分别模糊 RGB 与 alpha，避免透明区的黑色 RGB 经整图模糊染暗边缘线条
        r, g, b, a = rgba.split()
        rgb = Image.merge("RGB", (r, g, b)).filter(ImageFilter.GaussianBlur(5))
        rb, gb, bb = rgb.split()
        blurred = Image.merge("RGBA", (rb, gb, bb, a))
        rgba.paste(blurred, (0, 0), edge_mask)
    rgba.putalpha(alpha)
    return rgba


def _place(
    asset: StateAsset,
    canvas_w: int,
    canvas_h: int,
    meta: dict,
    frame_idx: int = 0,
) -> Image.Image:
    img = asset.frames[frame_idx % len(asset.frames)].copy()
    if meta.get("mirror"):
        img = ImageOps.mirror(img)

    # 应用 model.json 里的整体缩放系数（scale），缺省 1.0 不缩放
    try:
        scale = float(meta.get("scale", 1) or 1)
    except (TypeError, ValueError):
        scale = 1.0
    if scale > 0 and abs(scale - 1.0) > 1e-3:
        nw = max(1, round(img.width * scale))
        nh = max(1, round(img.height * scale))
        img = img.resize((nw, nh), Image.LANCZOS)

    scale = min(canvas_w / img.width, canvas_h / img.height)
    if abs(scale - 1.0) > 1e-3:
        img = img.resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
            Image.LANCZOS,
        )

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    ox = int(meta.get("offset_x", 0) or 0)
    oy = int(meta.get("offset_y", 0) or 0)
    x = (canvas_w - img.width) // 2 + ox
    y = (canvas_h - img.height) // 2 + oy
    canvas.alpha_composite(img, (x, y))
    return canvas


def _canvas_size(assets: dict[str, StateAsset], max_edge: int) -> tuple[int, int]:
    w = max(a.first.width for a in assets.values())
    h = max(a.first.height for a in assets.values())
    return _fit_size(w, h, max_edge)


def build_idle_groups(
    assets: dict[str, StateAsset], opt: RenderOptions, meta: dict
) -> list[tuple[Image.Image, int]]:
    """待机循环：返回 ``[(代表帧, 重复次数), ...]``，每种状态只合成一次。"""
    idle = assets["idle"]
    blink = assets.get("blink")
    cw, ch = _canvas_size(assets, opt.max_edge)

    if blink is None:
        # 无眨眼素材：待机为静态单帧循环
        return [(_place(idle, cw, ch, meta), 1)]

    period = max(opt.blink_interval, opt.blink_frames + 1)
    idle_hold = period - opt.blink_frames
    idle_img = _place(idle, cw, ch, meta)
    if idle_hold <= 0:
        return [(_place(blink, cw, ch, meta), period)]
    blink_img = _place(blink, cw, ch, meta)
    return [(idle_img, idle_hold), (blink_img, opt.blink_frames)]


def build_talk_groups(
    assets: dict[str, StateAsset], opt: RenderOptions, meta: dict
) -> list[tuple[Image.Image, int]]:
    """说话循环：返回 ``[(代表帧, 重复次数), ...]``，每种状态只合成一次。"""
    idle = assets["idle"]
    talk = assets.get("talking", idle)
    cw, ch = _canvas_size(assets, opt.max_edge)
    idle_img = _place(idle, cw, ch, meta)
    talk_img = _place(talk, cw, ch, meta)
    return [
        (idle_img, max(1, opt.idle_hold)),
        (talk_img, max(1, opt.talk_hold)),
    ]


FORMATS = ("gif", "apng")
FORMAT_SUFFIX = {"gif": ".gif", "apng": ".png"}


def _durations(frames: list[Image.Image], fps: int) -> list[int]:
    duration = max(20, round(1000 / fps))
    return [duration] * len(frames)


def _same_image(a: Image.Image, b: Image.Image) -> bool:
    if a.size != b.size:
        return False
    a = a.convert("RGBA")
    b = b.convert("RGBA")
    # 注意：PIL 在 RGBA 上 getbbox() 会把 alpha 纳入判定，alpha 全 0 差异时
    # 即使 RGB 明显不同也会误返回 None。因此 RGB 与 alpha 通道分别比较。
    if ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is not None:
        return False
    return ImageChops.difference(a.getchannel("A"), b.getchannel("A")).getbbox() is None


def _collapse(frames: list[Image.Image]) -> list[tuple[Image.Image, int]]:
    """合并连续完全相同的帧，返回 ``[(代表帧, 重复次数), ...]``，避免重复帧撑大体积。"""
    groups: list[list[object]] = []
    for f in frames:
        rgba = f.convert("RGBA")
        if groups and _same_image(groups[-1][0], rgba):
            groups[-1][1] += 1  # type: ignore[index]
        else:
            groups.append([rgba, 1])
    return [(img, n) for img, n in groups]  # type: ignore[return-value]


def _dither_flag(dither: bool) -> int:
    if dither:
        return getattr(Image.Dither, "FLOYDSTEINBERG", Image.FLOYDSTEINBERG)
    return getattr(Image.Dither, "NONE", Image.NONE)


def _prepare_gif_frames(
    frames: list[Image.Image],
    dither: bool,
    bg_color: Optional[tuple[int, int, int, int]] = None,
) -> list[Image.Image]:
    """把 RGBA 帧序列整理成 GIF 友好的 256 色调色板帧。

    - 先做透明边缘清理，避免半透明脏色 / 细线条色散进调色板；
    - 所有帧拼成一张纵向大图统一量化一次，得到全局共享调色板，
      避免逐帧独立调色板造成的颜色闪烁与体积膨胀；
    - 指定底色时先合成到不透明背景，再用 RGB 中位切分量化（画质最佳）；
    - 保留透明时用 Octree 量化（RGBA 仅支持该方式）。
    """
    dither_flag = _dither_flag(dither)
    prepared: list[Image.Image] = []
    for f in frames:
        rgba = _clean_alpha_edges(f)
        if bg_color is not None:
            canvas = Image.new("RGBA", rgba.size, bg_color)
            canvas.alpha_composite(rgba)
            prepared.append(canvas.convert("RGB"))
        else:
            prepared.append(rgba)

    w = max(i.width for i in prepared)
    h = sum(i.height for i in prepared)
    sheet = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    for im in prepared:
        sheet.paste(im, (0, y))
        y += im.height

    if bg_color is not None:
        palette = sheet.convert("RGB").quantize(
            colors=256, method=Image.MEDIANCUT, dither=dither_flag
        )
        return [p.quantize(palette=palette, dither=dither_flag) for p in prepared]

    # 透明 RGBA 仅支持 Octree 量化（Pillow 不允许外部 palette 作用于 RGBA），逐帧处理
    return [
        p.quantize(colors=256, method=Image.FASTOCTREE, dither=dither_flag)
        for p in prepared
    ]


def _composite_bg(img: Image.Image, bg_color: tuple[int, int, int, int]) -> Image.Image:
    canvas = Image.new("RGBA", img.size, bg_color)
    canvas.alpha_composite(img.convert("RGBA"))
    return canvas


def _build_ffmpeg_palette(
    frames: list[Image.Image],
    bg_color: Optional[tuple[int, int, int, int]] = None,
) -> Optional[Image.Image]:
    """用 ffmpeg ``palettegen`` 生成全局 256 色调色板（P 模式）。

    ffmpeg 只负责挑选调色板，最终 GIF 仍由 Pillow 编码：这样既拿到 ffmpeg
    更好的色彩 / 边缘统计，又能保留去重后的代表帧与逐帧加权延迟，
    避免 image2/concat 帧率方案无法表达不等长帧间隔的问题。
    ffmpeg 不可用或失败时返回 None，由调用方回退 Pillow 全局调色板。
    """
    from . import deps

    ff = deps.detect_ffmpeg()
    if not ff:
        return None

    tmp = Path(tempfile.mkdtemp(prefix="gifpal_"))
    try:
        for i, f in enumerate(frames, start=1):
            rgba = _clean_alpha_edges(f)
            if bg_color is not None:
                canvas = Image.new("RGBA", rgba.size, bg_color)
                canvas.alpha_composite(rgba)
                frame: Image.Image = canvas.convert("RGB")
            else:
                frame = rgba
            frame.save(tmp / f"frame_{i:03d}.png")

        pal = tmp / "palette.png"
        subprocess.run(
            [ff, "-y", "-start_number", "1", "-i", str(tmp / "frame_%03d.png"),
             "-vf", "palettegen=stats_mode=diff:reserve_transparent=1", str(pal)],
            check=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        return Image.open(pal).convert("P")
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def save_animated(
    frames: list[Image.Image],
    out_path: Path,
    fps: int,
    fmt: str = "gif",
    loop: int = 0,
    dither: bool = False,
    bg_color: Optional[tuple[int, int, int, int]] = None,
) -> None:
    """通用动画导出。fmt='gif' 为 256 色 GIF；fmt='apng' 为保留全彩半透明的 APNG。"""
    if not frames:
        raise ValueError("没有可导出的帧")
    if fmt not in FORMATS:
        raise ValueError(f"不支持的输出格式: {fmt}（可选 {', '.join(FORMATS)}）")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fps = max(1, int(fps))

    # 归一化为 [(代表帧, 重复次数), ...]：编排路径直接带次数；普通帧序列先合并连续同帧
    if isinstance(frames[0], tuple):
        groups = [(img, max(1, int(n))) for img, n in frames]
    else:
        groups = _collapse(frames)

    reps = [img for img, _ in groups]
    base = max(20, round(1000 / fps))
    durations = [base * count for _, count in groups]

    # 指定不透明底色时，先把各帧合成到底色（APNG / Pillow 回退路径共用）
    if bg_color is not None:
        reps = [_composite_bg(img, bg_color) for img in reps]

    if fmt == "apng":
        # APNG 直接保留 RGBA 全彩与半透明边缘，不做 256 色量化，细节最接近原图
        reps[0].save(
            out_path,
            format="PNG",
            save_all=True,
            append_images=reps[1:],
            duration=durations,
            loop=loop,
            disposal=2,
        )
        return

    # GIF 量化：不透明底色帧可复用 ffmpeg 统计的全局调色板；透明场景保持 RGBA
    # 交 Pillow 编码器——本机 Pillow 12.x 预量化（Octree/ADAPTIVE）会丢弃透明索引，
    # 直接传 RGBA 才能保留透明背景。保留去重代表帧与逐帧加权延迟。
    dither_flag = _dither_flag(dither)
    if bg_color is not None:
        palette = _build_ffmpeg_palette(reps, bg_color)
        if palette is not None:
            palette_frames = [
                f.convert("RGB").quantize(palette=palette, dither=dither_flag)
                for f in reps
            ]
        else:
            palette_frames = _prepare_gif_frames(reps, dither=dither, bg_color=bg_color)
    else:
        palette_frames = [_clean_alpha_edges(f) for f in reps]
    palette_frames[0].save(
        out_path,
        format="GIF",
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=loop,
        disposal=2,
        optimize=True,
    )


def save_gif(frames: list[Image.Image], out_path: Path, fps: int) -> None:
    save_animated(frames, out_path, fps, fmt="gif")


def normalize_frames(
    frames: list[Image.Image],
    max_edge: int = 0,
    background: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> list[Image.Image]:
    """统一帧尺寸：取最大宽高，等比缩放到边长上限后居中合成到画布。"""
    if not frames:
        return frames
    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    cw, ch = _fit_size(w, h, max_edge)
    out: list[Image.Image] = []
    for f in frames:
        f = f.convert("RGBA")
        scale = min(cw / f.width, ch / f.height)
        if abs(scale - 1.0) > 1e-3:
            f = f.resize(
                (max(1, round(f.width * scale)), max(1, round(f.height * scale))),
                Image.LANCZOS,
            )
        canvas = Image.new("RGBA", (cw, ch), background)
        canvas.alpha_composite(f, ((cw - f.width) // 2, (ch - f.height) // 2))
        out.append(canvas)
    return out


def save_plain_gif(
    frames: list[Image.Image],
    out_path: Path,
    fps: int,
    loop: int = 0,
    fmt: str = "gif",
    dither: bool = True,
) -> None:
    """通用帧序列 -> 循环动画（不做 PNGTuber 状态编排，保留帧自身背景）。"""
    save_animated(frames, out_path, fps, fmt=fmt, loop=loop, dither=dither)


EMOTION_KEYS = ("happy", "sad", "angry", "surprised")


@dataclass
class ExportResult:
    idle_gif: Path | None = None
    talk_gif: Path | None = None
    emotion_gifs: dict[str, Path] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def export_project(
    assets: dict[str, StateAsset],
    out_dir: Path,
    opt: RenderOptions,
    meta: dict,
    name: str,
    fmt: str = "gif",
) -> ExportResult:
    result = ExportResult()
    if "idle" not in assets:
        result.warnings.append("缺少 idle（待机）图，无法导出。")
        return result

    suffix = FORMAT_SUFFIX.get(fmt, ".gif")
    cw, ch = _canvas_size(assets, opt.max_edge)

    idle_groups = build_idle_groups(assets, opt, meta)
    idle_path = out_dir / f"{name}_idle{suffix}"
    save_animated(idle_groups, idle_path, opt.fps, fmt=fmt, dither=opt.dither, bg_color=opt.bg_color)
    result.idle_gif = idle_path

    if "talking" in assets:
        talk_groups = build_talk_groups(assets, opt, meta)
        talk_path = out_dir / f"{name}_talk{suffix}"
        save_animated(talk_groups, talk_path, opt.fps, fmt=fmt, dither=opt.dither, bg_color=opt.bg_color)
        result.talk_gif = talk_path
    else:
        result.warnings.append("缺少 talking（说话）图，仅导出待机 GIF。")

    # 情绪差分：happy / sad / angry / surprised 各导出一张静态循环动画
    for key in EMOTION_KEYS:
        if key in assets:
            emo_frames = [_place(assets[key], cw, ch, meta)]
            emo_path = out_dir / f"{name}_{key}{suffix}"
            save_animated(emo_frames, emo_path, opt.fps, fmt=fmt, dither=opt.dither, bg_color=opt.bg_color)
            result.emotion_gifs[key] = emo_path

    return result
