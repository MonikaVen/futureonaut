# Futureonaut

Docker Compose learning platform: learners play JS games, creators upload or generate them, and scores power a dashboard plus recommendations.

## Stack

- **Frontend:** React + Vite (nginx in production Compose)
- **Backend:** FastAPI + SQLAlchemy
- **Database:** PostgreSQL 16

## Quick start

```bash
cp .env.example .env
# optional: set OPENAI_API_KEY for AI game generation
docker compose up --build
```

Open **http://localhost:3080**

Default admin (from `.env`):

- Email: `admin@example.com`
- Password: `admin12345`

Promote a registered learner to **creator** in the Admin panel to unlock upload / template / AI tools.

### Local development (without rebuilding frontend)

```bash
# terminal 1
docker compose up db
# terminal 2
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://learnplay:learnplay@localhost:5432/learnplay
export GAMES_DIR=./data/games
uvicorn app.main:app --reload --port 8000
# terminal 3
cd frontend && npm install && npm run dev
```

Frontend dev server: http://localhost:5173 (proxies `/api` to the backend).

## Features

| Role | Capabilities |
|------|----------------|
| Guest | Browse and play without an account; progress stays on the device and merges on sign-in |
| Learner | Register, play games, dashboard, recommendations, classrooms, favourites, comments, share cards |
| Creator | Upload HTML/ZIP games, template games, AI generation, classroom assignments |
| Admin | User roles, platform stats, game popularity analytics, full game management |

Catalog filters cover AI / Physics / Math, difficulty, and popularity. The UI is mobile-friendly and available in English plus Baltic and Nordic languages (LT, LV, ET, FI, SV, NO).

### Metrics SDK

Every uploaded or generated game gets `learnplay-sdk.js` injected. Games can call:

- `LearnPlay.score(delta)`
- `LearnPlay.answer({ correct, taskId, points })`
- `LearnPlay.taskStart(taskId)` / `LearnPlay.taskEnd(taskId)`
- `LearnPlay.levelComplete(level, totalLevels)`
- `LearnPlay.complete()`

The play page listens via `postMessage` and posts events to `/api/sessions/{id}/events`.

### Templates

- `quiz`
- `drag_match`
- `timed_challenge`

AI generation uses an OpenAI-compatible Chat Completions API (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`).

Share pages and Open Graph previews use `PUBLIC_BASE_URL` (Compose default: `http://localhost:3080`).

## API health

`GET http://localhost:8000/api/health`
