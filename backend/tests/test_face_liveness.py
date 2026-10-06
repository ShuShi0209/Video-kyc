import pytest

import models
from core.config import settings

from .helpers import Flow, make_case


def started(client, db):
    flow = Flow(client, db, make_case(db).id)
    assert flow.start_recording().status_code == 200
    return flow


def at_liveness(client, db):
    flow = started(client, db)
    assert flow.face().status_code == 200
    return flow


# --- face ------------------------------------------------------------------------------------------

def test_face_requires_the_recording_to_be_started(client, db):
    flow = Flow(client, db, make_case(db).id)
    res = flow.face()
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "INVALID_STATE"
    assert res.json()["error"]["details"] == {"current_step": "STARTED", "requested_step": "FACE"}


def test_liveness_before_face_is_an_invalid_state(client, db):
    flow = started(client, db)
    res = flow.liveness()
    assert res.status_code == 409
    assert res.json()["error"]["details"] == {"current_step": "FACE", "requested_step": "LIVENESS"}


def test_face_pass_moves_to_liveness(client, db):
    flow = started(client, db)
    res = flow.face()
    assert res.status_code == 200
    body = res.json()
    assert (body["step"], body["result"], body["next_step"]) == ("FACE", "PASS", "LIVENESS")
    assert body["retry"] == {"allowed": False, "retry_count": 0, "max_retries": 3}
    assert flow.state()["current_step"] == "LIVENESS"
    assert "FACE_PASSED" in flow.audit_events()
    row = db.query(models.FaceResult).filter_by(attempt_id=flow.attempt().id).one()
    assert (row.result, row.retry_count, row.face_count) == ("PASS", 0, 1)


@pytest.mark.parametrize("kwargs, expected", [
    (dict(detected=False, face_count=0, quality=0.0), "No face detected"),
    (dict(detected=True, face_count=2, quality=0.9), "More than one face"),
    (dict(detected=True, face_count=1, quality=0.2), "could not see your face clearly"),
])
def test_face_failures_explain_what_went_wrong(client, db, kwargs, expected):
    flow = started(client, db)
    res = flow.face(**kwargs)
    assert res.status_code == 200
    body = res.json()
    assert (body["result"], body["next_step"]) == ("FAIL", "FACE")
    assert body["retry"] == {"allowed": True, "retry_count": 1, "max_retries": 3}
    assert expected in body["message"]
    assert flow.state()["current_step"] == "FACE"
    assert "FACE_FAILED" in flow.audit_events()


def test_face_can_pass_after_a_failure(client, db):
    flow = started(client, db)
    assert flow.face(detected=False, face_count=0, quality=0).json()["result"] == "FAIL"
    body = flow.face().json()
    assert body["result"] == "PASS"
    assert body["retry"]["retry_count"] == 1


def test_exhausting_face_retries_closes_the_attempt(client, db, monkeypatch):
    monkeypatch.setattr(settings, "FACE_MAX_RETRIES", 2)
    flow = started(client, db)
    first = flow.face(detected=False, face_count=0, quality=0).json()
    second = flow.face(detected=False, face_count=0, quality=0).json()
    assert first["retry"]["allowed"] is True
    assert second["retry"] == {"allowed": False, "retry_count": 2, "max_retries": 2}
    assert "start a new session" in second["message"]

    third = flow.face()
    assert third.status_code == 409
    assert third.json()["error"]["code"] == "RETRY_LIMIT_REACHED"
    assert flow.attempt().status == "FAILED"
    assert flow.state()["current_step"] == "FACE"  # the frontend must not invent a new step
    assert flow.audit_events().count("FACE_FAILED") == 2


def test_retry_limits_come_from_configuration(client, db, monkeypatch):
    monkeypatch.setattr(settings, "MAX_RETRIES", 5)
    assert settings.max_retries_for("FACE") == 5 and settings.max_retries_for("LIVENESS") == 5
    monkeypatch.setattr(settings, "LIVENESS_MAX_RETRIES", 1)
    assert settings.max_retries_for("LIVENESS") == 1 and settings.max_retries_for("FACE") == 5
    flow = started(client, db)
    assert flow.face(detected=False, face_count=0, quality=0).json()["retry"]["max_retries"] == 5


def test_face_request_values_are_validated(client, db):
    flow = started(client, db)
    res = flow.face(quality=1.5)
    assert res.status_code == 422
    assert "quality" in res.json()["error"]["details"]["fields"]


# --- liveness --------------------------------------------------------------------------------------

def test_liveness_pass_moves_to_general_questions(client, db):
    flow = at_liveness(client, db)
    res = flow.liveness(score=0.96, provider="browser-face-api")
    assert res.status_code == 200
    assert (res.json()["result"], res.json()["next_step"]) == ("PASS", "GENERAL_QUESTIONS")
    assert flow.state()["current_step"] == "GENERAL_QUESTIONS"
    assert "LIVENESS_PASSED" in flow.audit_events()
    row = db.query(models.LivenessResult).filter_by(attempt_id=flow.attempt().id).one()
    assert (row.result, row.provider, row.retry_count) == ("PASS", "browser-face-api", 0)


def test_liveness_provider_defaults_to_browser(client, db):
    flow = at_liveness(client, db)
    flow.liveness()
    assert db.query(models.LivenessResult).filter_by(attempt_id=flow.attempt().id).one().provider == "BROWSER"


def test_liveness_failure_allows_a_retry(client, db):
    flow = at_liveness(client, db)
    res = flow.liveness(status="FAIL", score=0.0)
    assert res.status_code == 200
    assert res.json()["result"] == "FAIL"
    assert res.json()["retry"] == {"allowed": True, "retry_count": 1, "max_retries": 3}
    assert "LIVENESS_FAILED" in flow.audit_events()
    assert flow.liveness().json()["next_step"] == "GENERAL_QUESTIONS"


def test_unknown_liveness_status_is_rejected_instead_of_counted_as_a_failure(client, db):
    flow = at_liveness(client, db)
    res = flow.liveness(status="MAYBE")
    assert res.status_code == 422
    assert "status" in res.json()["error"]["details"]["fields"]
    assert db.query(models.LivenessResult).filter_by(attempt_id=flow.attempt().id).count() == 0


def test_a_pass_with_a_very_low_score_is_not_trusted(client, db):
    flow = at_liveness(client, db)
    assert flow.liveness(status="PASS", score=0.1).json()["result"] == "FAIL"


def test_exhausting_liveness_retries_closes_the_attempt(client, db, monkeypatch):
    monkeypatch.setattr(settings, "LIVENESS_MAX_RETRIES", 2)
    flow = at_liveness(client, db)
    flow.liveness(status="FAIL", score=0)
    last = flow.liveness(status="FAIL", score=0).json()
    assert last["retry"]["allowed"] is False and "start a new session" in last["message"]
    assert flow.liveness().json()["error"]["code"] == "RETRY_LIMIT_REACHED"
    assert flow.attempt().status == "FAILED"
    assert flow.state()["current_step"] == "LIVENESS"


def test_attempt_state_reports_retry_counts(client, db):
    flow = at_liveness(client, db)
    flow.liveness(status="FAIL", score=0)
    res = client.get(flow.base)
    assert res.status_code == 200
    body = res.json()
    assert body["current_step"] == "LIVENESS" and body["status"] == "IN_PROGRESS"
    assert body["retry_counts"] == {"FACE": 1, "LIVENESS": 1}
