import uuid

import models

from core.config import settings

from .helpers import MP4, WEBM, Flow, make_case, move_to


def started(client, db):
    flow = Flow(client, db, make_case(db).id)
    assert flow.start_recording().status_code == 200
    return flow


def stored_files():
    root = settings.storage_root
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


# --- start -----------------------------------------------------------------------------------------

def test_start_recording_moves_the_attempt_to_face(client, db):
    flow = Flow(client, db, make_case(db).id)
    res = flow.start_recording()
    assert res.status_code == 200
    assert res.json()["status"] == "RECORDING"
    assert res.json()["attempt_id"] == flow.attempt_id
    assert flow.state()["current_step"] == "FACE"
    assert flow.audit_events().count("RECORDING_STARTED") == 1


def test_start_recording_twice_returns_the_same_recording(client, db):
    flow = started(client, db)
    again = flow.start_recording()
    assert again.status_code == 200
    assert db.query(models.Recording).filter_by(attempt_id=uuid.UUID(flow.attempt_id)).count() == 1
    assert flow.audit_events().count("RECORDING_STARTED") == 1


def test_a_finished_recording_cannot_be_started_again(client, db):
    flow = started(client, db)
    flow.upload()
    flow.stop()
    res = flow.start_recording()
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "INVALID_STATE"


def test_recording_status_endpoint(client, db):
    flow = Flow(client, db, make_case(db).id)
    assert client.get(flow.base + "/recording").status_code == 404
    flow.start_recording()
    res = client.get(flow.base + "/recording")
    assert res.status_code == 200
    assert res.json()["status"] == "RECORDING"


# --- upload ----------------------------------------------------------------------------------------

def test_upload_is_stored_under_a_logical_key(client, db):
    flow = started(client, db)
    res = flow.upload()
    assert res.status_code == 200
    body = res.json()
    assert (body["status"], body["mime_type"], body["size"]) == ("COMPLETED", "video/webm", len(WEBM))
    assert str(settings.storage_root) not in res.text  # no filesystem paths leave the backend

    recording = flow.recording()
    assert recording.storage_key == f"recordings/{flow.attempt_id}/recording.webm"
    assert (settings.storage_root / recording.storage_key).read_bytes() == WEBM
    assert (recording.file_size, recording.mime_type, recording.status) == (len(WEBM), "video/webm", "COMPLETED")
    assert "RECORDING_UPLOADED" in flow.audit_events()


def test_upload_accepts_codec_parameters_in_the_content_type(client, db):
    flow = started(client, db)
    assert flow.upload(content_type="video/webm;codecs=vp9,opus").status_code == 200


def test_mp4_upload_keeps_a_truthful_extension(client, db):
    flow = started(client, db)
    res = flow.upload(content=MP4, content_type="video/mp4", filename="recording.mp4")
    assert res.status_code == 200 and res.json()["mime_type"] == "video/mp4"
    assert flow.recording().storage_key.endswith("recording.mp4")


def test_container_is_detected_from_the_bytes_not_from_the_declared_type(client, db):
    flow = started(client, db)
    res = flow.upload(content=MP4, content_type="application/octet-stream", filename="whatever.webm")
    assert res.status_code == 200 and res.json()["mime_type"] == "video/mp4"
    key = flow.recording().storage_key
    assert key.endswith("recording.mp4") and (settings.storage_root / key).read_bytes() == MP4
    assert len(stored_files()) == 1


def test_upload_before_the_recording_started_is_not_found(client, db):
    flow = Flow(client, db, make_case(db).id)
    res = flow.upload()
    assert res.status_code == 404
    assert stored_files() == []


def test_upload_rejects_files_that_are_not_video(client, db):
    flow = started(client, db)
    res = flow.upload(content=b"this is definitely not a video")
    assert res.status_code == 422
    assert res.json()["error"] == {
        "code": "MEDIA_UPLOAD_FAILED",
        "message": "The uploaded file is not a readable video recording.",
        "details": {"reason": "UNREADABLE_MEDIA"},
    }
    assert stored_files() == []
    assert flow.recording().status == "RECORDING"  # the client may retry
    assert flow.upload().status_code == 200


