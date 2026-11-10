# Roshan Rozgar (روزگار روشن)

A mobile-first, hyper-local marketplace connecting households in Islamabad with nearby skilled
trade workers. Customers post jobs and receive quotes, accept one, the worker checks in with a
one-time arrival PIN, and the customer reviews the completed job.

> **Status — phase 1 (backend foundation).** Django + DRF project connected to PostgreSQL, a
> custom user model and a health endpoint. Marketplace features, the React/Tailwind client, AI
> services and seed data arrive in later phases.

## Tech stack

| Layer    | Choice                                                        |
| -------- | ------------------------------------------------------------- |
| Language | Python 3.13 (developed on 3.13.7)                             |
| Backend  | Django 5.2 LTS, Django REST Framework, Psycopg 3              |
| Database | PostgreSQL 17 (official `postgres:17` Docker image)           |
| Frontend | React + Tailwind (planned; Vite dev proxy to `/api`)          |

Exact Python package versions are pinned in [backend/requirements.txt](backend/requirements.txt).

## Repository layout

```
backend/            Django project (manage.py, config/, accounts/, requirements.txt)
compose.yaml        Local PostgreSQL service
.env.example        Environment variable template (copy to .env)
```

## Local setup (Windows PowerShell)

Run everything from the repository root.

```powershell
# 1. Environment file
Copy-Item .env.example .env
# Edit .env: set DJANGO_SECRET_KEY, and change DB_PORT (e.g. 5433) if something
# already listens on 5432, such as a native PostgreSQL install.

# 2. Python dependencies
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt

# 3. PostgreSQL (Docker Desktop must be running)
docker compose up -d --wait db

# 4. Database schema
python backend\manage.py migrate
python backend\manage.py createsuperuser   # optional, for /admin/

# 5. Run Django
python backend\manage.py runserver
```

Then open <http://127.0.0.1:8000/api/v1/health/> — expect `{"status":"ok","database":"ok"}`.

If `Activate.ps1` is blocked by execution policy, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or call `.\.venv\Scripts\python.exe`
directly. On macOS/Linux use `python3 -m venv .venv` and `source .venv/bin/activate`.

### Using an existing PostgreSQL instead of Docker

Skip step 3 and point the same variables at your server, then create the role and database once:

```sql
CREATE ROLE roshan_rozgar LOGIN PASSWORD 'local-dev-password';
CREATE DATABASE roshan_rozgar OWNER roshan_rozgar;
```

Set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD` in `.env` (or in the process
environment, which takes precedence over `.env`) to match.

## Configuration

| Variable                      | Purpose                                                    |
| ----------------------------- | ---------------------------------------------------------- |
| `DJANGO_SECRET_KEY`           | Required.                                                  |
| `DJANGO_DEBUG`                | `true`/`false` (also `1/0`, `yes/no`, `on/off`). Defaults to off. |
| `DJANGO_ALLOWED_HOSTS`        | Comma-separated host names.                                |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins, e.g. the Vite dev server.         |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection; also initialise the Compose container. |

## API conventions

- Versioned API under `/api/v1/`; Django Admin at `/admin/`.
- Session authentication with CSRF protection; endpoints require login unless marked public.
- The React client will call relative URLs (`/api/v1/...`) through a Vite dev proxy in
  development and same-origin routing in deployment.
- `GET /api/v1/health/` (public) runs `SELECT 1` against PostgreSQL. Returns `200`
  `{"status":"ok","database":"ok"}`, or `503` `{"status":"unavailable","database":"unavailable"}`
  without connection details.

## Seeded / mocked data

None yet. Seed data for workers, jobs and reviews will be added and listed here.

## AI services and tools

- **Runtime AI services:** none yet; each will be listed here when added.
- **AI coding assistant:** Claude Code (Anthropic) was used to scaffold this backend.

## Known limitations

- Phase 1 only: no marketplace models or account endpoints yet.
- `runserver` checks migrations at startup, so PostgreSQL must be reachable when Django starts.
  If the database goes down afterwards, `/api/v1/health/` returns `503` within about 5 seconds
  (`connect_timeout`).
