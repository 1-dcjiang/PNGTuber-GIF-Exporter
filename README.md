# 形象素材 → GIF 一键导出工具

把各类形象素材转成**循环播放** GIF，四种来源模式，独立 exe，无需安装 Python：

1. **PNGTuber 工程**：识别待机 / 说话 / 眨眼 / 情绪状态图，导出「待机循环」「说话循环」及各情绪差分动画；
2. **帧序列目录**：把有序图片（或动图展开帧）打包成循环动画；
3. **屏幕录制**：抓取全屏 / 指定窗口 / 自定义区域，把模型或软件里运行的画面录成动画；
4. **3D 模型（VRM）**：离线无头加载 `.vrm`（或带 VRM 扩展的 `.glb`），自适应探测嘴 / 眼参数；叠加说话嘴型、眨眼与轻微头部摆动，逐帧截 PNG 打包成循环动画。模型保持 T-pose，不播放自带的骨骼动画；需要骨骼动作请用屏幕录制。

输出格式可选 **GIF**（1-bit 透明，兼容性好）或 **APNG**（保留 RGBA 半透明边缘）。

> 模式 4 依赖本机 **Node.js 18+** 与 **Chrome / Edge**（工具复用本机浏览器内核，不内嵌浏览器、不内嵌 Node）。GUI 的「运行环境」区会自动探测这两项：缺 Node 可一键下载便携版到程序旁 `runtime/node`（免安装）；缺浏览器则给出官方下载页。其余三种模式不依赖 Node / 浏览器。

## 产物

- `dist/PNGTuber-GIF-Exporter/` — onedir 绿色程序目录（Windows 64-bit），主程序 `PNGTuber-GIF-Exporter.exe`，运行时资源在 `_internal/web/`
- 源码：`main.py` 入口 + `pngtuber_exporter/`（detect / frames / render / sequence / capture / gui / web_render / deps / presets）
- Web 渲染子系统：`web/`（VRM `three.js + three-vrm`，无头采集脚本 `render-vrm.mjs`）
- 示例素材：仓库不附带 `samples/`；请使用你拥有权利的图片、模型和角色素材。

## 快速开始

### 图形界面（推荐）

双击 `PNGTuber-GIF-Exporter.exe`，顶部可切换 **简易（小白）/ 高级（专业）** 两种界面：

- **简易模式**：每个模式页只选一个画质档位（流畅优先 / 清晰优先 / 小体积优先），点导出即可；点「AI 自动推荐」会按素材帧数、分辨率、是否含透明边缘等本地规则给出建议参数并写明理由（不联网、不需要 API Key）。
- **高级模式**：展开帧率、帧数、画布边长、边长上限、格式等全部参数逐项微调；预设给出的结果仍可继续覆盖。
- 「使用帮助」标签页有分步上手、参数解释与常见问题，新手可先看这里。

下方标签页按素材类型选择：

**① PNGTuber 工程**
- 选择 / 粘贴工程文件夹 → 自动识别状态图，列表核对 idle / talking / blink…
- 调整帧率、眨眼间隔、停留帧数、边长上限 → 一键导出。

**② 帧序列目录**
- 选择排好序的图片目录 → 按文件名自然排序打包；动图素材会展开为多帧。

**③ 屏幕录制**
- 选「全屏 / 指定窗口 / 自定义区域」；窗口列表可刷新；填时长、帧率、边长上限 → 开始录制并导出。
- 适用场景：VRM 3D 模型在 VTube Studio 等原软件里正常展示，录制它的窗口画面即可。

**④ 3D 模型（VRM）**
- 选择 `.vrm`，或带 VRM 扩展的 `.glb` / `.gltf`；普通 glTF/GLB 会明确报错。直接选模型文件夹也可，会自动递归识别入口；
- 填帧率、渲染帧数、画布边长、边长上限 → 渲染并导出透明循环 GIF；
- 模型在本机无头浏览器中加载，驱动说话嘴型、周期眨眼与轻微头部偏航；模型保持默认 T-pose，不播放自带骨骼动画。
- 默认启用 Chrome 沙箱；若个别系统上无头浏览器启动失败，可临时设置环境变量 `PNGTUBER_NO_SANDBOX=1` 再重试。

### 命令行（批量 / 脚本调用）

