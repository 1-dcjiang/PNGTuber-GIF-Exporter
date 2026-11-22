from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from pngtuber_exporter.frames import StateAsset
from pngtuber_exporter.render import _place, normalize_frames


def _bbox(img: Image.Image) -> tuple[int, int, int, int]:
    box = img.getchannel("A").getbbox()
    assert box is not None
    return box


class TestFrameAspect(unittest.TestCase):
    def test_normalize_frames_keeps_aspect_and_centers(self):
        wide = Image.new("RGBA", (100, 50), (255, 0, 0, 255))
        tall = Image.new("RGBA", (50, 100), (0, 0, 255, 255))
        out = normalize_frames([wide, tall], max_edge=0)
        self.assertEqual([im.size for im in out], [(100, 100), (100, 100)])
        self.assertEqual(_bbox(out[0]), (0, 25, 100, 75))
        self.assertEqual(_bbox(out[1]), (25, 0, 75, 100))

    def test_normalize_frames_respects_max_edge(self):
        wide = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
        out = normalize_frames([wide], max_edge=100)
        self.assertEqual(out[0].size, (100, 50))
        self.assertEqual(_bbox(out[0]), (0, 0, 100, 50))

    def test_place_scales_smaller_frame_without_distortion(self):
        asset = StateAsset("idle", Path("idle.png"), [Image.new("RGBA", (50, 25), (255, 0, 0, 255))], [100], False)
        out = _place(asset, 100, 100, {})
        self.assertEqual(_bbox(out), (0, 25, 100, 75))

    def test_place_scales_small_square_to_fill_canvas(self):
        asset = StateAsset("idle", Path("idle.png"), [Image.new("RGBA", (50, 50), (255, 0, 0, 255))], [100], False)
        out = _place(asset, 100, 100, {})
        self.assertEqual(_bbox(out), (0, 0, 100, 100))


if __name__ == "__main__":
    unittest.main()
