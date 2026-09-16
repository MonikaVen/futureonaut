from __future__ import annotations

import inspect
import unittest

from app.config import Settings
from app.main import lifespan
from app.seed import DEMO_TEACHER_JOIN_CODE, seed_teacher


class SeedTeacherTests(unittest.TestCase):
    def test_default_teacher_credentials(self) -> None:
        settings = Settings()
        self.assertEqual(settings.teacher_email, "teacher@example.com")
        self.assertEqual(settings.teacher_password, "teacher12345")
        self.assertLessEqual(len(DEMO_TEACHER_JOIN_CODE), 8)

    def test_boot_creates_teacher(self) -> None:
        self.assertIn("seed_teacher()", inspect.getsource(lifespan))
        self.assertTrue(callable(seed_teacher))

    def test_existing_teacher_password_is_not_reset(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from uuid import uuid4

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
            patch("app.seed.hash_password") as hashed,
        ):
            seed_teacher()
        hashed.assert_not_called()
        self.assertEqual(teacher.password_hash, "keep-me")

    def test_existing_admin_password_is_not_reset(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from uuid import uuid4

        from app.models import User, UserRole
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


if __name__ == "__main__":
    unittest.main()