```bash
# 1) PNGTuber 工程
PNGTuber-GIF-Exporter.exe --project <工程文件夹> --out <输出目录> [--fps 10]

# 2) 帧序列目录
PNGTuber-GIF-Exporter.exe --frames <帧目录> --out <输出目录> [--fps 10] [--max-edge 1024]

# 3) 屏幕录制（自定义区域 left,top,w,h）
PNGTuber-GIF-Exporter.exe --record --duration 3 --fps 10 --region 0,0,800,600 --out <输出目录>

# 3b) 按标题关键词录制窗口
PNGTuber-GIF-Exporter.exe --record --duration 3 --window "VTube Studio" --out <输出目录>

# 4) VRM 3D 模型（传模型文件或所在目录均可，目录会自动识别入口）
#    普通 glTF/GLB 不含 VRM 扩展，会明确报错；请用 .vrm 或带 VRM 扩展的 .glb
PNGTuber-GIF-Exporter.exe --model <模型.vrm|带VRM扩展的模型.glb|模型目录> --out <输出目录> [--fps 10] [--model-frames 12] [--model-size 768]

# 输出格式：--format gif（默认，1-bit 透明）| apng（半透明 PNG 动画）
PNGTuber-GIF-Exporter.exe --project <工程文件夹> --out <输出目录> --format apng
```

## 支持的工程 / 素材格式

| 来源 | 识别方式 | 状态 |
| --- | --- | --- |
| 扁平图片包 `simple_package` | 根目录 `model.json`，`pngtuber.idle_image / talking_image / blink_image …` | ✅ |
| 散图 `loose_images` | 文件夹内 PNG/GIF/WebP/JPG，按文件名关键词归类 | ✅ |
| 帧序列目录 | 任意有序图片，按文件名自然排序；GIF 展开多帧 | ✅ |
| 屏幕 / 窗口画面 | mss 抓帧，全屏 / 窗口矩形 / 自定义区域 | ✅ |
| VRM 3D 模型（`.vrm` / 带 VRM 扩展的 `.glb`） | three.js + three-vrm 无头加载，驱动 aa 嘴型 / blink 眨眼，叠加轻微头部偏航；无骨骼动画，保持 T-pose | ✅ |
| PNGTuber Plus `.save` | 分层节点树工程 | ⚠️ 可识别，图层合成待样本适配 |
| PNGTube Remix `.pngRemix` | Godot Variant 序列化工程 | ⚠️ 可识别，图层合成待样本适配 |

### 散图命名约定（关键词不区分大小写）

| 状态 key | 文件名关键词示例 |
| --- | --- |
| `idle` | `idle`、`neutral`、`closed-open`、`still`、`base` |
| `talking` | `talking`、`talk`、`mouth-open`、`open-open` |
| `blink` | `blink`、`closed-closed`、`eyes-closed` |
| `blink_talking` | `blink-talking`、`open-closed` |
| `happy` / `sad` / `angry` / `surprised` | 同名关键词 |

## 参数说明

下表是 GUI 的默认值；CLI 以 `--help` 为准，其中 `--format` 默认 `gif`（所有模式）。

| 参数 | 默认 | 含义 |
| --- | --- | --- |
| 帧率 FPS | 10 | 每帧时长 = 1000 / FPS 毫秒 |
| 眨眼间隔(帧) | 30 | 待机状态下每隔多少帧出现一次眨眼（仅工程模式） |
| 眨眼帧数 | 2 | 每次眨眼持续帧数（仅工程模式） |
| 说话停留(帧) | 6 | 说话段嘴张停留帧数（仅工程模式） |
| 待机停留(帧) | 4 | 说话段嘴闭停留帧数（仅工程模式） |
| 边长上限 | 1024 | 输出图最长边，超出等比缩小；0 不限制 |
| 渲染帧数 | 12 | 模型模式一个循环截取的帧数，越多越细腻 |
| 画布边长 | 768 | 模型模式离屏渲染正方形边长，越大越清晰 |
| 输出格式 | GUI 工程页 apng；CLI 与其他页 gif | APNG 全彩无损、保留半透明边缘，最接近原图；GIF 最多 256 色、1-bit 透明，兼容优先 |
| GIF 抖动 | 关 | 平涂立绘默认关闭以避免纯色区域网点脏色；渐变素材可开启让过渡更顺滑 |
| 录制时长(秒) | 3 | 录屏模式抓取时长 |
| 画质档位 | 清晰优先 | 流畅 / 清晰 / 小体积三档预设，简易模式一键套用 |

