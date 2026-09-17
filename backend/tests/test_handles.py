from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.handles import (
    allocate_handle,
    compose_handle_base,
    play_slug,
    resolve_game,
    slugify,
    username_slug,
)


class HandleHelperTests(unittest.TestCase):
    def test_slugify_strips_and_lowers(self) -> None:
        self.assertEqual(slugify(" Neural  Match Lab "), "neural-match-lab")
        self.assertEqual(slugify("Ångström & Co!"), "angstrom-co")
        self.assertEqual(slugify(""), "")

    def test_username_slug_from_display_or_email(self) -> None:
        self.assertEqual(username_slug(SimpleNamespace(display_name="Ada Lovelace", email="x@y.com")), "ada-lovelace")
        self.assertEqual(username_slug(SimpleNamespace(display_name="", email="Teacher@School.com")), "teacher")
        self.assertEqual(username_slug(None), "player")

    def test_compose_username_gamename(self) -> None:
        user = SimpleNamespace(display_name="Demo Teacher", email="teacher@example.com")
        self.assertEqual(compose_handle_base(user, "Neural Match Lab"), "demo-teacher-neural-match-lab")

    def test_allocate_handle_adds_suffix_when_taken(self) -> None:
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [object(), None]
        user = SimpleNamespace(display_name="Ada Lovelace", email="ada@x.com")
        self.assertEqual(allocate_handle(db, user, "Quiz"), "ada-lovelace-quiz-2")

    def test_resolve_game_by_uuid_and_handle(self) -> None:
        game = SimpleNamespace(id=uuid4(), handle="ada-quiz")
        db = MagicMock()
        db.get.return_value = game
        self.assertEqual(resolve_game(db, str(game.id)), game)

        db2 = MagicMock()
        db2.get.return_value = None
        db2.query.return_value.filter.return_value.first.return_value = game
        self.assertEqual(resolve_game(db2, "Ada-Quiz"), game)

    def test_play_slug_prefers_handle(self) -> None:
        game_id = uuid4()
        self.assertEqual(play_slug(SimpleNamespace(id=game_id, handle="ada-quiz")), "ada-quiz")
        self.assertEqual(play_slug(SimpleNamespace(id=game_id, handle=None)), str(game_id))


if __name__ == "__main__":
    unittest.main()
