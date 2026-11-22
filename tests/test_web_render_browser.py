from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from pngtuber_exporter import web_render


class TestBrowserForwarding(unittest.TestCase):
    def test_render_model_passes_detected_browser(self):
        browser = r"C:\Users\me\AppData\Local\Google\Chrome\Application\chrome.exe"
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            frame_dir = Path(cmd[cmd.index("--out") + 1])
            frame_dir.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (8, 8), (0, 0, 0, 255)).save(frame_dir / "frame_0001.png")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model = root / "avatar.vrm"
            model.write_bytes(b"fake")
            with mock.patch.object(web_render, "detect_node", return_value="node"), \
                 mock.patch.object(web_render, "detect_browser", return_value=browser), \
                 mock.patch.object(web_render, "web_root", return_value=root), \
                 mock.patch.object(web_render.subprocess, "run", side_effect=fake_run):
                web_render.render_model(model, root / "out", frames=1)

        cmd = captured["cmd"]
        self.assertIn("--browser", cmd)
        self.assertEqual(cmd[cmd.index("--browser") + 1], browser)


if __name__ == "__main__":
    unittest.main()