## 实现要点

- 图像解码：Pillow `ImageSequence` 读取 PNG / GIF / WebP / JPG 帧，统一转 RGBA。
- 画布对齐：以所有帧最大宽高为准，等比缩放到边长上限后居中合成。
- 透明 GIF：`disposal=2` 逐帧恢复背景，保留透明索引；循环 `loop=0`。
- GIF 编码：检测到本机 ffmpeg 时走两阶段调色板（palettegen/paletteuse）优化色彩与边缘；未安装回退内置 Pillow 量化。导出前清理半透明边缘（软阈值 + 主体色回填），连续相同帧自动合并去重并按次数加权时长。
- 录屏：`mss`（纯 ctypes 跨平台截屏）按固定间隔抓帧；窗口矩形经 Win32 `GetWindowRect` 获取。
- 工程模式为**固定循环编排**，不接麦克风：待机按间隔插眨眼，说话在 idle/talking 间交替。

## 已知限制与边界

- **模式 4 的运行前提**：本机需有 Node.js 18+ 与 Chrome/Edge；工具不内嵌 Node 与浏览器内核。未安装 Node 时模型模式不可用，其余三种模式不受影响。
- **模型姿态**：VRM 受限于无骨骼动画文件，仅驱动表情与头部微动，保持默认 T-pose；不播放模型自带的 Idle / 骨骼动画。需要骨骼动作请用屏幕录制模式。未做口型同步音频；模型自带动作若含表情曲线，会与叠加参数取后者覆盖。
- 分层 Plus / Remix 工程尚未做图层合成（需要真实分层工程样本）。
- GIF 最多 256 色、透明为 1-bit（半透明边缘被量化）；要全彩无损与干净半透明边缘请选 APNG。GIF 质量依赖本机 ffmpeg，未安装时回退内置量化，色彩边缘会略逊。
- PNGTuber 工程只搬运提供的状态图：素材是半身差分就出半身，工具不补全全身；完整全身动画请用「3D 模型（VRM）」模式加载 .vrm 或带 VRM 扩展的 .glb。待机 / 说话 / 眨眼帧要有差异，前提是 idle / talking / blink 素材本身是不同差分图，而非同一张复制改名。
- 录屏动画保留屏幕自身背景，不是透明底；静止画面的连续相同帧会被优化去重。
- 工程模式下 happy / sad / angry / surprised 情绪图会各自导出一张静态循环动画。

## 从源码复现打包

环境：Python 3.12+（实测 3.12 / 3.14，Pillow、mss）；Web 子系统依赖在 `web/` 内用 `npm ci` 安装并锁定。

```bash
python -m pip install -r requirements.txt -r requirements-build.txt
cd web && npm ci && cd ..
python build/make_package.py
# 诊断需要控制台输出时：EXPORTER_CONSOLE=1 python build/make_package.py
```

脚本会先把 `web/` 运行时资源裁剪到 `build/staging/web`（排除示例模型与临时调试产物），再以 onedir 形态收集进 `dist/PNGTuber-GIF-Exporter/`。

项目自身代码以 MIT 许可证发布，版权归 1-dcjiang 所有；许可证全文见 [`LICENSE`](LICENSE)。第三方组件沿用各自许可证，说明见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)，全文在 [`THIRD_PARTY_LICENSES/`](THIRD_PARTY_LICENSES/)。

## 开源参考

- 格式探测与分层解析思路：`Project-N-E-K-O/N.E.K.O` 的 `main_routers/pngtuber_importers/`
- GIF 帧解码与图层合成参考：`core-dump-dev/WebPNGTuber`（editor.py，Tkinter + Pillow）
- 四帧状态约定：`pngtubermaker/pngtuber-converter`
- 截屏：`mss`（纯 ctypes 跨平台）
- VRM 无头渲染：`mrdoob/three.js` + `pixiv/three-vrm`
- 宿主软件（非本工具依赖）：`MudkipWorld/PNGTuber-Remix`（Godot）、`Gemmstone/PyNGtuber`（Python+Qt，GPLv3）

## 许可证

本项目源代码采用 [MIT License](LICENSE)，Copyright (c) 2026 1-dcjiang。你可以自由使用、修改、分发和商用，但需保留版权与许可声明。第三方组件不适用 MIT，按 `THIRD_PARTY_NOTICES.md` 与 `THIRD_PARTY_LICENSES/` 中的各自许可证执行。
