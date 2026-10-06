"""Create a demo KYC case so the frontend has a case id to start a video session for.

Run from backend/:
    python seed.py          # reuse the newest case if one exists
    python seed.py --new    # always create a fresh case
"""
import sys

import models
from core.database import SessionLocal

DEMO_DOCUMENTS = [("AADHAAR", "aadhaar.jpg"), ("PAN", "pan.jpg")]


def seed(force_new: bool = False) -> None:
    db = SessionLocal()
    try:
        case = None if force_new else db.query(models.KycCase).order_by(models.KycCase.created_at.desc()).first()
        if case:
            print(f"KYC case already exists: {case.id} (status: {case.status})")
        else:
            case = models.KycCase(status="CREATED")
            db.add(case)
            db.flush()
            for sequence, (document_type, filename) in enumerate(DEMO_DOCUMENTS, start=1):
                db.add(models.Document(
                    case_id=case.id,
                    document_type=document_type,
                    filename=filename,
                    mime_type="image/jpeg",
                    storage_key=f"documents/{case.id}/{filename}",
                    sequence_number=sequence,
                ))
            db.commit()
            db.refresh(case)
            print(f"Created KYC case: {case.id}")
        for document in sorted(case.documents, key=lambda d: d.sequence_number):
            print(f"  Document: {document.id} ({document.document_type})")
        print("\nEnter this case id in the frontend to begin a session.")
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
        raise SystemExit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed(force_new="--new" in sys.argv[1:])
