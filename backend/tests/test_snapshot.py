from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from PIL import Image


class SnapshotTests(unittest.TestCase):
    def _game(self, **kwargs):
        defaults = dict(
            id=uuid4(),
            title="Intro to Neural Nets",
            description="Quick quiz on basic neural network concepts.",
            topic_tags=["AI"],
            difficulty=1,
            template_type="quiz",
            entry_path="index.html",
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_quiz_preview_is_png_1200x630(self) -> None:
        from app.services.snapshot import render_preview_png

        game = self._game()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / str(game.id)
            dest.mkdir()
            (dest / "content.json").write_text(
                json.dumps(
                    {
                        "title": "Intro to Neural Nets",
                        "questions": [
                            {
                                "prompt": "What does a neuron compute first?",
                                "options": [
                                    {"text": "A weighted sum of inputs"},
                                    {"text": "Only the bias"},
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with patch("app.services.snapshot.game_dir", return_value=dest):
                png = render_preview_png(game)
        self.assertTrue(png.startswith(b"\x89PNG"))
        img = Image.open(io.BytesIO(png))
        self.assertEqual(img.size, (1200, 630))
        self.assertEqual(img.format, "PNG")

    def test_ensure_writes_preview_once(self) -> None:
        from app.services.snapshot import PREVIEW_FILENAME, ensure_game_preview

        game = self._game(template_type="drag_match", title="Tokenization Match")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / str(game.id)
            dest.mkdir()
            (dest / "content.json").write_text(
                json.dumps(
                    {
                        "title": "Tokenization Match",
                        "pairs": [{"left": "Token", "right": "A unit of text"}],
                    }
                ),
                encoding="utf-8",
            )
            with patch("app.services.snapshot.game_dir", return_value=dest):
                path = ensure_game_preview(game)
                again = ensure_game_preview(game)
            self.assertEqual(path.name, PREVIEW_FILENAME)
            self.assertEqual(path, again)
            self.assertGreater(path.stat().st_size, 800)
            with Image.open(path) as img:
                self.assertEqual(img.size, (1200, 630))

    def test_html_game_falls_back_without_content_json(self) -> None:
        from app.services.snapshot import render_preview_png

        game = self._game(template_type=None, title="Orbit Lab")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / str(game.id)
            dest.mkdir()
            (dest / "index.html").write_text(
                "<html><body><h1>Orbit Lab</h1><button>Play</button></body></html>",
                encoding="utf-8",
            )
            with patch("app.services.snapshot.game_dir", return_value=dest):
                png = render_preview_png(game)
        img = Image.open(io.BytesIO(png))
        self.assertEqual(img.size, (1200, 630))

    def test_light_theme_html_stays_readable(self) -> None:
        from app.services.snapshot import _palette, render_preview_png

        game = self._game(template_type=None, title="Find Liucians Friends KNN")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / str(game.id)
            dest.mkdir()
            (dest / "index.html").write_text(
                """<html><style>:root{--bg:#f7f7f8;--card:#fff;--text:#1f2937;--muted:#6b7280;--border:#d1d5db}
                body{background:#fff;color:var(--text)}</style>
                <body><h1>Find Liucian's Friends</h1><button>Predict friend group</button></body></html>""",
                encoding="utf-8",
            )
            with patch("app.services.snapshot.game_dir", return_value=dest):
                palette = _palette(game, dest)
                png = render_preview_png(game)
        self.assertLess(sum(palette["ink"]) / 3, 80)
        self.assertGreater(sum(palette["bg"]) / 3, 200)
        img = Image.open(io.BytesIO(png))
        self.assertEqual(img.size, (1200, 630))

    def test_cover_crop_center_fills_target(self) -> None:
        from app.services.snapshot import OG_SIZE, cover_crop

        src = Image.new("RGB", (400, 800), (20, 180, 80))
        src.paste(Image.new("RGB", (400, 80), (220, 40, 40)), (0, 0))
        src.paste(Image.new("RGB", (400, 80), (40, 80, 220)), (0, 720))
        cropped = cover_crop(src)
        self.assertEqual(cropped.size, OG_SIZE)
        self.assertEqual(cropped.getpixel((600, 315)), (20, 180, 80))

    def test_save_icon_prefers_provided_file_over_screenshot(self) -> None:
        from app.services.snapshot import ICON_FILENAME, render_preview_png, save_game_icon

        game = self._game(title="Icon Card")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / str(game.id)
            dest.mkdir()
            screenshot = Image.new("RGB", (1400, 900), (12, 24, 180))
            screenshot.save(dest / "snapshot.png")
            buf = io.BytesIO()
            Image.new("RGB", (300, 500), (230, 70, 40)).save(buf, format="PNG")
            save_game_icon(dest, buf.getvalue())
            self.assertTrue((dest / ICON_FILENAME).is_file())
            with patch("app.services.snapshot.game_dir", return_value=dest):
                png = render_preview_png(game)
        img = Image.open(io.BytesIO(png))
        self.assertEqual(img.size, (1200, 630))
        self.assertEqual(img.getpixel((20, 20)), (230, 70, 40))
        self.assertEqual(img.getpixel((1180, 610)), (230, 70, 40))

    def test_promote_pack_icon_from_zip_candidate(self) -> None:
        from app.services.snapshot import ICON_FILENAME, promote_pack_icon

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            Image.new("RGB", (80, 120), (18, 200, 160)).save(dest / "poster.png")
            path = promote_pack_icon(dest)
            self.assertIsNotNone(path)
            self.assertEqual(path.name, ICON_FILENAME)
            with Image.open(path) as img:
                self.assertEqual(img.size, (1200, 630))
                self.assertEqual(img.getpixel((10, 10)), (18, 200, 160))

    def test_has_screenshot_only_when_icon_saved(self) -> None:
        from app.services.snapshot import has_game_screenshot, save_game_icon

        game = self._game()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / str(game.id)
            dest.mkdir()
            settings = SimpleNamespace(games_dir=tmp)
            with patch("app.services.snapshot.get_settings", return_value=settings):
                self.assertFalse(has_game_screenshot(game.id))
                buf = io.BytesIO()
                Image.new("RGB", (64, 64), (90, 40, 200)).save(buf, format="PNG")
                save_game_icon(dest, buf.getvalue())
                self.assertTrue(has_game_screenshot(game.id))


if __name__ == "__main__":
    unittest.main()
