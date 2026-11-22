// VRM 无头渲染：起本地静态服务 -> puppeteer 连本机 Chrome -> 逐帧截图存 PNG。
// 用法: node render-vrm.mjs --model <模型URL路径> --out <帧目录> --frames N [--fps 10] [--size 1024] [--browser <chrome路径>]
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";
import { isInside } from "./path_guard.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = __dirname;

function arg(name, def) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : def;
}

const modelUrl = arg("model", "/models/sample.vrm");
const modelDir = arg("model-dir", "");
const outDir = arg("out", path.join(WEB_ROOT, "_frames"));
const frames = Math.max(1, parseInt(arg("frames", "16"), 10) || 16);
const fps = Math.max(1, parseInt(arg("fps", "10"), 10) || 10);
const size = Math.max(64, parseInt(arg("size", "1024"), 10) || 1024);
const browserPath = arg("browser", "");

fs.mkdirSync(outDir, { recursive: true });

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".png": "image/png",
  ".vrm": "model/gltf-binary",
  ".glb": "model/gltf-binary",
  ".css": "text/css",
};

function serveStatic(req, res) {
  let urlPath = decodeURIComponent(req.url.split("?")[0]);
  let filePath;
  if (urlPath.startsWith("/external/") && modelDir) {
    filePath = path.join(modelDir, decodeURIComponent(urlPath.replace("/external/", "")));
    if (!isInside(modelDir, filePath)) {
      res.writeHead(403); res.end("forbidden"); return;
    }
  } else {
    if (urlPath === "/") urlPath = "/vrm.html";
    filePath = path.join(WEB_ROOT, urlPath);
    if (!isInside(WEB_ROOT, filePath)) {
      res.writeHead(403); res.end("forbidden"); return;
    }
  }
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    console.log("[404]", urlPath);
    res.writeHead(404);
    res.end("not found");
    return;
  }
  const ext = path.extname(filePath).toLowerCase();
  res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
  fs.createReadStream(filePath).pipe(res);
}

const server = http.createServer(serveStatic);
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

function detectBrowser() {
  if (browserPath && fs.existsSync(browserPath)) return browserPath;
  const candidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  ];
  return candidates.find((c) => fs.existsSync(c));
}

const executablePath = detectBrowser();
if (!executablePath) throw new Error("未找到本机 Chrome/Edge，请用 --browser 指定路径");

const chromeArgs = ["--disable-gpu", "--allow-file-access-from-files", "--hide-scrollbars", "--force-color-profile=srgb"];
if (process.env.PNGTUBER_NO_SANDBOX === "1") chromeArgs.unshift("--no-sandbox");

const browser = await puppeteer.launch({
  executablePath,
  headless: "new",
  defaultViewport: { width: size, height: size },
  args: chromeArgs,
});

try {
  const page = await browser.newPage();
  page.on("console", (m) => console.log("[browser]", m.type(), m.text()));
  page.on("pageerror", (e) => console.log("[pageerror]", e.message));
  const pageUrl = `http://127.0.0.1:${port}/vrm.html?model=${encodeURIComponent(modelUrl)}&size=${size}`;
  await page.goto(pageUrl, { waitUntil: "networkidle0", timeout: 30000 });
  await page.waitForFunction(() => window.__ready === true || !!window.__error, { timeout: 30000 });
  const err = await page.evaluate(() => window.__error);
  if (err) throw new Error(`页面渲染失败: ${err}`);
  const debug = await page.evaluate(() => window.__debug);
  console.log("[debug]", JSON.stringify(debug));

  for (let i = 0; i < frames; i++) {
    await page.evaluate((idx) => window.__setFrame(idx), i);
    await new Promise((r) => setTimeout(r, 40));
    const dataUrl = await page.evaluate(() => window.__snapshot());
    if (!dataUrl || typeof dataUrl !== "string" || !dataUrl.includes(",")) {
      throw new Error("页面快照为空，未能采集到帧画面");
    }
    const base = dataUrl.split(",")[1];
    const file = path.join(outDir, `frame_${String(i + 1).padStart(4, "0")}.png`);
    fs.writeFileSync(file, Buffer.from(base, "base64"));
  }
  console.log(`OK ${frames} frames -> ${outDir} (fps=${fps})`);
} finally {
  await browser.close();
  server.close();
}
