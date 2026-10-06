import uuid

import models

from .helpers import Flow, make_case, move_to


def test_start_session_returns_documents_and_marks_the_case_in_progress(client, db):
    case = make_case(db)
    res = client.post(f"/api/v1/kyc-cases/{case.id}/video-sessions")
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "IN_PROGRESS"
    assert data["current_step"] == "STARTED"
    assert data["attempt_number"] == 1
    assert data["recording"] == {"status": "NOT_STARTED"}
    assert [d["document_type"] for d in data["documents"]] == ["DOC1", "DOC2"]
    db.refresh(case)
    assert case.status == "IN_PROGRESS"


def test_unknown_case_is_not_found(client):
    res = client.post(f"/api/v1/kyc-cases/{uuid.uuid4()}/video-sessions")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_duplicate_start_hands_back_the_same_untouched_session(client, db):
    case = make_case(db)
    first = client.post(f"/api/v1/kyc-cases/{case.id}/video-sessions")
    second = client.post(f"/api/v1/kyc-cases/{case.id}/video-sessions")
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["session_id"] == second.json()["session_id"]
    assert first.json()["attempt_id"] == second.json()["attempt_id"]
    assert db.query(models.VideoSession).filter_by(case_id=case.id).count() == 1


def test_starting_again_after_progress_abandons_the_old_session_cleanly(client, db):
    case = make_case(db)
    old = Flow(client, db, case.id)
    assert old.start_recording().status_code == 200

    new = Flow(client, db, case.id)
    assert new.session_id != old.session_id

    db.expire_all()
    old_session = db.get(models.VideoSession, uuid.UUID(old.session_id))
    assert old_session.status == "CANCELLED"
    assert old.attempt().status == "FAILED"
    assert old.recording().status == "FAILED"
    abandoned = db.query(models.AuditEvent).filter_by(case_id=case.id, event_type="SESSION_ABANDONED").all()
    assert len(abandoned) == 1 and abandoned[0].metadata_ == {"reason": "NEW_SESSION_REQUESTED"}
    assert db.query(models.VideoSession).filter_by(case_id=case.id, status="IN_PROGRESS").count() == 1
    # The abandoned attempt can no longer be used.
    assert old.face().status_code == 409


def test_session_waiting_for_review_is_never_abandoned(client, db):
    case = make_case(db)
    flow = Flow(client, db, case.id)
    move_to(db, flow, "HUMAN_REVIEW")
    res = client.post(f"/api/v1/kyc-cases/{case.id}/video-sessions")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "INVALID_STATE"
    assert flow.state()["status"] == "IN_PROGRESS"


def test_verified_case_cannot_start_a_new_session(client, db):
    case = make_case(db, status="VERIFIED")
    res = client.post(f"/api/v1/kyc-cases/{case.id}/video-sessions")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "INVALID_STATE"


def test_get_session_state_follows_the_attempt(client, db):
    flow = Flow(client, db, make_case(db).id)
    assert flow.state()["current_step"] == "STARTED"
    flow.start_recording()
    state = flow.state()
    assert state["current_step"] == "FACE"
    assert state["recording"] == {"status": "RECORDING"}
