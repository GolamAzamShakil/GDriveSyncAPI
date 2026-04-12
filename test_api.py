from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import core.config as cfg

cfg.LOG_FILE = "/tmp/test_gdrive_sync.log"
cfg.STATE_FILE = "/tmp/test_gdrive_sync_state.json"
cfg.RCLONE_EXE = "/usr/bin/false"  # won't be called in tests

from core.state import FolderMapping, FolderState, ALL_STATES, PROGRESS
from core.schedule import SCHEDULE

# Inject a dummy folder state so /uploads endpoints have data
_dummy_mapping = FolderMapping(
    local_path="/tmp/test_local",
    rclone_dest="TestDrive:test",
    label="TestFolder",
)
_dummy_state = FolderState(mapping=_dummy_mapping)
_dummy_state.uploaded = {"/tmp/test_local/a.txt": 1700000000.0}
_dummy_state.handled_dirs = {"subdir"}
_dummy_state.skipped_dirs = set()
ALL_STATES.clear()
ALL_STATES.append(_dummy_state)

# Patch FOLDER_MAPPINGS so lifespan doesn't try to makedirs on H:\
cfg.FOLDER_MAPPINGS = []

from main import app  # noqa: E402 — import after patching

CLIENT = TestClient(app, raise_server_exceptions=True)

def _login(username="admin", password="admin123") -> str:
    r = CLIENT.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

