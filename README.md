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

Playable AI labs are stored in Postgres (HTML included). The seed pack is used only when the database has no games; later deploys hydrate from the database and do not recreate catalog rows.

- **Liucian's Hungry Bandit** — exploration vs exploitation (ε-greedy)
- **Liucian's Overfit Orchard** — train loss vs test loss
- **Liucian's Precision Pounce** — thresholds, precision, and recall
- **Liucian's Gradient Valley** — learning rate on a loss landscape
- **Liucian's 3D World Model** — configure dynamics so predicted trajectories stay true

Azure Database for PostgreSQL keeps **daily backups for 7 days** (point-in-time restore). `infra/db-snapshot.sh` locks that retention. Named on-demand copies (`fo-daily-YYYYMMDD`) are created on non-burstable SKUs and pruned after a week; the live Burstable server uses the automated daily backups.

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
| Learner | Register, play games, dashboard, recommendations |
| Creator | Upload HTML/ZIP games, template games, AI generation |
| Admin | User roles, platform stats, full game management |

### Metrics SDK

Every uploaded or generated game gets `learnplay-sdk.js` injected. Games can call:

- `LearnPlay.score(delta)`
- `LearnPlay.answer({ correct, taskId, points })`
- `LearnPlay.taskStart(taskId)` / `LearnPlay.taskEnd(taskId)`
- `LearnPlay.complete()`

The play page listens via `postMessage` and posts events to `/api/sessions/{id}/events`.

### Templates

- `quiz`
- `drag_match`
- `timed_challenge`

AI generation uses an OpenAI-compatible Chat Completions API (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`).

## API health

`GET http://localhost:8000/api/health`
