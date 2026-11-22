# -*- coding: utf-8 -*-
"""屏幕 / 窗口抓帧：把模型、软件等在原软件里运行的画面录成帧序列。"""
from __future__ import annotations

import math
import time
from typing import Optional

from PIL import Image

try:
    import mss  # 纯 ctypes 跨平台截屏
    # 兼容不同版本：优先长期稳定的小写主类 mss，回退大写别名 MSS
    _MSS = getattr(mss, "mss", None) or getattr(mss, "MSS", None)
except ImportError:  # pragma: no cover - 打包环境应具备
    mss = None  # type: ignore
    _MSS = None  # type: ignore

Region = dict  # {"left", "top", "width", "height"}
_DPI_DONE = False


def _init_dpi() -> None:
    """声明进程 DPI 感知，避免高缩放屏下窗口/屏幕矩形被系统缩放导致偏移。"""
    global _DPI_DONE
    if _DPI_DONE:
        return
    _DPI_DONE = True
    try:
        import ctypes

        # -4 = PER_MONITOR_AWARENESS_V2；老系统回退到系统级 DPI 感知
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                ctypes.windll.user32.SetProcessDPIAware()
    except OSError:
        pass


def primary_monitor() -> Region:
    """主显示器区域。"""
    if mss is None:
        return {"left": 0, "top": 0, "width": 1920, "height": 1080}
    _init_dpi()
    with _MSS() as sct:
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        return {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}


def list_windows() -> list[dict]:
    """枚举可见的顶层窗口（仅 Windows），返回标题与屏幕矩形。"""
    windows: list[dict] = []
    try:
        import ctypes
        from ctypes import wintypes

        _init_dpi()
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _enum(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.IsIconic(hwnd):  # 跳过最小化窗口
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
            if not title:
                return True
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if rect.right <= rect.left or rect.bottom <= rect.top:
                return True
            windows.append(
                {
                    "hwnd": int(hwnd),
                    "title": title,
                    "region": {
                        "left": rect.left,
                        "top": rect.top,
                        "width": rect.right - rect.left,
                        "height": rect.bottom - rect.top,
                    },
                }
            )
            return True

        user32.EnumWindows(WNDENUMPROC(_enum), 0)
    except (AttributeError, OSError):
        pass
    return windows


def grab(region: Region) -> Image.Image:
    """抓取指定区域一帧，返回 RGBA 图像。"""
    if mss is None:
        raise RuntimeError("截屏模块 mss 未安装")
    _init_dpi()
    with _MSS() as sct:
        shot = sct.grab(region)
        rgb = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return rgb.convert("RGBA")


def record(
    region: Region,
    duration: float,
    fps: int,
    on_tick: Optional[callable] = None,
    max_edge: int = 0,
) -> list[Image.Image]:
    """定时抓取区域画面，返回 RGB 帧序列。

    - 用 ``perf_counter`` 计时，避免 ``time.sleep`` 累积漂移；
    - 抓帧即按 ``max_edge`` 等比缩小，以 RGB 存储，压低全屏帧的内存占用；
    - 总帧数按 ``duration × fps`` 封顶，防止异常循环无限膨胀。
    """
    if mss is None:
        raise RuntimeError("截屏模块 mss 未安装")
    _init_dpi()
    fps = max(1, fps)
    interval = 1.0 / fps
    duration = max(0.1, duration)
    max_frames = math.ceil(duration * fps)
    frames: list[Image.Image] = []
    start = time.perf_counter()
    with _MSS() as sct:
        while len(frames) < max_frames and time.perf_counter() - start < duration:
            t0 = time.perf_counter()
            shot = sct.grab(region)
            rgb = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            if max_edge and max(rgb.size) > max_edge:
                scale = max_edge / max(rgb.size)
                rgb = rgb.resize(
                    (max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale))),
                    Image.LANCZOS,
                )
            frames.append(rgb)
            if on_tick:
                on_tick(len(frames))
            wait = interval - (time.perf_counter() - t0)
            if wait > 0:
                time.sleep(wait)
    return frames
