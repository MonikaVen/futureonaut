"""Insert a pack lab into an existing database if the title is missing."""

from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.models import User, UserRole
from app.services.demo_seed import import_named_lab


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title", help="Exact game title from seed_games/manifest.json")
    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        owner = (
            db.query(User).filter(User.email == "futureonaut@example.com").first()
            or db.query(User).filter(User.role == UserRole.admin).first()
        )
        if owner is None:
            print("No admin/Futureonaut user to own the lab", file=sys.stderr)
            return 1
        game = import_named_lab(db, args.title, owner.id)
        if game is None:
            print(f"already present: {args.title}")
            return 0
        print(f"stored {game.id} {game.title}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
