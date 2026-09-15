from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError

from app.schemas import GameUpdate
from app.services.demo_seed import (
    prune_games_to_manifest,
    refresh_seed_html,
    seed_demo_games,
)


class CatalogCurationTests(unittest.TestCase):
    def test_boot_only_seeds_empty_catalog(self) -> None:
        source = inspect.getsource(seed_demo_games)
        self.assertIn("db.query(Game).count() == 0", source)
        self.assertNotIn("prune_games_to_manifest(db)", source)
        self.assertNotIn("refresh_seed_html(db)", source)
        before, after = source.split("if db.query(Game).count() == 0:", 1)
        empty_branch, rest = after.split("backfill_seed_files", 1)
        self.assertIn("seed_html_pack", empty_branch)
        self.assertNotIn("seed_html_pack", rest)
        self.assertNotIn("seed_html_pack", before)

    def test_prune_and_refresh_do_not_touch_catalog(self) -> None:
        prune_games_to_manifest(SimpleNamespace())
        refresh_seed_html(SimpleNamespace())

    def test_populated_catalog_does_not_insert_seed_pack(self) -> None:
        db = MagicMock()
        admin = SimpleNamespace(id=uuid4(), role="admin")
        db.query.return_value.filter.return_value.first.return_value = admin
        db.query.return_value.count.return_value = 5
        with (
            patch("app.services.demo_seed.SessionLocal", return_value=db),
            patch("app.services.demo_seed.seed_html_pack") as pack,
            patch("app.services.demo_seed.backfill_seed_files"),
            patch("app.services.demo_seed.normalize_game_topics"),
            patch("app.services.demo_seed.restore_missing_game_files"),
            patch("app.services.demo_seed.restore_missing_template_html"),
            patch("app.services.demo_seed.refresh_game_previews"),
        ):
            seed_demo_games()
        pack.assert_not_called()

    def test_title_update_rejects_blank(self) -> None:
        with self.assertRaises(ValidationError):
            GameUpdate(title="")
        parsed = GameUpdate(title="Renamed game")
        self.assertEqual(parsed.title, "Renamed game")


if __name__ == "__main__":
    unittest.main()
