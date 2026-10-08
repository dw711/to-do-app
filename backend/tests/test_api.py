import os
import unittest
from unittest.mock import patch

from ..app import create_app, db


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


if __name__ == "__main__":
    unittest.main()
