from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models import GameDraft, GameSource, UserRole
from app.routers.games import _draft_to_out, generate_html_game_endpoint, publish_draft
from app.schemas import DraftPublishRequest, GameDraftOut, HtmlGenerateRequest


class DraftEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_html_creates_draft_not_game(self) -> None:
        html = "<!DOCTYPE html><html><body>draft only</body></html>"
        db = MagicMock()
        captured: dict = {}

        def add(obj):
            captured["obj"] = obj
            if isinstance(obj, GameDraft):
                obj.id = uuid4()
                obj.created_at = datetime.now(timezone.utc)
                obj.updated_at = obj.created_at

        db.add.side_effect = add
        user = SimpleNamespace(
            id=uuid4(),
            role=UserRole.teacher,
            llm_provider=None,
            llm_api_key_hash=None,
            llm_api_key_hint=None,
        )
        body = HtmlGenerateRequest(
            topic="neurons",
            levels_brief="Level 1 warm-up then practice then a boss check.",
            title="Neurons",
            difficulty=2,
            level_count=3,
            api_key="sk-test-1234567890",
            provider="openai",
        )
        with (
            patch("app.routers.games.generate_html_game", AsyncMock(return_value=(html, ["Missing LearnPlay.stage level markers"]))),
            patch("app.routers.games._write_draft_preview"),
        ):
            out = await generate_html_game_endpoint(body, db, user)
        self.assertIsInstance(captured["obj"], GameDraft)
        self.assertIsInstance(out, GameDraftOut)
        dumped = out.model_dump()
        self.assertNotIn("html", dumped)
        self.assertEqual(captured["obj"].html, html)
        self.assertTrue(out.warnings)

    async def test_publish_creates_catalog_game(self) -> None:
        draft_id = uuid4()
        user_id = uuid4()
        draft = GameDraft(
            id=draft_id,
            owner_id=user_id,
            title="Neurons",
            topic="neurons",
            description="levels",
            difficulty=2,
            level_count=3,
            language="en",
            provider="openai",
            html="<!DOCTYPE html><html><body>ok</body></html>",
            messages=[],
            warnings=[],
        )
        db = MagicMock()
        db.get.return_value = draft
        created: dict = {}

        def add(obj):
            created["game"] = obj
            obj.created_at = datetime.now(timezone.utc)

        db.add.side_effect = add
        user = SimpleNamespace(id=user_id, role=UserRole.teacher)
        with (
            patch("app.routers.games.save_uploaded_html", return_value="index.html"),
            patch("app.routers.games.write_game_preview"),
            patch("app.routers.games.game_to_out", side_effect=lambda g: SimpleNamespace(id=g.id, title=g.title, source=g.source)),
        ):
            out = publish_draft(draft_id, DraftPublishRequest(), db, user)
        self.assertEqual(created["game"].source, GameSource.ai)
        self.assertEqual(created["game"].title, "Neurons")
        self.assertEqual(draft.published_game_id, created["game"].id)
        self.assertEqual(out.title, "Neurons")


class DraftOutTests(unittest.TestCase):
    def test_draft_payload_omits_html(self) -> None:
        now = datetime.now(timezone.utc)
        out = _draft_to_out(
            SimpleNamespace(
                id=uuid4(),
                title="T",
                topic="AI",
                description="brief",
                difficulty=2,
                level_count=4,
                language="en",
                provider="openai",
                model=None,
                warnings=["Missing LearnPlay.stage level markers"],
                messages=[{"role": "assistant", "content": "Draft ready."}],
                published_game_id=None,
                created_at=now,
                updated_at=now,
                html="<html>secret</html>",
            )
        )
        dumped = out.model_dump()
        self.assertNotIn("html", dumped)
        self.assertEqual(out.messages[0].content, "Draft ready.")


if __name__ == "__main__":
    unittest.main()
