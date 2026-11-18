"""Public, read-only stats for the portfolio site (duowang.dev).

GET /api/public/stats returns aggregate numbers for ONE user, chosen by the
STATS_USER_EMAIL environment variable. It never returns task titles,
descriptions, tags or ids. If STATS_USER_EMAIL is unset the endpoint is off
and answers 404.

Config (environment variables):
    STATS_USER_EMAIL       whose tasks to count; unset = endpoint disabled
    STATS_ALLOWED_ORIGINS  comma-separated origins allowed by CORS
                           (default: https://duowang.dev,https://www.duowang.dev);
                           http://localhost and http://127.0.0.1 on any port are
                           always allowed for local development
    STATS_CACHE_SECONDS    how long one computed result is reused (default 60)
    STATS_RATE_LIMIT       requests per minute per client IP (default 60)
"""

import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from .. import db
from ..models import task_status, tasks, users

public_bp = Blueprint("public", __name__, url_prefix="/api/public")

LONDON = ZoneInfo("Europe/London")
STREAK_LOOKBACK_DAYS = 366
_LOCAL_ORIGIN = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")

_lock = threading.Lock()
_cache = {"key": None, "expires": 0.0, "body": None}
_hits = {}  # client ip -> list of request times (monotonic seconds)


def _now():
    """Current UTC time. Wrapped so tests can freeze the clock."""
    return datetime.now(timezone.utc)


def _allowed_origins():
    raw = os.environ.get("STATS_ALLOWED_ORIGINS", "https://duowang.dev,https://www.duowang.dev")
    return {origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()}


def _origin_allowed(origin):
    return bool(origin) and (origin in _allowed_origins() or bool(_LOCAL_ORIGIN.match(origin)))


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _rate_limited(ip):
    limit = int(os.environ.get("STATS_RATE_LIMIT", "60"))
    now = time.monotonic()
    with _lock:
        recent = [t for t in _hits.get(ip, []) if now - t < 60]
        if len(recent) >= limit:
            _hits[ip] = recent
            return True
        recent.append(now)
        _hits[ip] = recent
        # Keep the table small: forget clients with no requests in the last minute.
        if len(_hits) > 10_000:
            for key in [k for k, v in _hits.items() if not v or now - v[-1] >= 60]:
                del _hits[key]
        return False


def _utc_naive(dt):
    """completed_at is stored as naive UTC, so compare with naive UTC bounds."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _as_london_date(stored):
    """Convert a stored completed_at (naive UTC, or aware) to a London date."""
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    return stored.astimezone(LONDON).date()


def compute_stats(user_id, now_utc):
    """Aggregate numbers only: done today, total today, streak of active days."""
    today = now_utc.astimezone(LONDON).date()
    day_start = datetime.combine(today, datetime.min.time(), tzinfo=LONDON)
    day_end = day_start + timedelta(days=1)
    start, end = _utc_naive(day_start), _utc_naive(day_end)

    done_today_clause = (tasks.status == task_status.done) & (tasks.completed_at >= start) & (tasks.completed_at < end)

    done_today = db.session.scalar(
        db.select(func.count(tasks.id)).where(tasks.user_id == user_id, done_today_clause)
    )
    # "Today's tasks": due today, or finished today (whatever their due date).
    total_today = db.session.scalar(
        db.select(func.count(tasks.id)).where(
            tasks.user_id == user_id,
            or_(tasks.due_date == today, done_today_clause),
        )
    )

    # Streak: consecutive London days with at least one task done, ending today
    # (or yesterday, so the streak doesn't read 0 every morning).
    lookback = _utc_naive(day_start - timedelta(days=STREAK_LOOKBACK_DAYS))
    completed = db.session.scalars(
        db.select(tasks.completed_at).where(
            tasks.user_id == user_id,
            tasks.status == task_status.done,
            tasks.completed_at.is_not(None),
            tasks.completed_at >= lookback,
        )
    ).all()
    active_days = {_as_london_date(stamp) for stamp in completed}
    day = today if today in active_days else today - timedelta(days=1)
    streak = 0
    while day in active_days:
        streak += 1
        day -= timedelta(days=1)

    return {
        "done_today": done_today,
        "total_today": total_today,
        "streak_days": streak,
        "date": today.isoformat(),
        "updated_at": now_utc.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }


@public_bp.after_request
def _cors(response):
    origin = request.headers.get("Origin", "")
    if _origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "600"
    response.headers["Vary"] = "Origin"
    return response


@public_bp.route("/stats", methods=["GET", "OPTIONS"])
def stats():
    if request.method == "OPTIONS":
        return "", 204

    email = (os.environ.get("STATS_USER_EMAIL") or "").strip().lower()
    if not email:
        return _error("NOT_FOUND", "Not found", 404)

    if _rate_limited(request.remote_addr or "unknown"):
        response, status = _error("RATE_LIMITED", "Too many requests", 429)
        response.headers["Retry-After"] = "60"
        return response, status

    ttl = int(os.environ.get("STATS_CACHE_SECONDS", "60"))
    with _lock:
        if _cache["key"] == email and _cache["expires"] > time.monotonic():
            body = _cache["body"]
        else:
            body = None

    if body is None:
        user = db.session.scalar(db.select(users).where(func.lower(users.email) == email))
        if user is None:
            return _error("NOT_FOUND", "Not found", 404)
        body = compute_stats(user.id, _now())
        with _lock:
            _cache.update(key=email, expires=time.monotonic() + ttl, body=body)

    response = jsonify(body)
    response.headers["Cache-Control"] = f"public, max-age={ttl}"
    return response, 200


def reset_state():
    """Clear the cache and rate-limit table (used by tests)."""
    with _lock:
        _cache.update(key=None, expires=0.0, body=None)
        _hits.clear()
