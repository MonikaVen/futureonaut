from __future__ import annotations

import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from PIL import Image

from app.models import UserRole
from app.services.avatars import has_user_avatar, save_user_avatar
from app.services.creators import creator_slug, find_user_by_slug, public_creator_out
from app.services.handles import username_slug


class AvatarTests(unittest.TestCase):
    def test_saves_square_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("app.services.avatars.avatars_root", return_value=Path(tmp)):
                user_id = uuid4()
                image = Image.new("RGB", (80, 40), (0, 212, 255))
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                path = save_user_avatar(user_id, buf.getvalue())
                self.assertTrue(path.is_file())
                self.assertTrue(has_user_avatar(user_id))
                saved = Image.open(path)
                self.assertEqual(saved.size, (512, 512))
                saved.close()


class CreatorSlugTests(unittest.TestCase):
    def test_finds_user_by_display_name_slug(self) -> None:
        user = SimpleNamespace(
            id=uuid4(),
            display_name="futureonaut",
            email="futureonaut@example.com",
            role=UserRole.creator,
        )
        db = MagicMock()
        db.query.return_value.all.return_value = [user]
        found = find_user_by_slug(db, "futureonaut")
        self.assertIs(found, user)
        self.assertEqual(creator_slug(user), "futureonaut")
        self.assertEqual(username_slug(user), "futureonaut")

    def test_public_out_includes_slug(self) -> None:
        user = SimpleNamespace(
            id=uuid4(),
            display_name="Ada Lovelace",
            email="ada@example.com",
            role=UserRole.creator,
            created_at=datetime.now(timezone.utc),
        )
        with patch("app.services.creators.has_user_avatar", return_value=False):
            out = public_creator_out(user, 3)
        self.assertEqual(out.slug, "ada-lovelace")
        self.assertEqual(out.game_count, 3)
        self.assertFalse(out.has_avatar)


if __name__ == "__main__":
    unittest.main()