def test_upload_rejects_unsupported_declared_types(client, db):
    flow = started(client, db)
    res = flow.upload(content_type="text/plain")
    assert res.status_code == 415
    assert res.json()["error"]["details"]["reason"] == "UNSUPPORTED_MEDIA_TYPE"
    assert stored_files() == []


def test_upload_rejects_an_empty_file(client, db):
    flow = started(client, db)
    res = flow.upload(content=b"")
    assert res.status_code == 422
    assert res.json()["error"]["details"]["reason"] == "EMPTY_FILE"
    assert stored_files() == []


def test_upload_rejects_oversized_files_without_leaving_anything_behind(client, db, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1024)
    flow = started(client, db)
    res = flow.upload()
    assert res.status_code == 413
    assert res.json()["error"]["details"] == {"reason": "FILE_TOO_LARGE", "max_bytes": 1024}
    assert stored_files() == []
    assert flow.recording().status == "RECORDING"


def test_a_second_upload_never_overwrites_the_first(client, db):
    flow = started(client, db)
    assert flow.upload(content=WEBM).status_code == 200
    res = flow.upload(content=WEBM + b"extra")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "INVALID_STATE"
    assert res.json()["error"]["details"] == {"recording_status": "COMPLETED"}
    assert (settings.storage_root / flow.recording().storage_key).read_bytes() == WEBM


def test_upload_for_a_different_session_is_not_found(client, db):
    flow = started(client, db)
    url = f"/api/v1/video-sessions/{uuid.uuid4()}/attempts/{flow.attempt_id}/recording"
    res = client.post(url, files={"file": ("r.webm", WEBM, "video/webm")})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert stored_files() == []


# --- stop ------------------------------------------------------------------------------------------

def test_stop_does_not_skip_workflow_steps(client, db):
    """Regression: stopping used to jump straight to EVIDENCE_PACKAGE_CREATED and brick the attempt."""
    flow = started(client, db)
    flow.upload()
    res = flow.stop()
    assert res.status_code == 200
    assert res.json()["status"] == "COMPLETED"
    assert res.json()["next_step"] == "FACE"
    assert flow.state()["current_step"] == "FACE"
    assert flow.face().json()["next_step"] == "LIVENESS"  # the attempt is still usable


def test_stop_before_upload_reports_stopping_and_the_upload_completes_it(client, db):
    flow = started(client, db)
    res = flow.stop()
    assert res.status_code == 200 and res.json()["status"] == "STOPPING"
    assert flow.upload().status_code == 200
    recording = flow.recording()
    assert recording.status == "COMPLETED" and recording.ended_at is not None


def test_stop_is_idempotent(client, db):
    flow = started(client, db)
    flow.upload()
    first, second = flow.stop(), flow.stop()
    assert first.status_code == second.status_code == 200
    assert first.json()["ended_at"] == second.json()["ended_at"]
    assert flow.audit_events().count("RECORDING_STOPPED") == 1


def test_stop_without_a_recording_is_not_found(client, db):
    flow = Flow(client, db, make_case(db).id)
    assert flow.stop().status_code == 404


def test_stop_after_the_last_step_moves_on_to_the_evidence_package(client, db):
    flow = started(client, db)
    move_to(db, flow, "RECORDING_COMPLETE")
    flow.upload()
    res = flow.stop()
    assert res.status_code == 200
    assert res.json()["next_step"] == "EVIDENCE_PACKAGE_CREATED"
    assert flow.state()["current_step"] == "EVIDENCE_PACKAGE_CREATED"


def test_stop_then_upload_also_reaches_the_evidence_package(client, db):
    flow = started(client, db)
    move_to(db, flow, "RECORDING_COMPLETE")
    stopped = flow.stop()
    assert stopped.json()["next_step"] == "RECORDING_COMPLETE"  # nothing is uploaded yet
    flow.upload()
    assert flow.state()["current_step"] == "EVIDENCE_PACKAGE_CREATED"
