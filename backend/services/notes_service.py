"""
Service layer for notes generation.
Handles all communication with the local Ollama instance using LangChain for structured interactions.
Supports 10 detail levels (1=brief, 10=ultra-detailed) and recurrent chunking for long transcripts.
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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")

# ─────────────────────────────────────────────
# LLM CONFIGURATION
# ─────────────────────────────────────────────
llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.3,
    top_p=0.9,
    repeat_penalty=1.1,
)

llm_streaming = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.3,
    top_p=0.9,
    repeat_penalty=1.1,
)

# ─────────────────────────────────────────────
# CHUNKING CONFIG
# ─────────────────────────────────────────────
# Characters per token estimate (~4 chars/token)
# 128K context window for gpt-oss:120b-cloud
CHARS_PER_TOKEN = 4
MAX_CONTEXT_TOKENS = 128000

# Token budget per detail level:
# System prompt tokens + Output reservation + Input (transcript) tokens
# Detail 1-3:  1K system,  8K output, 119K input → 47.6K chars
# Detail 4-6:  2K system,  12K output, 114K input → 45.6K chars
# Detail 7-9:  3K system,  16K output, 109K input → 43.6K chars
# Detail 10:   4K system,  20K output, 104K input → 41.6K chars
DETAIL_MAX_CHARS = {
    1: 476000,  2: 476000,  3: 476000,
    4: 456000,  5: 456000,  6: 456000,
    7: 436000,  8: 436000,  9: 436000,
    10: 416000,
}

CHUNK_OVERLAP_CHARS = 500  # Small overlap for context continuity


# ─────────────────────────────────────────────
# 10 DETAIL-LEVEL SYSTEM PROMPTS
# ─────────────────────────────────────────────
# Each level produces progressively more comprehensive notes:
# 1 = Brief (bullet summary, 3-5 points)
# 5 = Standard (full notes with all sections)
# 10 = Ultra-detailed (exhaustive, textbook-level)

def _math_block(level: int) -> str:
    """Math formatting rules depend on detail level."""
    if level <= 3:
        return (
            "CRITICAL Math Formatting:\n"
            "- Inline math: $x^2$ or $\\lambda$\n"
            "- Block math: $$\\begin{{bmatrix}} a & b \\\\ c & d \\end{{bmatrix}}$$\n"
            "- NEVER use \\( or \\) or bare brackets for math.\n"
        )
    elif level <= 7:
        return (
            "CRITICAL Math Formatting:\n"
            "- Inline math: $x^2$ or $\\lambda$\n"
            "- Block math: $$\\begin{{bmatrix}} a & b \\\\ c & d \\end{{bmatrix}}$$\n"
            "- Definitions must bold the term: **Eigenvalue**: the root...\n"
            "- NEVER use \\( or \\) or bare brackets for math.\n"
        )
    else:
        return (
            "CRITICAL Math Formatting:\n"
            "- Inline math MUST use $...$: $\\lambda^2 - 5 = 0$\n"
            "- Display/block math MUST use $$...$$ on its own line:\n"
            "  $$\\begin{{bmatrix}} a & b \\\\ c & d \\end{{bmatrix}}$$\n"
            "- NEVER use \\( or \\) or [ ] for LaTeX.\n"
            "- Definitions format: **Term**: definition\n"
            "- NEVER write raw \\mathbf{{A}} without dollar signs.\n"
        )


def _output_sections(level: int) -> str:
    """Return the output sections based on detail level."""
    if level == 1:
        return (
            "## Summary\n"
            "- 3-5 concise bullet points covering the main ideas\n"
            "- Keep each point to one line\n"
            "- Focus on the single most important takeaway\n"
        )
    elif level == 2:
        return (
            "## Summary\n"
            "- 5-7 bullet points covering key ideas\n"
            "- One line per point\n"
            "## Key Concepts\n"
            "- **Concept name**: one-line explanation\n"
        )
    elif level == 3:
        return (
            "## Overview\n"
            "A brief paragraph (2-3 sentences) on what the video covers.\n\n"
            "## Key Topics\n"
            "- Bullet list of 5-8 main topics in order\n\n"
            "## Notes\n"
            "### [Topic]\n"
            "- 2-3 bullets per topic\n"
            "## Key Takeaways\n"
            "- 5 bullet points\n"
        )
    elif level == 4:
        return (
            "## Video Overview\n"
            "2-3 paragraph summary of the video's main subject and purpose.\n\n"
            "## Key Topics\n"
            "- List of 6-10 topics in order of appearance\n\n"
            "## Detailed Notes\n\n"
            "### [Topic Name]\n"
            "- Clear explanation (2-4 bullets)\n"
            "- Supporting examples\n\n"
            "## Important Definitions\n"
            "- **Term**: definition\n\n"
            "## Key Takeaways\n"
            "- 5-7 bullets summarizing main lessons\n"
        )
    elif level == 5:
        return (
            "## Video Overview\n"
            "A clear paragraph summarizing what the video covers and its main purpose.\n\n"
            "## Key Topics\n"
            "- List the main topics/concepts discussed\n"
            "- In order of appearance\n\n"
            "## Detailed Notes\n\n"
            "### [Topic Name]\n"
            "- Clear explanation of the concept\n"
            "- Supporting details and examples\n"
            "- **Bold** critical terms\n\n"
            "(Repeat for each major topic)\n\n"
            "## Important Definitions\n"
            "- **Term**: definition\n"
            "- **Another term**: its definition\n\n"
            "## Key Takeaways\n"
            "- 3-7 bullet points summarizing the most important lessons\n"
            "- Focus on actionable insights\n\n"
            "## Next Steps (optional)\n"
            "- Only include if the video suggests things to do or learn next\n"
        )
    elif level == 6:
        return (
            "## Video Overview\n"
            "A comprehensive paragraph (3-4 sentences) summarizing the video's scope and goals.\n\n"
            "## Key Topics\n"
            "- Enumerated list of all major topics in order\n"
            "- Each topic gets a brief descriptor\n\n"
            "## Detailed Notes\n\n"
            "### [Topic Name]\n"
            "- In-depth explanation with context\n"
            "- Real-world examples and applications\n"
            "- Connections to other topics\n"
            "- **Bold** all new or critical terminology\n\n"
            "## Important Definitions\n"
            "- **Term**: thorough definition with context\n"
            "- Include related terms\n\n"
            "## Key Takeaways\n"
            "- 7-10 bullet points with depth\n"
            "- Practical and theoretical insights\n\n"
            "## Next Steps\n"
            "- Suggested follow-up topics or actions\n"
        )
    elif level == 7:
        return (
            "## Video Overview\n"
            "An expansive paragraph summarizing the video's subject, approach, and audience.\n\n"
            "## Key Topics\n"
            "- Comprehensive enumerated list\n"
            "- Brief description of each topic's significance\n\n"
            "## Detailed Notes\n\n"
            "### [Topic Name]\n"
            "#### Sub-concept (if applicable)\n"
            "- Deep, thorough explanation\n"
            "- Theoretical foundations\n"
            "- Concrete examples and edge cases\n"
            "- Common misconceptions and clarifications\n"
            "- **Bold** all technical terms\n\n"
            "## Important Definitions\n"
            "Comprehensive glossary of all technical terms:\n"
            "- **Term**: detailed definition + context + examples\n\n"
            "## Key Takeaways\n"
            "- 10+ bullets with depth and nuance\n"
            "- Both practical applications and theoretical implications\n\n"
            "## Next Steps\n"
            "- Detailed follow-up roadmap\n"
        )
    elif level == 8:
        return (
            "## Video Overview\n"
            "An extensive summary (2-3 paragraphs) covering subject, methodology, and key findings.\n\n"
            "## Key Topics\n"
            "- Full enumeration with sub-topics\n"
            "- Cross-references between related topics\n\n"
            "## Detailed Notes\n\n"
            "### [Topic Name]\n"
            "#### [Sub-topic]\n"
            "- Comprehensive technical explanation\n"
            "- Mathematical/formal treatment where applicable\n"
            "- Historical context and development\n"
            "- State-of-the-art and limitations\n"
            "- Code examples, pseudocode, or worked examples\n"
            "- **Bold** all technical vocabulary\n\n"
            "## Important Definitions\n"
            "Complete technical glossary:\n"
            "- **Term**: complete definition + etymology + examples + edge cases\n\n"
            "## Key Takeaways\n"
            "- Extensive bullet analysis\n"
            "- Synthesis of multiple perspectives\n\n"
            "## Next Steps\n"
            "- Deep-dive resources and exercises\n"
        )
    elif level == 9:
        return (
            "## Video Overview\n"
            "A thorough multi-paragraph introduction covering background, motivation, and goals.\n\n"
            "## Key Topics\n"
            "Complete structured outline with hierarchy:\n"
            "1. Primary topics (numbered)\n"
            "2. Secondary sub-topics\n\n"
            "## Detailed Notes\n\n"
            "### [Topic Name]\n"
            "#### [Sub-topic]\n"
            "##### [Specific Concept]\n"
            "- Expert-level technical depth\n"
            "- Formal definitions and theorems\n"
            "- Full mathematical derivations where relevant\n"
            "- Historical notes and evolution of ideas\n"
            "- Current research directions\n"
            "- Common pitfalls and misconceptions (deeply explained)\n"
            "- Annotated examples with full reasoning\n"
            "- **Bold** every technical term on first definition\n\n"
            "## Important Definitions\n"
            "Complete reference glossary:\n"
            "- **Term**: full definition, motivation, examples, limitations, related terms\n\n"
            "## Key Takeaways\n"
            "- Comprehensive analysis from multiple expert perspectives\n"
            "- Connections across the entire field\n\n"
            "## Next Steps\n"
            "- Academic and industry resources\n"
            "- Suggested papers, projects, and experiments\n"
        )
    else:  # level == 10
        return (
            "## Video Overview\n"
            "A comprehensive multi-paragraph introduction providing complete context: subject, motivation, methodology, key results, and significance.\n\n"
            "## Key Topics\n"
            "Full hierarchical outline:\n"
            "1. Primary topics\n"
            "   1.1 Secondary topics\n"
            "       1.1.1 Specific concepts\n\n"
            "## Detailed Notes\n\n"
            "### [Topic Name]\n"
            "#### [Sub-topic]\n"
            "##### [Specific Concept]\n"
            "###### [Granular Detail]\n"
            "- Ultra-comprehensive technical explanation\n"
            "- Complete mathematical treatment with all steps\n"
            "- Historical development and evolution\n"
            "- Philosophical foundations and motivations\n"
            "- Formal proofs and derivations where applicable\n"
            "- Implementation details and code walkthroughs\n"
            "- Benchmark results and performance analysis\n"
            "- Edge cases, failure modes, and boundary conditions\n"
            "- Common misconceptions (with detailed rebuttals)\n"
            "- Real-world deployment considerations\n"
            "- Future research directions and open problems\n"
            "- Cross-disciplinary connections\n"
            "- **Bold** every technical vocabulary term on first definition\n\n"
            "## Important Definitions\n"
            "Definitive reference glossary:\n"
            "- **Term**: complete definition, historical origin, motivation, examples, counterexamples, formal statement, practical applications, limitations, related/contrasting terms\n\n"
            "## Key Takeaways\n"
            "- Exhaustive synthesis from expert-level perspective\n"
            "- All major themes, debates, and open questions\n"
            "- Practical and theoretical significance\n\n"
            "## Next Steps\n"
            "- Academic pathway: papers, courses, textbooks\n"
            "- Industry applications and case studies\n"
            "- Hands-on projects and experiments\n"
            "- Community resources and further reading\n"
        )


def _detail_instruction(level: int) -> str:
    """Add extra quality/enrichment instructions for higher detail levels."""
    base = (
        "You are an expert note-taker who creates "
        + {1: "brief", 2: "concise", 3: "standard", 4: "comprehensive",
           5: "thorough", 6: "detailed", 7: "extensive", 8: "comprehensive",
           9: "expert-level", 10: "definitive textbook-level"}[level]
        + " study notes from video transcripts in English Only.\n\n"
    )
    return base


def _build_system_prompt(level: int) -> str:
    """Build the full system prompt for a given detail level."""
    return (
        _detail_instruction(level)
        + "## Instructions\n"
        "1. Output ONLY clean Markdown - NO XML tags, NO wrapper tags, NO <section> tags\n"
        "2. Use proper Markdown headings (##, ###), bullet points, and formatting\n"
        "3. Do NOT invent information - only use content from the transcript\n"
        "4. Bold (**) key terms and definitions when first introduced\n"
        "5. Keep language clear, concise, and educational\n\n"
        + _math_block(level)
        + "\n## Output Format:\n\n"
        + _output_sections(level)
        + "\nRemember: Output clean, readable Markdown only. No XML. No wrapper tags. "
        "ALL math must be wrapped in $ or $$. Start directly with \"## Video Overview\" or the appropriate heading for this level."
    )


# ─────────────────────────────────────────────
# RECURRENT CHUNK SYSTEM PROMPTS
# ─────────────────────────────────────────────
# Each chunk gets prior accumulated notes as context.
# This prevents hallucinations, maintains continuity,
# and allows indefinite-length notes generation.

def _build_recurrent_first_prompt(level: int) -> str:
    """First chunk: writes overview + notes section start."""
    return (
        _detail_instruction(level)
        + "## Instructions\n"
        "1. Output ONLY clean Markdown - NO XML tags, NO wrapper tags\n"
        "2. Use proper Markdown headings (##, ###)\n"
        "3. Do NOT invent - only use content from the transcript\n"
        "4. Bold (**) key terms on first definition\n"
        "5. Write ONLY the beginning of the notes. Do NOT conclude or summarize.\n\n"
        + _math_block(level)
        + "\n## Output Format:\n\n"
        + _output_sections(level)
        + "\nWrite the overview and begin the detailed notes. Do NOT add Key Takeaways, "
        "Definitions list, or conclusion - those come after all content is processed."
    )


def _build_recurrent_continue_prompt(level: int) -> str:
    """Middle/final chunks: continue from prior notes."""
    return (
        "You are continuing notes from previous transcript chunks in English Only.\n\n"
        "## Instructions\n"
        "1. Output ONLY clean Markdown - NO XML, NO wrapper tags\n"
        "2. Use ### headings for new topics\n"
        "3. Do NOT invent - only use content from the current transcript chunk\n"
        "4. Bold (**) key terms on first definition\n"
        "5. Keep language consistent with the prior notes\n\n"
        + _math_block(level)
        + "\n## Your Task:\n"
        "- Review the PRIOR NOTES below (what has been written so far)\n"
        "- Continue the notes by documenting the NEW CONTENT from this transcript chunk\n"
        "- Preserve heading structure and tone of prior notes\n"
        "- Add new ### Topic sections for new topics\n"
        "- If a topic from the chunk continues a topic in prior notes, extend that section\n\n"
        "## Prior Notes (append to these):\n\n"
        "{prior_notes}\n\n"
        "## New Transcript Content (document this):\n\n"
        "{current_chunk}\n\n"
        "## Continue the notes below:\n"
    )


def _build_recurrent_final_prompt(level: int) -> str:
    """Final chunk: continues + adds Definitions, Takeaways, Next Steps."""
    return (
        "You are completing notes from a complete video transcript in English Only.\n\n"
        "## Instructions\n"
        "1. Output ONLY clean Markdown - NO XML, NO wrapper tags\n"
        "2. Use ### headings for new topics\n"
        "3. Do NOT invent - only use content from the transcript\n"
        "4. Bold (**) key terms on first definition\n\n"
        + _math_block(level)
        + "\n## Your Task:\n"
        "- Review the PRIOR NOTES (partial notes from earlier chunks)\n"
        "- Complete any remaining Detailed Notes sections from this final chunk\n"
        "- Add these FINISHING sections at the end (based on ALL content seen):\n\n"
        + _output_sections(level).split("## Key Takeaways")[1].strip()
        + "\n\n"
        "## Prior Notes (append to these):\n\n"
        "{prior_notes}\n\n"
        "## Final Transcript Content:\n\n"
        "{current_chunk}\n\n"
        "## Complete notes below:\n"
    )


# ─────────────────────────────────────────────
# PRE-BUILD ALL 10×3 PROMPT TEMPLATES
# ─────────────────────────────────────────────
_prompt_cache: dict = {}

def _get_prompts(level: int):
    """Get (non_streaming, streaming, recurrent_first, recurrent_continue, recurrent_final) for level."""
    if level not in _prompt_cache:
        sf = _build_system_prompt(level)
        rf = _build_recurrent_first_prompt(level)
        rc = _build_recurrent_continue_prompt(level)
        rv = _build_recurrent_final_prompt(level)

        _prompt_cache[level] = {
            "standard": (sf, rf, rc, rv),
            "full": ChatPromptTemplate.from_messages([("system", sf), ("human", "{user_input}")]),
            "first": ChatPromptTemplate.from_messages([("system", rf), ("human", "{user_input}")]),
            "continue": ChatPromptTemplate.from_messages([("system", rc), ("human", "{user_input}")]),
            "final": ChatPromptTemplate.from_messages([("system", rv), ("human", "{user_input}")]),
        }
    return _prompt_cache[level]


def _chain(streaming: bool, prompt_template: ChatPromptTemplate):
    model = llm_streaming if streaming else llm
    return prompt_template | model | StrOutputParser()


# ─────────────────────────────────────────────
# TRANSCRIPT CHUNKING
# ─────────────────────────────────────────────
def split_transcript_into_chunks(
    transcript: str,
    detail_level: int = 5,
    is_recurrent: bool = False
) -> List[str]:
    """
    Split a long transcript into chunks that fit within the model's context window.

    For recurrent mode, chunks are smaller to leave room for accumulated prior notes
    in the context. We reserve ~30% of the budget for prior notes.
    """
    max_chars = DETAIL_MAX_CHARS.get(detail_level, 456000)

    if len(transcript) <= max_chars:
        return [transcript]

    chunks = []
    start = 0

    while start < len(transcript):
        end = start + max_chars

        if end >= len(transcript):
            chunks.append(transcript[start:])
            break

        # Try to break at sentence boundary, paragraph, or newline
        break_point = end
        search_start = max(start + max_chars - 2000, start)

        for i in range(end, search_start, -1):
            if transcript[i] in '.!?\n':
                break_point = i + 1
                break

        chunks.append(transcript[start:break_point])
        start = break_point - CHUNK_OVERLAP_CHARS if break_point > CHUNK_OVERLAP_CHARS else break_point

    return chunks


def _get_chunk_count_for_recurrent(transcript: str, detail_level: int, prior_notes: str) -> int:
    """
    Estimate how many recurrent chunks are needed.
    Each iteration processes a chunk and accumulates notes.
    We can fit ~60% of max_chars per chunk in recurrent mode.
    """
    available = int(DETAIL_MAX_CHARS.get(detail_level, 456000) * 0.60)
    return max(1, len(transcript) // available + (1 if len(transcript) % available else 0))


# ─────────────────────────────────────────────
# CORE GENERATION FUNCTIONS
# ─────────────────────────────────────────────
def _generate_single_pass(
    transcript: str,
    title: str,
    detail_level: int,
    streaming: bool
):
    """
    Single-pass generation for short transcripts or when recurrent isn't needed.
    Uses standard (non-recurrent) chunking.
    """
    chunks = split_transcript_into_chunks(transcript, detail_level)
    total_chunks = len(chunks)

    accumulated = ""
    all_notes = []

    for i, chunk in enumerate(chunks):
        _, rf, rc, rv = _get_prompts(detail_level)["standard"]

        if total_chunks == 1:
            user_input = f"Video Title: {title}\n\n---\n\nTranscript:\n{chunk}"
            prompt_t = _get_prompts(detail_level)["full"]
        elif i == 0:
            user_input = f"Video Title: {title}\n\n---\n\nTranscript (Part 1 of {total_chunks}):\n{chunk}"
            prompt_t = _get_prompts(detail_level)["first"]
        elif i == total_chunks - 1:
            user_input = f"Video Title: {title}\n\n---\n\nFinal transcript section (Part {i+1} of {total_chunks}):\n{chunk}"
            prompt_t = _get_prompts(detail_level)["final"]
        else:
            user_input = f"Continuing (Part {i+1} of {total_chunks}):\n{chunk}"
            prompt_t = _get_prompts(detail_level)["continue"]

        chain = _chain(streaming, prompt_t)

        if streaming:
            for token in chain.stream({"user_input": user_input}):
                yield token
        else:
            result = chain.invoke({"user_input": user_input})
            yield result
            accumulated += result + "\n\n"

    return accumulated if not streaming else None


def _generate_recurrent(
    transcript: str,
    title: str,
    detail_level: int,
    streaming: bool
):
    """
    Recurrent generation: each chunk gets prior accumulated notes as context.
    This is the primary mode for long transcripts.
    - Chunk 1: Overview + notes start → prior_notes_1
    - Chunk 2: prior_notes_1 + chunk_2 → prior_notes_2
    - Chunk N: prior_notes_(N-1) + final_chunk → final notes (with Takeaways etc.)

    Yields tokens incrementally so the frontend can stream in real-time.
    """
    # Use smaller chunks for recurrent to ensure room for prior notes
    max_chars = int(DETAIL_MAX_CHARS.get(detail_level, 456000) * 0.55)
    chunks = []

    start = 0
    while start < len(transcript):
        end = start + max_chars
        if end >= len(transcript):
            chunks.append(transcript[start:])
            break

        break_point = end
        search_start = max(start + max_chars - 2000, start)
        for i in range(end, search_start, -1):
            if transcript[i] in '.!?\n':
                break_point = i + 1
                break

        chunks.append(transcript[start:break_point])
        start = break_point - CHUNK_OVERLAP_CHARS if break_point > CHUNK_OVERLAP_CHARS else break_point

    total_chunks = len(chunks)
    prior_notes = ""

    for i, chunk in enumerate(chunks):
        is_first = (i == 0)
        is_last = (i == total_chunks - 1)

        if is_first:
            prompt_t = _get_prompts(detail_level)["first"]
            user_input = f"Video Title: {title}\n\n---\n\nTranscript (Part 1 of {total_chunks}):\n{chunk}"
        elif is_last:
            # Final: include prior notes in the prompt, then add the final sections
            prompt_t = _get_prompts(detail_level)["final"]
            user_input = (
                f"Video Title: {title}\n\n"
                "---\n\n"
                "PRIOR NOTES (append to these):\n"
                f"{prior_notes}\n\n"
                "---\n\n"
                f"FINAL TRANSCRIPT SECTION (Part {i+1} of {total_chunks}):\n"
                f"{chunk}\n\n"
                "---\n"
                "Complete the notes using the format above. Add Key Takeaways and any other "
                "final sections based on the ENTIRE video content."
            )
        else:
            # Middle: pass prior notes for continuity
            prompt_t = _get_prompts(detail_level)["continue"]
            user_input = (
                f"Continuing (Part {i+1} of {total_chunks}):\n\n"
                "PRIOR NOTES (append to these):\n"
                f"{prior_notes}\n\n"
                "---\n\n"
                f"NEW CONTENT:\n{chunk}\n\n"
                "Continue the notes below."
            )

        chain = _chain(streaming, prompt_t)

        if streaming:
            chunk_tokens = []
            for token in chain.stream({"user_input": user_input, "prior_notes": prior_notes, "current_chunk": chunk}):
                yield token
                chunk_tokens.append(token)

            if is_last:
                prior_notes += "".join(chunk_tokens)
            else:
                prior_notes += "".join(chunk_tokens) + "\n\n"
        else:
            result = chain.invoke({"user_input": user_input, "prior_notes": prior_notes, "current_chunk": chunk})
            yield result
            if is_last:
                prior_notes += result
            else:
                prior_notes += result + "\n\n"

    return prior_notes


def generate_notes(
    transcript: str,
    title: str = "Untitled Video",
    detail_level: int = 5,
) -> NotesResponse:
    """
    Generate notes at the specified detail level (1-10).
    Automatically chooses single-pass or recurrent chunking based on transcript length.
    """
    total_chars = len(transcript)
    chunks = split_transcript_into_chunks(transcript, detail_level)
    total_chunks = len(chunks)

    print(f"[Notes] detail={detail_level}, chars={total_chars}, chunks={total_chunks}")

    try:
        # For transcripts that fit in 2+ chunks, use recurrent generation
        if total_chunks >= 2:
            accumulated = ""
            for result in _generate_recurrent(
                transcript, title, detail_level, streaming=False
            ):
                accumulated = result  # last result is full notes
            return NotesResponse(
                title=title,
                notes=accumulated,
                model_used=OLLAMA_MODEL,
                status="success",
                detail_level=detail_level,
                chunks_processed=total_chunks,
            )
        else:
            # Single pass
            results = list(_generate_single_pass(
                transcript, title, detail_level, streaming=False
            ))
            combined = "\n\n".join(results)
            return NotesResponse(
                title=title,
                notes=combined,
                model_used=OLLAMA_MODEL,
                status="success",
                detail_level=detail_level,
                chunks_processed=total_chunks,
            )

    except ConnectionError:
        return NotesResponse(
            title=title, notes="", model_used=OLLAMA_MODEL,
            status="error", error="Could not connect to Ollama. Is it running?",
            detail_level=detail_level, chunks_processed=0
        )
    except Exception as e:
        return NotesResponse(
            title=title, notes="", model_used=OLLAMA_MODEL,
            status="error", error=str(e),
            detail_level=detail_level, chunks_processed=0
        )


def generate_notes_stream(
    transcript: str,
    title: str = "Untitled Video",
    detail_level: int = 5,
) -> Generator[str, None, None]:
    """
    Streaming notes generator. Yields tokens as they're generated.
    Uses recurrent chunking for multi-chunk transcripts.
    """
    chunks = split_transcript_into_chunks(transcript, detail_level)
    total_chunks = len(chunks)

    print(f"[Notes Stream] detail={detail_level}, chars={len(transcript)}, chunks={total_chunks}")

    if total_chunks >= 2:
        yield from _generate_recurrent_streaming(
            transcript, title, detail_level
        )
    else:
        for token in _generate_single_pass(
            transcript, title, detail_level, streaming=True
        ):
            yield token


def _generate_recurrent_streaming(
    transcript: str,
    title: str,
    detail_level: int,
) -> Generator[str, None, None]:
    """
    Streaming recurrent generation.
    Each chunk yields tokens incrementally; prior notes are tracked locally.
    """
    max_chars = int(DETAIL_MAX_CHARS.get(detail_level, 456000) * 0.55)
    chunks = []

    start = 0
    while start < len(transcript):
        end = start + max_chars
        if end >= len(transcript):
            chunks.append(transcript[start:])
            break

        break_point = end
        search_start = max(start + max_chars - 2000, start)
        for i in range(end, search_start, -1):
            if transcript[i] in '.!?\n':
                break_point = i + 1
                break

        chunks.append(transcript[start:break_point])
        start = break_point - CHUNK_OVERLAP_CHARS if break_point > CHUNK_OVERLAP_CHARS else break_point

    total_chunks = len(chunks)
    prior_notes = ""

    for i, chunk in enumerate(chunks):
        is_first = (i == 0)
        is_last = (i == total_chunks - 1)

        if is_first:
            prompt_t = _get_prompts(detail_level)["first"]
            user_input = f"Video Title: {title}\n\n---\n\nTranscript (Part 1 of {total_chunks}):\n{chunk}"
        elif is_last:
            prompt_t = _get_prompts(detail_level)["final"]
            user_input = (
                f"Video Title: {title}\n\n"
                "---\n\n"
                "PRIOR NOTES (append to these):\n"
                f"{prior_notes}\n\n"
                "---\n\n"
                f"FINAL TRANSCRIPT SECTION (Part {i+1} of {total_chunks}):\n"
                f"{chunk}\n\n"
                "---\n"
                "Complete the notes. Add Key Takeaways and any other final sections "
                "based on the ENTIRE video content."
            )
        else:
            prompt_t = _get_prompts(detail_level)["continue"]
            user_input = (
                f"Continuing (Part {i+1} of {total_chunks}):\n\n"
                "PRIOR NOTES (append to these):\n"
                f"{prior_notes}\n\n"
                "---\n\n"
                f"NEW CONTENT:\n{chunk}\n\n"
                "Continue the notes below."
            )

        chain = _chain(streaming=True, prompt_template=prompt_t)

        # Stream tokens from this chunk
        for token in chain.stream({"user_input": user_input, "prior_notes": prior_notes, "current_chunk": chunk}):
            yield token

        # After streaming, accumulate for next iteration
        # We can't re-stream, so we re-run non-streaming for this chunk to accumulate
        if not is_last:
            acc_chain = _chain(streaming=False, prompt_template=prompt_t)
            result = acc_chain.invoke({"user_input": user_input, "prior_notes": prior_notes, "current_chunk": chunk})
            prior_notes += result + "\n\n"
        else:
            # Final: accumulate the last streamed result
            pass  # prior_notes already streamed to user; no next iteration
