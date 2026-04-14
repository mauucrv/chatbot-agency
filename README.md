# chatbot-agency

Production-grade WhatsApp chatbot built for a fictional AI consulting agency (**AgencyBot**). Demonstrates a full-stack agentic system: Chatwoot webhooks → LangChain agent (GPT-4o-mini) with 12 tools → appointment booking on Google Calendar, backed by a React admin panel. Spanish-language UX.

> Portfolio project. The brand "AgencyBot" and its data are fictional; the codebase is a generalized version of a real deployment.

## Features

### Messaging
- Chatwoot webhook receiver (text, audio, images)
- Audio transcription via OpenAI Whisper
- Image understanding via GPT-4o Vision
- Message grouping (buffers rapid-fire messages for 3s before replying)
- Rate limiting per phone number — **fail-closed** (rejects if Redis is down)

### Agent & Booking
- LangChain agent with 12 tools: availability checks, CRUD on bookings, services, consultants, info
- Google Calendar FreeBusy API for availability
- Distributed Redis lock on booking creation to prevent double-booking (TOCTOU-safe)
- Configurable booking horizon (default 90 days)

### Bot Control
- Auto-pauses when a human agent replies in Chatwoot
- Auto-resumes when the conversation is marked resolved
- Human-handoff keyword detection (opens conversation for an agent)
- Auto-resume of stale paused conversations (>24h, configurable)

### Scheduled Jobs
- Daily appointment reminders
- Weekly business stats report
- Daily PostgreSQL backup to Google Drive (Fernet-encrypted)
- Periodic Google Calendar sync

### Security
- Webhook signature verification (HMAC or URL token) — mandatory in production
- Hard-fail startup validation of critical env vars in production
- JWT auth (PyJWT) with token blacklist and refresh rotation
- Password complexity (min 12 chars + classes) + timing-safe login
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- Sensitive query params redacted from logs
- Non-root Docker user + resource limits
- Encrypted backups before external upload

### Admin Panel
- React 18 + Vite + TypeScript + Tailwind + shadcn/ui
- ~60 REST endpoints (FastAPI, JWT)
- Roles: `admin` (full CRUD) / `viewer` (read-only)
- Screens: Dashboard, Appointments, Services, Consultants, Clients, Inventory, Sales, Info, Stats, Reports

### Observability
- Structured JSON logs with `structlog`
- Optional Telegram error alerts with Redis-based dedup

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI (async) |
| Agent | LangChain + OpenAI GPT-4o-mini |
| DB | PostgreSQL 15 + SQLAlchemy 2.0 + asyncpg |
| Migrations | Alembic |
| Cache / Locks / Rate limit | Redis 7 |
| Jobs | APScheduler |
| Validation | Pydantic v2 |
| Google APIs | google-api-python-client |
| Frontend | React 18 + Vite + Tailwind + shadcn/ui |
| Containers | Docker + docker-compose |
| Tests | pytest + pytest-asyncio |

## Getting started

### Prerequisites
- Docker + Docker Compose
- OpenAI API key
- A Chatwoot instance (self-hosted or cloud)
- A Google Cloud project with the Calendar API enabled and a service account with calendar access

### Run
```bash
git clone <repo-url>
cd chatbot-agency
cp .env.example .env
chmod 600 .env
# fill in secrets in .env
docker-compose up -d
```

Alembic migrations run automatically on startup (in dev); in production, run them manually with `alembic upgrade head`.

### Configure the Chatwoot webhook
```
URL:    https://your-host/api/webhooks/chatwoot
Events: message_created, conversation_status_changed
Auth:   ?token=<CHATWOOT_WEBHOOK_TOKEN>  (or X-Chatwoot-Signature HMAC)
```

## Tests

```bash
pip install -r requirements.txt
pytest tests/ -v --cov=app --cov-report=term-missing
```

## Architecture notes

- Spanish-language UX; legacy model names (`ServicioBelleza`, `Estilista`) kept intact for migration compatibility — the code originally served a beauty salon use case before being generalized.
- Singletons for the agent, message processor, and service clients.
- All I/O is async.
- Agent temperature deliberately low (0.3) for transactional consistency when booking.

## License

MIT
