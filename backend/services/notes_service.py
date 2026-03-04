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
# NOTES STRUCTURE TEMPLATE
# This XML-like structure is injected into the system prompt so the LLM
# always follows the same skeleton — increases determinism significantly.
# ─────────────────────────────────────────────
NOTES_STRUCTURE = """
<notes_structure>
  <section name="Video Overview">
    One-paragraph summary of what the video covers and its main purpose.
  </section>

  <section name="Key Topics">
    A bullet list of the main topics/concepts discussed in order.
  </section>

  <section name="Detailed Notes">
    For each key topic:
    - ### Topic Name
    - Clear explanation of the concept
    - Sub-bullets for supporting details, examples, or nuances
    - **Bold** any critical terms or definitions
  </section>

  <section name="Important Definitions">
    A glossary-style list of technical terms mentioned:
    - **Term**: definition
  </section>

  <section name="Key Takeaways">
    3–7 concise bullet points summarising the most important lessons.
  </section>

  <section name="Action Items / Next Steps" optional="true">
    If the video suggests things to do or learn next, list them here.
    Omit this section entirely if not applicable.
  </section>
</notes_structure>
"""

# ─────────────────────────────────────────────
# SYSTEM PROMPT
# Combines role, task instructions, and the enforced structure template.
# ─────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are an expert note-taker specialising in creating comprehensive, \
well-structured study notes from video transcripts.

## Your Task
Analyse the provided transcript and produce detailed notes that strictly follow \
the structure template below. Do NOT invent information — only use content \
present in the transcript.

## Rules
1. Always output valid Markdown.
2. Follow the <notes_structure> sections in the exact order shown.
3. Use `###` for topic headings inside "Detailed Notes".
4. Bold (**) all key terms the first time they appear.
5. Keep language clear, concise, and accurate.
6. If a section is marked optional="true" and has no relevant content, skip it completely.
7. Do not add any preamble or closing remarks outside the structure.

## Output Structure
{NOTES_STRUCTURE}
"""


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