"""End-to-end walk through the whole V1 flow. Everything after liveness is still a stub (later phases);
this test makes sure the Phase 4 changes did not break the hand-over to those steps."""
from .helpers import WEBM, Flow, make_case


def test_full_video_kyc_workflow(client, db):
    # question pool + configuration (admin endpoints)
    for n in range(1, 4):
        res = client.post("/api/v1/questions", json={"text": f"Question {n}?", "category": "GENERAL", "active": True})
        assert res.status_code == 200
    assert client.put("/api/v1/question-config", json={"question_count": 2, "random_selection": True}).status_code == 200

    flow = Flow(client, db, make_case(db).id)
    assert flow.start_data["current_step"] == "STARTED"
    assert flow.start_recording().json()["status"] == "RECORDING"
    assert flow.face(quality=0.95).json()["next_step"] == "LIVENESS"
    assert flow.liveness(score=0.96).json()["next_step"] == "GENERAL_QUESTIONS"

    res = client.post(flow.base + "/questions/start")
    assert res.status_code == 200
    assert res.json()["total_questions"] == 2
    question_id = res.json()["current_question"]["id"]

    res = client.post(f"{flow.base}/questions/{question_id}/answer", json={"transcript": "Test", "audio_duration_ms": 1000})
    assert res.status_code == 200 and res.json()["completed"] is False
    question_id = res.json()["next_question"]["id"]

    res = client.post(f"{flow.base}/questions/{question_id}/answer", json={"transcript": "Test", "audio_duration_ms": 1000})
    assert res.status_code == 200 and res.json()["completed"] is True
    assert res.json()["next_step"] == "DOCUMENT_PRESENTATION"

    res = client.get(flow.base + "/documents/current")
    assert res.status_code == 200
    document_id = res.json()["document"]["id"]
    res = client.post(f"{flow.base}/documents/{document_id}/capture", files={"file": ("test.jpg", b"abc", "image/jpeg")})
    assert res.status_code == 200 and res.json()["completed"] is False
    document_id = res.json()["next_document"]["id"]
    res = client.post(f"{flow.base}/documents/{document_id}/capture", files={"file": ("test2.jpg", b"def", "image/jpeg")})
    assert res.status_code == 200 and res.json()["next_step"] == "RECORDING_COMPLETE"

    assert flow.upload(content=WEBM).status_code == 200
    res = flow.stop()
    assert res.status_code == 200
    assert res.json()["next_step"] == "EVIDENCE_PACKAGE_CREATED"

    res = client.post(flow.base + "/evidence")
    assert res.status_code == 200 and res.json()["next_step"] == "HUMAN_REVIEW"

    reviews = client.get("/api/v1/reviews").json()["reviews"]
    review_id = next(r["review_id"] for r in reviews if r["attempt_id"] == flow.attempt_id)
    res = client.post(f"/api/v1/reviews/{review_id}/approve", json={"notes": "All good"})
    assert res.status_code == 200 and res.json()["case_status"] == "VERIFIED"


def test_question_count_must_be_positive(client):
    res = client.put("/api/v1/question-config", json={"question_count": 0})
    assert res.status_code == 422
    assert "question_count" in res.json()["error"]["details"]["fields"]
