"""
Long Video Transcription Models
"""
from pydantic import BaseModel
from typing import Optional, List, Literal


class LongVideoRequest(BaseModel):
    """Request to transcribe a long YouTube video."""
    url: str
    chunk_seconds: int = 300  # 5 minutes default
    model_name: Literal["tiny", "base", "small", "medium", "large-v2", "large-v3"] = "base"
    language: Optional[str] = "en"  # Auto-detect if None


class TranscriptSegment(BaseModel):
    """Individual transcript segment with timestamps."""
    start: float
    end: float
    text: str


class TranscriptionProgress(BaseModel):
    """Real-time progress information."""
    current_chunk: int
    total_chunks: int
    completed_chunks: int
    current_segment: Optional[str] = None
    progress_percentage: float


class LongVideoStatus(BaseModel):
    """Status response for long video transcription."""
    session_id: str
    status: Literal["checking_transcripts", "downloading", "chunking", "transcribing", "completed", "error"]
    video_url: str
    progress: Optional[TranscriptionProgress] = None
    error: Optional[str] = None
    total_segments: Optional[int] = None
    total_duration: Optional[float] = None


class TranscriptionResult(BaseModel):
    """Final transcription result."""
    session_id: str
    video_url: str
    total_segments: int
    total_duration: float
    segments: List[TranscriptSegment]
    full_text: str
    source: Literal["youtube_captions", "whisper"] = "whisper"
