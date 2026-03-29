# Development

## Prerequisites

- Docker + Docker Compose
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [Bun](https://bun.sh) (`curl -fsSL https://bun.sh/install | bash`)

## Setup

### 1. Clone and configure

```bash
git clone <your-repo> && cd <your-repo>
cp .env.example .env
```

Edit `.env` and fill in at minimum:

| Variable | Required for | Where to get it |
|---|---|---|
| `SECRET_KEY` | JWT signing | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `POSTGRES_PASSWORD` | app_db | any strong password |
| `FHIR_DB_PASSWORD` | fhir_db | any strong password |
| `TWILIO_ACCOUNT_SID` | SMS | twilio.com/console |
| `TWILIO_AUTH_TOKEN` | SMS | twilio.com/console |
| `TWILIO_NUMBER` | SMS | purchased Twilio number |
| `THERAPIST_NUMBER` | SMS relay | therapist's mobile, E.164 format |
| `GOOGLE_CLIENT_ID` | OAuth | console.cloud.google.com |
| `GOOGLE_CLIENT_SECRET` | OAuth | console.cloud.google.com |

Apple OAuth and Ollama vars can be left empty to start.

### 2. Add local dev context (never committed)

```bash
cp docs/local-dev-context.example.md docs/local-dev-context.md
# Edit with your actual patient population and clinical context
```

This file is read by Claude Code for session context. It is in `.gitignore`.

### 3. Start the stack

```bash
docker compose up -d
```

This starts: FastAPI backend, React frontend, app Postgres, HAPI FHIR, FHIR Postgres.

**First startup takes ~2 minutes** — HAPI FHIR initialises its database schema on boot.
Watch for readiness:

```bash
docker compose logs -f hapi-fhir | grep "Started Application"
```

### 4. Verify services

| Service | URL | What to check |
|---|---|---|
| API docs | http://localhost:8000/docs | FastAPI Swagger UI |
| HAPI FHIR UI | http://localhost:8080 | FHIR browser (dev only) |
| Adminer | http://localhost:8081 | Database web admin |
| Frontend | http://localhost:5173 | React app |
| MailCatcher | http://localhost:1080 | Captured emails |
| Traefik UI | http://localhost:8090 | Proxy routing |
| app_db | localhost:5432 | psql / any Postgres client |

Quick FHIR smoke test:
```bash
curl http://localhost:8080/fhir/metadata | python -m json.tool | head -20
```

### 5. Run Alembic migrations

```bash
docker compose exec backend alembic upgrade head
```

### 6. Seed a superuser

```bash
docker compose exec backend python scripts/seed_superuser.py
```

### 7. Pull Ollama model (optional, needed for pipeline)

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

### 8. Generate the frontend API client

After any backend route change:
```bash
bash scripts/generate-client.sh
```

---

## Architecture at a glance

```
                    Docker network (internal)
  ┌─────────────────────────────────────────────────┐
  │                                                 │
  │  FastAPI :8000  ──FHIR REST──▶  HAPI FHIR :8080│
  │       │                               │         │
  │       ▼                               ▼         │
  │   app_db :5432                   fhir_db :5433  │
  │  (users, sessions,            (HAPI internal —  │
  │   blasts, pipeline)            never touch)     │
  │                                                 │
  │  Ollama :11434  (local inference, no GPU needed)│
  └─────────────────────────────────────────────────┘
         ▲
  Traefik (TLS termination in production)
```

**Two Postgres, two owners.** FastAPI owns `app_db` via SQLModel/Alembic.
HAPI FHIR owns `fhir_db` — never connect to it directly.
HAPI FHIR is not exposed outside the Docker network in production.

---

## Common tasks

```bash
# Backend shell
docker compose exec backend bash

# Run tests
docker compose exec backend bash scripts/tests-start.sh

# Tail pipeline logs
docker compose logs -f backend | grep pipeline

# Reset HAPI FHIR (wipes all FHIR data)
docker compose down hapi-fhir fhir-db
docker volume rm <project>_fhir-db-data
docker compose up -d hapi-fhir fhir-db

# Add a Python dependency
docker compose exec backend uv add <package>
```

---

## Local development without Docker

The Docker Compose services use the same ports as local dev servers. You can stop a Docker service and run it locally instead:

```bash
# Frontend
docker compose stop frontend
bun run dev

# Backend
docker compose stop backend
cd backend
fastapi dev app/main.py
```

---

## Docker Compose watch

For hot-reload via Docker (alternative to `up -d`):

```bash
docker compose watch
```

`compose.yml` is the main stack. `compose.override.yml` adds dev overrides (volume mounts, Traefik, Mailcatcher, exposed ports). Both are loaded automatically by `docker compose`.

After changing `.env` vars, restart:

```bash
docker compose watch
```

---

## Subdomain testing with Traefik

To test subdomain-based routing locally (mirrors production):

```dotenv
DOMAIN=localhost.tiangolo.com
```

This domain and all subdomains resolve to `127.0.0.1`. Traefik routes `api.localhost.tiangolo.com` → backend, `dashboard.localhost.tiangolo.com` → frontend.

---

## Pre-commits

Using [prek](https://prek.j178.dev/) (modern pre-commit alternative). Config in `.pre-commit-config.yaml`.

Install (from `backend/` folder):

```bash
uv run prek install -f
```

Run manually:

```bash
uv run prek run --all-files
```
