# Third-party notices

本文件覆盖随 `PNGTuber-GIF-Exporter` 分发的第三方组件。项目自身源代码采用 MIT 许可证，见仓库根目录 [`LICENSE`](LICENSE)。

第三方许可证全文集中在 [`THIRD_PARTY_LICENSES/`](THIRD_PARTY_LICENSES/)；构建脚本会把该目录复制到成品根目录。

## Python runtime and libraries

| Component | Version | License | Full text |
| --- | --- | --- | --- |
| Python runtime | 3.14.7 | PSF License | `THIRD_PARTY_LICENSES/python-3.14-LICENSE.txt` |
| Pillow | 12.3.0 | HPND | `THIRD_PARTY_LICENSES/pillow-12.3.0-LICENSE.txt` |
| mss | 10.2.0 | MIT | `THIRD_PARTY_LICENSES/mss-10.2.0-LICENSE.txt` |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later with bootloader exception | `THIRD_PARTY_LICENSES/pyinstaller-6.22.3-COPYING.txt` |
| Tcl/Tk | 9.0 | BSD-style | `THIRD_PARTY_LICENSES/tcl-tk-9.0-license.terms` |

PyInstaller 的 bootloader exception 允许把编译后的 bootloader 嵌入并随应用程序分发；GPL 的其他义务仍然适用于 PyInstaller 自身文件。

## Web rendering dependencies

| Component | Version | License | Full text |
| --- | --- | --- | --- |
| `three` | 0.187.0 | MIT | `THIRD_PARTY_LICENSES/three-MIT.txt` |
| `@pixiv/three-vrm` / `@pixiv/three-vrm-*` | 3.5.5 | MIT | `THIRD_PARTY_LICENSES/three-vrm-MIT.txt` |
| `puppeteer-core` | 25.18.1 | Apache-2.0 | `THIRD_PARTY_LICENSES/puppeteer-core-Apache-2.0.txt` |
| `@puppeteer/browsers` | locked by `puppeteer-core` | Apache-2.0 | `THIRD_PARTY_LICENSES/puppeteer-browsers-Apache-2.0.txt` |

`THIRD_PARTY_LICENSES/npm/` 按 `node_modules` 的相对路径保存各 npm 包自带的许可证文件，共 38 份；成品中的对应路径是 `_internal/web/node_modules/<package>/`。

`puppeteer-core` 与 `@puppeteer/browsers` 的 npm 包没有随包附带 `LICENSE` 文件，因此这里补充了 Apache License 2.0 标准全文。

## Sample assets

本仓库不附带示例角色素材，`samples/` 目录已移除。`web/download-sample.mjs` 只从外部下载 VRM 示例用于渲染管线验证；使用或再分发下载到的模型前，需要单独确认该模型自身的许可。

## Node.js runtime

应用程序不内嵌 Node.js。可选的“下载便携 Node”操作会获取 Node.js 官方 Windows x64 压缩包，并用 `https://nodejs.org/dist/<version>/SHASUMS256.txt` 校验 SHA-256 后解压。Node.js 使用 MIT 许可证，其许可证文件包含在下载的官方压缩包内。
