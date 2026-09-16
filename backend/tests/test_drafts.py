from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.models import GameDraft, GameSource, UserRole
from app.routers.games import (
    GAME_FRAME_CSP,
    GAME_IFRAME_SANDBOX,
    _draft_to_out,
    chat_draft,
    game_file_headers,
    generate_html_game_endpoint,
    publish_draft,
)
from app.schemas import DraftChatRequest, DraftPublishRequest, GameDraftOut, HtmlGenerateRequest


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

    async def test_chat_creates_draft_from_message(self) -> None:
        html = "<!DOCTYPE html><html><title>Gravity Lab</title><body>ok</body></html>"
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
        body = DraftChatRequest(
            message="Make 4 levels about gravity",
            api_key="sk-test-1234567890",
            provider="openai",
        )
        with (
            patch(
                "app.routers.games.generate_html_from_chat",
                AsyncMock(return_value=(html, [], "Gravity Lab", 4)),
            ),
            patch("app.routers.games._write_draft_preview"),
        ):
            out = await chat_draft(body, db, user)
        self.assertIsInstance(captured["obj"], GameDraft)
        self.assertEqual(captured["obj"].messages[0]["role"], "user")
        self.assertEqual(out.title, "Gravity Lab")
        self.assertNotIn("html", out.model_dump())


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
                owner_id=uuid4(),
                created_at=now,
                updated_at=now,
                html="<html>secret</html>",
            )
        )
        dumped = out.model_dump()
        self.assertNotIn("html", dumped)
        self.assertTrue(out.preview_token)
        self.assertEqual(out.messages[0].content, "Draft ready.")


class FrameIsolationTests(unittest.TestCase):
    def test_game_files_send_restrictive_csp(self) -> None:
        headers = game_file_headers()
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("sandbox", headers["Content-Security-Policy"])
        self.assertNotIn("frame-ancestors", headers["Content-Security-Policy"])
        self.assertNotIn("X-Frame-Options", headers)
        self.assertNotIn("allow-same-origin", headers["Content-Security-Policy"])
        self.assertEqual(headers["Content-Security-Policy"], GAME_FRAME_CSP)
        self.assertEqual(GAME_IFRAME_SANDBOX, "allow-scripts allow-forms")
        self.assertNotIn("allow-same-origin", GAME_IFRAME_SANDBOX)

    def test_play_and_creator_iframes_are_opaque(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        play = (root / "frontend/src/pages/Play.tsx").read_text(encoding="utf-8")
        frame = (root / "frontend/src/GameFrame.tsx").read_text(encoding="utf-8")
        creator = (root / "frontend/src/pages/Creator.tsx").read_text(encoding="utf-8")
        studio = (root / "frontend/src/CreatorDraftStudio.tsx").read_text(encoding="utf-8")
        self.assertIn("GameFrame", play)
        self.assertNotIn("allow-same-origin", play)
        self.assertNotIn("allow-same-origin", frame)
        self.assertIn("allow-scripts allow-forms", frame)
        self.assertIn("connect-src 'none'", frame)
        self.assertIn("sandbox={GAME_IFRAME_SANDBOX}", frame)
        self.assertNotIn("frame-ancestors", frame)
        self.assertNotIn("sandbox allow-scripts", frame)
        self.assertNotIn("Upload game", creator)
        self.assertIn("/api/games/drafts/chat", creator)
        self.assertIn("GameFrame", studio)
        self.assertIn("/t/", studio)
        self.assertIn("tryExampleChat", studio)
        self.assertIn("onSend(example)", studio)
        self.assertNotIn("/files/", studio)


class DraftFileTokenTests(unittest.TestCase):
    def test_token_is_bound_to_draft(self) -> None:
        from app.auth import create_draft_file_token, decode_draft_file_token

        draft_id = uuid4()
        owner_id = uuid4()
        token = create_draft_file_token(draft_id, owner_id)
        self.assertEqual(decode_draft_file_token(token, draft_id), owner_id)
        with self.assertRaises(HTTPException):
            decode_draft_file_token(token, uuid4())

    def test_serve_draft_file_rejects_wrong_owner(self) -> None:
        from app.auth import create_draft_file_token
        from app.routers.games import serve_draft_file

        draft_id = uuid4()
        token = create_draft_file_token(draft_id, uuid4())
        db = MagicMock()
        db.get.return_value = SimpleNamespace(
            id=draft_id,
            owner_id=uuid4(),
            published_game_id=None,
        )
        with self.assertRaises(HTTPException) as ctx:
            serve_draft_file(draft_id, token, "index.html", db)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_serve_draft_file_restores_html(self) -> None:
        from pathlib import Path
        import tempfile

        from app.auth import create_draft_file_token
        from app.routers.games import serve_draft_file

        draft_id = uuid4()
        owner_id = uuid4()
        token = create_draft_file_token(draft_id, owner_id)
        db = MagicMock()
        db.get.return_value = SimpleNamespace(
            id=draft_id,
            owner_id=owner_id,
            published_game_id=None,
            html="<!DOCTYPE html><html><body>draft ok</body></html>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / str(draft_id)
            dest.mkdir()
            with (
                patch("app.routers.games.draft_dir", return_value=dest),
                patch("app.routers.games.save_draft_html") as save,
            ):
                def write(_id, html):
                    (dest / "index.html").write_text(html, encoding="utf-8")
                    return "index.html"

                save.side_effect = write
                resp = serve_draft_file(draft_id, token, "index.html", db)
        save.assert_called_once()
        self.assertTrue(Path(resp.path).name == "index.html")


class ViewCapTests(unittest.TestCase):
    def test_view_without_identity_is_ignored(self) -> None:
        from app.routers.games import record_game_view

        game_id = uuid4()
        db = MagicMock()
        db.get.return_value = SimpleNamespace(id=game_id)
        record_game_view(game_id, db, None, None)
        db.add.assert_not_called()

    def test_view_dedupes_same_visitor(self) -> None:
        from app.routers.games import record_game_view

        game_id = uuid4()
        db = MagicMock()
        db.get.return_value = SimpleNamespace(id=game_id)
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = object()
        db.query.return_value = query
        record_game_view(game_id, db, None, "visitor-abc")
        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
