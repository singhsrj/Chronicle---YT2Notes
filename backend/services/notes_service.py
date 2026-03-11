"""
Service layer for notes generation.
Handles all communication with the local Ollama instance using LangChain for structured interactions.
"""

import os
from typing import Generator, List, AsyncGenerator
from backend.models.notes import NotesResponse

# LangChain imports for structured LLM interactions
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage

# ─────────────────────────────────────────────
# OLLAMA CONFIG (configurable via environment variables)
# ─────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2:7b")

# ─────────────────────────────────────────────
# LLM CONFIGURATION
# ─────────────────────────────────────────────
# Initialize the LangChain ChatOllama client with optimal settings
llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.3,
    top_p=0.9,
    repeat_penalty=1.1,
)

# For streaming responses
llm_streaming = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.3,
    top_p=0.9,
    repeat_penalty=1.1,
)

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
SYSTEM_PROMPT_FULL = """You are an expert note-taker who creates comprehensive, well-structured study notes from video transcripts in English Only.

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
$$A^T A = \\begin{{bmatrix}} 4 & 0 \\\\ 0 & 9 \\end{{bmatrix}}$$

### NEVER DO THIS (WRONG):
- [ \\lambda^2 - 5 = 0 ]  ← WRONG (square brackets)
- \\( x^2 \\)  ← WRONG (parentheses notation)
- Raw \\mathbf{{A}} without $ ← WRONG
- \\begin{{bmatrix}} without $$ ← WRONG

### ALWAYS DO THIS (CORRECT):
- $\\lambda^2 - 5 = 0$ or $$\\lambda^2 - 5 = 0$$
- $x^2$
- $\\mathbf{{A}}$
- $$\\begin{{bmatrix}} 1 & 2 \\\\ 3 & 4 \\end{{bmatrix}}$$

### For matrices, ALWAYS use:
$$
\\begin{{bmatrix}}
a & b \\\\
c & d
\\end{{bmatrix}}
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
SYSTEM_PROMPT_FIRST_CHUNK = """You are an expert note-taker creating notes from a LONG video transcript that has been split into multiple parts in English Only.

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
- Block: $$\\begin{{bmatrix}} a & b \\\\ c & d \\end{{bmatrix}}$$

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
SYSTEM_PROMPT_MIDDLE_CHUNK = """You are an expert note-taker continuing to document a LONG video transcript in English Only.

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
- Block: $$\\begin{{bmatrix}} a & b \\\\ c & d \\end{{bmatrix}}$$

## Output Format for this chunk (continue directly):

### [Topic Name]
- Clear explanation of the concept
- Supporting details and examples

(Continue documenting - DO NOT CONCLUDE)

Start directly with ### and continue the notes."""


# SYSTEM_PROMPT_FINAL_CHUNK: Used for the LAST part of a multi-chunk transcript.
# Writes: Remaining Detailed Notes + Important Definitions + Key Takeaways + Next Steps
# This is where all the summary/conclusion content goes for multi-chunk transcripts.
SYSTEM_PROMPT_FINAL_CHUNK = """You are an expert note-taker completing the documentation of a LONG video transcript in English Only.

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
- Block: $$\\begin{{bmatrix}} a & b \\\\ c & d \\end{{bmatrix}}$$

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


# ─────────────────────────────────────────────
# LANGCHAIN PROMPT TEMPLATES
# ─────────────────────────────────────────────
# Structured prompt templates using LangChain's ChatPromptTemplate
# These provide a well-rounded, consistent interface for LLM interactions

def create_notes_prompt_template(system_prompt: str) -> ChatPromptTemplate:
    """
    Factory function to create a ChatPromptTemplate with the given system prompt.
    
    Args:
        system_prompt: The system prompt defining the LLM's behavior
        
    Returns:
        ChatPromptTemplate configured for notes generation
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{user_input}")
    ])


# Pre-built prompt templates for each chunk type
PROMPT_TEMPLATE_FULL = create_notes_prompt_template(SYSTEM_PROMPT_FULL)
PROMPT_TEMPLATE_FIRST_CHUNK = create_notes_prompt_template(SYSTEM_PROMPT_FIRST_CHUNK)
PROMPT_TEMPLATE_MIDDLE_CHUNK = create_notes_prompt_template(SYSTEM_PROMPT_MIDDLE_CHUNK)
PROMPT_TEMPLATE_FINAL_CHUNK = create_notes_prompt_template(SYSTEM_PROMPT_FINAL_CHUNK)


# ─────────────────────────────────────────────
# LANGCHAIN CHAINS (LCEL - LangChain Expression Language)
# ─────────────────────────────────────────────
# Chains compose prompt templates with LLM and output parsers
# Using the | operator for clean, functional composition

# Output parser to extract string content from LLM response
output_parser = StrOutputParser()

# Pre-built chains for each chunk type (prompt | llm | parser)
CHAIN_FULL = PROMPT_TEMPLATE_FULL | llm | output_parser
CHAIN_FIRST_CHUNK = PROMPT_TEMPLATE_FIRST_CHUNK | llm | output_parser
CHAIN_MIDDLE_CHUNK = PROMPT_TEMPLATE_MIDDLE_CHUNK | llm | output_parser
CHAIN_FINAL_CHUNK = PROMPT_TEMPLATE_FINAL_CHUNK | llm | output_parser

