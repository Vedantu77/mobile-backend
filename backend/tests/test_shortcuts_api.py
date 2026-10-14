"""Backend API tests for Media Hub shortcuts."""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://kind-banach-8.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def created_ids():
    return []


# ---------------- Health / root ----------------
def test_root(session):
    r = session.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("message") == "Media Hub API"


# ---------------- Presets ----------------
class TestPresets:
    def test_list_returns_presets(self, session):
        r = session.get(f"{API}/shortcuts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        titles = {s["title"] for s in data if s.get("is_preset")}
        for expected in ["YouTube", "JioHotstar", "Netflix", "Prime Video"]:
            assert expected in titles, f"Missing preset {expected}"

    def test_no_mongo_id_in_response(self, session):
        r = session.get(f"{API}/shortcuts")
        for item in r.json():
            assert "_id" not in item
            # verify required fields
            for key in ["id", "title", "url", "color", "is_preset", "position"]:
                assert key in item


# ---------------- CRUD ----------------
class TestShortcutsCRUD:
    def test_create_custom(self, session, created_ids):
        payload = {
            "title": "TEST_SonyLIV",
            "url": "https://www.sonyliv.com",
            "color": "#8E24AA",
            "logo_url": "https://logo.clearbit.com/sonyliv.com",
        }
        r = session.post(f"{API}/shortcuts", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["title"] == payload["title"]
        assert data["url"] == payload["url"]
        assert data["color"] == payload["color"]
        assert data["is_preset"] is False
        assert data["id"]
        created_ids.append(data["id"])

    def test_created_shortcut_persists_in_list(self, session, created_ids):
        assert created_ids
        new_id = created_ids[-1]
        r = session.get(f"{API}/shortcuts")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert new_id in ids

    def test_patch_update(self, session, created_ids):
        new_id = created_ids[-1]
        r = session.patch(f"{API}/shortcuts/{new_id}", json={"title": "TEST_SonyLIV_Updated", "color": "#00C853"})
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "TEST_SonyLIV_Updated"
        assert data["color"] == "#00C853"
        # verify persistence
        r2 = session.get(f"{API}/shortcuts")
        found = [s for s in r2.json() if s["id"] == new_id][0]
        assert found["title"] == "TEST_SonyLIV_Updated"
        assert found["color"] == "#00C853"

    def test_patch_not_found(self, session):
        r = session.patch(f"{API}/shortcuts/nonexistent-id", json={"title": "x"})
        assert r.status_code == 404

    def test_delete_soft(self, session, created_ids):
        new_id = created_ids[-1]
        r = session.delete(f"{API}/shortcuts/{new_id}")
        assert r.status_code == 200
        assert r.json().get("success") is True
        # verify excluded from list
        r2 = session.get(f"{API}/shortcuts")
        ids = [s["id"] for s in r2.json()]
        assert new_id not in ids

    def test_delete_already_deleted_404(self, session, created_ids):
        new_id = created_ids[-1]
        r = session.delete(f"{API}/shortcuts/{new_id}")
        assert r.status_code == 404
