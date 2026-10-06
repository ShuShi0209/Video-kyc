import uuid

from .helpers import Flow, make_case, now_iso


def test_unknown_session_uses_the_contract_error_shape(client):
    res = client.get(f"/api/v1/video-sessions/{uuid.uuid4()}")
    assert res.status_code == 404
    assert res.json() == {
        "error": {"code": "SESSION_NOT_FOUND", "message": "The requested session was not found.", "details": {}}
    }


def test_invalid_uuid_is_a_validation_error(client):
    res = client.get("/api/v1/video-sessions/not-a-uuid")
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert "session_id" in error["details"]["fields"]


def test_bad_body_reports_the_offending_field(client, db):
    flow = Flow(client, db, make_case(db).id)
    res = client.post(flow.base + "/recording/start", json={"started_at": "garbage"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "started_at" in res.json()["error"]["details"]["fields"]


def test_missing_upload_field_is_a_validation_error(client, db):
    flow = Flow(client, db, make_case(db).id)
    flow.start_recording()
    res = client.post(flow.base + "/recording")
    assert res.status_code == 422
    assert "file" in res.json()["error"]["details"]["fields"]


def test_unknown_route_uses_the_contract_error_shape(client):
    res = client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_attempt_must_belong_to_the_session_in_the_url(client, db):
    one = Flow(client, db, make_case(db).id)
    two = Flow(client, db, make_case(db).id)
    url = f"/api/v1/video-sessions/{one.session_id}/attempts/{two.attempt_id}/recording/start"
    res = client.post(url, json={"started_at": now_iso()})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"


def test_timestamps_without_a_timezone_are_accepted_as_utc(client, db):
    flow = Flow(client, db, make_case(db).id)
    res = client.post(flow.base + "/recording/start", json={"started_at": "2026-10-01T12:00:00"})
    assert res.status_code == 200
    assert res.json()["started_at"].startswith("2026-10-01T12:00:00")
