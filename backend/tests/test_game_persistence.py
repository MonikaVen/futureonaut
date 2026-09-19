import os
import unittest
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://learnplay:learnplay@localhost:5432/learnplay",
)
os.environ.setdefault("GAMES_DIR", "/tmp/futureonaut-game-tests")

from app.database import SessionLocal, engine  # noqa: E402
from app.main import ensure_schema  # noqa: E402
from app.models import Base, Game, User, UserRole  # noqa: E402
from app.services.demo_seed import (  # noqa: E402
    import_named_lab,
    persist_and_hydrate_game_files,
    seed_html_pack,
)
from app.services.storage import delete_game_files, snapshot_game_files  # noqa: E402


class GamePersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.create_all(bind=engine)
        ensure_schema()

    def test_seed_pack_runs_only_on_empty_database(self) -> None:
        db = SessionLocal()
        try:
            before = db.query(Game).count()
            admin = db.query(User).filter(User.role == UserRole.admin).first()
            self.assertIsNotNone(admin)
            added = seed_html_pack(db, admin.id)
            after = db.query(Game).count()
            self.assertEqual(after, before)
            self.assertEqual(added, 0)
        finally:
            db.close()

    def test_files_round_trip_from_database_not_seed_disk(self) -> None:
        db = SessionLocal()
        try:
            game = (
                db.query(Game)
                .filter(Game.files.isnot(None))
                .filter(Game.files != {})
                .first()
            )
            self.assertIsNotNone(game)
            self.assertTrue(game.files)
            delete_game_files(game.id)
            persist_and_hydrate_game_files(db)
            db.refresh(game)
            on_disk = snapshot_game_files(game.id)
            self.assertIn(game.entry_path or "index.html", on_disk)
            self.assertTrue(on_disk[game.entry_path or "index.html"])
        finally:
            db.close()

    def test_import_named_lab_is_idempotent_and_stores_html(self) -> None:
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.role == UserRole.admin).first()
            title = "Liucian 3D World Model"
            first = import_named_lab(db, title, admin.id)
            second = import_named_lab(db, title, admin.id)
            stored = db.query(Game).filter(Game.title == title).one()
            self.assertTrue(stored.files)
            self.assertIn("index.html", stored.files)
            self.assertIn("world model", stored.files["index.html"].lower())
            self.assertIsNone(second)
            if first is not None:
                self.assertEqual(first.id, stored.id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
