from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.prompts import (
    DEFAULT_STYLE_GUIDELINES,
    normalize_style_source,
    resolve_style_guidelines,
)
from app.services.recommendations import game_is_new, game_to_out
from app.models import GameSource


class StyleGuidelineTests(unittest.TestCase):
    def test_normalize_defaults_to_futureonaut(self) -> None:
        self.assertEqual(normalize_style_source(None), "futureonaut")
        self.assertEqual(normalize_style_source("custom"), "custom")
        self.assertEqual(normalize_style_source("nope"), "futureonaut")

    def test_resolve_uses_platform_default_unless_custom(self) -> None:
        settings = SimpleNamespace(style_guidelines="DEFAULT STYLE TEXT")
        user = SimpleNamespace(style_source="futureonaut", style_guidelines="CUSTOM LOOK")
        self.assertEqual(resolve_style_guidelines(settings, user), "DEFAULT STYLE TEXT")
        user.style_source = "custom"
        self.assertEqual(resolve_style_guidelines(settings, user), "CUSTOM LOOK")
        user.style_guidelines = "  "
        self.assertEqual(resolve_style_guidelines(settings, user), "DEFAULT STYLE TEXT")

    def test_empty_platform_falls_back_to_builtin(self) -> None:
        settings = SimpleNamespace(style_guidelines="  ")
        self.assertEqual(resolve_style_guidelines(settings, None), DEFAULT_STYLE_GUIDELINES)


class NewGameStickerTests(unittest.TestCase):
    def test_recent_games_are_new(self) -> None:
        now = datetime.now(timezone.utc)
        self.assertTrue(game_is_new(now, now=now))
        self.assertTrue(game_is_new(now - timedelta(days=6), now=now))
        self.assertFalse(game_is_new(now - timedelta(days=8), now=now))
        self.assertFalse(game_is_new(None, now=now))

    def test_game_to_out_sets_is_new(self) -> None:
        game = SimpleNamespace(
            id=uuid4(),
            title="New Lab",
            description="",
            owner_id=None,
            owner=None,
            source=GameSource.ai,
            topic_tags=["AI"],
            difficulty=1,
            entry_path="index.html",
            template_type=None,
            source_language="en",
            handle="futureonaut/new-lab",
            created_at=datetime.now(timezone.utc),
        )
        out = game_to_out(game)
        self.assertTrue(out.is_new)
        self.assertEqual(out.owner_slug, "futureonaut")


class LlmKeyCryptoTests(unittest.TestCase):
    def test_encrypt_roundtrip_is_not_plaintext(self) -> None:
        from app.services.llm import decrypt_api_key, encrypt_api_key, upsert_llm_key

        secret = "sk-live-abcdefghijklmnopqrstuv"
        token = encrypt_api_key(secret)
        self.assertNotIn(secret, token)
        self.assertEqual(decrypt_api_key(token), secret)

        user = SimpleNamespace(
            id=uuid4(),
            llm_provider=None,
            llm_api_key_hash=None,
            llm_api_key_hint=None,
        )
        stored = {}

        class Query:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return stored.get("row")

        db = MagicMock()
        db.query.return_value = Query()

        def add(obj):
            stored.setdefault("row", obj)

        db.add.side_effect = add
        upsert_llm_key(db, user, "openai", secret)
        self.assertEqual(user.llm_provider, "openai")
        self.assertNotEqual(user.llm_api_key_hash, secret)
        self.assertTrue(stored["row"].key_ciphertext)
        self.assertNotIn(secret, stored["row"].key_ciphertext)

    def test_resolve_uses_saved_key_when_request_omits_it(self) -> None:
        from app.services.llm import encrypt_api_key, resolve_llm_key

        secret = "sk-live-abcdefghijklmnopqrstuv"
        user = SimpleNamespace(id=uuid4(), llm_provider="openai")
        row = SimpleNamespace(key_ciphertext=encrypt_api_key(secret))

        class Query:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return row

        db = MagicMock()
        db.query.return_value = Query()
        provider, key = resolve_llm_key(db, user, "openai", None)
        self.assertEqual(provider, "openai")
        self.assertEqual(key, secret)


if __name__ == "__main__":
    unittest.main()
