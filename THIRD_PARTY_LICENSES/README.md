# Third-party license texts

本目录保存随 `PNGTuber-GIF-Exporter` 分发的第三方组件许可证全文。构建脚本会把整个目录复制到成品根目录。

## Python 运行时与库

| 组件 | 版本 | 许可证 | 文件 |
| --- | --- | --- | --- |
| Python runtime | 3.14.7 | PSF License | `python-3.14-LICENSE.txt` |
| Pillow | 12.3.0 | HPND | `pillow-12.3.0-LICENSE.txt` |
| mss | 10.2.0 | MIT | `mss-10.2.0-LICENSE.txt` |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later with bootloader exception | `pyinstaller-6.22.3-COPYING.txt` |
| Tcl/Tk | 9.0 | BSD-style | `tcl-tk-9.0-license.terms` |

## Web 渲染依赖

| 组件 | 版本 | 许可证 | 文件 |
| --- | --- | --- | --- |
| `three` | 0.187.0 | MIT | `three-MIT.txt` |
| `@pixiv/three-vrm` | 3.5.5 | MIT | `three-vrm-MIT.txt` |
| `puppeteer-core` | 25.18.1 | Apache-2.0 | `puppeteer-core-Apache-2.0.txt` |
| `@puppeteer/browsers` | 由 `puppeteer-core` 锁定 | Apache-2.0 | `puppeteer-browsers-Apache-2.0.txt` |

`npm/` 目录按 `node_modules` 的相对路径保存各 npm 包自带的 `LICENSE` / `license` / `COPYING` / `NOTICE` 文件，共 38 份。成品中的对应路径为 `_internal/web/node_modules/<package>/`。

对于上游包没有随包提供许可证文件的 Apache-2.0 组件（`puppeteer-core`、`@puppeteer/browsers`），本目录补充了 Apache License 2.0 标准全文。

## 说明

- 本目录只覆盖随成品分发的第三方组件，不改变项目自身代码的版权归属。
- 项目自身版权与使用限制见仓库根目录 `LICENSE`。
- 如果升级依赖或更换 Python / Tcl/Tk 版本，应重新生成对应许可证文本并更新本清单。
