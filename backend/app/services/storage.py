from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from uuid import UUID

from app.config import get_settings

SDK_MARKER = "learnplay-sdk.js"
I18N_MARKER = "learnplay-i18n.js"


def sdk_source_path() -> Path:
    return Path(__file__).resolve().parents[2] / "sdk" / "learnplay-sdk.js"


def i18n_source_path() -> Path:
    return Path(__file__).resolve().parents[2] / "sdk" / "learnplay-i18n.js"


def games_root() -> Path:
    root = Path(get_settings().games_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def game_dir(game_id: UUID) -> Path:
    path = games_root() / str(game_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _inline_script(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = source.replace("</", "<\\/")
    return f"<script>\n{source}\n</script>"


def inject_sdk_into_html(html: str) -> str:
    html = re.sub(
        r"<script[^>]+src=['\"][^'\"]*learnplay-(?:i18n|sdk)\.js['\"][^>]*>\s*</script>\s*",
        "",
        html,
        flags=re.IGNORECASE,
    )
    tags = []
    i18n = i18n_source_path()
    if i18n.exists() and "LEARNPLAY_I18N" not in html:
        tags.append(_inline_script(i18n))
    if 'source: "learnplay-sdk"' not in html:
        tags.append(_inline_script(sdk_source_path()))
    if not tags:
        return html
    block = "  " + "\n  ".join(tags) + "\n"
    if re.search(r"</head\s*>", html, flags=re.IGNORECASE):
        return re.sub(r"</head\s*>", block + "</head>", html, count=1, flags=re.IGNORECASE)
    if re.search(r"<body[^>]*>", html, flags=re.IGNORECASE):
        return re.sub(r"(<body[^>]*>)", rf"\1\n{block}", html, count=1, flags=re.IGNORECASE)
    return block + html


def write_sdk(dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sdk_source_path(), dest_dir / SDK_MARKER)
    i18n = i18n_source_path()
    if i18n.exists():
        shutil.copyfile(i18n, dest_dir / I18N_MARKER)


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
    children = [c for c in dest.iterdir() if c.name not in {SDK_MARKER, I18N_MARKER}]
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


def drafts_root() -> Path:
    path = games_root() / "_drafts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def draft_dir(draft_id: UUID) -> Path:
    path = drafts_root() / str(draft_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_draft_html(draft_id: UUID, html: str) -> str:
    dest = draft_dir(draft_id)
    (dest / "index.html").write_text(html, encoding="utf-8")
    ensure_sdk_injected(dest, "index.html")
    return "index.html"


def delete_draft_files(draft_id: UUID) -> None:
    dest = drafts_root() / str(draft_id)
    if dest.exists():
        shutil.rmtree(dest)
