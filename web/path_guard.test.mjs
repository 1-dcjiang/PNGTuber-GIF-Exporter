import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, symlinkSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { isInside } from "./path_guard.mjs";

test("accepts a file inside the root", () => {
  const root = mkdtempSync(path.join(os.tmpdir(), "pngtuber-guard-"));
  try {
    const file = path.join(root, "model.json");
    writeFileSync(file, "{}");
    assert.equal(isInside(root, file), true);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("accepts a nested directory entry", () => {
  const root = mkdtempSync(path.join(os.tmpdir(), "pngtuber-guard-"));
  try {
    const nested = path.join(root, "parts");
    mkdirSync(nested);
    assert.equal(isInside(root, nested), true);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("rejects a sibling with the same prefix", () => {
  const root = mkdtempSync(path.join(os.tmpdir(), "pngtuber-guard-"));
  const sibling = `${root}-evil`;
  try {
    mkdirSync(sibling);
    assert.equal(isInside(root, path.join(sibling, "secret.txt")), false);
  } finally {
    rmSync(root, { recursive: true, force: true });
    rmSync(sibling, { recursive: true, force: true });
  }
});

test("rejects a symlink that escapes the root", (t) => {
  const root = mkdtempSync(path.join(os.tmpdir(), "pngtuber-guard-"));
  const outside = mkdtempSync(path.join(os.tmpdir(), "pngtuber-outside-"));
  try {
    writeFileSync(path.join(outside, "secret.txt"), "secret");
    try {
      symlinkSync(path.join(outside, "secret.txt"), path.join(root, "link.txt"));
    } catch (exc) {
      t.skip(`无法创建符号链接：${exc.message}`);
      return;
    }
    assert.equal(isInside(root, path.join(root, "link.txt")), false);
  } finally {
    rmSync(root, { recursive: true, force: true });
    rmSync(outside, { recursive: true, force: true });
  }
});
