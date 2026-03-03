# Long Video Transcription API

FastAPI-based service for transcribing YouTube videos with **intelligent transcript detection** and fallback to faster-whisper for videos without captions.

## 🎯 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Transcription Request                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  Check YouTube Captions     │◄─── FAST PATH (2-5 sec)
         │  (youtube-transcript-api)   │
         └──────────┬──────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
    ✅ Found              ❌ Not Found
         │                     │
         ▼                     ▼
 ┌───────────────┐     ┌──────────────────┐
 │ Use YouTube   │     │ Whisper Pipeline │◄─── SLOW PATH
 │ Captions      │     │ (chunking + STT) │     (minutes)
 │ (instant)     │     └──────────────────┘
 └───────────────┘              │
         │                      │
         └──────────┬───────────┘
                    ▼
         ┌─────────────────────┐
         │  Save to Session    │
         │  (output/ folder)   │
         └─────────────────────┘
```

### **Smart Transcription Flow:**

1. **🔍 Check YouTube Captions** (`checking_transcripts`)
   - Tries English variants first (`en`, `en-US`, `en-GB`)
   - Falls back to any available language
   - Completes in ~2-5 seconds if found
   - Marks result with `source: "youtube_captions"`

2. **🎙️ Whisper Pipeline** (fallback if no captions)
   - Downloads audio (`downloading`)
   - Converts to 16kHz mono (`chunking`)
   - Splits into 5-minute chunks
   - Transcribes with faster-whisper (`transcribing`)
   - Marks result with `source: "whisper"`

## ✨ Features

- ✅ **Smart Transcript Detection**: Prioritizes YouTube captions for instant results
- ✅ **Automatic Fallback**: Uses Whisper transcription when captions unavailable
- ✅ **Session Management**: Each transcription gets a unique session ID
- ✅ **Background Processing**: Non-blocking async transcription
- ✅ **Checkpoint System**: Resume interrupted Whisper transcriptions
- ✅ **Progress Tracking**: Real-time status and progress updates
- ✅ **Multiple Output Formats**: Text and structured JSON with timestamps
- ✅ **Multi-language Support**: Detects and uses any available language
- ✅ **Source Tracking**: Know if transcript came from YouTube or Whisper
- ✅ **Organized Storage**: Separate output/ directory for each session

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make sure you have ffmpeg and yt-dlp installed
# Windows (with Chocolatey): choco install ffmpeg yt-dlp
# Or download from: https://ffmpeg.org/ and https://github.com/yt-dlp/yt-dlp
```

## Quick Start

```bash
# Navigate to backend directory
cd backend

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

## API Endpoints

### 1. Start Transcription

**POST** `/api/long-video/transcribe`

Request:
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "chunk_seconds": 300,
  "model_name": "base",
  "language": "en"
}
```

Response:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "checking_transcripts",
  "message": "Transcription started. Use /status/{session_id} to check progress."
}
```

**Model Options:** `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`

**Note:** The `model_name` and `chunk_seconds` parameters only apply if Whisper transcription is needed (no YouTube captions available).

---

### 2. Check Status

**GET** `/api/long-video/status/{session_id}`

Response:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "transcribing",
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "progress": {
    "current_chunk": 5,
    "total_chunks": 12,
    "completed_chunks": 4,
    "progress_percentage": 41.67
  },
  "error": null,
  "total_segments": null,
  "total_duration": null
}
```

**Status Values:**
- `checking_transcripts` - Checking for YouTube captions (usually 2-5 seconds)
- `downloading` - Downloading audio from YouTube (Whisper path)
- `chunking` - Splitting audio into chunks (Whisper path)
- `transcribing` - Processing chunks with Whisper
- `completed` - Transcription finished
- `error` - Failed (check error field)

---

### 3. Get Result

**GET** `/api/long-video/result/{session_id}`

