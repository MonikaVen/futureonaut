from __future__ import annotations

import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError

from app.models import UserRole
from app.schemas import GameUpdate
from app.services.demo_seed import (
    REUPLOAD_SEED_FILES,
    prune_games_to_manifest,
    refresh_seed_html,
    seed_demo_games,
)


class CatalogCurationTests(unittest.TestCase):
    def test_boot_only_seeds_empty_catalog(self) -> None:
        source = inspect.getsource(seed_demo_games)
        self.assertIn("restore_published_html", source)
        self.assertIn("assign_catalog_to_owner", source)
        self.assertIn("reupload_seed_games", source)
        self.assertIn("db.query(Game).count() == 0", source)
        self.assertNotIn("prune_games_to_manifest(db)", source)
        self.assertNotIn("refresh_seed_html(db)", source)
        before, after = source.split("if db.query(Game).count() == 0:", 1)
        empty_branch, rest = after.split("backfill_seed_files", 1)
        self.assertIn("seed_html_pack", empty_branch)
        self.assertNotIn("seed_html_pack", rest)
        self.assertNotIn("seed_html_pack", before)
        self.assertIn("reupload_seed_games", rest)

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
            patch("app.services.demo_seed.reupload_seed_games"),
            patch("app.services.demo_seed.normalize_game_topics"),
            patch("app.services.demo_seed.restore_published_html"),
            patch("app.services.demo_seed.restore_missing_game_files"),
            patch("app.services.demo_seed.restore_missing_template_html"),
            patch("app.services.demo_seed.refresh_game_previews"),
            patch("app.services.demo_seed.backfill_game_handles"),
            patch("app.services.demo_seed.assign_catalog_to_owner"),
        ):
            seed_demo_games()
        pack.assert_not_called()

    def test_title_update_rejects_blank(self) -> None:
        with self.assertRaises(ValidationError):
            GameUpdate(title="")
        parsed = GameUpdate(title="Renamed game")
        self.assertEqual(parsed.title, "Renamed game")

    def test_assign_catalog_moves_games_to_futureonaut(self) -> None:
        from app.services.demo_seed import assign_catalog_to_owner

        owner_id = uuid4()
        owner = SimpleNamespace(id=owner_id, display_name="futureonaut", email="futureonaut@example.com")
        admin = SimpleNamespace(id=uuid4(), role=UserRole.admin, email="admin@example.com")
        game = SimpleNamespace(
            id=uuid4(),
            title="Neural Match Lab",
            handle="example-teacher/neural-match-lab",
            owner_id=admin.id,
        )
        settings = SimpleNamespace(catalog_assigned=False)
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None
        q.all.return_value = [game]
        db.query.return_value = q
        db.get.return_value = admin
        with patch("app.services.prompts.get_or_create_platform_settings", return_value=settings):
            assign_catalog_to_owner(db, owner)
        self.assertEqual(game.owner_id, owner_id)
        self.assertEqual(game.handle, "futureonaut/neural-match-lab")
        self.assertTrue(settings.catalog_assigned)
        db.commit.assert_called()

    def test_assign_catalog_skips_when_already_assigned(self) -> None:
        from app.services.demo_seed import assign_catalog_to_owner

        owner = SimpleNamespace(id=uuid4(), display_name="futureonaut", email="futureonaut@example.com")
        game = SimpleNamespace(owner_id=uuid4(), handle="other/game", title="X")
        settings = SimpleNamespace(catalog_assigned=True)
        db = MagicMock()
        with patch("app.services.prompts.get_or_create_platform_settings", return_value=settings):
            assign_catalog_to_owner(db, owner)
        self.assertNotEqual(game.owner_id, owner.id)
        db.commit.assert_not_called()

    def test_assign_catalog_skips_other_creators(self) -> None:
        from app.services.demo_seed import assign_catalog_to_owner

        owner = SimpleNamespace(id=uuid4(), display_name="futureonaut", email="futureonaut@example.com")
        other = SimpleNamespace(id=uuid4(), role=UserRole.creator, email="other@example.com")
        game = SimpleNamespace(id=uuid4(), title="Other Game", handle="other/game", owner_id=other.id)
        settings = SimpleNamespace(catalog_assigned=False)
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None
        q.all.return_value = [game]
        db.query.return_value = q
        db.get.return_value = other
        with patch("app.services.prompts.get_or_create_platform_settings", return_value=settings):
            assign_catalog_to_owner(db, owner)
        self.assertEqual(game.owner_id, other.id)
        self.assertEqual(game.handle, "other/game")
        self.assertTrue(settings.catalog_assigned)

    def test_reupload_updates_html_and_inserts_missing(self) -> None:
        from app.services.demo_seed import reupload_seed_games

        owner = SimpleNamespace(id=uuid4(), display_name="futureonaut", email="futureonaut@example.com")
        existing = SimpleNamespace(
            id=uuid4(),
            title="Liucian Hungry Bandit",
            seed_file="liucian_hungry_bandit.html",
            entry_path="index.html",
            html="<html>old</html>",
        )
        db = MagicMock()
        db.query.return_value.all.return_value = [existing]
        item = {
            "file": "liucian_hungry_bandit.html",
            "title": "Liucian Hungry Bandit",
            "description": "Explore or exploit",
            "topic_tags": ["AI"],
            "difficulty": 2,
        }
        with (
            patch(
                "app.services.demo_seed._manifest_items",
                return_value=[
                    item,
                    {
                        "file": "liucian_gradient_valley.html",
                        "title": "Liucian Gradient Valley",
                        "description": "Loss landscape",
                        "topic_tags": ["AI"],
                        "difficulty": 2,
                    },
                ],
            ),
            patch("app.services.demo_seed._seed_dir") as seed_dir,
            patch("app.services.demo_seed.save_uploaded_html", return_value="index.html"),
            patch("app.services.demo_seed.write_game_preview"),
            patch("app.services.demo_seed._insert_seed_game") as insert,
        ):
            hungry = SimpleNamespace(exists=lambda: True)
            hungry.read_text.return_value = "<html>new bandit</html>"
            valley = SimpleNamespace(exists=lambda: True)
            valley.read_text.return_value = "<html>new valley</html>"
            seed_dir.return_value.__truediv__.side_effect = lambda name: (
                hungry if name == "liucian_hungry_bandit.html" else valley
            )
            inserted = SimpleNamespace(id=uuid4(), title="Liucian Gradient Valley", seed_file="liucian_gradient_valley.html")
            insert.return_value = inserted
            reupload_seed_games(db, owner)
        self.assertEqual(existing.html, "<html>new bandit</html>")
        insert.assert_called_once()
        db.commit.assert_called()

    def test_reupload_files_are_in_the_seed_pack(self) -> None:
        from pathlib import Path

        seed_dir = Path(__file__).resolve().parents[1] / "seed_games"
        manifest = {item["file"] for item in json.loads((seed_dir / "manifest.json").read_text(encoding="utf-8"))}
        for name in REUPLOAD_SEED_FILES:
            self.assertIn(name, manifest, name)
            self.assertTrue((seed_dir / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
