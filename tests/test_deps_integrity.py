from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from pngtuber_exporter import deps


def _node_zip(version: str = "v20.0.0") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"node-{version}-win-x64/node.exe", b"fake node")
    return buf.getvalue()


def _shasums(blob: bytes, version: str = "v20.0.0") -> str:
    name = f"node-{version}-win-x64.zip"
    return f"{hashlib.sha256(blob).hexdigest()}  {name}\n"


class TestNodeIntegrity(unittest.TestCase):
    def test_expected_sha256_parses_official_format(self):
        text = "a" * 64 + "  node-v20.0.0-win-x64.zip\n"
        self.assertEqual(
            deps._expected_sha256(text, "node-v20.0.0-win-x64.zip"),
            "a" * 64,
        )

    def test_expected_sha256_rejects_missing_or_malformed(self):
        with self.assertRaises(RuntimeError):
            deps._expected_sha256("not-a-hash  node-v20.0.0-win-x64.zip\n", "node-v20.0.0-win-x64.zip")
        with self.assertRaises(RuntimeError):
            deps._expected_sha256("b" * 64 + "  other.zip\n", "node-v20.0.0-win-x64.zip")

    def test_install_rejects_hash_mismatch_without_extracting(self):
        blob = _node_zip()
        bad_sums = "0" * 64 + "  node-v20.0.0-win-x64.zip\n"
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            with mock.patch.object(deps, "latest_lts_version", return_value="v20.0.0"), \
                 mock.patch.object(deps, "_http_get", side_effect=[blob, bad_sums.encode()]), \
                 mock.patch.object(deps, "runtime_dir", return_value=base), \
                 mock.patch.object(deps, "portable_node_dir", return_value=base / "node"):
                with self.assertRaisesRegex(RuntimeError, "sha256"):
                    deps.install_portable_node()
            self.assertFalse((base / "node").exists())

    def test_install_accepts_matching_hash_and_flattens(self):
        blob = _node_zip()
        good_sums = _shasums(blob)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            with mock.patch.object(deps, "latest_lts_version", return_value="v20.0.0"), \
                 mock.patch.object(deps, "_http_get", side_effect=[blob, good_sums.encode()]), \
                 mock.patch.object(deps, "runtime_dir", return_value=base), \
                 mock.patch.object(deps, "portable_node_dir", return_value=base / "node"), \
                 mock.patch.object(deps, "_node_version", return_value="20.0.0"):
                result = deps.install_portable_node()
            self.assertEqual(result, base / "node" / "node.exe")
            self.assertEqual(result.read_bytes(), b"fake node")


if __name__ == "__main__":
    unittest.main()
