# CLAUDE.md

HIPAA-compliant telehealth EMR/EHR for PTSD group therapy.
See `docs/local-dev-context.md` for patient population and clinical context (gitignored).
See `docs/schema.md` for full FHIR resource definitions and data model.
See `docs/pipeline.md` for transcript pipeline detail.

---

## Base template

https://github.com/fastapi/full-stack-fastapi-template (master)
FastAPI + SQLModel + PostgreSQL + Alembic + React + Docker Compose + Traefik.
Package manager: uv. Frontend: React 19, TanStack Router, auto-generated API client.

Follow template conventions unless explicitly told otherwise.
Pattern for new models: `XBase` → `X(XBase, table=True)` → `XCreate`/`XUpdate`/`XPublic`.

---

## Architecture

```
Internet → Traefik → FastAPI (:8000)
                         │
              ┌──────────┴──────────┐
              │                     │
           app_db              HAPI FHIR (:8080)
         (Postgres)                 │
         SQLModel/Alembic        fhir_db
         app.* tables           (Postgres)
                                HAPI internal
```

**Two Postgres databases, two owners:**
- `app_db` — FastAPI owns via SQLModel. Auth, sessions, operational metadata.
- `fhir_db` — HAPI FHIR owns exclusively. Never query this directly.

**FastAPI → HAPI FHIR:** httpx async client + fhir.resources R4B for serialization.
**HAPI FHIR is internal only.** Port 8080 is never exposed outside Docker network.
FastAPI is the sole auth boundary. HAPI has no auth configured.

Additional services (override only):
- `ollama` — local LLM inference, no GPU required (CPU fallback)

---

## Services

| Service | Image | Port (internal) | Port (host, dev only) |
|---|---|---|---|
| backend | local build | 8000 | 8000 |
| frontend | local build | 80 | 5173 |
| db (app_db) | postgres:15 | 5432 | 5432 |
| hapi-fhir | hapiproject/hapi:latest | 8080 | 8080 |
| fhir-db | postgres:15 | 5433 | 5433 |
| adminer | adminer | 8080 | 8081 |
| mailcatcher | schickling/mailcatcher | 1025/1080 | 1025/1080 |
| ollama | ollama/ollama | 11434 | 11434 |
| traefik | traefik | 80/443 | 80/443 |

---

## FHIR layer

**Library:** `fhir.resources` R4B subpackage. Pydantic v2 native — zero friction with FastAPI.
**Import pattern:** `from fhir.resources.R4B.<resource> import <Resource>`
**Do NOT use** `fhirclient`.
**Default version is R5** — always import from `fhir.resources.R4B`.

**FHIR client (`backend/app/fhir/client.py`):**
```python
import httpx
from app.core.config import settings

FHIR_BASE = settings.FHIR_BASE_URL  # http://hapi-fhir:8080/fhir

async def fhir_get(path: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{FHIR_BASE}/{path}")
        r.raise_for_status()
        return r.json()

async def fhir_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{FHIR_BASE}/{path}",
            json=body,
            headers={"Content-Type": "application/fhir+json"},
        )
        r.raise_for_status()
        return r.json()

async def fhir_put(path: str, body: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.put(
            f"{FHIR_BASE}/{path}",
            json=body,
            headers={"Content-Type": "application/fhir+json"},
        )
        r.raise_for_status()
        return r.json()
```

**FHIR resources in use:**
- `Patient` — everyone gets one (minimal: preferred name + contact). Therapy consent upgrades to full clinical record.
- `Practitioner` — therapist
- `Consent` — gates all data collection. Types: therapy_participation, location_sharing, recording_ai, mmj_management. See consent model below.
- `Encounter` — one per group session
- `DocumentReference` — redacted transcript
- `Composition` — progress note (draft → final)
- `Task` — pipeline job tracking (deferred; `PipelineRun` in app_db sufficient for MVP)
- `Observation` — attendance (valueBoolean) and location (lat/lng)
- `AuditEvent` — HIPAA audit trail (written to HAPI directly)

**Custom extension namespace:** `http://compassionateveterans.org/fhir/StructureDefinition/`

**`Patient.identifier` systems:**
- `http://compassionateveterans.org/patient-id` — internal ID
- `http://re-compass.com/patient-id` — links to ReCompass for MMJ management
- `http://va.gov/patient-id` — VA patient ID (deferred, not in v0)

No cannabis card data stored locally. MMJ cards, verification, and documents
live entirely in ReCompass. Integration via API (or link-out for v1).

**Consent model:** Consent is the feature gate, not roles. Everyone starts minimal.
Each FHIR Consent resource unlocks capabilities:
- `therapy_participation` — FHIR Patient becomes full clinical record, HIPAA notice, SOAP/DAP notes
- `location_sharing` — VA requirement, opt-in only
- `recording_ai` — transcript processing + AI note generation
- `mmj_management` — ReCompass manages card. Consent gates cannabis admin access to contact patient and link to ReCompass. Expires with card.
No consent = feature is invisible for that person, not disabled.
Attendance is universal and not consent-gated.

---

## App database models (`backend/app/models.py`)

Replaces template `User`/`Item`. All app.* tables; no PHI.