class TestHealth:
    def test_health_ok(self):
        r = CLIENT.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestAuth:
    def test_login_admin_success(self):
        r = CLIENT.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "admin"
        assert "access_token" in body

    def test_login_viewer_success(self):
        r = CLIENT.post(
            "/api/v1/auth/login", json={"username": "viewer", "password": "viewer123"}
        )
        assert r.status_code == 200
        assert r.json()["role"] == "viewer"

    def test_login_wrong_password(self):
        r = CLIENT.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert r.status_code == 401

    def test_login_unknown_user(self):
        r = CLIENT.post(
            "/api/v1/auth/login", json={"username": "ghost", "password": "x"}
        )
        assert r.status_code == 401

    def test_me_endpoint(self):
        token = _login()
        r = CLIENT.get("/api/v1/auth/me", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["username"] == "admin"

    def test_me_no_token(self):
        r = CLIENT.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_me_bad_token(self):
        r = CLIENT.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401


class TestSync:
    def test_get_state_viewer(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.get("/api/v1/sync/state", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert "paused" in body
        assert "upload_active" in body

    def test_get_state_unauthenticated(self):
        r = CLIENT.get("/api/v1/sync/state")
        assert r.status_code == 401

    def test_pause_resume_admin(self):
        token = _login()
        # Ensure resumed first
        CLIENT.post("/api/v1/sync/resume", headers=_auth(token))
        r = CLIENT.post("/api/v1/sync/pause", headers=_auth(token))
        assert r.status_code == 200
        assert "paused" in r.json()["message"].lower()
        r2 = CLIENT.post("/api/v1/sync/resume", headers=_auth(token))
        assert r2.status_code == 200

    def test_pause_viewer_forbidden(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.post("/api/v1/sync/pause", headers=_auth(token))
        assert r.status_code == 403

    def test_scan_now_admin(self):
        token = _login()
        r = CLIENT.post("/api/v1/sync/scan", headers=_auth(token))
        assert r.status_code == 200

    def test_scan_now_viewer_forbidden(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.post("/api/v1/sync/scan", headers=_auth(token))
        assert r.status_code == 403

    def test_get_progress(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.get("/api/v1/sync/progress", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert "active" in body
        assert "pct" in body


class TestSchedule:
    def test_get_schedule_viewer(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.get("/api/v1/schedule", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert "interval" in body
        assert "clock" in body
        assert "countdown_label" in body

    def test_put_schedule_admin(self):
        token = _login()
        payload = {
            "interval": {"enabled": True, "hours": 3, "minutes": 30},
            "clock": {"enabled": False, "times": []},
        }
        r = CLIENT.put("/api/v1/schedule", json=payload, headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["interval"]["hours"] == 3
        assert body["interval"]["minutes"] == 30

    def test_put_schedule_invalid_interval(self):
        token = _login()
        payload = {"interval": {"enabled": True, "hours": 0, "minutes": 0}}
        r = CLIENT.put("/api/v1/schedule", json=payload, headers=_auth(token))
        assert r.status_code == 400

    def test_put_schedule_invalid_clock_time(self):
        token = _login()
        payload = {"clock": {"enabled": True, "times": ["99:99"]}}
        r = CLIENT.put("/api/v1/schedule", json=payload, headers=_auth(token))
        assert r.status_code == 400

    def test_patch_interval(self):
        token = _login()
        r = CLIENT.patch(
            "/api/v1/schedule/interval",
            json={"enabled": True, "hours": 2, "minutes": 0},
            headers=_auth(token),
        )
        assert r.status_code == 200

    def test_patch_clock(self):
        token = _login()
        r = CLIENT.patch(
            "/api/v1/schedule/clock",
            json={"enabled": True, "times": ["08:00", "20:00"]},
            headers=_auth(token),
        )
        assert r.status_code == 200
        assert "08:00" in r.json()["clock"]["times"]

    def test_patch_clock_bad_time(self):
        token = _login()
        r = CLIENT.patch(
            "/api/v1/schedule/clock",
            json={"enabled": True, "times": ["8am"]},
            headers=_auth(token),
        )
        assert r.status_code == 400

    def test_reset_interval_admin(self):
        token = _login()
        r = CLIENT.post("/api/v1/schedule/reset", headers=_auth(token))
        assert r.status_code == 200

    def test_schedule_viewer_cannot_modify(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.put(
            "/api/v1/schedule",
            json={"interval": {"enabled": False, "hours": 1, "minutes": 0}},
            headers=_auth(token),
        )
        assert r.status_code == 403


class TestUploads:
    def test_list_uploads_viewer(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.get("/api/v1/uploads", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert "files" in body
        assert "total" in body
        assert body["total"] >= 1  # dummy state has 1 file

    def test_list_uploads_filter_label(self):
        token = _login()
        r = CLIENT.get("/api/v1/uploads?label=TestFolder", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_uploads_filter_nonexistent_label(self):
        token = _login()
        r = CLIENT.get("/api/v1/uploads?label=NoSuchLabel", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_uploads_path_like(self):
        token = _login()
        r = CLIENT.get("/api/v1/uploads?path_like=a.txt", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_uploads_pagination(self):
        token = _login()
        r = CLIENT.get("/api/v1/uploads?limit=1&offset=0", headers=_auth(token))
        assert r.status_code == 200
        assert len(r.json()["files"]) <= 1

    def test_list_folders(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.get("/api/v1/uploads/folders", headers=_auth(token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert r.json()[0]["label"] == "TestFolder"

    def test_get_folder_by_label(self):
        token = _login()
        r = CLIENT.get("/api/v1/uploads/folders/TestFolder", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["label"] == "TestFolder"

    def test_get_folder_not_found(self):
        token = _login()
        r = CLIENT.get("/api/v1/uploads/folders/Ghost", headers=_auth(token))
        assert r.status_code == 404

    def test_clear_skipped_admin(self):
        token = _login()
        r = CLIENT.delete(
            "/api/v1/uploads/folders/TestFolder/skipped", headers=_auth(token)
        )
        assert r.status_code == 200
        assert "Cleared" in r.json()["message"]

    def test_clear_skipped_viewer_forbidden(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.delete(
            "/api/v1/uploads/folders/TestFolder/skipped", headers=_auth(token)
        )
        assert r.status_code == 403

    def test_uploads_unauthenticated(self):
        r = CLIENT.get("/api/v1/uploads")
        assert r.status_code == 401


#  Logs  (admin only)
class TestLogs:
    def test_get_logs_admin(self):
        token = _login()
        r = CLIENT.get("/api/v1/logs", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert "lines" in body
        assert "count" in body

    def test_get_logs_viewer_forbidden(self):
        token = _login("viewer", "viewer123")
        r = CLIENT.get("/api/v1/logs", headers=_auth(token))
        assert r.status_code == 403

    def test_get_logs_level_filter(self):
        token = _login()
        r = CLIENT.get("/api/v1/logs?level=INFO", headers=_auth(token))
        assert r.status_code == 200

    def test_get_logs_n_param(self):
        token = _login()
        r = CLIENT.get("/api/v1/logs?n=10", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["count"] <= 10

    def test_tail_log_file_missing(self):
        token = _login()
        # LOG_FILE is patched to /tmp/test_gdrive_sync.log which may not exist
        r = CLIENT.get("/api/v1/logs/file", headers=_auth(token))
        # Either 200 (exists) or 404 (doesn't exist yet) are fine
        assert r.status_code in (200, 404)

    def test_logs_unauthenticated(self):
        r = CLIENT.get("/api/v1/logs")
        assert r.status_code == 401


#  CORS headers
class TestCORS:
    def test_options_preflight(self):
        r = CLIENT.options(
            "/api/v1/sync/state",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # TestClient may return 200 or 405 for OPTIONS depending on CORS setup
        assert r.status_code in (200, 405)

    def test_security_headers_present(self):
        token = _login()
        r = CLIENT.get("/health")
        # Security headers added by middleware
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"


class TestApiStatus:
    """Unit tests for the ApiStatus state machine."""

    def setup_method(self):
        from core.api_status import API_STATUS

        self.s = API_STATUS

    def test_initial_state_after_set_starting(self):
        self.s.set_starting()
        assert self.s.state == "starting"
        assert not self.s.is_healthy

    def test_set_healthy(self):
        self.s.set_healthy("0.0.0.0", 8000)
        assert self.s.state == "healthy"
        assert self.s.is_healthy
        assert self.s.port == 8000
        assert "localhost" in self.s.url
        assert "8000" in self.s.url

    def test_set_unhealthy(self):
        self.s.set_unhealthy("connection refused")
        assert self.s.state == "unhealthy"
        assert not self.s.is_healthy
        assert "❌" in self.s.tray_status_line()

    def test_set_stopped(self):
        self.s.set_stopped()
        assert self.s.state == "stopped"
        assert not self.s.is_healthy

    def test_url_normalises_0000(self):
        self.s.set_healthy("0.0.0.0", 9000)
        assert "localhost:9000" in self.s.url

    def test_docs_url(self):
        self.s.set_healthy("0.0.0.0", 8000)
        assert self.s.docs_url.endswith("/docs")

    def test_tray_status_line_healthy(self):
        self.s.set_healthy("0.0.0.0", 8000)
        line = self.s.tray_status_line()
        assert "✅" in line
        assert "8000" in line

    def test_tray_status_line_starting(self):
        self.s.set_starting()
        assert "⏳" in self.s.tray_status_line()

    def test_icon_color_per_state(self):
        self.s.set_healthy("127.0.0.1", 8000)
        assert self.s.tray_icon_color() == "#4CAF50"
        self.s.set_starting()
        assert self.s.tray_icon_color() == "#2196F3"
        self.s.set_unhealthy("boom")
        assert self.s.tray_icon_color() == "#F44336"
        self.s.set_stopped()
        assert self.s.tray_icon_color() == "#9E9E9E"

    def test_health_endpoint_returns_host_port(self):
        """The /health HTTP endpoint now includes host and port fields."""
        r = CLIENT.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert "host" in body
        assert "port" in body
        assert body["port"] == 8000
