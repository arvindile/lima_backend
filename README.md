# LIMA Backend

FastAPI backend for the LIMA pickleball ranking app. Mirrors the same data
model and scoring logic as the Android app (see `app/scoring.py`, which is a
Python port of the Kotlin `ScoringEngine`).

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

By default it runs against a local SQLite file (`lima.db`) with zero setup —
good for testing the API right away. To use real PostgreSQL instead, copy
`.env.example` to `.env` and fill in your connection string, then load it
before running (e.g. with `python-dotenv`, or export it in your shell).

## Run

```bash
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs for the interactive Swagger UI — you can
try every endpoint from the browser without writing any client code yet.

## Endpoints

- `POST /players` — register a player
- `GET /players/search?q=...` — search by username or ID
- `GET /players/{id}` — get a player
- `PATCH /players/{id}/username` — change username (once per 30 days)
- `POST /matches` — create a match (vanguard, sentinel, optional referee)
- `PATCH /matches/{id}/score` — update the live score
- `POST /matches/{id}/finish` — end the match; applies the 15-min/5-min-per-set
  verification rule, then the skill-gap scoring formula, and updates both
  players' points
- `GET /leaderboard/barangay/{id}` / `city/{id}` / `province/{id}` / `national`
  — top 100, flat sort by points, no proportional-slice aggregation

## Connecting from the Android app

Point Retrofit's base URL at wherever this is hosted. For local testing with
an emulator, Android's emulator reaches your host machine's localhost via
`10.0.2.2` instead of `127.0.0.1` — e.g. `http://10.0.2.2:8000/`.