```python
class UserRole(str, Enum):
    PATIENT = "PATIENT"
    ADMIN_CANNABIS = "ADMIN_CANNABIS"
    PROVIDER = "PROVIDER"
    SUPER_USER = "SUPER_USER"

class AuthProvider(str, Enum):
    GOOGLE = "google"
    APPLE = "apple"
    SMS_OTP = "sms_otp"

class PipelineStage(str, Enum):
    RAW = "raw"
    FILTERED = "filtered"       # in-memory only — never written as content
    REDACTED = "redacted"
    NOTE_GENERATED = "note_generated"
    COMPLETE = "complete"
    FAILED = "failed"

class ZoomSessionStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
```

Tables: `AppUser`, `AuthIdentity`, `ZoomSession`, `PipelineRun`, `TextBlast`.
Full definitions in `docs/schema.md`.

---

## Auth

Replaces template email+password entirely.

| Provider | Endpoint | Notes |
|---|---|---|
| Google OAuth | `GET /auth/google/callback` | authlib |
| Apple OAuth | `GET /auth/apple/callback` | authlib |
| SMS OTP send | `POST /auth/sms/send` | Twilio Verify |
| SMS OTP verify | `POST /auth/sms/verify` | issues JWT |

No passwords. No email/password. Delete template `login.py` password flow.
JWT payload: `{ sub: user_id, role: UserRole, fhir_ref: str|None, exp }`.
Expiry: patients 12h, providers 8h.

`CurrentUser` dep returns `AppUser`. Role deps:
```python
RequireProvider      = require_role(UserRole.PROVIDER, UserRole.SUPER_USER)
RequireAdminCannabis = require_role(UserRole.ADMIN_CANNABIS, UserRole.PROVIDER, UserRole.SUPER_USER)
RequirePatient       = require_role(UserRole.PATIENT, UserRole.PROVIDER, UserRole.SUPER_USER)
RequireSuperUser     = require_role(UserRole.SUPER_USER)
```

---

## API routes

Delete `backend/app/api/routes/items.py`. Add:

- `routes/auth.py` — OAuth + SMS OTP (replaces `login.py`)
- `routes/patients.py` — FHIR Patient CRUD (Provider + Patient self)
- `routes/encounters.py` — Encounter management, attendance, location
- `routes/compositions.py` — Progress note CRUD + review workflow
- `routes/sms.py` — Twilio relay webhook + blast endpoint

---

## Transcript pipeline (`backend/app/pipeline/`)

Asyncio background tasks inside the backend process. No Celery, no separate worker service.

Triggered by Zoom `recording.transcript_completed` webhook or manual Provider action.
Zoom cloud recording provides VTT transcripts with speaker display names — no need for
WhisperX diarization. Speaker identity comes from mapping Zoom display names to
Encounter participants.

```
pipeline/
  worker.py      # task dispatcher; called after Zoom webhook or manual trigger
  vtt_parser.py  # parse Zoom VTT → structured segments with speaker display names
  filter.py      # map display names to fhir_refs; discard unmapped (UNKNOWN) IN MEMORY
  redact.py      # build redacted transcript, POST to HAPI as DocumentReference
  purge.py       # DELETE raw VTT from all storage, write AuditEvent
  notes.py       # Ollama → draft Composition per patient
  notify.py      # set generation-status → review_requested, in-app notification
```

**Privacy invariants — never break:**
1. Unmapped speaker turns discarded in `filter.py` before any write
2. Count only written to `PipelineRun.community_turns_discarded`
3. Raw VTT deleted after `DocumentReference` (redacted) confirmed via HAPI 201
4. No PHI to external services at any pipeline stage

Ollama model: `OLLAMA_MODEL` env var (default `llama3.1:8b`).
Speaker match: display name → `fhir_ref` via Encounter participant list.

---

## SMS (`backend/app/api/routes/sms.py`)

`POST /sms/relay` — Twilio webhook. Forward only from `THERAPIST_NUMBER` env var.
Patient numbers from HAPI: `GET /Patient?active=true` → `telecom[system=phone]`.
Non-PHI content only. TwiML confirmation back to therapist.

Env: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_NUMBER`, `THERAPIST_NUMBER`.

---

## Zoom

`GET /join` — public endpoint. Check `ZoomSession.status == in_progress` →
redirect to Zoom URL. Else return 200 + "no session in progress" message.
Meeting ID from Encounter extension `zoom-meeting-id`.
Zoom for Healthcare plan (Pro). BAA signed.

**Zoom API integration:** Server-to-Server OAuth app on Zoom Marketplace.
`recording.transcript_completed` webhook triggers pipeline.
VTT transcript downloaded via `GET /meetings/{meetingId}/recordings`.
Download URLs expire — always fetch fresh via REST API.

---

## Env vars (add to .env)

```
# FHIR
FHIR_BASE_URL=http://hapi-fhir:8080/fhir
FHIR_DB_PASSWORD=changethis

# Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_NUMBER=
THERAPIST_NUMBER=

# OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
APPLE_CLIENT_ID=
APPLE_CLIENT_SECRET=

# Zoom (Server-to-Server OAuth)
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
ZOOM_ACCOUNT_ID=
ZOOM_WEBHOOK_SECRET_TOKEN=

# Inference
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1:8b
```

---

## Key invariants

1. Community/unknown speakers: no row, no FHIR resource, no content written — ever
2. Raw transcripts: deleted after redacted DocumentReference confirmed
3. PHI: never leaves self-hosted infra
4. SMS: non-PHI content only
5. HAPI FHIR: internal Docker network only, never exposed
6. FHIR is source of truth for clinical data; app_db is operational only
7. Consent gates features: no consent = feature invisible, not disabled
8. Every participant gets a FHIR Patient; therapy consent upgrades to full clinical record