# Streaming chains (same structure, but invoke differently)
CHAIN_FULL_STREAM = PROMPT_TEMPLATE_FULL | llm_streaming
CHAIN_FIRST_CHUNK_STREAM = PROMPT_TEMPLATE_FIRST_CHUNK | llm_streaming
CHAIN_MIDDLE_CHUNK_STREAM = PROMPT_TEMPLATE_MIDDLE_CHUNK | llm_streaming
CHAIN_FINAL_CHUNK_STREAM = PROMPT_TEMPLATE_FINAL_CHUNK | llm_streaming


def get_chain_for_chunk(chunk_index: int, total_chunks: int, streaming: bool = False):
    """
    Get the appropriate chain based on chunk position.
    
    Args:
        chunk_index: 0-based index of current chunk
        total_chunks: Total number of chunks
        streaming: Whether to return streaming chain
        
    Returns:
        Appropriate LangChain chain
    """
    if total_chunks == 1:
        return CHAIN_FULL_STREAM if streaming else CHAIN_FULL
    
    if chunk_index == 0:
        return CHAIN_FIRST_CHUNK_STREAM if streaming else CHAIN_FIRST_CHUNK
    elif chunk_index == total_chunks - 1:
        return CHAIN_FINAL_CHUNK_STREAM if streaming else CHAIN_FINAL_CHUNK
    else:
        return CHAIN_MIDDLE_CHUNK_STREAM if streaming else CHAIN_MIDDLE_CHUNK


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
    Sends the transcript to the local Ollama model using LangChain and returns structured notes.
    Automatically splits long transcripts into chunks that fit within the context window.

    Uses LangChain's LCEL (LangChain Expression Language) for clean, composable chains:
    - ChatPromptTemplate for structured prompts
    - ChatOllama for LLM interaction
    - StrOutputParser for output parsing

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
        # Get the appropriate chain for this chunk position
        chain = get_chain_for_chunk(i, total_chunks, streaming=False)
        
        # Build the user input for the prompt template
        if total_chunks == 1:
            user_input = f"Video Title: {title}\n\n---\n\nTranscript:\n{chunk}"
        elif i == 0:
            user_input = f"Video Title: {title}\n\n---\n\nTranscript (Part 1 of {total_chunks}):\n{chunk}"
        else:
            user_input = f"Continuing transcript (Part {i + 1} of {total_chunks}):\n{chunk}"

        try:
            print(f"[Notes] Processing chunk {i + 1}/{total_chunks} via LangChain...")
            
            # Invoke the chain with structured input
            # The chain handles: prompt formatting -> LLM call -> output parsing
            notes_text = chain.invoke({"user_input": user_input})
            all_notes.append(notes_text.strip())

        except ConnectionError:
            return NotesResponse(
                title=title,
                notes="",
                model_used=OLLAMA_MODEL,
                status="error",
                error="Could not connect to Ollama. Is it running? Try: ollama serve"
            )
        except TimeoutError:
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
    Generator that streams notes from Ollama using LangChain's streaming interface.
    Automatically splits long transcripts into chunks that fit within the context window.
    
    Uses LangChain's streaming capabilities for real-time token generation:
    - ChatPromptTemplate for structured prompts
    - ChatOllama with streaming enabled
    - Yields tokens as they are generated
    
    Yields:
        str: Each chunk of text as it's generated.
    """
    # Split transcript into chunks if needed
    chunks = split_transcript_into_chunks(transcript)
    total_chunks = len(chunks)
    
    print(f"[Notes Stream] Transcript length: {len(transcript)} chars, split into {total_chunks} chunk(s)")
    
    for i, chunk in enumerate(chunks):
        # Get the appropriate streaming chain for this chunk position
        chain = get_chain_for_chunk(i, total_chunks, streaming=True)
        
        # Build the user input for the prompt template
        if total_chunks == 1:
            user_input = f"Video Title: {title}\n\n---\n\nTranscript:\n{chunk}"
        elif i == 0:
            user_input = f"Video Title: {title}\n\n---\n\nTranscript (Part 1 of {total_chunks}):\n{chunk}"
        else:
            user_input = f"Continuing transcript (Part {i + 1} of {total_chunks}):\n{chunk}"

        # Add separator between chunks (except first)
        if i > 0:
            yield "\n\n"
            print(f"[Notes Stream] Processing chunk {i + 1}/{total_chunks} via LangChain...")

        try:
            # Stream tokens from the chain
            # LangChain's .stream() method yields AIMessageChunks
            for message_chunk in chain.stream({"user_input": user_input}):
                # Extract content from the AIMessageChunk
                if hasattr(message_chunk, 'content'):
                    text_chunk = message_chunk.content
                else:
                    text_chunk = str(message_chunk)
                    
                if text_chunk:
                    yield text_chunk

        except ConnectionError:
            yield "[ERROR] Could not connect to Ollama. Is it running?"
            return
        except TimeoutError:
            yield f"[ERROR] Ollama request timed out on chunk {i + 1}."
            return
        except Exception as e:
            yield f"[ERROR] {str(e)}"
            return