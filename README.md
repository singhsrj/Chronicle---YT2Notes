# ◈ YT Notes

> Transform YouTube videos into structured, interactive knowledge — powered by local LLMs and faster-whisper.

---

## **NEW: Long Video Transcription API** 🎉

Transcribe videos of any length with chunked processing, checkpoints, and progress tracking!

```bash
# Start the API server
cd backend
python main.py

# Test with a video
python test_client.py test https://www.youtube.com/watch?v=VIDEO_ID
```

See [backend/README.md](backend/README.md) for complete API documentation.

---

## Architecture Overview

```
yt-notes/
├── backend/                  # FastAPI — modular, async
│   ├── main.py               # App entrypoint, CORS, router mounting
│   ├── config.py             # All settings (env-driven)
│   ├── models/
│   │   └── long_video.py     # Long video transcription models
│   ├── routers/
│   │   ├── ingest.py         # POST /api/ingest — YouTube URL → session
│   │   ├── notes.py          # POST /api/notes/generate — LLM notes
│   │   ├── chat.py           # POST /api/chat — streaming SSE chat
│   │   ├── export.py         # GET /api/export/{json|markdown}
│   │   └── long_video.py     # POST /api/long-video/transcribe — long video pipeline
│   └── services/
│       ├── ingestion.py      # URL parsing + transcript + metadata
│       ├── llm.py            # All prompts, Ollama calls, streaming
│       ├── storage.py        # JSON session persistence
│       └── long_video_service.py # Chunked transcription with faster-whisper
│
├── services/                 # Standalone services
│   ├── long_video_pipeline.py # CLI tool for long video transcription
│   ├── yt_to_mp3.py          # YouTube to MP3 downloader
│   └── get_transcribe.py     # Simple transcript fetcher
│
├── frontend/                 # React + Vite + TypeScript
│   └── src/
│       ├── App.tsx           # Full UI (single-component)
│       └── services/api.ts   # All backend calls
│
└── ollama/
    └── Modelfile             # Custom yt-notes model definition
```

### Data Flow

```
User pastes URL
    → POST /api/ingest        (background task)
    → YouTube oEmbed + youtube-transcript-api
    → Session saved as JSON   (status: ready)

User clicks "Generate Notes"
    → POST /api/notes/generate (background task)
    → Transcript → Ollama (structured JSON prompt)
    → NoteBlocks parsed + saved to session

User selects text → asks question
    → POST /api/chat          (streaming SSE)
    → Ollama streams tokens → frontend renders live
    → Full response appended to ChatThread in session
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | python.org |
| Node.js | 18+ | nodejs.org |
| Ollama | latest | [ollama.com](https://ollama.com) |

---

## Setup

### 1. Ollama — Build the custom model

```bash
# Pull base model (llama3.2 is recommended — change in Modelfile if preferred)
ollama pull llama3.2

# Build the yt-notes model from Modelfile
cd ollama/
ollama create yt-notes -f ./Modelfile

# Verify
ollama list   # should show yt-notes
ollama run yt-notes "Hello"
```

**Swapping the base model:** Edit line 1 of `ollama/Modelfile`:
```
FROM llama3.2        # default
FROM llama3.1:8b     # better quality, more RAM
FROM mistral         # fast alternative
FROM qwen2.5:7b      # strong multilingual
```
Then re-run `ollama create yt-notes -f ./Modelfile`.

---

### 2. Backend

```bash
cd backend/

# Create venv
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Configure (optional)
cp .env.example .env
# Edit .env to add YOUTUBE_API_KEY if you want rich metadata (duration, etc.)

# Run
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`.
Swagger docs: `http://localhost:8000/docs`

**Environment variables (`.env`):**
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=yt-notes
YOUTUBE_API_KEY=           # optional — oEmbed fallback works without it
DATA_DIR=./data
SESSIONS_DIR=./data/sessions
```

---

### 3. Frontend

```bash
cd frontend/
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## Usage

### Ingest a Video
Paste any YouTube URL format into the sidebar input:
- `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- `https://youtu.be/dQw4w9WgXcQ`
- `https://www.youtube.com/shorts/dQw4w9WgXcQ`
- `https://www.youtube.com/embed/dQw4w9WgXcQ`
- `dQw4w9WgXcQ` (bare video ID)

