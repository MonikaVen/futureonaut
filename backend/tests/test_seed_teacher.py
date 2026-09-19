from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.config import Settings
from app.main import lifespan
from app.seed import DEMO_TEACHER_JOIN_CODE, seed_creator, seed_teacher


def _teacher_settings(**overrides) -> SimpleNamespace:
    values = {
        "teacher_email": "teacher@example.com",
        "teacher_password": "teacher12345",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _creator_settings(**overrides) -> SimpleNamespace:
    values = {
        "creator_email": "futureonaut@example.com",
        "creator_password": "creator12345",
        "creator_display_name": "futureonaut",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class SeedTeacherTests(unittest.TestCase):
    def test_default_teacher_credentials_are_empty(self) -> None:
        settings = Settings()
        self.assertEqual(settings.teacher_email, "")
        self.assertEqual(settings.teacher_password, "")
        self.assertLessEqual(len(DEMO_TEACHER_JOIN_CODE), 8)

    def test_boot_creates_teacher(self) -> None:
        self.assertIn("seed_teacher()", inspect.getsource(lifespan))
        self.assertIn("seed_creator()", inspect.getsource(lifespan))
        self.assertTrue(callable(seed_teacher))

    def test_skips_when_password_empty(self) -> None:
        db = MagicMock()
        with (
            patch("app.seed.SessionLocal", return_value=db),
            patch("app.seed.get_settings", return_value=_teacher_settings(teacher_password="")),
            patch("app.seed.hash_password") as hashed,
        ):
            seed_teacher()
        hashed.assert_not_called()
        db.query.assert_not_called()

    def test_existing_teacher_password_is_not_reset(self) -> None:
        from app.models import User, UserRole

        teacher = SimpleNamespace(
            id=uuid4(),
            role=UserRole.teacher,
            password_hash="keep-me",
            display_name="Example Teacher",
        )
        db = MagicMock()

        def query(model):
            q = MagicMock()
            if model is User:
                q.filter.return_value.first.return_value = teacher
            else:
                q.filter.return_value.first.return_value = object()
            return q

        db.query.side_effect = query
        with (
            patch("app.seed.SessionLocal", return_value=db),
            patch("app.seed.get_settings", return_value=_teacher_settings()),
            patch("app.seed.hash_password") as hashed,
        ):
            seed_teacher()
        hashed.assert_not_called()
        self.assertEqual(teacher.password_hash, "keep-me")

    def test_existing_admin_password_is_not_reset(self) -> None:
        from app.models import UserRole
        from app.seed import seed_admin

        admin = SimpleNamespace(
            id=uuid4(),
            role=UserRole.learner,
            password_hash="keep-admin",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = admin
        with (
            patch("app.seed.SessionLocal", return_value=db),
            patch("app.seed.hash_password") as hashed,
        ):
            seed_admin()
        hashed.assert_not_called()
        self.assertEqual(admin.password_hash, "keep-admin")
        self.assertEqual(admin.role, UserRole.learner)


class SeedCreatorTests(unittest.TestCase):
    def test_default_creator_credentials_are_empty(self) -> None:
        settings = Settings()
        self.assertEqual(settings.creator_email, "")
        self.assertEqual(settings.creator_password, "")
        self.assertEqual(settings.creator_display_name, "futureonaut")

    def test_skips_when_password_empty(self) -> None:
        db = MagicMock()
        with (
            patch("app.seed.SessionLocal", return_value=db),
            patch("app.seed.get_settings", return_value=_creator_settings(creator_password="")),
            patch("app.seed.hash_password") as hashed,
        ):
            seed_creator()
        hashed.assert_not_called()
        db.query.assert_not_called()

    def test_existing_creator_password_is_not_reset(self) -> None:
        from app.models import UserRole

        creator = SimpleNamespace(
            id=uuid4(),
            role=UserRole.creator,
            password_hash="keep-creator",
            display_name="futureonaut",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = creator
        with (
            patch("app.seed.SessionLocal", return_value=db),
            patch("app.seed.get_settings", return_value=_creator_settings()),
            patch("app.seed.hash_password") as hashed,
        ):
            seed_creator()
        hashed.assert_not_called()
        self.assertEqual(creator.password_hash, "keep-creator")
        self.assertEqual(creator.role, UserRole.creator)

    def test_promotes_existing_account_to_creator(self) -> None:
        from app.models import UserRole

        user = SimpleNamespace(
            id=uuid4(),
            role=UserRole.learner,
            password_hash="keep-me",
            display_name="other",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        with (
            patch("app.seed.SessionLocal", return_value=db),
            patch("app.seed.get_settings", return_value=_creator_settings()),
            patch("app.seed.hash_password") as hashed,
        ):
            seed_creator()
        hashed.assert_not_called()
        self.assertEqual(user.role, UserRole.creator)
        self.assertEqual(user.display_name, "futureonaut")
        db.commit.assert_called()


if __name__ == "__main__":
    unittest.main()
