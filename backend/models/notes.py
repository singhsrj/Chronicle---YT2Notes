"""
Pydantic models for the notes generation pipeline.
These define the input/output contracts for the notes router.
"""

from pydantic import BaseModel
from typing import Optional


class TranscriptInput(BaseModel):
    """
    Accepts transcript as plain text.
    Used when the frontend sends a JSON body with a 'transcript' field.
    """
    transcript: str
    title: Optional[str] = "Untitled Video"  # Optional video title for context


class NotesResponse(BaseModel):
    """
    Structured response returned to the frontend after notes generation.
    """
    title: str
    notes: str                  # Full markdown-formatted notes from the LLM
    model_used: str             # Which ollama model was used
    status: str                 # "success" or "error"
    error: Optional[str] = None # Error message if status == "error"