Click **Ingest** or press Enter. Status updates in real-time.

### Generate Notes
Once ingested (status: `ready`), select note depth and click **Generate Notes**:
- **Brief** — Summary + 5 key points
- **Detailed** — Summary, key points (10), concepts, timeline
- **Comprehensive** — All 6 note types (summary, key_points, concepts, timeline, quotes, action_items)

### Inline Chat
1. Select any text in the Notes panel (highlights trigger a reply box)
2. Type your question in the chat input
3. The response appears as a **sub-thread** anchored to the selected passage
4. Switch to the **Threads** tab to see all conversation threads
5. Click any thread to continue it

### Export
- **↓ JSON** — Full session (video meta, transcript, notes, all threads)
- **↓ MD** — Clean Markdown document for Obsidian, Notion, etc.

---

## API Reference

### Ingest
```
POST /api/ingest/
Body: { "url": "...", "language": "en" }
Returns: { "session_id": "...", "status": "ingesting" }

GET /api/ingest/status/{session_id}
Returns: { session_id, status, error, video_meta }
```

### Notes
```
POST /api/notes/generate
Body: { "session_id": "...", "depth": "detailed" }

GET /api/notes/session/{session_id}    → full Session object
GET /api/notes/sessions                → list of SessionSummary
DELETE /api/notes/session/{session_id}
```

### Chat
```
POST /api/chat/
Body: { session_id, message, selected_text?, thread_id? }
Returns: SSE stream → { token, thread_id } ... { done: true, thread_id }

GET /api/chat/threads/{session_id}
```

### Export
```
GET /api/export/json/{session_id}      → .json download
GET /api/export/markdown/{session_id}  → .md download
```

---

## Session JSON Schema

```json
{
  "id": "uuid",
  "created_at": "ISO datetime",
  "video_meta": {
    "video_id": "...", "title": "...", "channel": "...",
    "duration_seconds": 0, "thumbnail_url": "..."
  },
  "transcript": [
    { "start": 0.0, "duration": 2.5, "text": "Hello everyone..." }
  ],
  "notes": [
    {
      "type": "summary",
      "title": "...",
      "content": "markdown content",
      "timestamp_refs": [0.0, 45.2]
    }
  ],
  "threads": [
    {
      "id": "uuid",
      "anchor_text": "the selected text",
      "messages": [
        { "id": "uuid", "role": "user", "content": "...", "selected_text": "..." },
        { "id": "uuid", "role": "assistant", "content": "..." }
      ]
    }
  ],
  "status": "ready"
}
```

---

## Customizing the LLM Behavior

All prompt logic lives in `backend/services/llm.py`:

- **`NOTES_SYSTEM_PROMPT`** — controls note generation personality and JSON contract
- **`CHAT_SYSTEM_PROMPT`** — controls chat assistant behavior
- **`DEPTH_INSTRUCTIONS`** — controls what note types are generated per depth level
- **`NOTE_SCHEMA`** — JSON schema injected into the notes prompt
- Sampling params (temperature, top_p, etc.) are in each function's `options` dict

The `ollama/Modelfile` sets the model-level system prompt and sampling defaults. Changes there take effect after re-running `ollama create yt-notes -f ./Modelfile`.

---

## Extending the System

| Add this | Where |
|----------|-------|
| New note type | Add to `NoteBlock.type` enum in `models.py`, update `NOTE_SCHEMA` and `NOTE_ICONS`/`NOTE_COLORS` in `App.tsx` |
| YouTube Data API rich metadata | Set `YOUTUBE_API_KEY` in `.env` |
| Multiple language transcripts | Pass `language` param in ingest request |
| PostgreSQL instead of JSON | Replace `services/storage.py` — interface stays the same |
| Different LLM provider | Replace `services/llm.py` — routers don't change |
| Authentication | Add FastAPI middleware in `main.py` |

---

## Troubleshooting

**"Could not fetch transcript"** — The video has transcripts disabled, is private, or is very new. Try a different video.

**Ollama connection refused** — Make sure Ollama is running: `ollama serve`

**Notes generation fails** — Check Ollama logs: `ollama logs`. The model may be returning malformed JSON; try a different base model or lower temperature in the Modelfile.

**CORS errors** — Make sure the frontend dev server port matches the allowed origins in `backend/main.py`.
