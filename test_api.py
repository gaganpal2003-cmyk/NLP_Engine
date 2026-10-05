import unittest
from fastapi.testclient import TestClient
from main import app
from config import settings
from database.tenant_manager import tenant_manager

class TestNLPEngineAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.api_key = settings.DEFAULT_CLIENT_API_KEY
        cls.admin_key = settings.ADMIN_API_KEY
        cls.auth_headers = {"X-API-Key": cls.api_key}

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertTrue(data["database"]["connected"])
        self.assertIn("multi_tenant", data)

    def test_missing_api_key_rejected(self):
        # When called without header or demo referer
        response = self.client.post("/api/chat", json={"message": "count alerts"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Missing API Key", response.json()["detail"])

    def test_invalid_api_key_rejected(self):
        response = self.client.post(
            "/api/chat",
            headers={"X-API-Key": "invalid_bogus_key_123"},
            json={"message": "count alerts"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid or revoked API Key", response.json()["detail"])

    def test_verify_valid_api_key(self):
        response = self.client.get("/api/auth/verify", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "valid")
        self.assertTrue(data["database"]["connected"])

    def test_get_schema_with_api_key(self):
        response = self.client.get("/api/database/schema", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        table_names = [t["table_name"] for t in data["tables"]]
        self.assertGreater(len(table_names), 0)
        self.assertGreater(len(table_names), 0)
        self.assertTrue(any(t in table_names for t in ["ppe_detection", "alerts", "camera", "detection"]))

    def test_chat_query_camera_count(self):
        response = self.client.post(
            "/api/chat",
            headers=self.auth_headers,
            json={"message": "how many cameras are there"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data["answer"])
        self.assertTrue("camera" in data["sql_query"].lower() and "count" in data["sql_query"].lower())
        self.assertIsNotNone(data.get("client_name"))

    def test_chat_query_breakdown_with_chart(self):
        response = self.client.post(
            "/api/chat",
            headers=self.auth_headers,
            json={"message": "Show detections breakdown"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data["sql_query"])

    def test_chat_query_spelling_tolerance(self):
        """Validates that queries with severe misspellings and shorthand produce accurate answers."""
        misspelled_cases = [
            ("how many camra are there", "camera"),
            ("hw mny camras", "camera"),
            ("how meny caemra", "camera"),
            ("giv pep detecion", "detection"),
            ("camra ofline", "camera"),
        ]
        for q, expected_substr in misspelled_cases:
            res = self.client.post("/api/chat", headers=self.auth_headers, json={"message": q})
            self.assertEqual(res.status_code, 200, f"Failed on typo query: {q}")
            data = res.json()
            self.assertIsNotNone(data.get("sql_query"), f"No SQL for typo query: {q}")
            self.assertIn(expected_substr.lower(), data["sql_query"].lower(), f"Expected '{expected_substr}' in SQL for '{q}'")

    def test_security_guardrail_blocks_drop(self):
        response = self.client.post(
            "/api/query/raw",
            headers=self.auth_headers,
            json={"query": "DROP TABLE ppe_detection"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("DROP' is forbidden", response.json()["detail"])

    def test_admin_api_key_lifecycle(self):
        # 1. List keys
        list_res = self.client.get("/api/admin/keys", headers={"X-Admin-Key": self.admin_key})
        self.assertEqual(list_res.status_code, 200)
        initial_count = len(list_res.json())

        # 2. Create new key for Client B
        create_res = self.client.post(
            "/api/admin/keys",
            headers={"X-Admin-Key": self.admin_key},
            json={
                "client_name": "Test Factory Dashboard",
                "database_url": "sqlite:///./data/detections.db",
                "api_key": "nlp_test_factory_key",
                "max_rows": 50,
            }
        )
        self.assertEqual(create_res.status_code, 200)
        self.assertEqual(create_res.json()["api_key"], "nlp_test_factory_key")

        # 3. Test chat with the newly created key
        client_chat_res = self.client.post(
            "/api/chat",
            headers={"X-API-Key": "nlp_test_factory_key"},
            json={"message": "How many alerts happened today?"},
        )
        self.assertEqual(client_chat_res.status_code, 200)
        self.assertEqual(client_chat_res.json()["client_name"], "Test Factory Dashboard")

        # 4. Delete the key
        del_res = self.client.delete(
            "/api/admin/keys/nlp_test_factory_key",
            headers={"X-Admin-Key": self.admin_key},
        )
        self.assertEqual(del_res.status_code, 200)

        # 5. Verify the key no longer works (401)
        revoked_res = self.client.post(
            "/api/chat",
            headers={"X-API-Key": "nlp_test_factory_key"},
            json={"message": "How many alerts happened today?"},
        )
        self.assertEqual(revoked_res.status_code, 401)

    def test_switch_database_endpoint(self):
        original_url = settings.get_effective_database_url()
        # Test connecting via /api/database/connect
        res = self.client.post(
            "/api/database/connect",
            json={"url": "sqlite:///./data/detections.db"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "connected")
        self.assertEqual(data["dialect"], "sqlite")
        self.assertGreater(data["tables_found"], 0)

        # Restore original url
        res_restore = self.client.post(
            "/api/database/connect",
            json={"url": original_url},
        )
        self.assertEqual(res_restore.status_code, 200)

if __name__ == "__main__":
    unittest.main()
