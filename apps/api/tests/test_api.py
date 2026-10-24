import unittest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class ApiTestCase(unittest.TestCase):
    def test_health_live(self):
        response = client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "live"})

    def test_system_info(self):
        response = client.get("/api/v1/system/info")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["version"], "0.1.0")
        self.assertIn("capabilities", data)

    def test_create_job_requires_rights_attestation(self):
        payload = {
            "source": {"type": "synthetic", "url": "test://test"},
            "output": {"mode": "video", "container": "mp4"},
            "rightsConfirmed": False,
        }
        response = client.post("/api/v1/jobs", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn(data["code"], ["POLICY_VIOLATION", "VALIDATION_ERROR"])

    def test_sources_capabilities(self):
        response = client.get("/api/v1/sources/capabilities")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("enabledAdapters", data)
        self.assertIn("youtube", data["enabledAdapters"])

    def test_ssrf_inspection_blocked(self):
        payload = {
            "url": "http://127.0.0.1:8000/sample.mp4",
            "rightsConfirmed": True,
        }
        response = client.post("/api/v1/sources/inspect", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["policy"]["decision"], "denied")
        self.assertEqual(data["policy"]["reasonCode"], "SSRF_SECURITY_VIOLATION")

    def test_assets_list(self):
        response = client.get("/api/v1/assets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        self.assertIn("total", data)


if __name__ == "__main__":
    unittest.main()
