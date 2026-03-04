"""
Long Video Transcription Router
Handles long YouTube video transcription with chunking and checkpoints
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
from pathlib import Path

from backend.models.long_video import (
    LongVideoRequest,
    LongVideoStatus,
    TranscriptionResult,
    TranscriptionProgress
)
from backend.services.long_video_service import LongVideoTranscriptionService

router = APIRouter()
service = LongVideoTranscriptionService()


async def _run_transcription(
    session_id: str,
    url: str,
    chunk_seconds: int,
    model_name: str,
    language: str
):
    """Background task to run transcription pipeline."""
    try:
        await service.transcribe_video(
            session_id=session_id,
            url=url,
            chunk_seconds=chunk_seconds,
            model_name=model_name,
            language=language
        )
    except Exception as e:
        print(f"Transcription error for {session_id}: {str(e)}")


@router.post("/transcribe", response_model=dict)
async def start_transcription(
    request: LongVideoRequest,
    background_tasks: BackgroundTasks
):
    """
    Start long video transcription process.
    Returns session_id immediately; processing happens in background.
    
    - **url**: YouTube video URL
    - **chunk_seconds**: Size of each chunk in seconds (default: 300)
    - **model_name**: Whisper model to use (tiny, base, small, medium, large-v2, large-v3)
    - **language**: Language code for transcription (default: "en", None for auto-detect)
    """
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Initialize checkpoint
    service.update_status(
        session_id,
        "downloading",
        video_url=request.url,
        total_chunks=0,
        current_chunk=0,
        completed_chunks=0,
        progress_percentage=0.0
    )
    
    # Start background transcription
    background_tasks.add_task(
        _run_transcription,
        session_id,
        request.url,
        request.chunk_seconds,
        request.model_name,
        request.language
    )
    
    return {
        "session_id": session_id,
        "status": "downloading",
        "message": "Transcription started. Use /status/{session_id} to check progress."
    }


@router.get("/status/{session_id}", response_model=LongVideoStatus)
async def get_transcription_status(session_id: str):
    """
    Get current status of transcription process.
    
    Returns progress information including:
    - Current status (downloading, chunking, transcribing, completed, error)
    - Progress percentage
    - Current chunk being processed
    - Error message if failed
    """
    checkpoint = service.get_status(session_id)
    
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Session not found")
    
    progress = None
    if checkpoint.get("total_chunks", 0) > 0:
        progress = TranscriptionProgress(
            current_chunk=checkpoint.get("current_chunk", 0),
            total_chunks=checkpoint.get("total_chunks", 0),
            completed_chunks=checkpoint.get("completed_chunks", 0),
            progress_percentage=checkpoint.get("progress_percentage", 0.0)
        )
    
    return LongVideoStatus(
        session_id=session_id,
        status=checkpoint.get("status", "unknown"),
        video_url=checkpoint.get("video_url", ""),
        progress=progress,
        error=checkpoint.get("error"),
        total_segments=checkpoint.get("total_segments"),
        total_duration=checkpoint.get("total_duration")
    )


@router.get("/result/{session_id}", response_model=TranscriptionResult)
async def get_transcription_result(session_id: str):
    """
    Get final transcription result with all segments and timestamps.
    
    Only available when transcription is completed.
    Returns structured data with:
    - All transcript segments with timestamps
    - Full text transcript
    - Total duration
    """
    result = service.get_result(session_id)
    
    if not result:
        # Check if still processing
        checkpoint = service.get_status(session_id)
        if checkpoint:
            if checkpoint.get("status") == "error":
                raise HTTPException(
                    status_code=500,
                    detail=f"Transcription failed: {checkpoint.get('error', 'Unknown error')}"
                )
            elif checkpoint.get("status") != "completed":
                raise HTTPException(
                    status_code=202,
                    detail=f"Transcription still in progress: {checkpoint.get('status')}"
                )
        raise HTTPException(status_code=404, detail="Session not found")
    
    return TranscriptionResult(**result)


@router.get("/download/text/{session_id}")
async def download_text_transcript(session_id: str):
    """
    Download transcript as plain text file.
    """
    text_path, _ = service.get_output_paths(session_id)
    
    if not text_path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found or not completed")
    
    return FileResponse(
        path=text_path,
        media_type="text/plain",
        filename=f"{session_id}_transcript.txt"
    )


@router.get("/download/json/{session_id}")
async def download_json_transcript(session_id: str):
    """
    Download transcript as JSON file with timestamps.
    """
    _, json_path = service.get_output_paths(session_id)
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found or not completed")
    
    return FileResponse(
        path=json_path,
        media_type="application/json",
        filename=f"{session_id}_transcript.json"
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete session and all associated files.
    """
    session_dir = service.get_session_dir(session_id)
    
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Delete all files in session directory
    import shutil
    shutil.rmtree(session_dir)
    
    return {
        "session_id": session_id,
        "deleted": True,
        "message": "Session and all associated files deleted"
    }


@router.get("/sessions")
async def list_sessions():
    """
    List all transcription sessions.
    """
    sessions_dir = service.base_dir
    
    if not sessions_dir.exists():
        return {"sessions": []}
    
    sessions = []
    for session_dir in sessions_dir.iterdir():
        if session_dir.is_dir():
            session_id = session_dir.name
            checkpoint = service.get_status(session_id)
            if checkpoint:
                sessions.append({
                    "session_id": session_id,
                    "status": checkpoint.get("status", "unknown"),
                    "video_url": checkpoint.get("video_url", ""),
                    "progress_percentage": checkpoint.get("progress_percentage", 0.0)
                })
    
    return {"sessions": sessions}
