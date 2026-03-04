"""
Service layer for notes generation.
Handles all communication with the local Ollama instance.
"""

import requests
from backend.models.notes import NotesResponse

# ─────────────────────────────────────────────
# OLLAMA CONFIG
# ─────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"  # Change to any model you have pulled locally

# ─────────────────────────────────────────────
# SYSTEM PROMPT
# Clean markdown output without XML tags
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert note-taker who creates comprehensive, well-structured study notes from video transcripts.

## Instructions
1. Output ONLY clean Markdown - NO XML tags, NO wrapper tags, NO <section> tags
2. Use proper Markdown headings (##, ###), bullet points, and formatting
3. Do NOT invent information - only use content from the transcript
4. Bold (**) key terms and definitions when first introduced
5. Use LaTeX math notation with $ for inline and $$ for block equations when needed
6. Keep language clear, concise, and educational

## Output Format (use these exact headings):

## Video Overview
Write a clear paragraph summarizing what the video covers and its main purpose.

## Key Topics
- List the main topics/concepts discussed
- In order of appearance

## Detailed Notes

### [Topic Name]
- Clear explanation of the concept
- Supporting details and examples
- **Bold** critical terms

(Repeat for each major topic)

## Important Definitions
- **Term**: definition
- **Another term**: its definition

## Key Takeaways
- 3-7 bullet points summarizing the most important lessons
- Focus on actionable insights

## Next Steps (optional)
- Only include if the video suggests things to do or learn next
- Omit this section entirely if not applicable

Remember: Output clean, readable Markdown only. No XML. No wrapper tags. Start directly with "## Video Overview"."""


def generate_notes(transcript: str, title: str = "Untitled Video") -> NotesResponse:
    """
    Sends the transcript to the local Ollama model and returns structured notes.

    Args:
        transcript: Raw transcript text (plain text or JSON-extracted text).
        title:      Optional video title for context.

    Returns:
        NotesResponse with markdown notes or an error message.
    """

    # Build the user prompt — include title if provided
    user_prompt = f"Video Title: {title}\n\n---\n\nTranscript:\n{transcript}"

    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": user_prompt,
        "stream": False,  # ← Set to True when integrating with React streaming frontend
        "options": {
            "temperature": 0.3,   # Lower = more deterministic output
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=300  # Generous timeout for long transcripts
        )

        if response.status_code == 200:
            result = response.json()
            notes_text = result.get("response", "").strip()

            return NotesResponse(
                title=title,
                notes=notes_text,
                model_used=OLLAMA_MODEL,
                status="success"
            )
        else:
            return NotesResponse(
                title=title,
                notes="",
                model_used=OLLAMA_MODEL,
                status="error",
                error=f"Ollama returned status {response.status_code}: {response.text}"
            )

    except requests.exceptions.ConnectionError:
        return NotesResponse(
            title=title,
            notes="",
            model_used=OLLAMA_MODEL,
            status="error",
            error="Could not connect to Ollama. Is it running? Try: ollama serve"
        )
    except requests.exceptions.Timeout:
        return NotesResponse(
            title=title,
            notes="",
            model_used=OLLAMA_MODEL,
            status="error",
            error="Ollama request timed out. The transcript may be too long."
        )
    except Exception as e:
        return NotesResponse(
            title=title,
            notes="",
            model_used=OLLAMA_MODEL,
            status="error",
            error=f"Unexpected error: {str(e)}"
        )


def generate_notes_stream(transcript: str, title: str = "Untitled Video"):
    """
    Generator that streams notes from Ollama token by token.
    
    Yields:
        str: Each chunk of text as it's generated.
    """
    user_prompt = f"Video Title: {title}\n\n---\n\nTranscript:\n{transcript}"

    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": user_prompt,
        "stream": True,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        }
    }

    try:
        with requests.post(
            OLLAMA_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            stream=True,
            timeout=300
        ) as response:
            if response.status_code != 200:
                yield f"[ERROR] Ollama returned status {response.status_code}"
                return

            for line in response.iter_lines():
                if line:
                    try:
                        import json
                        data = json.loads(line)
                        chunk = data.get("response", "")
                        if chunk:
                            yield chunk
                    except json.JSONDecodeError:
                        continue

    except requests.exceptions.ConnectionError:
        yield "[ERROR] Could not connect to Ollama. Is it running?"
    except requests.exceptions.Timeout:
        yield "[ERROR] Ollama request timed out."
    except Exception as e:
        yield f"[ERROR] {str(e)}"