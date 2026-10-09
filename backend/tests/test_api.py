import os
import unittest
from unittest.mock import patch

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app import create_app, db
from app.models import task_tags


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite ignores foreign keys unless told otherwise. Without this the
    ON DELETE CASCADE rules on task_tags would never actually run in tests."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class BackendApiTestCase(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "DATABASE_URL": "sqlite://",
                "JWT_SECRET": "unit-test-secret",
            },
        )
        self.environment.start()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.environment.stop()

    def register(self, email="person@example.com", display_name="Test Person"):
        response = self.client.post(
            "/api/auth/register",
            json={
                "display_name": display_name,
                "email": email,
                "password": "correct-horse-battery",
            },
        )
        return response

    def authorization(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_register_normalizes_email_and_returns_token_and_user(self):
        response = self.register(email="  PERSON@Example.COM ")

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["user"]["email"], "person@example.com")
        self.assertEqual(payload["user"]["display_name"], "Test Person")
        self.assertNotIn("password_hash", payload["user"])

    def test_register_rejects_invalid_fields_and_duplicate_email(self):
        missing_name = self.client.post(
            "/api/auth/register",
            json={"display_name": " ", "email": "person@example.com", "password": "password123"},
        )
        invalid_email = self.client.post(
            "/api/auth/register",
            json={"display_name": "Person", "email": "invalid", "password": "password123"},
        )
        short_password = self.client.post(
            "/api/auth/register",
            json={"display_name": "Person", "email": "person@example.com", "password": "short"},
        )

        self.assertEqual(missing_name.status_code, 400)
        self.assertEqual(invalid_email.status_code, 400)
        self.assertEqual(short_password.status_code, 400)
        self.assertEqual(self.register().status_code, 201)
        duplicate = self.register(email="PERSON@example.com")
        self.assertEqual(duplicate.status_code, 409)

    def test_login_and_me_require_valid_credentials_and_token(self):
        self.register()
        invalid_login = self.client.post(
            "/api/auth/login",
            json={"email": "person@example.com", "password": "incorrect"},
        )
        login = self.client.post(
            "/api/auth/login",
            json={"email": "PERSON@example.com", "password": "correct-horse-battery"},
        )

        self.assertEqual(invalid_login.status_code, 401)
        self.assertEqual(login.status_code, 200)
        token = login.get_json()["token"]

        unauthorized = self.client.get("/api/auth/me")
        me = self.client.get("/api/auth/me", headers=self.authorization(token))
        invalid_token = self.client.get(
            "/api/auth/me",
            headers=self.authorization("not-a-valid-token"),
        )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["user"]["email"], "person@example.com")
        self.assertEqual(invalid_token.status_code, 401)

    def test_task_endpoints_require_authentication(self):
        response = self.client.get("/api/tasks")

        self.assertEqual(response.status_code, 401)

    def test_create_list_and_filter_tasks(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        first = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Write tests", "description": "Cover the task API"},
        )
        second = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Ship tests", "status": "in_progress"},
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.get_json()["status"], "todo")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.get_json()["status"], "in_progress")

        all_tasks = self.client.get("/api/tasks", headers=headers)
        in_progress = self.client.get("/api/tasks?status=in_progress", headers=headers)

        self.assertEqual(all_tasks.status_code, 200)
        self.assertEqual(len(all_tasks.get_json()), 2)
        self.assertEqual([task["title"] for task in in_progress.get_json()], ["Ship tests"])

    def test_create_task_rejects_missing_title(self):
        token = self.register().get_json()["token"]

        response = self.client.post(
            "/api/tasks",
            headers=self.authorization(token),
            json={"description": "No title"},
        )

        self.assertEqual(response.status_code, 400)

    def test_task_priority_defaults_medium(self):
        token = self.register().get_json()["token"]

        response = self.client.post(
            "/api/tasks",
            headers=self.authorization(token),
            json={"title": "No priority given"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["priority"], "medium")

    def test_task_priority_accepts_values_and_patches(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "High priority", "priority": "high"},
        )

        self.assertEqual(created.status_code, 201)
        task_id = created.get_json()["id"]
        self.assertEqual(created.get_json()["priority"], "high")

        updated = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"priority": "low"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["priority"], "low")

        invalid = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Bad priority", "priority": "urgent"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_task_due_date_create_persists_and_invalid_rejected(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Dated task", "due_date": "2026-12-31"},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["due_date"], "2026-12-31")

        invalid = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Bad date", "due_date": "not-a-date"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_task_due_date_patch_set_and_clear_to_null(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Date editor"},
        ).get_json()
        task_id = created["id"]

        set_date = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"due_date": "2026-10-09"},
        )
        self.assertEqual(set_date.status_code, 200)
        self.assertEqual(set_date.get_json()["due_date"], "2026-10-09")

        cleared = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"due_date": None},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.get_json()["due_date"])

    def test_task_completed_at_set_on_done_and_cleared_moving_back(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Finish me"},
        ).get_json()
        task_id = created["id"]
        self.assertIsNone(created["completed_at"])

        done = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "done", "position": 0},
        )
        self.assertEqual(done.status_code, 200)
        self.assertIsNotNone(done.get_json()["completed_at"])

        # Moving back out of Completed clears it.
        back = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "todo", "position": 0},
        )
        self.assertEqual(back.status_code, 200)
        self.assertIsNone(back.get_json()["completed_at"])

        # Reordering within Completed must not touch completed_at.
        re_done = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "done", "position": 0},
        )
        completed_at = re_done.get_json()["completed_at"]
        self.assertIsNotNone(completed_at)

        same_status = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "done", "position": 0},
        )
        self.assertEqual(same_status.status_code, 200)
        self.assertEqual(same_status.get_json()["completed_at"], completed_at)

    def test_task_priority_defaults_medium(self):
        token = self.register().get_json()["token"]

        response = self.client.post(
            "/api/tasks",
            headers=self.authorization(token),
            json={"title": "No priority given"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["priority"], "medium")

    def test_task_priority_accepts_values_and_patches(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "High priority", "priority": "high"},
        )

        self.assertEqual(created.status_code, 201)
        task_id = created.get_json()["id"]
        self.assertEqual(created.get_json()["priority"], "high")

        updated = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"priority": "low"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["priority"], "low")

        invalid = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Bad priority", "priority": "urgent"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_task_due_date_create_persists_and_invalid_rejected(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Dated task", "due_date": "2026-12-31"},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["due_date"], "2026-12-31")

        invalid = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Bad date", "due_date": "not-a-date"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_task_due_date_patch_set_and_clear_to_null(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Date editor"},
        ).get_json()
        task_id = created["id"]

        set_date = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"due_date": "2026-10-09"},
        )
        self.assertEqual(set_date.status_code, 200)
        self.assertEqual(set_date.get_json()["due_date"], "2026-10-09")

        cleared = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"due_date": None},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.get_json()["due_date"])

    def test_task_completed_at_set_on_done_and_cleared_moving_back(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Finish me"},
        ).get_json()
        task_id = created["id"]
        self.assertIsNone(created["completed_at"])

        done = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "done", "position": 0},
        )
        self.assertEqual(done.status_code, 200)
        self.assertIsNotNone(done.get_json()["completed_at"])

        # Moving back out of Completed clears it.
        back = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "todo", "position": 0},
        )
        self.assertEqual(back.status_code, 200)
        self.assertIsNone(back.get_json()["completed_at"])

        # Reordering within Completed must not touch completed_at.
        re_done = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "done", "position": 0},
        )
        completed_at = re_done.get_json()["completed_at"]
        self.assertIsNotNone(completed_at)

        same_status = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "done", "position": 0},
        )
        self.assertEqual(same_status.status_code, 200)
        self.assertEqual(same_status.get_json()["completed_at"], completed_at)

    def test_task_read_update_move_and_delete(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tasks",
            headers=headers,
            json={"title": "Original title", "description": "Details"},
        )
        task_id = created.get_json()["id"]

        fetched = self.client.get(f"/api/tasks/{task_id}", headers=headers)
        updated = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"title": "Updated title"},
        )
        moved = self.client.patch(
            f"/api/tasks/{task_id}/move",
            headers=headers,
            json={"status": "done", "position": 2},
        )
        # The destination (done) column is empty, so the requested index 2 is
        # clamped to the single available slot and the column is renumbered 0..n.
        deleted = self.client.delete(f"/api/tasks/{task_id}", headers=headers)
        missing = self.client.get(f"/api/tasks/{task_id}", headers=headers)

        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["title"], "Updated title")
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.get_json()["status"], "done")
        self.assertEqual(moved.get_json()["position"], 0)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(missing.status_code, 404)

    def test_users_cannot_read_or_delete_another_users_task(self):
        first_token = self.register().get_json()["token"]
        task = self.client.post(
            "/api/tasks",
            headers=self.authorization(first_token),
            json={"title": "Private task"},
        ).get_json()
        second_token = self.register(
            email="other@example.com",
            display_name="Other Person",
        ).get_json()["token"]
        second_headers = self.authorization(second_token)

        self.assertEqual(self.client.get("/api/tasks", headers=second_headers).get_json(), [])
        self.assertEqual(
            self.client.get(f"/api/tasks/{task['id']}", headers=second_headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(f"/api/tasks/{task['id']}", headers=second_headers).status_code,
            404,
        )

    def test_tag_endpoints_require_authentication(self):
        response = self.client.get("/api/tags")

        self.assertEqual(response.status_code, 401)

    def test_create_and_list_tags(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        first = self.client.post(
            "/api/tags",
            headers=headers,
            json={"name": "Work", "colour": "#6c8ebf"},
        )
        second = self.client.post(
            "/api/tags",
            headers=headers,
            json={"name": "urgent", "colour": "#B85450"},
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.get_json()["name"], "Work")
        self.assertEqual(first.get_json()["colour"], "#6c8ebf")
        self.assertEqual(second.status_code, 201)
        # Colour is normalised to lowercase.
        self.assertEqual(second.get_json()["colour"], "#b85450")

        listing = self.client.get("/api/tags", headers=headers)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([tag["name"] for tag in listing.get_json()], ["Work", "urgent"])

    def test_create_tag_validates_name_and_colour(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        missing_name = self.client.post("/api/tags", headers=headers, json={"colour": "#6c8ebf"})
        blank_name = self.client.post("/api/tags", headers=headers, json={"name": "  ", "colour": "#6c8ebf"})
        bad_colour = self.client.post("/api/tags", headers=headers, json={"name": "Work", "colour": "red"})
        short_colour = self.client.post("/api/tags", headers=headers, json={"name": "Work", "colour": "#fff"})

        self.assertEqual(missing_name.status_code, 400)
        self.assertEqual(blank_name.status_code, 400)
        self.assertEqual(bad_colour.status_code, 400)
        self.assertEqual(short_colour.status_code, 400)

    def test_create_duplicate_tag_returns_conflict(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        created = self.client.post(
            "/api/tags",
            headers=headers,
            json={"name": "Work", "colour": "#6c8ebf"},
        )
        duplicate = self.client.post(
            "/api/tags",
            headers=headers,
            json={"name": "Work", "colour": "#ff0000"},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.get_json()["error"]["code"], "CONFLICT")

    def test_tags_are_scoped_per_user(self):
        first_token = self.register().get_json()["token"]
        tag = self.client.post(
            "/api/tags",
            headers=self.authorization(first_token),
            json={"name": "Work", "colour": "#6c8ebf"},
        ).get_json()
        second_token = self.register(
            email="other@example.com",
            display_name="Other Person",
        ).get_json()["token"]
        second_headers = self.authorization(second_token)

        self.assertEqual(self.client.get("/api/tags", headers=second_headers).get_json(), [])
        self.assertEqual(
            self.client.delete(f"/api/tags/{tag['id']}", headers=second_headers).status_code,
            404,
        )

    def test_put_task_tags_replaces_the_set(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        task = self.client.post("/api/tasks", headers=headers, json={"title": "Tagged task"}).get_json()
        work = self.client.post(
            "/api/tags",
            headers=headers,
            json={"name": "Work", "colour": "#6c8ebf"},
        ).get_json()
        urgent = self.client.post(
            "/api/tags",
            headers=headers,
            json={"name": "Urgent", "colour": "#b85450"},
        ).get_json()

        self.assertEqual(task["tags"], [])

        assigned = self.client.put(
            f"/api/tasks/{task['id']}/tags",
            headers=headers,
            json={"tag_ids": [work["id"], urgent["id"]]},
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual([tag["name"] for tag in assigned.get_json()["tags"]], ["Work", "Urgent"])

        narrowed = self.client.put(
            f"/api/tasks/{task['id']}/tags",
            headers=headers,
            json={"tag_ids": [work["id"]]},
        )
        self.assertEqual(narrowed.status_code, 200)
        self.assertEqual([tag["id"] for tag in narrowed.get_json()["tags"]], [work["id"]])

        cleared = self.client.put(
            f"/api/tasks/{task['id']}/tags",
            headers=headers,
            json={"tag_ids": []},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.get_json()["tags"], [])

    def test_put_task_tags_rejects_unknown_and_foreign_tags(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        task = self.client.post("/api/tasks", headers=headers, json={"title": "Strict"}).get_json()
        other_token = self.register(
            email="other@example.com",
            display_name="Other Person",
        ).get_json()["token"]
        foreign_tag = self.client.post(
            "/api/tags",
            headers=self.authorization(other_token),
            json={"name": "Theirs", "colour": "#6c8ebf"},
        ).get_json()

        unknown = self.client.put(
            f"/api/tasks/{task['id']}/tags",
            headers=headers,
            json={"tag_ids": [999]},
        )
        foreign = self.client.put(
            f"/api/tasks/{task['id']}/tags",
            headers=headers,
            json={"tag_ids": [foreign_tag["id"]]},
        )
        not_a_list = self.client.put(
            f"/api/tasks/{task['id']}/tags",
            headers=headers,
            json={"tag_ids": "Work"},
        )

        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(not_a_list.status_code, 400)

    def test_delete_tag_removes_it_from_tasks_without_deleting_them(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        task = self.client.post("/api/tasks", headers=headers, json={"title": "Survivor"}).get_json()
        tag = self.client.post(
            "/api/tags",
            headers=headers,
            json={"name": "Doomed", "colour": "#6c8ebf"},
        ).get_json()
        self.client.put(
            f"/api/tasks/{task['id']}/tags",
            headers=headers,
            json={"tag_ids": [tag["id"]]},
        )

        deleted = self.client.delete(f"/api/tags/{tag['id']}", headers=headers)
        self.assertEqual(deleted.status_code, 204)

        remaining = self.client.get(f"/api/tasks/{task['id']}", headers=headers)
        self.assertEqual(remaining.status_code, 200)
        self.assertEqual(remaining.get_json()["tags"], [])

        with self.app.app_context():
            orphan_joins = db.session.query(task_tags).filter_by(tag_id=tag["id"]).count()
        self.assertEqual(orphan_joins, 0)

    def test_delete_task_cleans_up_its_tag_links(self):
        token = self.register().get_json()["token"]
        headers = self.authorization(token)
        task = self.client.post("/api/tasks", headers=headers, json={"title": "Vanishing"}).get_json()
        tag = self.client.post(
            "/api/tags",
            headers=headers,
            json={"name": "Sticky", "colour": "#6c8ebf"},
        ).get_json()
        self.client.put(
            f"/api/tasks/{task['id']}/tags",
            headers=headers,
            json={"tag_ids": [tag["id"]]},
        )

        deleted = self.client.delete(f"/api/tasks/{task['id']}", headers=headers)
        self.assertEqual(deleted.status_code, 204)

        # The tag itself survives; only the join row is cascaded away.
        tags_after = self.client.get("/api/tags", headers=headers).get_json()
        self.assertEqual([t["id"] for t in tags_after], [tag["id"]])
        with self.app.app_context():
            orphan_joins = db.session.query(task_tags).filter_by(task_id=task["id"]).count()
        self.assertEqual(orphan_joins, 0)


if __name__ == "__main__":
    unittest.main()
