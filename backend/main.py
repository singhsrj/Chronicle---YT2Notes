"""
YT Notes - FastAPI Backend
Long Video Transcription API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routers import long_video

app = FastAPI(
    title="YT Notes - Long Video Transcription API",
    description="YouTube long video transcription with chunking, checkpoints, and faster-whisper",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(
    long_video.router,
    prefix="/api/long-video",
    tags=["Long Video Transcription"]
)


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "message": "YT Notes Long Video Transcription API",
        "version": "1.0.0",
        "endpoints": {
            "transcribe": "POST /api/long-video/transcribe",
            "status": "GET /api/long-video/status/{session_id}",
            "result": "GET /api/long-video/result/{session_id}",
            "download_text": "GET /api/long-video/download/text/{session_id}",
            "download_json": "GET /api/long-video/download/json/{session_id}",
            "sessions": "GET /api/long-video/sessions",
            "delete": "DELETE /api/long-video/session/{session_id}"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}