Response:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "total_segments": 245,
  "total_duration": 3625.5,
  "source": "youtube_captions",
  "segments": [
    {
      "start": 0.0,
      "end": 4.5,
      "text": "Welcome to this video"
    },
    {
      "start": 4.5,
      "end": 8.2,
      "text": "Today we'll discuss..."
    }
  ],
  "full_text": "Welcome to this video Today we'll discuss..."
}
```

**Source Values:**
- `youtube_captions` - Transcript obtained from YouTube's caption API (instant)
- `whisper` - Transcript generated using faster-whisper STT (slower but works without captions)

---

### 4. Download Text Transcript

**GET** `/api/long-video/download/text/{session_id}`

Downloads plain text transcript file.

---

### 5. Download JSON Transcript

**GET** `/api/long-video/download/json/{session_id}`

Downloads structured JSON with all segments and timestamps.

---

### 6. List All Sessions

**GET** `/api/long-video/sessions`

Response:
```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
      "progress_percentage": 100.0
    }
  ]
}
```

---

### 7. Delete Session

**DELETE** `/api/long-video/session/{session_id}`

Response:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "deleted": true,
  "message": "Session and all associated files deleted"
}
```

---

## Usage Example (Python)

```python
import requests
import time

API_BASE = "http://localhost:8000/api/long-video"

# 1. Start transcription
response = requests.post(f"{API_BASE}/transcribe", json={
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "model_name": "base",
    "language": "en"
})
session_id = response.json()["session_id"]
print(f"Session ID: {session_id}")

# 2. Poll status
while True:
    status = requests.get(f"{API_BASE}/status/{session_id}").json()
    print(f"Status: {status['status']} - {status.get('progress', {}).get('progress_percentage', 0)}%")
    
    if status["status"] == "completed":
        break
    elif status["status"] == "error":
        print(f"Error: {status['error']}")
        break
    
    time.sleep(5)

# 3. Get result
result = requests.get(f"{API_BASE}/result/{session_id}").json()
print(f"Total segments: {result['total_segments']}")
print(f"Duration: {result['total_duration']} seconds")

# 4. Download files
with open(f"{session_id}_transcript.txt", "wb") as f:
    f.write(requests.get(f"{API_BASE}/download/text/{session_id}").content)
```

---

## Usage Example (JavaScript)

```javascript
const API_BASE = "http://localhost:8000/api/long-video";

// 1. Start transcription
const response = await fetch(`${API_BASE}/transcribe`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    model_name: "base",
    language: "en"
  })
});
const { session_id } = await response.json();
console.log(`Session ID: ${session_id}`);

// 2. Poll status
const checkStatus = async () => {
  const status = await fetch(`${API_BASE}/status/${session_id}`).then(r => r.json());
  console.log(`Status: ${status.status} - ${status.progress?.progress_percentage || 0}%`);
  
  if (status.status === "completed") {
    return getResult();
  } else if (status.status === "error") {
    console.error(`Error: ${status.error}`);
    return;
  }
  
  setTimeout(checkStatus, 5000);
};

// 3. Get result
const getResult = async () => {
  const result = await fetch(`${API_BASE}/result/${session_id}`).then(r => r.json());
  console.log(`Total segments: ${result.total_segments}`);
  console.log(`Duration: ${result.total_duration} seconds`);
};

checkStatus();
```

---

## 📊 Transcription Behavior

### **Videos WITH YouTube Captions:**
```
Request → Checking (2-5s) → ✅ Completed
Source: youtube_captions
Time: ~2-5 seconds
```

Example log output:
```
[Session abc123] Checking for existing YouTube transcripts...
Found English transcript
[Session abc123] ✅ Using YouTube captions (no audio processing needed)
```

### **Videos WITHOUT Captions:**
```
Request → Checking (2-5s) → Downloading → Chunking → Transcribing → ✅ Completed
Source: whisper
Time: ~5-15 minutes (depends on video length and model)
```

Example log output:
```
[Session abc123] Checking for existing YouTube transcripts...
No YouTube captions found, using Whisper transcription...
[Session abc123] Processing chunk 1/12...
```

---

## File Structure

