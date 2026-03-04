"""
Service layer for notes generation.
Handles all communication with the local Ollama instance.
"""

import requests
import json
from typing import Generator, List
from backend.models.notes import NotesResponse

# ─────────────────────────────────────────────
# OLLAMA CONFIG
# ─────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"  # Change to any model you have pulled locally

# ─────────────────────────────────────────────
# CHUNKING CONFIG FOR 32K CONTEXT WINDOW
# ─────────────────────────────────────────────
# The model (qwen2.5:7b) has a 32K token context window.
# We need to split long transcripts to fit within this limit.
#
# Token budget breakdown:
#   - System prompt: ~1K tokens
#   - Output (notes): ~8K tokens reserved
#   - Input (transcript): ~23K tokens available
#
# At approximately 4 characters per token:
#   23K tokens × 4 chars = ~92K chars max
#   Using 60K chars per chunk for safety margin
#
# When transcript is split into multiple chunks:
#   - First chunk: Gets overview + detailed notes, NO conclusion
#   - Middle chunks: Continues notes only, NO intro/conclusion
#   - Final chunk: Finishes notes + writes Key Takeaways & summary
# ─────────────────────────────────────────────
MAX_CHUNK_CHARS = 60000
CHUNK_OVERLAP_CHARS = 500  # Small overlap for context continuity

# ─────────────────────────────────────────────
# SYSTEM PROMPTS
# ─────────────────────────────────────────────

# SYSTEM_PROMPT_FULL: Used when the entire transcript fits in one chunk.
# This is the standard prompt with full structure: Overview → Topics → Notes → Definitions → Takeaways
SYSTEM_PROMPT_FULL = """You are an expert note-taker who creates comprehensive, well-structured study notes from video transcripts.

## Instructions
1. Output ONLY clean Markdown - NO XML tags, NO wrapper tags, NO <section> tags
2. Use proper Markdown headings (##, ###), bullet points, and formatting
3. Do NOT invent information - only use content from the transcript
4. Bold (**) key terms and definitions when first introduced
5. Keep language clear, concise, and educational

## CRITICAL: Math Formatting Rules
ALWAYS use dollar sign delimiters for ALL math:

### Inline math (within text):
Use single $: "The matrix $A$ has eigenvalue $\lambda = 5$"

### Display/block math (equations on their own line):
Use double $$:
$$A^T A = \\begin{bmatrix} 4 & 0 \\\\ 0 & 9 \\end{bmatrix}$$

### NEVER DO THIS (WRONG):
- [ \\lambda^2 - 5 = 0 ]  ← WRONG (square brackets)
- \\( x^2 \\)  ← WRONG (parentheses notation)
- Raw \\mathbf{A} without $ ← WRONG
- \\begin{bmatrix} without $$ ← WRONG

### ALWAYS DO THIS (CORRECT):
- $\\lambda^2 - 5 = 0$ or $$\\lambda^2 - 5 = 0$$
- $x^2$
- $\\mathbf{A}$
- $$\\begin{bmatrix} 1 & 2 \\\\ 3 & 4 \\end{bmatrix}$$

### For matrices, ALWAYS use:
$$
\\begin{bmatrix}
a & b \\\\
c & d
\\end{bmatrix}
$$

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

Remember: Output clean, readable Markdown only. No XML. No wrapper tags. ALL math must be wrapped in $ or $$. Start directly with "## Video Overview"."""


# SYSTEM_PROMPT_FIRST_CHUNK: Used for the FIRST part of a multi-chunk transcript.
# Writes: Video Overview + Key Topics + Detailed Notes (partial)
# Does NOT write: Definitions, Key Takeaways, Conclusion (saved for final chunk)
SYSTEM_PROMPT_FIRST_CHUNK = """You are an expert note-taker creating notes from a LONG video transcript that has been split into multiple parts.

THIS IS PART 1 OF THE TRANSCRIPT. More parts will follow.

## Instructions
1. Output ONLY clean Markdown - NO XML tags, NO wrapper tags
2. Use proper Markdown headings (##, ###), bullet points, and formatting
3. Do NOT invent information - only use content from the transcript
4. Bold (**) key terms and definitions when first introduced
5. Keep language clear, concise, and educational

## CRITICAL: DO NOT write any conclusion, summary, or "Key Takeaways" section!
Since this is only part of the transcript, do NOT:
- Write a conclusion or summary
- Write "Key Takeaways" or "Important Points" section
- Wrap up as if the content is finished
- Say "in conclusion" or similar phrases

Just document the content from this portion and STOP. The summary will come at the end.

## CRITICAL: Math Formatting Rules
ALWAYS use dollar sign delimiters for ALL math:
- Inline: $x^2$ or $\\lambda$
- Block: $$\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}$$

## Output Format for this chunk:

## Video Overview
Brief overview of what this video appears to cover (will be refined later).

## Detailed Notes

### [Topic Name]
- Clear explanation of the concept
- Supporting details and examples
- **Bold** critical terms

(Continue documenting topics as they appear - DO NOT CONCLUDE)

Start directly with "## Video Overview"."""


