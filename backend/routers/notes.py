"""
FastAPI router for transcript-to-notes generation.

Endpoints:
  POST /notes/from-json  — accepts JSON body { "transcript": "...", "title": "..." }
  POST /notes/from-txt   — accepts a raw .txt file upload
  GET  /notes/health     — checks if Ollama is reachable

Mount in main.py with:
    from backend.routers.notes import router as notes_router
    app.include_router(notes_router, prefix="/notes", tags=["Notes"])
"""

import json
import requests

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional

from backend.models.notes import TranscriptInput, NotesResponse
from backend.services.notes_service import generate_notes, generate_notes_stream

# ─────────────────────────────────────────────
# Router setup — prefix & tags are set in main.py
# ─────────────────────────────────────────────
router = APIRouter()

OLLAMA_HEALTH_URL = "http://localhost:11434/v1/models"


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────
@router.get("/health")
def health_check():
    """
    Checks whether the local Ollama instance is running and reachable.
    Call this before sending a transcript to avoid confusing timeout errors.
    """
    try:
        resp = requests.get(OLLAMA_HEALTH_URL, timeout=5)
        if resp.status_code == 200:
            return {"ollama_status": "running", "models": resp.json()}
        return {"ollama_status": "unreachable", "detail": resp.text}
    except requests.exceptions.ConnectionError:
        return {"ollama_status": "offline", "detail": "Could not connect to localhost:11434"}


# ─────────────────────────────────────────────
# ENDPOINT 1 — JSON input
# Frontend sends: { "transcript": "...", "title": "My Video" }
# ─────────────────────────────────────────────
@router.post("/from-json", response_model=NotesResponse)
def notes_from_json(payload: TranscriptInput):
    """
    Generate notes from a JSON body.

    Request body:
        {
            "transcript": "<raw transcript text>",
            "title": "<optional video title>"   // optional, defaults to "Untitled Video"
        }

    Returns:
        NotesResponse with markdown notes.

    React fetch example:
        const res = await fetch("http://localhost:8000/notes/from-json", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ transcript: text, title: videoTitle })
        });
        const data = await res.json();
        setNotes(data.notes);
    """
    if not payload.transcript.strip():
        raise HTTPException(status_code=422, detail="Transcript cannot be empty.")

    result = generate_notes(transcript=payload.transcript, title=payload.title)

    if result.status == "error":
        # Return 503 so the frontend can show a proper "service unavailable" message
        raise HTTPException(status_code=503, detail=result.error)

    return result


# ─────────────────────────────────────────────
# ENDPOINT 2 — TXT file upload
# Frontend sends a multipart/form-data with a .txt file
# ─────────────────────────────────────────────
@router.post("/from-txt", response_model=NotesResponse)
async def notes_from_txt(
    file: UploadFile = File(..., description="Plain .txt transcript file"),
    title: Optional[str] = Form(default="Untitled Video", description="Optional video title")
):
    """
    Generate notes from an uploaded .txt transcript file.

    Accepts:
        multipart/form-data with:
            - file:  a .txt file containing the transcript
            - title: (optional) the video title as a form field

    Returns:
        NotesResponse with markdown notes.

    React fetch example:
        const formData = new FormData();
        formData.append("file", txtFile);          // File object from <input type="file">
        formData.append("title", "My Video Title");
        const res = await fetch("http://localhost:8000/notes/from-txt", {
            method: "POST",
            body: formData   // DO NOT set Content-Type header — browser sets it with boundary
        });
        const data = await res.json();
        setNotes(data.notes);
    """
    # Validate file type
    if not file.filename.endswith(".txt"):
        raise HTTPException(
            status_code=415,
            detail="Only .txt files are accepted. For JSON transcripts use /from-json."
        )

    raw_bytes = await file.read()

    try:
        transcript = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail="Could not decode file as UTF-8. Please ensure the .txt file is UTF-8 encoded."
        )

    if not transcript.strip():
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    result = generate_notes(transcript=transcript, title=title)

    if result.status == "error":
        raise HTTPException(status_code=503, detail=result.error)

    return result


# ─────────────────────────────────────────────
# ENDPOINT 3 — JSON file upload (session transcript JSONs)
# Handles the JSON transcript files your pipeline already saves in sessions/
# ─────────────────────────────────────────────
@router.post("/from-json-file", response_model=NotesResponse)
async def notes_from_json_file(
    file: UploadFile = File(..., description="JSON transcript file from the session pipeline"),
    title: Optional[str] = Form(default="Untitled Video", description="Optional video title"),
    text_key: Optional[str] = Form(default="text", description="Key in JSON that holds the transcript text")
):
    """
    Generate notes from an uploaded JSON transcript file (like the ones saved in sessions/output/).

    The router tries to extract the transcript text using `text_key` (default: "text").
    If the JSON is a list of segments, it concatenates all segment texts automatically.

    React fetch example:
        const formData = new FormData();
        formData.append("file", jsonFile);
        formData.append("title", "My Video");
        formData.append("text_key", "text");   // adjust if your JSON uses a different key
        const res = await fetch("http://localhost:8000/notes/from-json-file", {
            method: "POST",
            body: formData
        });
    """
    raw_bytes = await file.read()

    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse JSON file: {str(e)}")

    # Handle list of segments (common Whisper output format)
    if isinstance(data, list):
        transcript = " ".join(
            seg.get(text_key, "") for seg in data if isinstance(seg, dict)
        ).strip()

    # Handle dict with a text key (e.g. {"text": "full transcript..."})
    elif isinstance(data, dict):
        transcript = data.get(text_key, "").strip()

        # Fallback: if text_key not found, try common alternatives
        if not transcript:
            for fallback_key in ["transcript", "content", "result"]:
                transcript = data.get(fallback_key, "").strip()
                if transcript:
                    break

    else:
        raise HTTPException(
            status_code=422,
            detail="Unsupported JSON structure. Expected a list of segments or a dict with a text field."
        )

    if not transcript:
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract transcript text. Tried key '{text_key}' and common fallbacks."
        )

    result = generate_notes(transcript=transcript, title=title)

    if result.status == "error":
        raise HTTPException(status_code=503, detail=result.error)

    return result


# ─────────────────────────────────────────────
# ENDPOINT 4 — Streaming notes generation
# ─────────────────────────────────────────────
@router.post("/stream")
async def notes_stream(payload: TranscriptInput):
    """
    Generate notes from transcript with streaming response.
    Returns text/plain stream for real-time token display.
    
    Request body:
        {
            "transcript": "<raw transcript text>",
            "title": "<optional video title>"
        }
    
    Returns:
        StreamingResponse with text chunks as they're generated.
    """
    if not payload.transcript.strip():
        raise HTTPException(status_code=422, detail="Transcript cannot be empty.")

    def stream_generator():
        for chunk in generate_notes_stream(
            transcript=payload.transcript,
            title=payload.title or "Untitled Video"
        ):
            yield chunk

    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )