# Chronicle - YT to Notes Frontend

A React + TypeScript frontend for converting YouTube videos to structured notes.

## Features

- 🎬 YouTube video transcription
- 📝 AI-powered notes generation with streaming
- 💾 Session management with local storage persistence
- 🌙 Dark purple theme
- ⚡ Fast Vite build

## Project Structure

```
frontend/
├── src/
│   ├── components/          # UI components
│   │   ├── Sidebar/         # Session list sidebar
│   │   ├── MainContent/     # Main content area
│   │   └── common/          # Shared components
│   ├── context/             # React context providers
│   │   └── SessionContext.tsx
│   ├── hooks/               # Custom React hooks
│   │   └── useTranscription.ts
│   ├── services/            # API service modules
│   │   ├── transcriptionApi.ts
│   │   └── notesApi.ts
│   ├── styles/              # Global styles and theme
│   │   └── global.css
│   ├── types/               # TypeScript type definitions
│   │   └── index.ts
│   ├── App.tsx              # Main App component
│   └── main.tsx             # Entry point
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

## Getting Started

### Prerequisites

- Node.js 18+
- Backend server running on `http://localhost:8000`
- Ollama running locally for notes generation

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Opens at `http://localhost:5173`

### Production Build

```bash
npm run build
npm run preview
```

## API Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `POST /api/long-video/transcribe` | Start video transcription |
| `GET /api/long-video/status/:id` | Get transcription status |
| `GET /api/long-video/result/:id` | Get transcription result |
| `POST /notes/from-json` | Generate notes (non-streaming) |
| `POST /notes/stream` | Generate notes (streaming) |
| `GET /notes/health` | Check Ollama status |

## Theme

Dark theme with purple accents:
- Background: `#0a0a0f`
- Primary accent: `#8b5cf6`
- Cards: `#12121a`

## License

MIT
