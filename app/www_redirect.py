"""301-redirect www.<PUBLIC_BASE_URL host> to the same URL on PUBLIC_BASE_URL.

Without this, www.la-queta.com serves a second copy of every page, which
splits search ranking between two hosts. The canonical tags already point at
PUBLIC_BASE_URL; this makes the www host redirect there too.

It only runs when PUBLIC_BASE_URL is set (tests leave it empty unless a test
sets it), it never touches /api/health (monitoring probes must see the app
itself), and it matches only the exact www host, so localhost and IP access
keep working. nginx does the same redirect at the edge
(deploy/nginx-la-queta.conf); this is the fallback if that config is missing.
"""

from urllib.parse import urlsplit

from flask import Flask, current_app, redirect, request

EXEMPT_PATHS = frozenset({"/api/health"})


def _www_redirect():
    base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if not base or request.path in EXEMPT_PATHS:
        return None
    canonical_host = urlsplit(base).netloc.lower()
    if not canonical_host or canonical_host.startswith("www."):
        return None
    if request.host.lower() != "www." + canonical_host:
        return None
    target = base + request.path
    if request.query_string:
        target += "?" + request.query_string.decode("latin-1")
    # 301 for reads; 308 keeps the method and body for anything else (a POST
    # turned into a GET by a 301 would silently lose the form data).
    code = 301 if request.method in ("GET", "HEAD") else 308
    return redirect(target, code=code)


def register_www_redirect(application: Flask) -> None:
    application.before_request(_www_redirect)
