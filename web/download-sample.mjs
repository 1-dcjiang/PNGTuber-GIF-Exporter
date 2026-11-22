// 下载公开示例 VRM 模型，用于渲染管线验证。
import { writeFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const modelsDir = join(__dirname, "models");
await mkdir(modelsDir, { recursive: true });

const urls = [
  "https://raw.githubusercontent.com/scorpionknifes/VRM-examples/ed85b917b08bb353de647f26fef0c5d8359d2650/ExampleAvatar_A.vrm",
  "https://cdn.jsdelivr.net/gh/scorpionknifes/VRM-examples@ed85b917b08bb353de647f26fef0c5d8359d2650/ExampleAvatar_A.vrm",
  "https://raw.githubusercontent.com/pixiv/three-vrm/ff42fae4fcee1fcbca2cd262c7f5f8cbddeaf5ab/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm",
  "https://cdn.jsdelivr.net/gh/pixiv/three-vrm@ff42fae4fcee1fcbca2cd262c7f5f8cbddeaf5ab/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm",
];

let done = false;
for (const url of urls) {
  try {
    process.stdout.write(`try: ${url}\n`);
    const res = await fetch(url, { signal: AbortSignal.timeout(90_000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.length < 100_000) throw new Error(`too small ${buf.length}`);
    await writeFile(join(modelsDir, "sample.vrm"), buf);
    console.log(`OK ${buf.length} bytes <- ${url}`);
    done = true;
    break;
  } catch (e) {
    console.log(`  fail: ${e.message}`);
  }
}
if (!done) process.exit(1);
