# The Doppelklick Times

AI-powered Q&A System basierend auf 121 TikTok-Transkripten von @mr.doppelklick.

## Features

- **Dual AI Models**: Claude Opus 4.5 (Anthropic) + GPT-4.1 (OpenAI)
- **RAG System**: Intelligente Suche durch 121 Video-Transkripte
- **Retro Design**: Newspaper-Style UI inspiriert von "The Artificial Times"

## Quick Start

### 1. Backend starten

```bash
cd /Users/michaelhajster/mr.doppelklick

# API Keys setzen
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

# Server starten
uvicorn tiktok_pipeline.answer_api:app --reload --port 8000
```

### 2. Frontend starten

```bash
cd frontend
npm install
npm run dev
```

Frontend läuft auf http://localhost:3000

## Vercel Deployment (Frontend)

1. Push zu GitHub
2. Import in Vercel
3. Environment Variable setzen:
   - `NEXT_PUBLIC_API_URL`: URL deines gehosteten Backends

## Backend Hosting (Optional)

Für Produktion kann das Backend auf Railway, Render oder Fly.io gehostet werden.

## Tech Stack

- **Frontend**: Next.js 16, Tailwind CSS v4, TypeScript
- **Backend**: FastAPI, Python
- **AI**: Claude Opus 4.5, GPT-4.1
- **RAG**: OpenAI Embeddings + Cosine Similarity

## API Endpoints

- `POST /answer` - Frage stellen
- `GET /health` - Health Check
- `GET /models` - Verfügbare Models

---

Built with Claude Code
