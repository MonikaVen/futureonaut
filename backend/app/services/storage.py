from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from uuid import UUID

from app.config import get_settings

SDK_MARKER = "learnplay-sdk.js"


def sdk_source_path() -> Path:
    return Path(__file__).resolve().parents[2] / "sdk" / "learnplay-sdk.js"


def games_root() -> Path:
    root = Path(get_settings().games_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def game_dir(game_id: UUID) -> Path:
    path = games_root() / str(game_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def inject_sdk_into_html(html: str) -> str:
    sdk_tag = f'<script src="./{SDK_MARKER}"></script>'
    if SDK_MARKER in html:
        return html
    if re.search(r"</head\s*>", html, flags=re.IGNORECASE):
        return re.sub(r"</head\s*>", f"  {sdk_tag}\n</head>", html, count=1, flags=re.IGNORECASE)
    if re.search(r"<body[^>]*>", html, flags=re.IGNORECASE):
        return re.sub(r"(<body[^>]*>)", rf"\1\n  {sdk_tag}", html, count=1, flags=re.IGNORECASE)
    return f"{sdk_tag}\n{html}"


def write_sdk(dest_dir: Path) -> None:
    dest = dest_dir / SDK_MARKER
    shutil.copyfile(sdk_source_path(), dest)


def ensure_sdk_injected(dest_dir: Path, entry_path: str = "index.html") -> str:
    write_sdk(dest_dir)
    entry = dest_dir / entry_path
    if not entry.exists():
        htmls = list(dest_dir.rglob("*.html"))
        if not htmls:
            raise FileNotFoundError("No HTML entry found for game")
        entry = htmls[0]
        entry_path = str(entry.relative_to(dest_dir))
    html = entry.read_text(encoding="utf-8", errors="replace")
    entry.write_text(inject_sdk_into_html(html), encoding="utf-8")
    return entry_path


def save_uploaded_zip(game_id: UUID, zip_bytes: bytes) -> str:
    dest = game_dir(game_id)
    zip_path = dest / "_upload.zip"
    zip_path.write_bytes(zip_bytes)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    zip_path.unlink(missing_ok=True)
    # flatten if single top-level folder
    children = [c for c in dest.iterdir() if c.name != SDK_MARKER]
    if len(children) == 1 and children[0].is_dir():
        nested = children[0]
        for item in nested.iterdir():
            shutil.move(str(item), dest / item.name)
        nested.rmdir()
    entry = "index.html"
    if not (dest / entry).exists():
        htmls = list(dest.rglob("*.html"))
        if not htmls:
            raise FileNotFoundError("Uploaded archive must contain an HTML file")
        entry = str(htmls[0].relative_to(dest))
    ensure_sdk_injected(dest, entry)
    return entry


def save_uploaded_html(game_id: UUID, html: str, filename: str = "index.html") -> str:
    dest = game_dir(game_id)
    name = Path(filename).name or "index.html"
    if not name.endswith(".html"):
        name = "index.html"
    (dest / name).write_text(html, encoding="utf-8")
    ensure_sdk_injected(dest, name)
    return name


def write_template_game(game_id: UUID, template_type: str, content: dict) -> str:
    dest = game_dir(game_id)
    template_root = Path(__file__).resolve().parents[2] / "templates" / template_type
    if not template_root.exists():
        raise ValueError(f"Unknown template type: {template_type}")
    for item in template_root.iterdir():
        if item.is_file():
            shutil.copyfile(item, dest / item.name)
    (dest / "content.json").write_text(json.dumps(content, indent=2), encoding="utf-8")
    ensure_sdk_injected(dest, "index.html")
    return "index.html"


def delete_game_files(game_id: UUID) -> None:
    dest = games_root() / str(game_id)
    if dest.exists():
        shutil.rmtree(dest)
