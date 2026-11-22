# -*- coding: utf-8 -*-
"""PNGTuber / 帧序列 / 录屏 -> GIF 图形界面（Tkinter）。"""
from __future__ import annotations

import threading
import traceback
import webbrowser
from pathlib import Path
from tkinter import Tk, StringVar, filedialog, messagebox
from tkinter import ttk, Text, END

from . import deps, presets
from .capture import list_windows, primary_monitor, record
from .detect import detect, STATE_LABELS
from .frames import load_project_images
from .render import FORMAT_SUFFIX, RenderOptions, export_project, normalize_frames, save_plain_gif
from .sequence import load_sequence_images
from .web_render import classify_model, render_model


class App:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title("PNGTuber / 帧序列 / 录屏 → GIF 一键导出")
        root.geometry("760x680")
        root.minsize(720, 600)

        self.project = None
        self._windows: list[dict] = []
        self._env_ready = False

        # 简易/高级视图；档位预设（小白一键套用，专业可逐项覆盖）
        self.ui_mode = StringVar(value="easy")
        self.preset_key = StringVar(value=presets.DEFAULT_PRESET)
        self._easy_boxes: list[ttk.Frame] = []
        self._adv_boxes: list[ttk.Widget] = []

        self._build_top_bar()
        self._build_notebook()
        self._build_log()
        self.check_env()

    # ---------- 顶部：视图切换 ----------
    def _build_top_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        bar.pack(fill="x")
        ttk.Label(bar, text="界面模式：").pack(side="left")
        ttk.Radiobutton(bar, text="简易（小白）", variable=self.ui_mode, value="easy",
                         command=self._apply_view).pack(side="left", padx=(4, 16))
        ttk.Radiobutton(bar, text="高级（专业）", variable=self.ui_mode, value="adv",
                         command=self._apply_view).pack(side="left")
        ttk.Label(bar, text="简易只选档位即可；高级可逐项调整帧率 / 帧数 / 边长等全部参数",
                  foreground="#777").pack(side="right")

    def _apply_view(self) -> None:
        advanced = self.ui_mode.get() == "adv"
        for w in self._adv_boxes:
            w.grid() if advanced else w.grid_remove()
        for f in self._easy_boxes:
            f.grid() if not advanced else f.grid_remove()

    # ---------- 布局 ----------
    def _build_notebook(self) -> None:
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        self._build_project_tab()
        self._build_sequence_tab()
        self._build_record_tab()
        self._build_model_tab()
        self._build_help_tab()

    # ===== Tab 1: PNGTuber 工程 =====
    def _build_project_tab(self) -> None:
        frm = ttk.Frame(self.nb, padding=10)
        self.nb.add(frm, text="PNGTuber 工程")

        self.project_dir = StringVar()
        self.out_dir = StringVar()

        ttk.Label(frm, text="工程文件夹:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.project_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(frm, text="浏览…", command=self._choose_project).grid(row=0, column=2)
        ttk.Label(frm, text="输出目录:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.out_dir).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(frm, text="浏览…", command=self._choose_out).grid(row=1, column=2, pady=(8, 0))
        frm.columnconfigure(1, weight=1)

        self.info = ttk.Label(frm, text="尚未识别工程。选择或粘贴文件夹路径后自动解析。", foreground="#555")
        self.info.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.tree = ttk.Treeview(frm, columns=("state", "file", "label"), height=6, show="headings")
        self.tree.heading("state", text="状态")
        self.tree.heading("file", text="图片文件")
        self.tree.heading("label", text="说明")
        self.tree.column("state", width=110)
        self.tree.column("file", width=260)
        self.tree.column("label", width=260)
        self.tree.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        # 工程专属参数
        self.fps = StringVar(value="10")
        self.blink_interval = StringVar(value="30")
        self.blink_frames = StringVar(value="2")
        self.talk_hold = StringVar(value="6")
        self.idle_hold = StringVar(value="4")
        self.max_edge = StringVar(value="1024")
        self.project_fmt = StringVar(value="apng")

        self._easy_block(frm, 4, "project", "选好工程文件夹后，点「一键导出」即可；想细调可切到顶部「高级」。")

        p = ttk.LabelFrame(frm, text="导出参数（高级）", padding=10)
        p.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._adv_boxes.append(p)
        rows = [
            ("帧率 FPS", self.fps, "眨眼间隔(帧)", self.blink_interval),
            ("眨眼帧数", self.blink_frames, "说话停留(帧)", self.talk_hold),
            ("待机停留(帧)", self.idle_hold, "边长上限", self.max_edge),
        ]
        for r, (l1, v1, l2, v2) in enumerate(rows):
            ttk.Label(p, text=l1).grid(row=r, column=0, sticky="w")
            ttk.Entry(p, textvariable=v1, width=8).grid(row=r, column=1, padx=(6, 18))
            ttk.Label(p, text=l2).grid(row=r, column=2, sticky="w")
            ttk.Entry(p, textvariable=v2, width=8).grid(row=r, column=3, padx=(6, 0))

        ttk.Label(p, text="输出格式").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(p, textvariable=self.project_fmt, state="readonly", width=8,
                     values=["gif", "apng"]).grid(row=3, column=1, padx=(6, 0), pady=(10, 0))
        ttk.Button(p, text="识别工程", command=self.detect_project).grid(row=3, column=2, pady=(10, 0))
        self.export_btn = ttk.Button(p, text="一键导出", command=self.do_export)
        self.export_btn.grid(row=3, column=3, sticky="e", pady=(10, 0))

    # ===== Tab 2: 帧序列目录 =====
    def _build_sequence_tab(self) -> None:
        frm = ttk.Frame(self.nb, padding=10)
        self.nb.add(frm, text="帧序列目录")

        self.seq_dir = StringVar()
        self.seq_out = StringVar()
        self.seq_fps = StringVar(value="10")
        self.seq_max_edge = StringVar(value="1024")
        self.seq_fmt = StringVar(value="gif")

        ttk.Label(frm, text="帧图片目录:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.seq_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(frm, text="浏览…", command=self._choose_seq).grid(row=0, column=2)
        ttk.Label(frm, text="输出目录:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.seq_out).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(frm, text="浏览…", command=self._choose_seq_out).grid(row=1, column=2, pady=(8, 0))
        frm.columnconfigure(1, weight=1)

        tip = ttk.Label(frm, text="按文件名自然排序读取 PNG/JPG/WebP/GIF；动图素材会展开为多帧。", foreground="#555")
        tip.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self._easy_block(frm, 3, "sequence", "选好图片目录，点「导出帧序列动画」即可；文件按文件名自动排序。")

        p = ttk.LabelFrame(frm, text="导出参数（高级）", padding=10)
        p.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._adv_boxes.append(p)
        ttk.Label(p, text="帧率 FPS").grid(row=0, column=0, sticky="w")
        ttk.Entry(p, textvariable=self.seq_fps, width=8).grid(row=0, column=1, padx=(6, 18))
        ttk.Label(p, text="边长上限").grid(row=0, column=2, sticky="w")
        ttk.Entry(p, textvariable=self.seq_max_edge, width=8).grid(row=0, column=3, padx=(6, 0))
        ttk.Label(p, text="输出格式").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(p, textvariable=self.seq_fmt, state="readonly", width=8,
                     values=["gif", "apng"]).grid(row=1, column=1, padx=(6, 0), pady=(10, 0))

        self.seq_btn = ttk.Button(p, text="导出帧序列动画", command=self.do_sequence)
        self.seq_btn.grid(row=1, column=3, sticky="e", pady=(10, 0))

    # ===== Tab 3: 屏幕 / 窗口录屏 =====
    def _build_record_tab(self) -> None:
        frm = ttk.Frame(self.nb, padding=10)
        self.nb.add(frm, text="屏幕录制")

        self.rec_mode = StringVar(value="full")
        self.rec_window = StringVar()
        self.rec_custom = StringVar()
        self.rec_out = StringVar()
        self.rec_duration = StringVar(value="3")
        self.rec_fps = StringVar(value="10")
        self.rec_max_edge = StringVar(value="1024")
        self.rec_fmt = StringVar(value="gif")

        ttk.Label(frm, text="录制对象:").grid(row=0, column=0, sticky="w")
        mode = ttk.Frame(frm)
        mode.grid(row=0, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(mode, text="全屏", variable=self.rec_mode, value="full").pack(side="left")
        ttk.Radiobutton(mode, text="指定窗口", variable=self.rec_mode, value="window").pack(side="left", padx=(16, 0))
        ttk.Radiobutton(mode, text="自定义区域", variable=self.rec_mode, value="custom").pack(side="left", padx=(16, 0))

        self.win_combo = ttk.Combobox(frm, textvariable=self.rec_window, state="readonly", width=48)
        self.win_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(frm, text="刷新窗口", command=self._refresh_windows).grid(row=1, column=2, pady=(8, 0))

        ttk.Label(frm, text="区域 left,top,w,h:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.rec_custom).grid(row=2, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Label(frm, text="输出目录:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.rec_out).grid(row=3, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(frm, text="浏览…", command=self._choose_rec_out).grid(row=3, column=2, pady=(8, 0))
        frm.columnconfigure(1, weight=1)

        tip = ttk.Label(frm, text="把 3D 模型或软件画面在原软件里跑起来，录制它的窗口或区域即可生成 GIF。", foreground="#555")
        tip.grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self._easy_block(frm, 5, "record", "先在原软件里把模型跑起来，再选窗口 / 区域录制；结束后自动导出。")

        p = ttk.LabelFrame(frm, text="录制参数（高级）", padding=10)
        p.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._adv_boxes.append(p)
        ttk.Label(p, text="时长(秒)").grid(row=0, column=0, sticky="w")
        ttk.Entry(p, textvariable=self.rec_duration, width=8).grid(row=0, column=1, padx=(6, 18))
        ttk.Label(p, text="帧率 FPS").grid(row=0, column=2, sticky="w")
        ttk.Entry(p, textvariable=self.rec_fps, width=8).grid(row=0, column=3, padx=(6, 0))
        ttk.Label(p, text="边长上限").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(p, textvariable=self.rec_max_edge, width=8).grid(row=1, column=1, padx=(6, 18), pady=(8, 0))
        ttk.Label(p, text="输出格式").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Combobox(p, textvariable=self.rec_fmt, state="readonly", width=8,
                     values=["gif", "apng"]).grid(row=1, column=3, padx=(6, 0), pady=(8, 0))

        self.rec_btn = ttk.Button(p, text="开始录制并导出", command=self.do_record)
        self.rec_btn.grid(row=2, column=3, sticky="e", pady=(8, 0))

        self._refresh_windows()

    # ===== Tab 4: 3D 模型（VRM / GLB） =====
    def _build_model_tab(self) -> None:
        frm = ttk.Frame(self.nb, padding=10)
        self.nb.add(frm, text="3D 模型（VRM / GLB）")

        self.model_file = StringVar()
        self.model_out = StringVar()
        self.model_fps = StringVar(value="10")
        self.model_frames = StringVar(value="12")
        self.model_size = StringVar(value="768")
        self.model_max_edge = StringVar(value="1024")
        self.model_fmt = StringVar(value="gif")

        ttk.Label(frm, text="模型文件:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.model_file).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(frm, text="浏览…", command=self._choose_model).grid(row=0, column=2)
        ttk.Label(frm, text="输出目录:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.model_out).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(frm, text="浏览…", command=self._choose_model_out).grid(row=1, column=2, pady=(8, 0))
        frm.columnconfigure(1, weight=1)

        self.model_info = ttk.Label(
            frm,
            text="支持 .vrm/.glb/.gltf（VRM 3D）；选择模型文件或所在文件夹均可。",
            foreground="#555",
        )
        self.model_info.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        # 运行环境状态区：检测 Node / 浏览器，缺失时提供下载入口
        env = ttk.LabelFrame(frm, text="运行环境（模型渲染依赖）", padding=10)
        env.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.env_node = ttk.Label(env, text="检测中…")
        self.env_node.grid(row=0, column=0, sticky="w")
        self.env_browser = ttk.Label(env, text="")
        self.env_browser.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.env_refresh = ttk.Button(env, text="重新检测", command=self.check_env)
        self.env_refresh.grid(row=0, column=2, padx=(16, 6))
        self.env_dl_node = ttk.Button(env, text="下载 Node", command=self.dl_node)
        self.env_dl_node.grid(row=1, column=2, padx=(16, 6))
        self.env_dl_browser = ttk.Button(env, text="下载浏览器", command=self.dl_browser)
        self.env_dl_browser.grid(row=1, column=3, padx=(0, 0))

        self._easy_block(frm, 4, "model", "选模型文件或文件夹，环境就绪后点「渲染并导出动画」；动作沿用模型自带待机循环。")

        p = ttk.LabelFrame(frm, text="渲染参数（高级）", padding=10)
        p.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._adv_boxes.append(p)
        ttk.Label(p, text="帧率 FPS").grid(row=0, column=0, sticky="w")
        ttk.Entry(p, textvariable=self.model_fps, width=8).grid(row=0, column=1, padx=(6, 18))
        ttk.Label(p, text="渲染帧数").grid(row=0, column=2, sticky="w")
        ttk.Entry(p, textvariable=self.model_frames, width=8).grid(row=0, column=3, padx=(6, 0))
        ttk.Label(p, text="画布边长").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(p, textvariable=self.model_size, width=8).grid(row=1, column=1, padx=(6, 18), pady=(8, 0))
        ttk.Label(p, text="边长上限").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(p, textvariable=self.model_max_edge, width=8).grid(row=1, column=3, padx=(6, 0), pady=(8, 0))
        ttk.Label(p, text="输出格式").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(p, textvariable=self.model_fmt, state="readonly", width=8,
                     values=["gif", "apng"]).grid(row=2, column=1, padx=(6, 0), pady=(10, 0))

        self.model_btn = ttk.Button(p, text="渲染并导出动画", command=self.do_model)
        self.model_btn.grid(row=2, column=3, sticky="e", pady=(10, 0))

    # ===== Tab 5: 使用帮助 =====
    def _build_help_tab(self) -> None:
        frm = ttk.Frame(self.nb, padding=10)
        self.nb.add(frm, text="使用帮助")
        box = Text(frm, wrap="word", padx=10, pady=10, background="#fafafa", relief="flat")
        box.pack(fill="both", expand=True)
        help_text = HELP_TEXT
        box.insert("1.0", help_text)
        box.configure(state="disabled")

    def _build_log(self) -> None:
        frm = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        frm.pack(fill="both", expand=True)
        self.log = Text(frm, height=9, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

    # ---------- 通用辅助 ----------
    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(END, text + "\n")
        self.log.see(END)
        self.log.configure(state="disabled")

    @staticmethod
    def _iv(var: StringVar, default: int, *, allow_zero: bool = False) -> int:
        try:
            v = int(float(var.get()))
            return max(0, v) if allow_zero else max(1, v)
        except ValueError:
            return default

    def _out_dir(self, var: StringVar, fallback: Path) -> Path:
        d = var.get().strip()
        return Path(d) if d else fallback

    # ---------- 档位预设 / AI 推荐 ----------
    def _easy_block(self, parent: ttk.Frame, row: int, mode: str, hint: str) -> None:
        box = ttk.Frame(parent)
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Label(box, text="画质档位:").pack(side="left")
        cb = ttk.Combobox(box, textvariable=self.preset_key, state="readonly", width=12,
                           values=presets.preset_names())
        cb.pack(side="left", padx=(6, 12))
        cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset(mode))
        ttk.Button(box, text="AI 自动推荐", command=lambda: self._ai_recommend(mode)).pack(side="right")
        ttk.Label(parent, text=hint, foreground="#777").grid(
            row=row + 1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self._easy_boxes.append(box)

    def _apply_preset(self, mode: str) -> None:
        self._set_mode_params(mode, presets.preset_for_mode(mode, self.preset_key.get()))

    def _set_mode_params(self, mode: str, params: dict) -> None:
        if mode == "project":
            if "fps" in params: self.fps.set(params["fps"])
            if "blink_interval" in params: self.blink_interval.set(params["blink_interval"])
            if "blink_frames" in params: self.blink_frames.set(params["blink_frames"])
            if "talk_hold" in params: self.talk_hold.set(params["talk_hold"])
            if "idle_hold" in params: self.idle_hold.set(params["idle_hold"])
            if "max_edge" in params: self.max_edge.set(params["max_edge"])
            if "fmt" in params: self.project_fmt.set(params["fmt"])
        elif mode == "sequence":
            if "fps" in params: self.seq_fps.set(params["fps"])
            if "max_edge" in params: self.seq_max_edge.set(params["max_edge"])
            if "fmt" in params: self.seq_fmt.set(params["fmt"])
        elif mode == "record":
            if "duration" in params: self.rec_duration.set(params["duration"])
            if "fps" in params: self.rec_fps.set(params["fps"])
            if "max_edge" in params: self.rec_max_edge.set(params["max_edge"])
            if "fmt" in params: self.rec_fmt.set(params["fmt"])
        elif mode == "model":
            if "fps" in params: self.model_fps.set(params["fps"])
            if "frames" in params: self.model_frames.set(params["frames"])
            if "size" in params: self.model_size.set(params["size"])
            if "max_edge" in params: self.model_max_edge.set(params["max_edge"])
            if "fmt" in params: self.model_fmt.set(params["fmt"])

    def _collect_info(self, mode: str) -> dict:
        info: dict = {}
        if mode == "sequence":
            d = self.seq_dir.get().strip()
            pd = Path(d)
            imgs = [p for p in pd.iterdir() if p.suffix.lower() in
                    {".png", ".jpg", ".jpeg", ".webp", ".gif"}] if pd.is_dir() else []
            info["frames"] = len(imgs)
            if imgs:
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(imgs[0]) as im:
                        info["width"], info["height"] = im.size
                except OSError:
                    pass
        elif mode == "project":
            if self.project and self.project.images:
                info["frames"] = len(self.project.images)
                try:
                    from PIL import Image as PILImage
                    first = next(iter(self.project.images.values()))
                    with PILImage.open(first) as im:
                        info["width"], info["height"] = im.size
                        rgba = im.convert("RGBA")
                        info["has_alpha"] = rgba.getchannel("A").getextrema()[0] < 255
                except OSError:
                    pass
        elif mode == "record":
            info["duration"] = self._iv(self.rec_duration, 3)
        elif mode == "model":
            info["kind"] = classify_model(self.model_file.get())
        return info

    def _ai_recommend(self, mode: str) -> None:
        rec = presets.recommend(mode, self._collect_info(mode))
        self._set_mode_params(mode, rec.params)
        self._log("AI 推荐参数：")
        for reason in rec.reasons:
            self._log("  · " + reason)

    # ---------- Tab1 动作 ----------
    def _choose_project(self) -> None:
        path = filedialog.askdirectory(title="选择 PNGTuber 工程文件夹")
        if path:
            self.project_dir.set(path)
            if not self.out_dir.get():
                self.out_dir.set(str(Path(path) / "output"))
            self.detect_project()

    def _choose_out(self) -> None:
        path = filedialog.askdirectory(title="选择 GIF 输出目录")
        if path:
            self.out_dir.set(path)

    def detect_project(self) -> None:
        path = self.project_dir.get().strip()
        if not path:
            messagebox.showwarning("提示", "请先选择或粘贴工程文件夹路径。")
            return
        proj = detect(path)
        self.project = proj

        for item in self.tree.get_children():
            self.tree.delete(item)
        for key, p in proj.images.items():
            self.tree.insert("", END, values=(key, p.name, STATE_LABELS.get(key, "")))

        if proj.layered:
            self.info.configure(text=f"已识别：{proj.source_format}（分层工程，当前版本待适配）", foreground="#b06000")
            self.export_btn.configure(state="disabled")
            self._log(proj.note)
        elif proj.images:
            self.info.configure(
                text=f"已识别：{proj.source_format} · {proj.model_name} · {len(proj.images)} 个状态图",
                foreground="#2a7",
            )
            self.export_btn.configure(state="normal")
            if proj.note:
                self._log("备注: " + proj.note)
        else:
            self.info.configure(text="未识别到可用图片或工程文件。", foreground="#c00")
            self.export_btn.configure(state="disabled")
            if proj.note:
                self._log(proj.note)

    def _current_dither(self) -> bool:
        return bool(presets.PRESETS.get(self.preset_key.get(), {}).get("dither", True))

    def _options(self) -> RenderOptions:
        return RenderOptions(
            fps=self._iv(self.fps, 10),
            blink_interval=self._iv(self.blink_interval, 30),
            blink_frames=self._iv(self.blink_frames, 2),
            talk_hold=self._iv(self.talk_hold, 6),
            idle_hold=self._iv(self.idle_hold, 4),
            max_edge=self._iv(self.max_edge, 1024, allow_zero=True),
            dither=self._current_dither(),
        )

    def do_export(self) -> None:
        if not self.project:
            self.detect_project()
        if not self.project or self.project.layered or not self.project.images:
            messagebox.showwarning("无法导出", "当前工程不可导出（缺少状态图或为待适配的分层工程）。")
            return
        out_dir = self._out_dir(self.out_dir, Path(self.project.root) / "output")
        self.export_btn.configure(state="disabled")
        self._log("开始导出 PNGTuber 工程…")

        def worker() -> None:
            try:
                assets = load_project_images(self.project.images)
                result = export_project(
                    assets, out_dir, self._options(), self.project.model_meta,
                    self.project.model_name, fmt=self.project_fmt.get(),
                )
                self.root.after(0, lambda: self._export_done(result))
            except Exception:
                err = traceback.format_exc()
                self.root.after(0, lambda: self._export_fail(err))

        threading.Thread(target=worker, daemon=True).start()

    def _export_done(self, result) -> None:
        self.export_btn.configure(state="normal")
        for w in result.warnings:
            self._log("⚠ " + w)
        if result.idle_gif:
            self._log(f"✓ 待机: {result.idle_gif}")
        if result.talk_gif:
            self._log(f"✓ 说话: {result.talk_gif}")
        for key, emo in result.emotion_gifs.items():
            self._log(f"✓ {key}: {emo}")
        self._log("导出完成。")

    def _export_fail(self, err_text: str = "") -> None:
        self.export_btn.configure(state="normal")
        self._log("导出失败:\n" + (err_text or "未知错误"))
        messagebox.showerror("导出失败", "详见日志框。")

    # ---------- Tab2 动作 ----------
    def _choose_seq(self) -> None:
        path = filedialog.askdirectory(title="选择帧图片目录")
        if path:
            self.seq_dir.set(path)
            if not self.seq_out.get():
                self.seq_out.set(str(Path(path) / "output"))

    def _choose_seq_out(self) -> None:
        path = filedialog.askdirectory(title="选择 GIF 输出目录")
        if path:
            self.seq_out.set(path)

    def do_sequence(self) -> None:
        d = self.seq_dir.get().strip()
        if not d:
            messagebox.showwarning("提示", "请先选择帧图片目录。")
            return
        out_dir = self._out_dir(self.seq_out, Path(d) / "output")
        fps = self._iv(self.seq_fps, 10)
        max_edge = self._iv(self.seq_max_edge, 1024, allow_zero=True)
        fmt = self.seq_fmt.get()
        self.seq_btn.configure(state="disabled")
        self._log("开始读取帧序列…")

        def worker() -> None:
            try:
                frames = load_sequence_images(d, max_edge)
                suffix = FORMAT_SUFFIX.get(fmt, ".gif")
                out_path = out_dir / f"{Path(d).name}_frames{suffix}"
                save_plain_gif(frames, out_path, fps, fmt=fmt, dither=self._current_dither())
                self.root.after(0, lambda: self._seq_done(out_path, len(frames)))
            except Exception:
                err = traceback.format_exc()
                self.root.after(0, lambda: self._seq_fail(err))

        threading.Thread(target=worker, daemon=True).start()

    def _seq_done(self, out_path: Path, count: int) -> None:
        self.seq_btn.configure(state="normal")
        self._log(f"✓ 帧序列动画: {out_path}（{count} 帧）")

    def _seq_fail(self, err_text: str = "") -> None:
        self.seq_btn.configure(state="normal")
        self._log("导出失败:\n" + (err_text or "未知错误"))
        messagebox.showerror("导出失败", "详见日志框。")

    # ---------- Tab3 动作 ----------
    def _refresh_windows(self) -> None:
        self._windows = list_windows()
        self.win_combo["values"] = [w["title"] for w in self._windows]
        if self._windows and not self.rec_window.get():
            self.rec_window.set(self._windows[0]["title"])

    def _choose_rec_out(self) -> None:
        path = filedialog.askdirectory(title="选择 GIF 输出目录")
        if path:
            self.rec_out.set(path)

    def _record_region(self) -> dict | None:
        mode = self.rec_mode.get()
        if mode == "full":
            return primary_monitor()
        if mode == "window":
            title = self.rec_window.get()
            for w in self._windows:
                if w["title"] == title:
                    return w["region"]
            messagebox.showwarning("提示", "未匹配到所选窗口，请刷新窗口列表后重试。")
            return None
        raw = self.rec_custom.get().strip()
        try:
            left, top, w, h = (int(x) for x in raw.split(","))
            if w <= 0 or h <= 0:
                raise ValueError("宽高需为正")
            return {"left": left, "top": top, "width": w, "height": h}
        except ValueError:
            messagebox.showwarning("提示", "自定义区域格式应为 left,top,w,h（如 100,100,600,500），宽高为正整数。")
            return None

    def do_record(self) -> None:
        region = self._record_region()
        if region is None:
            return
        out_dir = self._out_dir(self.rec_out, Path.cwd() / "output")
        fps = self._iv(self.rec_fps, 10)
        duration = self._iv(self.rec_duration, 3)
        max_edge = self._iv(self.rec_max_edge, 1024, allow_zero=True)
        fmt = self.rec_fmt.get()
        self.rec_btn.configure(state="disabled")
        self._log(f"开始录制 {duration}s @ {fps}fps，区域 {region} …")

        def worker() -> None:
            try:
                frames = record(region, duration, fps, max_edge=max_edge)
                self.root.after(0, lambda: self._record_done(frames, out_dir, fps, max_edge, fmt))
            except Exception:
                err = traceback.format_exc()
                self.root.after(0, lambda: self._record_fail(err))

        threading.Thread(target=worker, daemon=True).start()

    def _record_done(self, frames: list, out_dir: Path, fps: int, max_edge: int, fmt: str = "gif") -> None:
        self.rec_btn.configure(state="normal")
        try:
            frames = normalize_frames(frames, max_edge)
            suffix = FORMAT_SUFFIX.get(fmt, ".gif")
            out_path = out_dir / f"record{suffix}"
            save_plain_gif(frames, out_path, fps, fmt=fmt, dither=self._current_dither())
            self._log(f"✓ 录屏动画: {out_path}（{len(frames)} 帧）")
        except Exception:
            self._log("导出失败:\n" + traceback.format_exc())
            messagebox.showerror("导出失败", "详见日志框。")

    def _record_fail(self, err_text: str = "") -> None:
        self.rec_btn.configure(state="normal")
        self._log("录制失败:\n" + (err_text or "未知错误"))
        messagebox.showerror("录制失败", "详见日志框。")


    # ---------- Tab4 动作 ----------
    def check_env(self) -> None:
        """检测 Node / 浏览器，刷新状态与按钮可用性。"""
        statuses = {s.key: s for s in deps.detect_all()}
        node, br = statuses["node"], statuses["browser"]
        self.env_node.configure(
            text=("✓ " if node.ok else "✗ ") + node.label + "：" + node.detail,
            foreground="#2a7" if node.ok else "#c00",
        )
        self.env_browser.configure(
            text=("✓ " if br.ok else "✗ ") + br.label + "：" + br.detail,
            foreground="#2a7" if br.ok else "#c00",
        )
        self.env_dl_node.configure(state="normal" if not node.ok else "disabled")
        self.env_dl_browser.configure(state="normal" if not br.ok else "disabled")
        ready = node.ok and br.ok
        self.model_btn.configure(state="normal" if ready else "disabled")
        self._env_ready = ready

    def dl_browser(self) -> None:
        webbrowser.open(deps.detect_browser().download_url)

    def dl_node(self) -> None:
        """后台下载便携版 Node（免安装解压到程序 runtime 目录）。"""
        self.env_dl_node.configure(state="disabled")
        self._log("开始下载便携 Node（免安装）…")

        def worker() -> None:
            try:
                deps.install_portable_node(
                    progress=lambda msg, r: self.root.after(0, lambda: self._log(f"  {msg} {int(r * 100)}%"))
                )
                self.root.after(0, self._node_installed)
            except Exception:
                err = traceback.format_exc()
                self.root.after(0, lambda: self._node_install_fail(err))

        threading.Thread(target=worker, daemon=True).start()

    def _node_installed(self) -> None:
        self._log("✓ 便携 Node 已就绪。")
        self.check_env()

    def _node_install_fail(self, err_text: str = "") -> None:
        self._log("Node 下载失败:\n" + (err_text or "未知错误"))
        self.env_dl_node.configure(state="normal")
        messagebox.showerror(
            "下载失败",
            "便携 Node 下载失败，可改用官方页面安装：\n" + deps.NODE_DOWNLOAD_PAGE,
        )

    @staticmethod
    def _resolve_model_entry(path: str) -> str:
        """若给的是目录，自动在其中识别模型入口文件。"""
        p = Path(path)
        if p.is_file():
            return str(p)
        if not p.is_dir():
            return path
        for suffix in (".vrm", ".glb", ".gltf"):
            hit = next(p.rglob(f"*{suffix}"), None)
            if hit:
                return str(hit)
        return path

    def _choose_model(self) -> None:
        path = filedialog.askopenfilename(
            title="选择模型文件",
            filetypes=[("3D 模型", "*.vrm *.glb *.gltf"), ("所有文件", "*.*")],
        )
        if not path:
            return
        path = self._resolve_model_entry(path)
        self.model_file.set(path)
        if not self.model_out.get():
            self.model_out.set(str(Path(path).parent / "output"))
        kind = classify_model(path)
        label = {"vrm": "VRM / GLB 3D"}.get(kind, "未知格式")
        ok = kind == "vrm"
        self.model_info.configure(text=f"识别: {label}", foreground="#2a7" if ok else "#c00")

    def _choose_model_out(self) -> None:
        path = filedialog.askdirectory(title="选择 GIF 输出目录")
        if path:
            self.model_out.set(path)

    def do_model(self) -> None:
        m = self._resolve_model_entry(self.model_file.get().strip())
        self.model_file.set(m)
        if not m:
            messagebox.showwarning("提示", "请先选择 3D 模型文件（.vrm/.glb/.gltf）。")
            return
        if not getattr(self, "_env_ready", False):
            self.check_env()
        if not self._env_ready:
            messagebox.showwarning("缺少运行环境", "Node / 浏览器未就绪，请在上方「运行环境」区检测并补齐后再渲染。")
            return
        out_dir = self._out_dir(self.model_out, Path(m).parent / "output")
        fps = self._iv(self.model_fps, 10)
        frames = self._iv(self.model_frames, 12)
        size = self._iv(self.model_size, 768)
        max_edge = self._iv(self.model_max_edge, 1024, allow_zero=True)
        self.model_btn.configure(state="disabled")
        self._log(f"开始渲染模型: {Path(m).name} …")

        def worker() -> None:
            try:
                res = render_model(
                    m, out_dir, fps=fps, frames=frames, size=size,
                    max_edge=max_edge, fmt=self.model_fmt.get(),
                    dither=self._current_dither(),
                    log=lambda t: self.root.after(0, lambda: self._log(t)),
                )
                self.root.after(0, lambda: self._model_done(res))
            except Exception:
                err = traceback.format_exc()
                self.root.after(0, lambda: self._model_fail(err))

        threading.Thread(target=worker, daemon=True).start()

    def _model_done(self, res) -> None:
        self.model_btn.configure(state="normal")
        self._log(f"✓ 模型 GIF: {res.gif}（{res.frames} 帧）")

    def _model_fail(self, err_text: str = "") -> None:
        self.model_btn.configure(state="normal")
        self._log("渲染失败:\n" + (err_text or "未知错误"))
        messagebox.showerror("渲染失败", "详见日志框。")


HELP_TEXT = """\
欢迎使用：把形象素材 / 帧序列 / 录屏 / 模型一键转成循环 GIF（或 APNG）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
一、最快上手（三步）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 顶部先选界面模式：
   · 简易（小白）：只选一个画质档位，点导出即可，不用懂参数。
   · 高级（专业）：展开帧率、帧数、边长等全部参数逐项微调。
2. 按素材类型选下面对应的标签页：
   · 已有 PNGTuber 拆件（待机 / 说话 / 眨眼等图）→「PNGTuber 工程」
   · 一排按顺序排好的图片            →「帧序列目录」
   · 想录制软件里正在动的画面        →「屏幕录制」
   · 有 .vrm / .glb / .gltf 模型 →「3D 模型（VRM / GLB）」
3. 选好输入素材和输出目录，点导出按钮；结果在日志框和输出目录里。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
二、四种模式分别做什么
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
· PNGTuber 工程：识别待机、说话、眨眼、开心 / 难过 / 生气 / 惊讶等状态图，
  自动拼成待机循环、说话循环，并把各情绪差分单独导出。
· 帧序列目录：把目录里的图片按文件名自然排序（frame_2 排在 frame_10 前），
  打包成循环动画；GIF 素材会自动展开成多帧。
· 屏幕录制：抓取全屏、指定窗口或自定义区域，把模型或软件里
  跑起来的画面录成动画；适合软件本身不能直接导出 GIF 的情况。
· 3D 模型（VRM / GLB）：无头加载模型，自动播放模型自带的待机动作，
  叠加说话嘴型、眨眼、呼吸与轻微头部摆动，逐帧截图后打包成透明循环动画。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
三、参数怎么理解（高级视图）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
· 帧率 FPS：每秒多少帧。数值越高动作越顺，文件也越大；一般 8~12 够用。
· 渲染帧数（模型模式）：一个循环截取多少帧；帧数越多循环越细腻。
· 画布边长（模型模式）：离屏渲染的正方形边长，越大越清晰，越吃性能。
· 边长上限：输出图最长边限制，超出等比缩小；0 表示不限制。
· 输出格式：
   - APNG：保留全彩与 RGBA 半透明边缘，画质无损、最接近原图；立绘 / 细节多的素材优先选它，体积略大。
   - GIF：兼容性最好，聊天 / 网页通用；最多 256 色、透明为 1-bit，半透明边缘会被简化。
     本机检测到 ffmpeg 时会用两阶段调色板优化色彩与边缘；未安装则回退内置量化。
· 抖动（GIF）：平涂立绘建议关闭，避免纯色区域出现网点脏色；渐变素材可开启让过渡更顺滑。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
四、AI 自动推荐是什么
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
点「AI 自动推荐」后，工具根据素材帧数、分辨率、是否含透明边缘、时长等信息，
用本地规则给出一套建议参数，并在日志里写明理由。它不需要联网、不需要 API Key；
推荐结果仍可在高级视图里继续手动覆盖。三档预设含义：
· 流畅优先：帧率偏高、画质优先，体积偏大，适合动作明显的素材。
· 清晰优先：分辨率与细节优先，适合静态或慢动作素材（默认）。
· 小体积优先：降低帧率与边长、压缩体积，适合聊天窗口 / 网页快速加载。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
五、常见问题
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
· 模型模式提示缺 Node / 浏览器：在「3D 模型（VRM / GLB）」页的运行环境区查看状态；
  缺 Node 可点「下载 Node」自动装便携版（免安装），缺浏览器按提示装 Chrome / Edge。
  其余三种模式不依赖 Node 和浏览器。
· 透明边缘有锯齿：GIF 会把半透明边缘简化成硬边；需要干净边缘请把格式改为 APNG。
· 导出的人物是半身 / 大头，和全身立绘对不上：PNGTuber 工程只搬运你提供的状态图，素材是半身差分就出半身；
  要完整全身动画，请用「3D 模型（VRM / GLB）」模式加载 .vrm / .glb 模型。
· 待机、说话、眨眼几帧看起来一模一样：确认 idle / talking / blink 素材本身是不同的差分图，
  而不是同一张图复制改名；只有局部（嘴、眼）不同的立绘才能交替出动作。
· 文件太大：切到「小体积优先」档位，或在高级里降低帧率、边长上限与分辨率。
· 画面不动：检查输入素材是否有序、是否被正常识别；录屏模式确认录制对象里有画面变化。
· 选的是文件夹：工程 / 模型模式会在文件夹内自动递归识别入口文件，无需手动挑单个文件。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
六、支持的素材格式
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
图片：PNG / JPG / JPEG / WebP / GIF；模型：VRM / GLB / glTF。
使用第三方模型需遵守模型作者与对应软件的许可。
"""


def run() -> None:
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    run()