```
backend/
├── main.py                          # FastAPI application
├── models/
│   ├── __init__.py
│   └── long_video.py               # Pydantic models
├── routers/
│   ├── __init__.py
│   └── long_video.py               # API endpoints
└── services/
    ├── __init__.py
    └── long_video_service.py       # Transcription logic

sessions/                            # Session data directory
└── {session_id}/
    ├── checkpoint.json             # Progress checkpoint
    ├── output/                     # Final transcription outputs
    │   ├── {session_id}_transcript.txt  # Text output
    │   └── {session_id}_transcript.json # JSON output
    └── chunks/                     # Temporary (auto-deleted)
```

---

## ⚙️ Configuration

Edit these values in `backend/services/long_video_service.py`:

```python
# Default chunk size (seconds) - only for Whisper pipeline
CHUNK_SECONDS = 300  # 5 minutes

# Default model - only for Whisper pipeline
MODEL_NAME = "base"

# Session storage directory
BASE_DIR = "sessions"
```

---

## 🚀 Performance Tips

### **1. Leverage YouTube Captions (Automatic):**
   - Most popular videos have captions → instant transcripts!
   - API automatically checks for captions first
   - No configuration needed

### **2. Model Selection (Whisper fallback only):**
   - `tiny` - Fastest, lowest accuracy (~4x realtime)
   - `base` - Good balance (recommended) (~2x realtime)
   - `small` - Better accuracy, slower (~1x realtime)
   - `medium` - High accuracy, much slower (~0.5x realtime)
   - `large-v2/v3` - Best accuracy, very slow (~0.3x realtime)

### **3. Chunk Size (Whisper fallback only):**
   - Smaller chunks (120-180s) = More frequent checkpoints, slightly slower
   - Larger chunks (300-600s) = Faster overall, less granular progress

### **4. GPU Support (Whisper fallback only):**
   - Edit `long_video_service.py` around line 240:
   - Change `device="cpu"` to `device="cuda"` if you have NVIDIA GPU
   - Install: `pip install faster-whisper[cuda]`
   - Can achieve 10-20x speedup on GPU

---

## 📈 Performance Comparison

| Video Type | Detection Time | Transcription Time | Total Time | Source |
|------------|---------------|-------------------|------------|---------|
| **With Captions** (typical) | ~2-5s | 0s (skipped) | **~2-5s** | `youtube_captions` |
| **Without Captions** (5 min) | ~2-5s | ~2-5 min | **~2-6 min** | `whisper` (base model) |
| **Without Captions** (30 min) | ~2-5s | ~15-30 min | **~15-30 min** | `whisper` (base model) |
| **Without Captions** (1 hour) | ~2-5s | ~30-60 min | **~30-60 min** | `whisper` (base model) |

**Key Insight:** ~80% of YouTube videos have captions, meaning most requests complete in **under 5 seconds**!

---

## Error Handling

The API includes automatic checkpoint recovery. If transcription fails:

1. Check the error with `/status/{session_id}`
2. Fix the issue (network, disk space, etc.)
3. Restart the same request - it will resume from the last completed chunk

---

## Testing

Test the API with curl:

```bash
# Start transcription
curl -X POST "http://localhost:8000/api/long-video/transcribe" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Check status
curl "http://localhost:8000/api/long-video/status/{session_id}"

# Get result
curl "http://localhost:8000/api/long-video/result/{session_id}"
```

---

## 📦 Dependencies

### **Core:**
- `fastapi==0.109.0` - Web framework
- `uvicorn` - ASGI server
- `pydantic==2.6.0` - Data validation

### **Transcription:**
- `youtube-transcript-api` - YouTube caption fetching (fast path)
- `faster-whisper` - Speech-to-text (fallback path)
- `yt-dlp` - YouTube audio download (fallback path only)

### **System Requirements (for Whisper fallback only):**
- `ffmpeg` - Audio processing
- `yt-dlp` - Video/audio download

Install system requirements:
```bash
# Windows (with Chocolatey)
choco install ffmpeg yt-dlp

# Or download manually:
# ffmpeg: https://ffmpeg.org/
# yt-dlp: https://github.com/yt-dlp/yt-dlp
```

---

## License

MIT License - See main repository LICENSE file.
