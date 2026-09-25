"""Checks for deterministic adverse-pixel rejection."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
import unittest

from PIL import Image, ImageDraw, ImageFilter


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from rocell_ai.pixel_quality import assess  # noqa: E402
from rocell_ai.scene_observation import FrameEvidence  # noqa: E402


def encoded(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class PixelQualityTests(unittest.TestCase):
    def frame(self, name: str, image: Image.Image) -> FrameEvidence:
        return FrameEvidence(name, "2026-09-25T16:00:00Z", encoded(image))

    def test_textured_control_is_accepted(self) -> None:
        image = Image.new("RGB", (256, 192), (170, 160, 150))
        draw = ImageDraw.Draw(image)
        for y in range(20, 170, 20):
            for x in range(20, 235, 20):
                draw.rectangle((x, y, x + 12, y + 12), fill=(40 + x % 80, 50, 80))
        self.assertTrue(assess(self.frame("control", image))["accepted"])

    def test_dark_blur_bright_area_and_blank_reject(self) -> None:
        patterned = Image.effect_noise((256, 192), 80).convert("RGB")
        cases = {
            "dark": Image.new("RGB", (256, 192), (5, 5, 5)),
            "blur": patterned.filter(ImageFilter.GaussianBlur(22)),
            "bright": Image.new("RGB", (256, 192), (255, 255, 255)),
            "blank": Image.new("RGB", (256, 192), (205, 205, 205)),
        }
        for name, image in cases.items():
            with self.subTest(name=name):
                self.assertFalse(assess(self.frame(name, image))["accepted"])

    def test_invalid_encoded_bytes_reject(self) -> None:
        result = assess(FrameEvidence("bad", "2026-09-25T16:00:00Z", b"not-an-image"))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reasons"], ["invalid_image"])


if __name__ == "__main__":
    unittest.main()
