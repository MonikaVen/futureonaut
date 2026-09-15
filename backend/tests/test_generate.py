from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.auth import can_author_games
from app.models import UserRole
from app.services.generate import html_game_prompt
from app.services.llm import (
    STAGE_INSTRUCTIONS,
    api_key_hint,
    extract_html,
    hash_api_key,
    store_llm_key,
    validate_generated_html,
)


SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<body>
  <h1>Tokens</h1>
  <button id="next">Next</button>
  <script>
    const TOTAL = 3;
    let done = 0;
    function win() {
      done = TOTAL;
      LearnPlay.stage(TOTAL, TOTAL, { complete: true, score: 30, label: "Complete" });
    }
    LearnPlay.stage(1, TOTAL, { label: "Warm-up", id: "level-1", points: 10, correct: true });
  </script>
</body>
</html>
"""


class ApiKeyHashTests(unittest.TestCase):
    def test_hash_is_stable_and_not_plaintext(self) -> None:
        key = "sk-test-1234567890abcdef"
        digest = hash_api_key(key)
        self.assertNotEqual(digest, key)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, hash_api_key("  " + key + "  "))
        self.assertEqual(api_key_hint(key), "cdef")

    def test_store_llm_key_writes_hash_only(self) -> None:
        user = SimpleNamespace(llm_provider=None, llm_api_key_hash=None, llm_api_key_hint=None)
        store_llm_key(user, "openai", "sk-live-abcdefghijklmnopqrstuv")
        self.assertEqual(user.llm_provider, "openai")
        self.assertEqual(user.llm_api_key_hash, hash_api_key("sk-live-abcdefghijklmnopqrstuv"))
        self.assertNotEqual(user.llm_api_key_hash, "sk-live-abcdefghijklmnopqrstuv")
        self.assertEqual(user.llm_api_key_hint, "stuv")


class AuthorAccessTests(unittest.TestCase):
    def test_teacher_and_creator_can_author(self) -> None:
        self.assertTrue(can_author_games(SimpleNamespace(role=UserRole.teacher)))
        self.assertTrue(can_author_games(SimpleNamespace(role=UserRole.creator)))
        self.assertTrue(can_author_games(SimpleNamespace(role=UserRole.admin)))
        self.assertFalse(can_author_games(SimpleNamespace(role=UserRole.learner)))

    def test_classroom_teacher_can_author(self) -> None:
        db = MagicMock()
        db.query.return_value.filter.return_value.limit.return_value.first.return_value = (1,)
        self.assertTrue(can_author_games(SimpleNamespace(role=UserRole.learner, id="u1"), db))


class HtmlExtractTests(unittest.TestCase):
    def test_strips_markdown_fence(self) -> None:
        html = extract_html("```html\n<!DOCTYPE html><html>ok</html>\n```")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertNotIn("```", html)

    def test_validate_requires_stage_and_complete(self) -> None:
        with self.assertRaises(HTTPException):
            validate_generated_html("<html><body>hello</body></html>", 3)
        validated = validate_generated_html(SAMPLE_HTML, 3)
        self.assertIn("LearnPlay.stage", validated)

    def test_rejects_remote_script(self) -> None:
        bad = SAMPLE_HTML.replace(
            "<script>",
            '<script src="https://evil.example/x.js"></script><script>',
        )
        with self.assertRaises(HTTPException):
            validate_generated_html(bad, 3)


class PromptContractTests(unittest.TestCase):
    def test_generation_prompt_keeps_level_structure(self) -> None:
        self.assertIn("LearnPlay.stage", STAGE_INSTRUCTIONS)
        self.assertIn("complete: true", STAGE_INSTRUCTIONS)
        self.assertIn("TOTAL must never change", STAGE_INSTRUCTIONS)
        system, user = html_game_prompt(
            title="Cat pixels",
            topic="CNNs",
            difficulty=2,
            level_count=4,
            levels_brief="1 warm-up\n2 filter\n3 map\n4 boss",
            language="en",
        )
        self.assertIn("LearnPlay.stage", system)
        payload = json.loads(user)
        self.assertEqual(payload["level_count"], 4)
        self.assertTrue(any("TOTAL = 4" in rule for rule in payload["requirements"]))
        self.assertTrue(any("complete: true" in rule for rule in payload["requirements"]))


class ChatCompleteTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_compatible_reads_message_content(self) -> None:
        from app.services.llm import chat_complete

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"choices": [{"message": {"content": SAMPLE_HTML}}]}
        response.text = ""
        client = AsyncMock()
        client.post.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        with patch("app.services.llm.httpx.AsyncClient", return_value=client):
            text = await chat_complete(
                provider="openai",
                api_key="sk-test-1234567890",
                system="sys",
                user="do it",
            )
        self.assertIn("LearnPlay.stage", text)
        kwargs = client.post.call_args.kwargs
        self.assertIn("Authorization", kwargs["headers"])
        self.assertEqual(kwargs["json"]["messages"][0]["role"], "system")

    async def test_claude_reads_text_blocks(self) -> None:
        from app.services.llm import chat_complete

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"content": [{"type": "text", "text": SAMPLE_HTML}]}
        response.text = ""
        client = AsyncMock()
        client.post.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        with patch("app.services.llm.httpx.AsyncClient", return_value=client):
            text = await chat_complete(
                provider="claude",
                api_key="sk-ant-1234567890",
                system="sys",
                user="do it",
            )
        self.assertIn("complete: true", text)
        headers = client.post.call_args.kwargs["headers"]
        self.assertIn("x-api-key", headers)


if __name__ == "__main__":
    unittest.main()
