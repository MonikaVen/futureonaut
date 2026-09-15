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


if __name__ == "__main__":
    unittest.main()
