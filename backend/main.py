from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.errors import install_error_handlers
from fastapi import FastAPI
from core.config import settings

from api import router as api_router
from api_questions import router as questions_router
from api_documents import router as documents_router
from api_evidence import router as evidence_router

app = FastAPI(
    title="Video KYC API",
    version="1.0.0"
)

install_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(questions_router)
app.include_router(documents_router)
app.include_router(evidence_router)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Video KYC API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
