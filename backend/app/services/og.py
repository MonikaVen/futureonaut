from __future__ import annotations

import html
import textwrap
from xml.sax.saxutils import escape

from app.models import Game
from app.services.topics import TOPICS, normalize_topic


def primary_topic(game: Game) -> str:
    for tag in game.topic_tags or []:
        normalized = normalize_topic(tag)
        if normalized in TOPICS:
            return normalized
    return "AI"


def og_description(game: Game) -> str:
    desc = (game.description or "").strip()
    if desc:
        return desc[:280]
    topic = primary_topic(game)
    return f"Play {game.title} — an interactive {topic} learning game on Futureonaut."


def og_image_svg(game: Game, site_name: str = "Futureonaut") -> str:
    title = escape(textwrap.shorten(game.title, width=48, placeholder="…"))
    topic = escape(primary_topic(game))
    desc = escape(textwrap.shorten(og_description(game), width=120, placeholder="…"))
    level = game.difficulty
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#050810"/>
      <stop offset="55%" style="stop-color:#0a1628"/>
      <stop offset="100%" style="stop-color:#0d2137"/>
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#00d4ff;stop-opacity:0.9"/>
      <stop offset="100%" style="stop-color:#7b5cff;stop-opacity:0.9"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="0" y="0" width="1200" height="6" fill="url(#glow)"/>
  <circle cx="1050" cy="120" r="180" fill="#00d4ff" opacity="0.08"/>
  <circle cx="150" cy="520" r="140" fill="#7b5cff" opacity="0.1"/>
  <text x="72" y="88" fill="#7a8ba8" font-family="system-ui,sans-serif" font-size="28" font-weight="600" letter-spacing="6">{escape(site_name.upper())}</text>
  <text x="72" y="290" fill="#e8f4ff" font-family="system-ui,sans-serif" font-size="64" font-weight="700">{title}</text>
  <text x="72" y="360" fill="#9eb4d0" font-family="system-ui,sans-serif" font-size="30">{desc}</text>
  <rect x="72" y="410" width="120" height="44" rx="22" fill="#00d4ff" opacity="0.15"/>
  <text x="92" y="440" fill="#00d4ff" font-family="system-ui,sans-serif" font-size="22" font-weight="700">{topic}</text>
  <rect x="210" y="410" width="110" height="44" rx="22" fill="#7b5cff" opacity="0.15"/>
  <text x="230" y="440" fill="#b8a8ff" font-family="system-ui,sans-serif" font-size="22" font-weight="700">LV {level}</text>
  <text x="72" y="560" fill="#5a6d88" font-family="system-ui,sans-serif" font-size="24">Interactive learning game</text>
</svg>"""


def share_html(
    *,
    title: str,
    description: str,
    share_url: str,
    play_url: str,
    image_url: str,
    site_name: str = "Futureonaut",
) -> str:
    safe_title = html.escape(title)
    safe_desc = html.escape(description)
    safe_share = html.escape(share_url, quote=True)
    safe_play = html.escape(play_url, quote=True)
    safe_image = html.escape(image_url, quote=True)
    full_title = html.escape(f"{title} · {site_name}")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{full_title}</title>
  <meta name="description" content="{safe_desc}" />
  <link rel="canonical" href="{safe_share}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="{html.escape(site_name)}" />
  <meta property="og:title" content="{safe_title}" />
  <meta property="og:description" content="{safe_desc}" />
  <meta property="og:url" content="{safe_share}" />
  <meta property="og:image" content="{safe_image}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{safe_title}" />
  <meta name="twitter:description" content="{safe_desc}" />
  <meta name="twitter:image" content="{safe_image}" />
  <meta http-equiv="refresh" content="0;url={safe_play}" />
</head>
<body style="font-family:system-ui,sans-serif;background:#050810;color:#e8f4ff;padding:2rem;">
  <p>Opening <a href="{safe_play}" style="color:#00d4ff;">{safe_title}</a>…</p>
</body>
</html>"""


def score_card_svg(
    *,
    title: str,
    points: int,
    accuracy_pct: float,
    levels_completed: int | None = None,
    total_levels: int | None = None,
    site_name: str = "Futureonaut",
) -> str:
    safe_title = escape(textwrap.shorten(title, width=42, placeholder="…"))
    level_line = ""
    if levels_completed and total_levels:
        level_line = f"Level {levels_completed}/{total_levels}"
    elif levels_completed:
        level_line = f"Level {levels_completed} complete"
    else:
        level_line = "Run complete"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#050810"/>
      <stop offset="100%" style="stop-color:#102040"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <text x="72" y="80" fill="#7a8ba8" font-family="system-ui,sans-serif" font-size="26" letter-spacing="5">{escape(site_name.upper())} SCORE</text>
  <text x="72" y="220" fill="#e8f4ff" font-family="system-ui,sans-serif" font-size="52" font-weight="700">{safe_title}</text>
  <text x="72" y="340" fill="#00d4ff" font-family="system-ui,sans-serif" font-size="96" font-weight="700">{points} pts</text>
  <text x="72" y="420" fill="#9eb4d0" font-family="system-ui,sans-serif" font-size="36">{accuracy_pct:.0f}% accuracy</text>
  <text x="72" y="490" fill="#b8a8ff" font-family="system-ui,sans-serif" font-size="28">{escape(level_line)}</text>
</svg>"""
