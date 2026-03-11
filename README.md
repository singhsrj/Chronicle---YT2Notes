<div align="center">

# 📺 Chronicle — YouTube to Notes

**Transform any YouTube video into structured, AI-powered notes with a single click**

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=black)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black?logo=ollama)](https://ollama.com)

[Quick Start](#-quick-start-with-docker) • [Features](#-features) • [Tech Stack](#-tech-stack) • [Architecture](#-architecture) • [API Docs](#-api-reference)

</div>

---

## 🎯 What is Chronicle?

Chronicle is a **full-stack AI application** that converts YouTube videos into interactive, structured notes using local LLMs. Simply paste a video URL, and Chronicle handles transcription, summarization, and note generation—all running locally on your machine with no API costs.

### Key Highlights

- 🎬 **Video Processing** — Supports any YouTube video format (standard, shorts, embeds)
- 🤖 **Local AI** — Uses Ollama for privacy-first, cost-free LLM inference
- ⚡ **Long Video Support** — Chunked transcription with checkpoints for videos of any length
- 💬 **Interactive Chat** — Ask follow-up questions on any section of your notes
- 📤 **Export Ready** — Download as Markdown or JSON for Obsidian, Notion, etc.

---

## 🚀 Quick Start with Docker

Get Chronicle running in **under 2 minutes** with Docker:

### Prerequisites

1. **[Docker Desktop](https://docker.com/products/docker-desktop)** installed and running
2. **[Ollama](https://ollama.com)** installed with a model pulled:
   ```bash
   ollama pull llama2:7b   # or any preferred model
   ollama serve            # ensure Ollama is running
   ```

### One-Command Setup

```bash
# Clone the repository
git clone https://github.com/singhsrj/Chronicle---YT2Notes.git
cd Chronicle---YT2Notes

# Start with Docker Compose
docker-compose up --build
```

### Access the Application

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | Main application UI |
| **Backend API** | http://localhost:8000 | REST API |
| **API Documentation** | http://localhost:8000/docs | Interactive Swagger docs |

### Docker Configuration Options

```bash
# Use a different Ollama model
OLLAMA_MODEL=qwen2.5:7b docker-compose up --build

# Run in background (detached mode)
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

> 📖 For detailed Docker configuration (Linux setup, troubleshooting), see [DOCKER.md](DOCKER.md)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Smart Transcription** | Automatic YouTube transcript extraction with multi-language support |
| **AI Note Generation** | Choose from Brief, Detailed, or Comprehensive note formats |
| **Context-Aware Chat** | Select any text and ask questions—AI understands the context |
| **Threaded Conversations** | Each question creates a sub-thread for organized discussions |
| **Checkpoint System** | Resume long video transcriptions from where you left off |
| **Multi-Format Export** | Export notes as Markdown (for Obsidian/Notion) or JSON |
| **Real-Time Progress** | Live status updates during ingestion and note generation |

---

## 🛠 Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | High-performance async REST API framework |
| **LangChain + LangGraph** | LLM orchestration and structured outputs |
| **Ollama** | Local LLM inference (Llama, Mistral, Qwen) |
| **faster-whisper** | High-speed audio transcription |
| **yt-dlp** | YouTube video/audio extraction |
| **Pydantic** | Data validation and serialization |

### Frontend
| Technology | Purpose |
|------------|---------|
| **React 18** | Component-based UI library |
| **TypeScript** | Type-safe JavaScript |
| **Vite** | Lightning-fast build tooling |
| **CSS Modules** | Scoped component styling |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **Docker + Docker Compose** | Containerized deployment |
| **Nginx** | Production-ready frontend serving |
| **GitHub Actions** | CI/CD pipeline (optional) |

---

## 🏗 Architecture

```
Chronicle/
├── backend/                 # FastAPI Application
│   ├── main.py              # Application entrypoint, CORS, router mounting
│   ├── models/              # Pydantic schemas and data models
│   ├── routers/             # API endpoint definitions
│   │   ├── notes.py         # Note generation endpoints
│   │   └── long_video.py    # Long video transcription pipeline
│   └── services/            # Business logic layer
│       ├── notes_service.py # LLM-powered note generation
│       └── long_video_service.py # Chunked transcription with checkpoints
│
├── frontend/                # React + TypeScript Application
│   └── src/
│       ├── components/      # Reusable UI components
│       ├── services/        # API client layer
│       ├── hooks/           # Custom React hooks
│       └── context/         # Global state management
│
├── docker-compose.yml       # Multi-container orchestration
└── tests/                   # API test suite
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  User pastes YouTube URL                                        │
│      ↓                                                          │
│  POST /api/ingest → Extract transcript + metadata               │
│      ↓                                                          │
│  Session created (JSON persistence)                             │
│      ↓                                                          │
│  User clicks "Generate Notes"                                   │
│      ↓                                                          │
│  POST /api/notes/generate → LLM processes transcript            │
│      ↓                                                          │
│  Structured notes returned (summary, key points, timeline...)   │
│      ↓                                                          │
│  User selects text → POST /api/chat (streaming SSE)             │
│      ↓                                                          │
│  Real-time AI response rendered in UI                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 💻 Local Development Setup

<details>
<summary><strong>Click to expand manual setup instructions</strong></summary>

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Ollama | latest | [ollama.com](https://ollama.com) |

### 1. Setup Ollama

```bash
# Pull your preferred model
ollama pull llama3.2

# Optional: Create a custom yt-notes model
cd ollama/
ollama create yt-notes -f ./Modelfile
```

### 2. Backend Setup

```bash
cd backend/

# Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend/
npm install
npm run dev
```

Open http://localhost:5173

</details>

---

## 📖 Usage Guide

### Supported YouTube URL Formats
```
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
https://www.youtube.com/shorts/VIDEO_ID
https://www.youtube.com/embed/VIDEO_ID
VIDEO_ID (bare video ID)
```

### Note Generation Modes

| Mode | Output |
|------|--------|
| **Brief** | Summary + 5 key points |
| **Detailed** | Summary, 10 key points, concepts, timeline |
| **Comprehensive** | All 6 types: summary, key points, concepts, timeline, quotes, action items |

### Interactive Chat
1. Select any text in the Notes panel
2. Type your question in the chat input
3. AI responds with context-aware answers
4. View all conversation threads in the Threads tab

---

## 📡 API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ingest/` | Ingest a YouTube video |
| `POST` | `/api/notes/generate` | Generate AI notes |
| `POST` | `/api/chat` | Streaming chat (SSE) |
| `GET` | `/api/export/json` | Export session as JSON |
| `GET` | `/api/export/markdown` | Export session as Markdown |

### Long Video Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/long-video/transcribe` | Start transcription |
| `GET` | `/api/long-video/status/{session_id}` | Check progress |
| `GET` | `/api/long-video/result/{session_id}` | Get transcript |

> 📖 Full API documentation available at http://localhost:8000/docs

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ by [Suraj Singh](https://github.com/singhsrj)**

</div>

**Ollama connection refused** — Make sure Ollama is running: `ollama serve`

**Notes generation fails** — Check Ollama logs: `ollama logs`. The model may be returning malformed JSON; try a different base model or lower temperature in the Modelfile.

**CORS errors** — Make sure the frontend dev server port matches the allowed origins in `backend/main.py`.
