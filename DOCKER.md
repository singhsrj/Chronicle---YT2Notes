# Docker Deployment Guide

This guide will help you run Chronicle (YT to Notes) with Docker.

## Prerequisites

1. **Docker Desktop** installed and running
2. **Ollama** installed and running on your host machine
3. **An LLM model** pulled in Ollama

### Install Ollama & Pull a Model

```bash
# Install Ollama from https://ollama.com

# Pull the default model (or any model you prefer)
ollama pull llama2:7b

# Verify Ollama is running
ollama list
```

## Quick Start

### 1. Clone and Navigate

```bash
cd "YT VIDEOS TO NOTES APP"
```

### 2. Start Services

```bash
docker-compose up --build
```

### 3. Access the App

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Configuration

### Using a Different Model

Set the `OLLAMA_MODEL` environment variable:

```bash
# Option 1: Set in shell before running
export OLLAMA_MODEL=qwen2.5:7b
docker-compose up --build

# Option 2: Create a .env file
cp .env.example .env
# Edit .env and change OLLAMA_MODEL
docker-compose up --build
```

### Linux Host Configuration

On Linux, Docker can't use `host.docker.internal` by default. Set the Ollama host IP:

```bash
# Option 1: Use Docker's bridge IP
export OLLAMA_HOST=http://172.17.0.1:11434

# Option 2: Use your machine's IP
export OLLAMA_HOST=http://192.168.1.100:11434

docker-compose up --build
```

## Commands Reference

### Start in Background
```bash
docker-compose up -d --build
```

### View Logs
```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

### Stop Services
```bash
docker-compose down
```

### Rebuild After Code Changes
```bash
docker-compose up --build
```

### Remove Everything (including volumes)
```bash
docker-compose down -v
```

## Troubleshooting

### "Could not connect to Ollama"

1. Ensure Ollama is running: `ollama serve`
2. Check if Ollama is accessible: `curl http://localhost:11434/api/tags`
3. On Linux, set `OLLAMA_HOST` environment variable (see above)

### "Model not found"

1. Pull the model: `ollama pull llama2:7b`
2. Or change `OLLAMA_MODEL` to a model you have

### Container Can't Reach Host

On Linux, add to docker-compose.yml under backend service:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

(This is already included in the default config)

### Frontend Shows "Failed to fetch"

1. Check backend is running: `docker-compose logs backend`
2. Verify CORS settings if accessing from different domain
3. Check nginx logs: `docker-compose logs frontend`

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Docker Network                  │
│                                                  │
│  ┌─────────────┐        ┌─────────────────┐    │
│  │  Frontend   │───────▶│     Backend     │    │
│  │  (nginx)    │  proxy │    (FastAPI)    │    │
│  │  :3000      │        │     :8000       │    │
│  └─────────────┘        └────────┬────────┘    │
│                                  │              │
└──────────────────────────────────┼──────────────┘
                                   │
                                   ▼
                         ┌─────────────────┐
                         │     Ollama      │
                         │  (Host Machine) │
                         │    :11434       │
                         └─────────────────┘
```

## Development vs Production

For local development without Docker:

```bash
# Backend
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend
npm run dev
```

The frontend will use `http://localhost:8000` for API calls in development.
