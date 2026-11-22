import fs from "node:fs";
import path from "node:path";

function _realPath(p) {
  try {
    return fs.realpathSync(p);
  } catch {
    return path.resolve(p);
  }
}

// 判断 child 是否位于 parent 目录内；realpath 会解析符号链接，避免链接逃逸。
export function isInside(parent, child) {
  const parentReal = _realPath(parent);
  const childReal = _realPath(child);
  const rel = path.relative(parentReal, childReal);
  return Boolean(rel) && !rel.startsWith("..") && !path.isAbsolute(rel);
}
