import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from app import create_app, db
from app.models import task_status, tasks, users
from app.routes import public

OWNER = "owner@example.com"


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class PublicStatsTestCase(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "DATABASE_URL": "sqlite://",
                "JWT_SECRET": "unit-test-secret",
                "STATS_USER_EMAIL": OWNER,
                "STATS_CACHE_SECONDS": "0",
            },
        )
        self.environment.start()
        public.reset_state()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.owner_id = self._user(OWNER)
            self.other_id = self._user("someone@example.com")

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.environment.stop()
        public.reset_state()

    def _user(self, email):
        user = users(email=email, password_hash="x", display_name="X")
        db.session.add(user)
        db.session.commit()
        return user.id

    def _task(self, user_id, title="Secret plan", done_at=None, due=None):
        with self.app.app_context():
            task = tasks(
                user_id=user_id,
                title=title,
                description="private notes",
                status=task_status.done if done_at else task_status.todo,
                completed_at=done_at.astimezone(timezone.utc).replace(tzinfo=None) if done_at else None,
                due_date=due,
            )
            db.session.add(task)
            db.session.commit()

    def _get(self, now, **headers):
        with patch.object(public, "_now", return_value=now):
            return self.client.get("/api/public/stats", headers=headers)

    def test_counts_today_in_london_time_and_hides_task_content(self):
        now = utc(2026, 7, 10, 12, 0)  # 13:00 in London (BST)
        self._task(self.owner_id, done_at=utc(2026, 7, 10, 9, 0))
        self._task(self.owner_id, done_at=utc(2026, 7, 9, 23, 30))  # 00:30 London on the 10th
        self._task(self.owner_id, done_at=utc(2026, 7, 9, 22, 30))  # 23:30 London on the 9th
        self._task(self.owner_id, due=date(2026, 7, 10))  # due today, not done
        self._task(self.other_id, done_at=utc(2026, 7, 10, 9, 0))  # someone else's

        response = self._get(now)

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["done_today"], 2)
        self.assertEqual(body["total_today"], 3)
        self.assertEqual(body["date"], "2026-07-10")
        text = response.get_data(as_text=True)
        self.assertNotIn("Secret plan", text)
        self.assertNotIn("private notes", text)
        self.assertEqual(set(body), {"done_today", "total_today", "streak_days", "date", "updated_at"})

    def test_midnight_boundary_in_winter(self):
        # 23:59 and 00:01 London time in GMT; only the second is "today".
        self._task(self.owner_id, done_at=utc(2026, 1, 14, 23, 59))
        self._task(self.owner_id, done_at=utc(2026, 1, 15, 0, 1))
        body = self._get(utc(2026, 1, 15, 8, 0)).get_json()
        self.assertEqual(body["done_today"], 1)

    def test_streak_counts_consecutive_days_and_survives_until_tonight(self):
        for day in (7, 8, 9):  # three days in a row, nothing yet today
            self._task(self.owner_id, done_at=utc(2026, 7, day, 10, 0))
        self._task(self.owner_id, done_at=utc(2026, 7, 4, 10, 0))  # older, after a gap
        body = self._get(utc(2026, 7, 10, 8, 0)).get_json()
        self.assertEqual(body["streak_days"], 3)

        self._task(self.owner_id, done_at=utc(2026, 7, 10, 9, 0))
        body = self._get(utc(2026, 7, 10, 10, 0)).get_json()
        self.assertEqual(body["streak_days"], 4)

    def test_cors_allows_portfolio_and_localhost_only(self):
        now = utc(2026, 7, 10, 12, 0)
        allowed = self._get(now, Origin="https://duowang.dev")
        local = self._get(now, Origin="http://localhost:5173")
        other = self._get(now, Origin="https://evil.example")

        self.assertEqual(allowed.headers.get("Access-Control-Allow-Origin"), "https://duowang.dev")
        self.assertEqual(local.headers.get("Access-Control-Allow-Origin"), "http://localhost:5173")
        self.assertIsNone(other.headers.get("Access-Control-Allow-Origin"))

        preflight = self.client.options("/api/public/stats", headers={"Origin": "https://duowang.dev"})
        self.assertEqual(preflight.status_code, 204)
        self.assertEqual(preflight.headers.get("Access-Control-Allow-Origin"), "https://duowang.dev")

    def test_rate_limit(self):
        with patch.dict(os.environ, {"STATS_RATE_LIMIT": "3"}):
            codes = [self._get(utc(2026, 7, 10, 12, 0)).status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])

    def test_disabled_without_configured_user(self):
        with patch.dict(os.environ, {"STATS_USER_EMAIL": ""}):
            self.assertEqual(self._get(utc(2026, 7, 10, 12, 0)).status_code, 404)

    def test_private_task_api_still_requires_login(self):
        self.assertEqual(self.client.get("/api/tasks").status_code, 401)


if __name__ == "__main__":
    unittest.main()