# SYSTEM_PROMPT_MIDDLE_CHUNK: Used for MIDDLE parts of a multi-chunk transcript (not first, not last).
# Writes: Continued Detailed Notes only (### Topic headings)
# Does NOT write: Overview (already done), Definitions, Key Takeaways, Conclusion (saved for final)
SYSTEM_PROMPT_MIDDLE_CHUNK = """You are an expert note-taker continuing to document a LONG video transcript.

THIS IS A CONTINUATION. You are receiving the next part of the transcript.

## Instructions
1. Output ONLY clean Markdown - NO XML tags, NO wrapper tags
2. Continue documenting topics using ### headings
3. Do NOT invent information - only use content from the transcript
4. Bold (**) key terms and definitions when first introduced
5. Keep language clear, concise, and educational

## CRITICAL: DO NOT write any conclusion, summary, or "Key Takeaways" section!
Since this is a middle portion of the transcript:
- Do NOT write any introduction or overview (that was done in part 1)
- Do NOT write a conclusion or summary
- Do NOT write "Key Takeaways" or wrap up
- Just continue documenting the content

## CRITICAL: Math Formatting Rules
ALWAYS use dollar sign delimiters for ALL math:
- Inline: $x^2$ or $\\lambda$
- Block: $$\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}$$

## Output Format for this chunk (continue directly):

### [Topic Name]
- Clear explanation of the concept
- Supporting details and examples

(Continue documenting - DO NOT CONCLUDE)

Start directly with ### and continue the notes."""


# SYSTEM_PROMPT_FINAL_CHUNK: Used for the LAST part of a multi-chunk transcript.
# Writes: Remaining Detailed Notes + Important Definitions + Key Takeaways + Next Steps
# This is where all the summary/conclusion content goes for multi-chunk transcripts.
SYSTEM_PROMPT_FINAL_CHUNK = """You are an expert note-taker completing the documentation of a LONG video transcript.

THIS IS THE FINAL PART of the transcript. Now you should conclude the notes.

## Instructions
1. Output ONLY clean Markdown - NO XML tags, NO wrapper tags
2. First, continue documenting any remaining topics from this final portion
3. Then, provide the conclusion sections based on ALL content you've seen
4. Bold (**) key terms and definitions when first introduced
5. Keep language clear, concise, and educational

## CRITICAL: Math Formatting Rules
ALWAYS use dollar sign delimiters for ALL math:
- Inline: $x^2$ or $\\lambda$
- Block: $$\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}$$

## Output Format for this FINAL chunk:

### [Continue any remaining topics]
- Document remaining content from this portion

## Important Definitions
- **Term**: definition (compile all key terms from the ENTIRE video)

## Key Takeaways
- 3-7 bullet points summarizing the most important lessons from the ENTIRE video
- Focus on actionable insights

## Next Steps (optional)
- Only include if the video suggests things to do or learn next

Start directly with ### to continue any remaining topics, then conclude with the summary sections."""


def split_transcript_into_chunks(transcript: str) -> List[str]:
    """
    Split a long transcript into chunks that fit within the model's context window.
    
    Args:
        transcript: The full transcript text
        
    Returns:
        List of transcript chunks
    """
    if len(transcript) <= MAX_CHUNK_CHARS:
        return [transcript]
    
    chunks = []
    start = 0
    
    while start < len(transcript):
        end = start + MAX_CHUNK_CHARS
        
        if end >= len(transcript):
            # Last chunk
            chunks.append(transcript[start:])
            break
        
        # Try to break at a sentence boundary (., !, ?) or newline
        # Look backwards from the end to find a good break point
        break_point = end
        search_start = max(start + MAX_CHUNK_CHARS - 2000, start)  # Search last 2000 chars
        
        for i in range(end, search_start, -1):
            if transcript[i] in '.!?\n':
                break_point = i + 1
                break
        
        chunks.append(transcript[start:break_point])
        # Start next chunk with overlap for context continuity
        start = break_point - CHUNK_OVERLAP_CHARS if break_point > CHUNK_OVERLAP_CHARS else break_point
    
    return chunks


def get_system_prompt_for_chunk(chunk_index: int, total_chunks: int) -> str:
    """
    Get the appropriate system prompt based on chunk position.
    
    Args:
        chunk_index: 0-based index of current chunk
        total_chunks: Total number of chunks
        
    Returns:
        Appropriate system prompt string
    """
    if total_chunks == 1:
        return SYSTEM_PROMPT_FULL
    
    if chunk_index == 0:
        return SYSTEM_PROMPT_FIRST_CHUNK
    elif chunk_index == total_chunks - 1:
        return SYSTEM_PROMPT_FINAL_CHUNK
    else:
        return SYSTEM_PROMPT_MIDDLE_CHUNK


