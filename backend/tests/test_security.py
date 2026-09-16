from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError
from starlette.requests import Request

from app.limits import MAX_GAME_LEVEL, bounded_int, cap_event_payload
from app.models import EventType, UserRole
from app.public_url import public_base_url, safe_host, safe_proto
from app.schemas import SessionEventIn
from app.services.guest_merge import apply_session_event
from app.services.og import share_html


def _request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/share/x",
            "raw_path": b"/share/x",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("backend", 8000),
        }
    )


class PublicUrlTests(unittest.TestCase):
    def test_rejects_injected_host(self) -> None:
        self.assertIsNone(safe_host('evil.example"><script>'))
        self.assertIsNone(safe_host("evil.example/phish"))
        self.assertIsNone(safe_host("https://evil.example"))
        self.assertIsNone(safe_host("evil.com:99999"))
        self.assertEqual(safe_host("app.example.com:443"), "app.example.com:443")

    def test_proto_allowlist(self) -> None:
        self.assertEqual(safe_proto("https,http"), "https")
        self.assertEqual(safe_proto("javascript"), "https")
        self.assertEqual(safe_proto("http"), "http")

    def test_prefers_configured_base(self) -> None:
        request = _request(
            [
                (b"x-forwarded-host", b"evil.example"),
                (b"x-forwarded-proto", b"https"),
                (b"host", b"backend:8000"),
            ]
        )
        with patch("app.public_url.get_settings") as settings:
            settings.return_value.public_base_url = "https://futureonaut.example"
            self.assertEqual(public_base_url(request), "https://futureonaut.example")

    def test_sanitizes_forwarded_host(self) -> None:
        request = _request(
            [
                (b"x-forwarded-host", b'evil.example"><script>alert(1)'),
                (b"x-forwarded-proto", b"https"),
                (b"host", b"app.example.com"),
            ]
        )
        with patch("app.public_url.get_settings") as settings:
            settings.return_value.public_base_url = ""
            self.assertEqual(public_base_url(request), "https://app.example.com")


class ShareHtmlTests(unittest.TestCase):
    def test_does_not_embed_raw_url_in_script(self) -> None:
        html = share_html(
            title="Game",
            description="Play now",
            share_url="https://app.example/share/1",
            play_url="https://app.example/play/1</script><script>alert(1)",
            image_url="https://app.example/card.png",
        )
        self.assertNotIn("<script>", html)
        self.assertIn("https://app.example/play/1", html)
        self.assertIn('property="og:image:type" content="image/png"', html)


class EventLimitTests(unittest.TestCase):
    def test_bounded_int_caps_and_rejects_huge_strings(self) -> None:
        self.assertEqual(bounded_int(10**12, hi=MAX_GAME_LEVEL), MAX_GAME_LEVEL)
        self.assertEqual(bounded_int("1" * 40, hi=MAX_GAME_LEVEL), 0)
        self.assertEqual(bounded_int(True, hi=MAX_GAME_LEVEL), 0)

    def test_payload_size_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SessionEventIn(type=EventType.score, payload={f"k{i}": i for i in range(40)})
        with self.assertRaises(ValidationError):
            SessionEventIn(type=EventType.score, payload={"blob": "x" * 5000})

    def test_numeric_fields_capped_in_schema(self) -> None:
        body = SessionEventIn(
            type=EventType.level_complete,
            payload={"level": 999999, "totalLevels": 10**9, "delta": 10**12},
        )
        self.assertEqual(body.payload["level"], MAX_GAME_LEVEL)
        self.assertEqual(body.payload["totalLevels"], MAX_GAME_LEVEL)
        self.assertEqual(body.payload["delta"], 1_000_000)

    def test_apply_session_event_caps_levels(self) -> None:
        session = SimpleNamespace(
            total_points=0,
            attempt_count=0,
            correct_count=0,
            total_time_ms=0,
            levels_completed=0,
            total_levels=None,
            ended_at=None,
        )
        apply_session_event(
            session,  # type: ignore[arg-type]
            EventType.level_complete,
            cap_event_payload({"level": 10**9, "totalLevels": 10**9}),
        )
        self.assertEqual(session.levels_completed, MAX_GAME_LEVEL)
        self.assertEqual(session.total_levels, MAX_GAME_LEVEL)


class FunnelCapTests(unittest.TestCase):
    def test_level_funnel_never_expands_unbounded(self) -> None:
        from app.services.game_analytics import _level_funnel

        session_id = uuid4()
        session = SimpleNamespace(id=session_id, levels_completed=10**9, total_levels=10**9)
        events = [
            SimpleNamespace(
                session_id=session_id,
                type=EventType.level_complete,
                payload={"level": 10**9, "totalLevels": 10**9},
            )
        ]
        funnel = _level_funnel([session], events)  # type: ignore[arg-type]
        self.assertEqual(len(funnel), MAX_GAME_LEVEL)
        self.assertEqual(funnel[-1].level, MAX_GAME_LEVEL)


class JwtTests(unittest.TestCase):
    def test_access_token_roundtrip(self) -> None:
        from app.auth import create_access_token, decode_token

        user_id = uuid4()
        token = create_access_token(user_id, UserRole.learner)
        payload = decode_token(token)
        self.assertEqual(payload["sub"], str(user_id))
        self.assertEqual(payload["type"], "access")
        self.assertEqual(payload["role"], UserRole.learner.value)


class ClassroomPrivilegeTests(unittest.TestCase):
    def test_learner_cannot_create_classroom(self) -> None:
        from fastapi import HTTPException

        from app.routers.classrooms import create_classroom
        from app.schemas import ClassroomCreate

        user = SimpleNamespace(id=uuid4(), role=UserRole.learner)
        with self.assertRaises(HTTPException) as ctx:
            create_classroom(ClassroomCreate(name="Mine"), MagicMock(), user)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
