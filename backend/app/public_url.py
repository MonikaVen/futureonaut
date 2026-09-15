from __future__ import annotations

import re

from fastapi import Request

from app.config import get_settings

_HOST_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?::\d{1,5})?$",
    re.IGNORECASE,
)


def safe_proto(value: str | None, fallback: str = "https") -> str:
    proto = (value or fallback).split(",")[0].strip().lower()
    return proto if proto in {"http", "https"} else fallback


def safe_host(value: str | None) -> str | None:
    if not value:
        return None
    host = value.split(",")[0].strip()
    if not host or any(ch in host for ch in "/\\@?# \t\r\n"):
        return None
    if not _HOST_RE.fullmatch(host):
        return None
    hostname, sep, port = host.partition(":")
    if sep:
        if not port.isdigit() or not (1 <= int(port) <= 65535):
            return None
    if hostname.startswith("[") or not hostname:
        return None
    return host


def public_base_url(request: Request) -> str:
    """Build the public site origin without trusting raw forwarded headers."""
    configured = (get_settings().public_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    proto = safe_proto(request.headers.get("x-forwarded-proto"), request.url.scheme or "https")
    host = safe_host(request.headers.get("x-forwarded-host")) or safe_host(request.headers.get("host"))
    if not host:
        return str(request.base_url).rstrip("/")
    return f"{proto}://{host}"