def generate_notes(transcript: str, title: str = "Untitled Video") -> NotesResponse:
    """
    Sends the transcript to the local Ollama model and returns structured notes.
    Automatically splits long transcripts into chunks that fit within the context window.

    Args:
        transcript: Raw transcript text (plain text or JSON-extracted text).
        title:      Optional video title for context.

    Returns:
        NotesResponse with markdown notes or an error message.
    """
    # Split transcript into chunks if needed
    chunks = split_transcript_into_chunks(transcript)
    total_chunks = len(chunks)
    
    print(f"[Notes] Transcript length: {len(transcript)} chars, split into {total_chunks} chunk(s)")
    
    all_notes = []
    
    for i, chunk in enumerate(chunks):
        system_prompt = get_system_prompt_for_chunk(i, total_chunks)
        
        # Build the user prompt
        if total_chunks == 1:
            user_prompt = f"Video Title: {title}\n\n---\n\nTranscript:\n{chunk}"
        elif i == 0:
            user_prompt = f"Video Title: {title}\n\n---\n\nTranscript (Part 1 of {total_chunks}):\n{chunk}"
        else:
            user_prompt = f"Continuing transcript (Part {i + 1} of {total_chunks}):\n{chunk}"

        payload = {
            "model": OLLAMA_MODEL,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            }
        }

        try:
            print(f"[Notes] Processing chunk {i + 1}/{total_chunks}...")
            response = requests.post(
                OLLAMA_URL,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=300
            )

            if response.status_code == 200:
                result = response.json()
                notes_text = result.get("response", "").strip()
                all_notes.append(notes_text)
            else:
                return NotesResponse(
                    title=title,
                    notes="",
                    model_used=OLLAMA_MODEL,
                    status="error",
                    error=f"Ollama returned status {response.status_code} on chunk {i + 1}: {response.text}"
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
                error=f"Ollama request timed out on chunk {i + 1}."
            )
        except Exception as e:
            return NotesResponse(
                title=title,
                notes="",
                model_used=OLLAMA_MODEL,
                status="error",
                error=f"Unexpected error on chunk {i + 1}: {str(e)}"
            )
    
    # Combine all notes
    combined_notes = "\n\n".join(all_notes)
    
    return NotesResponse(
        title=title,
        notes=combined_notes,
        model_used=OLLAMA_MODEL,
        status="success"
    )


def generate_notes_stream(transcript: str, title: str = "Untitled Video") -> Generator[str, None, None]:
    """
    Generator that streams notes from Ollama token by token.
    Automatically splits long transcripts into chunks that fit within the context window.
    
    Yields:
        str: Each chunk of text as it's generated.
    """
    # Split transcript into chunks if needed
    chunks = split_transcript_into_chunks(transcript)
    total_chunks = len(chunks)
    
    print(f"[Notes Stream] Transcript length: {len(transcript)} chars, split into {total_chunks} chunk(s)")
    
    for i, chunk in enumerate(chunks):
        system_prompt = get_system_prompt_for_chunk(i, total_chunks)
        
        # Build the user prompt
        if total_chunks == 1:
            user_prompt = f"Video Title: {title}\n\n---\n\nTranscript:\n{chunk}"
        elif i == 0:
            user_prompt = f"Video Title: {title}\n\n---\n\nTranscript (Part 1 of {total_chunks}):\n{chunk}"
        else:
            user_prompt = f"Continuing transcript (Part {i + 1} of {total_chunks}):\n{chunk}"

        payload = {
            "model": OLLAMA_MODEL,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": True,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            }
        }

        # Add separator between chunks (except first)
        if i > 0:
            yield "\n\n"
            print(f"[Notes Stream] Processing chunk {i + 1}/{total_chunks}...")

        try:
            with requests.post(
                OLLAMA_URL,
                headers={"Content-Type": "application/json"},
                json=payload,
                stream=True,
                timeout=300
            ) as response:
                if response.status_code != 200:
                    yield f"[ERROR] Ollama returned status {response.status_code} on chunk {i + 1}"
                    return

                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            text_chunk = data.get("response", "")
                            if text_chunk:
                                yield text_chunk
                        except json.JSONDecodeError:
                            continue

        except requests.exceptions.ConnectionError:
            yield "[ERROR] Could not connect to Ollama. Is it running?"
            return
        except requests.exceptions.Timeout:
            yield f"[ERROR] Ollama request timed out on chunk {i + 1}."
            return
        except Exception as e:
            yield f"[ERROR] {str(e)}"
            return