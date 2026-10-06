import uuid
from datetime import datetime, timezone

import models

# Minimal byte strings that carry the real container signatures the backend sniffs for.
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 2048
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2048


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_case(db, status="CREATED", documents=2):
    case = models.KycCase(status=status)
    db.add(case)
    db.flush()
    for n in range(1, documents + 1):
        db.add(models.Document(
            case_id=case.id, document_type=f"DOC{n}", filename=f"doc{n}.jpg", mime_type="image/jpeg",
            storage_key=f"documents/{case.id}/doc{n}.jpg", sequence_number=n,
        ))
    db.commit()
    return case


def move_to(db, flow, step):
    """Put the attempt (and its session) at a workflow step without going through the earlier steps."""
    attempt = db.get(models.Attempt, uuid.UUID(flow.attempt_id))
    attempt.current_step = step
    attempt.video_session.current_step = step
    db.commit()


class Flow:
    """Drives one video KYC attempt through the HTTP API."""

    def __init__(self, client, db, case_id):
        self.client = client
        self.db = db
        res = client.post(f"/api/v1/kyc-cases/{case_id}/video-sessions")
        assert res.status_code in (200, 201), res.text
        self.start_data = res.json()
        self.session_id = self.start_data["session_id"]
        self.attempt_id = self.start_data["attempt_id"]

    @property
    def base(self):
        return f"/api/v1/video-sessions/{self.session_id}/attempts/{self.attempt_id}"

    def start_recording(self):
        return self.client.post(self.base + "/recording/start", json={"started_at": now_iso()})

    def upload(self, content=WEBM, content_type="video/webm", filename="recording.webm"):
        return self.client.post(self.base + "/recording", files={"file": (filename, content, content_type)})

    def stop(self):
        return self.client.post(self.base + "/recording/stop", json={"ended_at": now_iso()})

    def face(self, detected=True, face_count=1, quality=0.9):
        return self.client.post(self.base + "/face", json={
            "detected": detected, "face_count": face_count, "quality": quality, "timestamp": now_iso(),
        })

    def liveness(self, status="PASS", score=0.9, **extra):
        return self.client.post(self.base + "/liveness", json={
            "status": status, "score": score, "timestamp": now_iso(), **extra,
        })

    def state(self):
        res = self.client.get(f"/api/v1/video-sessions/{self.session_id}")
        assert res.status_code == 200, res.text
        return res.json()

    def recording(self):
        self.db.expire_all()
        return self.db.query(models.Recording).filter(models.Recording.attempt_id == uuid.UUID(self.attempt_id)).first()

    def attempt(self):
        self.db.expire_all()
        return self.db.get(models.Attempt, uuid.UUID(self.attempt_id))

    def audit_events(self):
        self.db.expire_all()
        rows = (
            self.db.query(models.AuditEvent)
            .filter(models.AuditEvent.attempt_id == uuid.UUID(self.attempt_id))
            .order_by(models.AuditEvent.created_at)
            .all()
        )
        return [row.event_type for row in rows]
