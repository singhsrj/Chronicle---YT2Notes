"""
Long Video Transcription Service
Handles chunked transcription of long YouTube videos using faster-whisper
"""
import os
import json
import subprocess
import re
from pathlib import Path
from faster_whisper import WhisperModel
from typing import Optional
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi


class LongVideoTranscriptionService:
    """Service for transcribing long YouTube videos with checkpoint management."""
    
    def __init__(self, base_dir: str = "sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
    
    def get_session_dir(self, session_id: str) -> Path:
        """Get or create session directory."""
        session_dir = self.base_dir / session_id
        session_dir.mkdir(exist_ok=True)
        return session_dir
    
    def get_checkpoint_path(self, session_id: str) -> Path:
        """Get checkpoint file path."""
        return self.get_session_dir(session_id) / "checkpoint.json"
    
    def get_output_paths(self, session_id: str) -> tuple[Path, Path]:
        """Get output file paths (text, json) in separate output directory."""
        session_dir = self.get_session_dir(session_id)
        output_dir = session_dir / "output"
        output_dir.mkdir(exist_ok=True)
        return (
            output_dir / f"{session_id}_transcript.txt",
            output_dir / f"{session_id}_transcript.json"
        )
    
    def load_checkpoint(self, session_id: str) -> Optional[dict]:
        """Load checkpoint if exists."""
        checkpoint_path = self.get_checkpoint_path(session_id)
        if checkpoint_path.exists():
            with open(checkpoint_path, "r") as f:
                return json.load(f)
        return None
    
    def save_checkpoint(self, session_id: str, data: dict):
        """Save checkpoint data."""
        checkpoint_path = self.get_checkpoint_path(session_id)
        with open(checkpoint_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def update_status(self, session_id: str, status: str, **kwargs):
        """Update session status in checkpoint."""
        checkpoint = self.load_checkpoint(session_id) or {}
        checkpoint["status"] = status
        checkpoint.update(kwargs)
        self.save_checkpoint(session_id, checkpoint)
    
    def extract_video_id(self, url: str) -> str:
        """Extract YouTube video ID from URL."""
        # If it looks like a plain video ID already (11 chars, alphanumeric + - _)
        if re.match(r'^[A-Za-z0-9_-]{11}$', url):
            return url
        
        parsed = urlparse(url)
        
        # youtu.be/VIDEO_ID
        if parsed.netloc in ('youtu.be', 'www.youtu.be'):
            return parsed.path.lstrip('/')
        
        # youtube.com variants
        if 'youtube.com' in parsed.netloc:
            # /watch?v=VIDEO_ID
            qs = parse_qs(parsed.query)
            if 'v' in qs:
                return qs['v'][0]
            
            # /embed/VIDEO_ID or /shorts/VIDEO_ID
            path_parts = parsed.path.strip('/').split('/')
            if path_parts[0] in ('embed', 'shorts', 'v') and len(path_parts) > 1:
                return path_parts[1]
        
        raise ValueError(f"Could not extract video ID from: {url}")
    
    async def check_youtube_transcript(self, session_id: str, url: str) -> Optional[dict]:
        """
        Check if YouTube has transcripts available for the video.
        Returns transcript data if available, None otherwise.
        """
        try:
            video_id = self.extract_video_id(url)
            self.update_status(session_id, "checking_transcripts", video_url=url)
            
            print(f"Checking for YouTube transcripts for video: {video_id}")
            
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            
            # Try en variants first, then fall back to any available language
            try:
                transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"])
                print(f"Found English transcript")
            except Exception:
                # Grab the first available transcript (any language)
                transcript = next(iter(transcript_list))
                print(f"Found transcript in: {transcript.language} ({transcript.language_code})")
            
            # Fetch the transcript
            fetched = transcript.fetch()
            
            # Convert to our format with timestamps
            segments = []
            for entry in fetched:
                segments.append({
                    "start": entry.start,
                    "end": entry.start + entry.duration,
                    "text": entry.text.strip()
                })
            
            full_text = " ".join([seg["text"] for seg in segments])
            
            return {
                "video_id": video_id,
                "segments": segments,
                "full_text": full_text,
                "source": "youtube_captions"
            }
            
        except Exception as e:
            print(f"No YouTube transcripts available: {str(e)}")
            return None
    
    async def save_transcript_result(self, session_id: str, url: str, segments: list, full_text: str, source: str = "whisper"):
        """Save transcript result in standard format."""
        text_path, json_path = self.get_output_paths(session_id)
        
        # Save text file
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        
        # Save JSON file
        final_data = {
            "session_id": session_id,
            "video_url": url,
            "total_segments": len(segments),
            "total_duration": segments[-1]["end"] if segments else 0,
            "segments": segments,
            "full_text": full_text,
            "source": source
        }
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        # Update final status
        self.update_status(
            session_id,
            "completed",
            total_segments=len(segments),
            total_duration=segments[-1]["end"] if segments else 0,
            progress_percentage=100.0,
            source=source
        )
        
        return final_data
    
    async def download_audio(self, session_id: str, url: str) -> Path:
        """Download audio from YouTube."""
        session_dir = self.get_session_dir(session_id)
        output_path = session_dir / "full_audio.wav"
        
        self.update_status(session_id, "downloading", video_url=url)
        
        download_cmd = [
            "yt-dlp",
            "-f", "bestaudio",
            "--extract-audio",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", str(output_path),
            url
        ]
        
        result = subprocess.run(download_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Download failed: {result.stderr}")
        
        return output_path
    
    async def convert_audio(self, session_id: str, input_path: Path) -> Path:
        """Convert audio to 16kHz mono WAV."""
        session_dir = self.get_session_dir(session_id)
        output_path = session_dir / "processed.wav"
        
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-ar", "16000",
            "-ac", "1",
            str(output_path)
        ], capture_output=True)
        
        # Remove original
        input_path.unlink()
        
        return output_path
    
    async def split_audio(
        self, 
        session_id: str, 
        audio_path: Path, 
        chunk_seconds: int
    ) -> Path:
        """Split audio into chunks."""
        session_dir = self.get_session_dir(session_id)
        chunk_dir = session_dir / "chunks"
        chunk_dir.mkdir(exist_ok=True)
        
        self.update_status(session_id, "chunking")
        
        subprocess.run([
            "ffmpeg",
            "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", str(chunk_seconds),
            "-c", "copy",
            str(chunk_dir / "chunk_%03d.wav")
        ], capture_output=True)
        
        # Remove processed audio
        audio_path.unlink()
        
        return chunk_dir
    
    async def transcribe_chunks(
        self,
        session_id: str,
        chunk_dir: Path,
        model_name: str,
        chunk_seconds: int,
        language: Optional[str] = "en"
    ):
        """Transcribe all chunks with checkpoint support."""
        self.update_status(session_id, "transcribing")
        
        # Load model
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        
        # Get checkpoint
        checkpoint = self.load_checkpoint(session_id) or {}
        start_index = checkpoint.get("last_completed_chunk", -1) + 1
        all_segments = checkpoint.get("segments", [])
        
        # Get chunks
        chunks = sorted(chunk_dir.glob("chunk_*.wav"))
        total_chunks = len(chunks)
        
        text_path, json_path = self.get_output_paths(session_id)
        
        # Process each chunk
        for i, chunk_path in enumerate(chunks):
            if i < start_index:
                continue
            
            chunk_offset = i * chunk_seconds
            
            # Update progress
            self.update_status(
                session_id,
                "transcribing",
                current_chunk=i + 1,
                total_chunks=total_chunks,
                completed_chunks=i,
                progress_percentage=round((i / total_chunks) * 100, 2)
            )
            
            # Transcribe
            segments, info = model.transcribe(
                str(chunk_path),
                beam_size=5,
                language=language,
                condition_on_previous_text=True
            )
            
            # Process segments
            chunk_text = []
            for segment in segments:
                global_start = chunk_offset + segment.start
                global_end = chunk_offset + segment.end
                
                segment_data = {
                    "start": global_start,
                    "end": global_end,
                    "text": segment.text.strip()
                }
                
                all_segments.append(segment_data)
                chunk_text.append(segment.text.strip())
            
            # Append to text file
            full_chunk_text = " ".join(chunk_text)
            with open(text_path, "a", encoding="utf-8") as f:
                f.write(full_chunk_text + "\n\n")
            
            # Save checkpoint
            checkpoint_data = {
                "status": "transcribing",
                "last_completed_chunk": i,
                "total_chunks": total_chunks,
                "segments": all_segments,
                "video_url": checkpoint.get("video_url", ""),
                "current_chunk": i + 1,
                "completed_chunks": i + 1,
                "progress_percentage": round(((i + 1) / total_chunks) * 100, 2)
            }
            self.save_checkpoint(session_id, checkpoint_data)
            
            # Delete chunk
            chunk_path.unlink()
        
        # Save final JSON
        full_text = " ".join([seg["text"] for seg in all_segments])
        final_data = {
            "session_id": session_id,
            "video_url": checkpoint.get("video_url", ""),
            "total_segments": len(all_segments),
            "total_duration": all_segments[-1]["end"] if all_segments else 0,
            "segments": all_segments,
            "full_text": full_text,
            "source": "whisper"
        }
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        # Update final status
        self.update_status(
            session_id,
            "completed",
            total_segments=len(all_segments),
            total_duration=all_segments[-1]["end"] if all_segments else 0,
            completed_chunks=total_chunks,
            total_chunks=total_chunks,
            progress_percentage=100.0,
            source="whisper"
        )
        
        # Cleanup chunk directory
        if chunk_dir.exists():
            chunk_dir.rmdir()
        
        return final_data
    
    async def transcribe_video(
        self,
        session_id: str,
        url: str,
        chunk_seconds: int = 300,
        model_name: str = "base",
        language: Optional[str] = "en"
    ):
        """
        Complete transcription pipeline.
        First checks for YouTube captions, falls back to Whisper if unavailable.
        """
        try:
            # Step 0: Check for YouTube transcripts first (fast path)
            print(f"[Session {session_id}] Checking for existing YouTube transcripts...")
            yt_transcript = await self.check_youtube_transcript(session_id, url)
            
            if yt_transcript:
                print(f"[Session {session_id}] ✅ Using YouTube captions (no audio processing needed)")
                result = await self.save_transcript_result(
                    session_id=session_id,
                    url=url,
                    segments=yt_transcript["segments"],
                    full_text=yt_transcript["full_text"],
                    source="youtube_captions"
                )
                return result
            
            # No YouTube transcripts available, proceed with Whisper pipeline
            print(f"[Session {session_id}] No YouTube captions found, using Whisper transcription...")
            
            # Step 1: Download
            audio_path = await self.download_audio(session_id, url)
            
            # Step 2: Convert
            processed_path = await self.convert_audio(session_id, audio_path)
            
            # Step 3: Split
            chunk_dir = await self.split_audio(session_id, processed_path, chunk_seconds)
            
            # Step 4: Transcribe
            result = await self.transcribe_chunks(
                session_id, chunk_dir, model_name, chunk_seconds, language
            )
            
            return result
            
        except Exception as e:
            self.update_status(session_id, "error", error=str(e))
            raise
    
    def get_status(self, session_id: str) -> Optional[dict]:
        """Get current status of transcription."""
        return self.load_checkpoint(session_id)
    
    def get_result(self, session_id: str) -> Optional[dict]:
        """Get final transcription result."""
        _, json_path = self.get_output_paths(session_id)
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
