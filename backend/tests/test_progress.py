from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models import EventType
from app.services.guest_merge import apply_session_event
from app.services.progress import progress_from_session, session_is_solved, summarize_assignment


def _session(**kwargs):
    defaults = dict(
        ended_at=None,
        total_points=0,
        correct_count=0,
        attempt_count=0,
        levels_completed=0,
        total_levels=None,
        started_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class ProgressTests(unittest.TestCase):
    def test_solved_when_ended(self) -> None:
        session = _session(ended_at=datetime.now(timezone.utc))
        self.assertTrue(session_is_solved(session))
        self.assertTrue(progress_from_session(session)["completed"])

    def test_solved_when_all_levels_done(self) -> None:
        session = _session(levels_completed=4, total_levels=4)
        self.assertTrue(session_is_solved(session))
        self.assertEqual(progress_from_session(session)["progress_pct"], 100)

    def test_in_progress_percentage(self) -> None:
        session = _session(levels_completed=2, total_levels=8, total_points=20)
        self.assertFalse(session_is_solved(session))
        self.assertEqual(progress_from_session(session)["progress_pct"], 25)

    def test_assignment_summary_counts(self) -> None:
        solved = _session(ended_at=datetime.now(timezone.utc), total_points=40, levels_completed=3, total_levels=3)
        mid = _session(total_points=10, levels_completed=1, total_levels=3)
        stats = summarize_assignment([solved, mid, None], member_count=3)
        self.assertEqual(stats["solved_count"], 1)
        self.assertEqual(stats["in_progress_count"], 1)
        self.assertEqual(stats["not_started_count"], 1)

    def test_milestone_updates_levels(self) -> None:
        session = _session()
        apply_session_event(
            session,  # type: ignore[arg-type]
            EventType.milestone,
            {"id": "level-2", "label": "Attention", "level": 3, "totalLevels": 10},
        )
        self.assertEqual(session.levels_completed, 3)
        self.assertEqual(session.total_levels, 10)


if __name__ == "__main__":
    unittest.main()
