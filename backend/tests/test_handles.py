from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import HTTPException

from app.models import UserRole
from app.services.accounts import delete_user_keeping_games
from app.services.handles import (
    allocate_handle,
    compose_handle_base,
    migrate_handle,
    play_slug,
    resolve_game,
    slugify,
    split_handle,
    user_slug_for_game,
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

    def test_compose_username_slash_gamename(self) -> None:
        user = SimpleNamespace(display_name="Demo Teacher", email="teacher@example.com")
        self.assertEqual(compose_handle_base(user, "Neural Match Lab"), "demo-teacher/neural-match-lab")

    def test_split_handle(self) -> None:
        self.assertEqual(split_handle("ada/quiz"), ("ada", "quiz"))
        self.assertIsNone(split_handle("ada-quiz"))

    def test_migrate_hyphenated_handle(self) -> None:
        user = SimpleNamespace(display_name="Example Teacher", email="teacher@example.com")
        game = SimpleNamespace(title="Neural Match Lab", handle="example-teacher-neural-match-lab")
        self.assertEqual(migrate_handle(game, user), "example-teacher/neural-match-lab")
        already = SimpleNamespace(title="Neural Match Lab", handle="example-teacher/neural-match-lab")
        self.assertIsNone(migrate_handle(already, user))

    def test_allocate_handle_adds_suffix_when_taken(self) -> None:
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [object(), None]
        user = SimpleNamespace(display_name="Ada Lovelace", email="ada@x.com")
        self.assertEqual(allocate_handle(db, user, "Quiz"), "ada-lovelace/quiz-2")

    def test_resolve_game_by_uuid_and_handle(self) -> None:
        game = SimpleNamespace(id=uuid4(), handle="ada/quiz")
        db = MagicMock()
        db.get.return_value = game
        self.assertEqual(resolve_game(db, str(game.id)), game)

        db2 = MagicMock()
        db2.get.return_value = None
        db2.query.return_value.filter.return_value.first.return_value = game
        self.assertEqual(resolve_game(db2, "Ada/Quiz"), game)

    def test_user_slug_survives_deleted_owner(self) -> None:
        game = SimpleNamespace(handle="example-teacher/neural-match-lab")
        self.assertEqual(user_slug_for_game(game, None), "example-teacher")

    def test_play_slug_prefers_handle(self) -> None:
        game_id = uuid4()
        self.assertEqual(play_slug(SimpleNamespace(id=game_id, handle="ada/quiz")), "ada/quiz")
        self.assertEqual(play_slug(SimpleNamespace(id=game_id, handle=None)), str(game_id))


class DeleteUserKeepsGamesTests(unittest.TestCase):
    def test_nulls_game_owner_and_deletes_user(self) -> None:
        actor_id = uuid4()
        target_id = uuid4()
        game = SimpleNamespace(id=uuid4(), owner_id=target_id)
        target = SimpleNamespace(id=target_id, role=UserRole.teacher)
        actor = SimpleNamespace(id=actor_id, role=UserRole.admin)
        db = MagicMock()
        db.get.return_value = target

        def query(model):
            q = MagicMock()
            q.filter.return_value = q
            q.update.return_value = 0
            q.delete.return_value = 0
            if model.__name__ == "Game":
                q.all.return_value = [game]
            elif model.__name__ == "Classroom":
                q.all.return_value = []
            elif model.__name__ == "User":
                q.count.return_value = 2
            else:
                q.all.return_value = []
            return q

        db.query.side_effect = query
        delete_user_keeping_games(db, actor=actor, user_id=target_id)
        self.assertIsNone(game.owner_id)
        db.delete.assert_called_with(target)
        db.commit.assert_called()

    def test_cannot_delete_self(self) -> None:
        user_id = uuid4()
        user = SimpleNamespace(id=user_id, role=UserRole.admin)
        db = MagicMock()
        db.get.return_value = user
        with self.assertRaises(HTTPException) as ctx:
            delete_user_keeping_games(db, actor=user, user_id=user_id)
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
