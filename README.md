# Roshan Rozgar (روزگار روشن)

A mobile-first, hyper-local marketplace connecting households in Islamabad with nearby skilled
trade workers. Customers post jobs and receive quotes, accept one, the worker checks in with a
one-time arrival PIN, and the customer reviews the completed job.

> **Status — phase 7 (backend complete).** Accounts, catalog, OCR-assisted worker onboarding,
> discovery, job requests with voice notes, quotes, bookings with arrival PIN, reviews, reports and
> the worker dashboard work end to end through the API. Contract: [docs/API.md](docs/API.md);
> captured samples: [docs/api-samples.md](docs/api-samples.md). The React client is next.

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
backend/
  config/      settings, root URLs, /api/v1/ router, health check
  accounts/    custom User (role: customer | worker), session auth endpoints
  catalog/     Trade, Specialty, ServiceArea models, public read-only API, seed_catalog
compose.yaml   Local PostgreSQL service
.env.example   Environment variable template (copy to .env)
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

# 4. Schema and fictional demo data (catalog, demo accounts, sample jobs)
python backend\manage.py migrate
python backend\manage.py seed_demo

# 5. Run Django
python backend\manage.py runserver
```

### Frontend (React + Tailwind, `frontend/`)

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173 — proxies /api to Django on 127.0.0.1:8000
# or, one origin served by Django itself:
npm run build    # writes frontend/dist; restart runserver, then open http://127.0.0.1:8000/
```

Requires Node 20+ (developed on Node 24.12). Use the same host consistently in development
(`localhost:5173` and `127.0.0.1:5173` are both CSRF-trusted in `.env.example`).

Then open <http://127.0.0.1:8000/api/v1/health/> — expect `{"status":"ok","database":"ok"}`.

If `Activate.ps1` is blocked by execution policy, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or call `.\.venv\Scripts\python.exe`
directly. On macOS/Linux use `python3 -m venv .venv` and `source .venv/bin/activate`.

Run the test suite (it creates a temporary `test_<DB_NAME>` database, so the DB user needs
`CREATEDB`; the Compose user has it):

```powershell
python backend\manage.py test accounts catalog workers marketplace
```

(Pass the app labels: run from the repo root, plain `manage.py test` discovers nothing.)

### Demo accounts (local, demo-only)

`seed_demo` creates fictional accounts that all use the password `RozgarDemo#2026`
(override with `--password` or `DEMO_PASSWORD`). It refuses to run with `DJANGO_DEBUG` off.

| Username | Role | State |
| --- | --- | --- |
| `demo_ayesha` | customer | no history — use for the live walkthrough |
| `demo_bilal` | customer | past completed jobs with reviews; one open carpentry request in G-13 |
| `demo_imran` | worker | **fresh** — onboard with the ID scan (mock returns "Imran Ali") |
| `demo_tariq` | worker | fresh spare — name the photo `card-6.jpg` for "Tariq Javed" |
| `demo_akram` | worker | ready: Electrical (wiring, fans), G-11/G-13, rated 4.5 from 2 jobs |
| `demo_naveed` | worker | ready: AC repair + Electrical, G-11/I-10 |
| `demo_rashid` | worker | ready: Plumbing, G-11/G-13/I-10 |
| `demo_sajid` | worker | ready: Carpentry, G-13/F-10 |
| `demo_staff` | staff | Django Admin: catalog, report queue |

Re-run onboarding later with `python backend\manage.py seed_demo --reset-onboarding`
(removes only the profiles of `demo_imran` and `demo_tariq`). Nothing else is ever overwritten.

### Provision a test worker (until worker onboarding exists)

Public registration only creates customers. To get a worker account:
**/admin/ → Users → Add user**, enter a username and password, set **Role = Worker**, save.
`role` is independent of the *Staff* / *Superuser* flags — leave those off for a worker.

### Using an existing PostgreSQL instead of Docker

Skip step 3 and point the same variables at your server, then create the role and database once:

```sql
CREATE ROLE roshan_rozgar LOGIN CREATEDB PASSWORD 'local-dev-password';
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
| `DJANGO_SECURE_COOKIES`       | `true` behind HTTPS: marks session and CSRF cookies `Secure`. Default `false`. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection; also initialise the Compose container. |

## API

All routes are under `/api/v1/`; Django Admin is at `/admin/`. Responses are JSON. Errors use
DRF's shape: field errors as `{"field": ["message"]}`, anything else as `{"detail": "message"}`.

| Method | Path | Auth | Behaviour |
| ------ | ---- | ---- | --------- |
| GET  | `/api/v1/health/` | public | `200 {"status":"ok","database":"ok"}` or `503` |
| GET  | `/api/v1/auth/csrf/` | public | `200 {"csrf_token":"…"}`, sets the `csrftoken` cookie, not cacheable |
| POST | `/api/v1/auth/register/` | public + CSRF | Body `{"username","password"}` only. Creates a **customer**, signs in, `201` user |
| POST | `/api/v1/auth/login/` | public + CSRF | Body `{"username","password"}`. Either role. `200` user |
| GET  | `/api/v1/auth/me/` | session | `200` user; `403` when signed out |
| POST | `/api/v1/auth/logout/` | CSRF | Ends the session, `204` |
| GET  | `/api/v1/catalog/trades/` | public | Active trades |
| GET  | `/api/v1/catalog/trades/<trade_id>/specialties/` | public | Active specialties of an active trade; `404` if the trade is unknown or retired |
| GET  | `/api/v1/catalog/service-areas/` | public | Active service areas |

A **user** is always exactly `{"id": 3, "username": "ustad_akram", "role": "worker"}`.

Registration rejects any other field (e.g. `role`, `is_staff`) with
`400 {"role": ["This field is not allowed."]}`; the role is always set by the server. Usernames
and passwords go through Django's validators; a taken username (case-insensitive) returns
`400 {"username": ["A user with that username already exists."]}`. Wrong username, wrong password
and inactive accounts all return the same `400 {"detail": "Invalid username or password."}`.
A missing or stale CSRF token returns `403 {"detail": "CSRF verification failed. …"}`.

Catalog payloads (sorted by `sort_order`, then English name; service areas by city first):

```json
GET /api/v1/catalog/trades/
[{"id": 1, "slug": "plumbing", "name_en": "Plumbing", "name_ur": "پلمبنگ", "icon_key": "droplet"}, …]

GET /api/v1/catalog/trades/1/specialties/
[{"id": 1, "trade": 1, "slug": "leak-repair", "name_en": "Leak repair", "name_ur": "لیکیج کی مرمت"}, …]

GET /api/v1/catalog/service-areas/
[{"id": 1, "city": "Islamabad", "sector_code": "G-11", "name_en": "G-11", "name_ur": "جی-11"}, …]
```

Use `id` as the stable reference; every trade, including ones added later in Admin, is served
from the same paths, so the frontend needs no change when staff add a trade.

### React session sequence

The session cookie is `HttpOnly` and never read by JavaScript. Use relative URLs (`/api/v1/...`)
so requests go through the Vite proxy in development and stay same-origin in deployment.

1. `GET /api/v1/auth/csrf/` → keep `csrf_token` in memory.
2. `POST` login or register with headers `Content-Type: application/json` and
   `X-CSRFToken: <token>`.
3. **Fetch a fresh token** with `GET /api/v1/auth/csrf/` — Django rotates it on login.
4. Send `X-CSRFToken` on every later `POST`/`PUT`/`PATCH`/`DELETE`, including logout.
5. On app load, call `GET /api/v1/auth/me/`: `200` means signed in, `403` means signed out.

```js
async function csrf() {
  return (await (await fetch("/api/v1/auth/csrf/")).json()).csrf_token;
}

export async function login(username, password) {
  const res = await fetch("/api/v1/auth/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": await csrf() },
    body: JSON.stringify({ username, password }),
  });
  const body = await res.json();
  if (!res.ok) throw body;      // {"detail": ...} or {"field": [...]}
  return body;                  // {id, username, role}; fetch a fresh token before the next POST
}
```

The Vite proxy for `/api` should keep `changeOrigin: true`; the dev origin
(`http://localhost:5173`) is listed in `DJANGO_CSRF_TRUSTED_ORIGINS`.

### Trying it from PowerShell

```powershell
$api = "http://127.0.0.1:8000/api/v1"
$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$t = (Invoke-RestMethod "$api/auth/csrf/" -WebSession $s).csrf_token
Invoke-RestMethod "$api/auth/login/" -Method Post -WebSession $s -ContentType "application/json" `
  -Headers @{ "X-CSRFToken" = $t } -Body '{"username":"ustad_akram","password":"<password>"}'
Invoke-RestMethod "$api/auth/me/" -WebSession $s
$t = (Invoke-RestMethod "$api/auth/csrf/" -WebSession $s).csrf_token   # rotated after login
Invoke-RestMethod "$api/auth/logout/" -Method Post -WebSession $s -Headers @{ "X-CSRFToken" = $t }
Invoke-RestMethod "$api/catalog/trades/"
```

### HTTPS deployment

Serve React and the API from the same origin. Then set `DJANGO_DEBUG=false`,
`DJANGO_SECURE_COOKIES=true` (adds `Secure` to the session and CSRF cookies),
`DJANGO_ALLOWED_HOSTS=<your host>` and `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your host>`. If TLS
is terminated by a proxy, it must forward `X-Forwarded-Proto` and Django needs
`SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` (not yet set).

## Catalog administration

Trades, specialties and service areas are database records edited in **/admin/ → Catalog**.

- **Retire, don't delete:** untick *Is active* to hide an entry from the API. A trade that still
  has specialties cannot be deleted at all.
- Specialty slugs are unique within their trade. Sector codes are normalized on save
  (`g 11`, `G11`, `g_11` → `G-11`) and must be unique per city (case-insensitive).
- `python backend\manage.py seed_catalog` is safe to re-run: it creates only missing entries
  (matched by trade slug, trade + specialty slug, city + sector code) and never changes
  existing ones, so Admin edits and retirements are kept.

## Seeded / mocked data

- `seed_catalog` creates starter trades — Plumbing, Electrical, AC Repair, Carpentry — with 3–4
  sample specialties each, and Islamabad sectors G-11, G-13 and I-10. Urdu names are starter
  translations and should be reviewed by a native speaker.
- No users, workers, jobs or reviews are seeded yet. Test workers are created by hand in Admin.

## AI services and tools

- **Runtime AI services:** none yet; each will be listed here when added.
- **AI coding assistant:** Claude Code (Anthropic) was used to scaffold this backend.

## Known limitations

- No worker self-onboarding, jobs, quotes or reviews yet.
- No login rate limiting or account lockout yet.
- `runserver` checks migrations at startup, so PostgreSQL must be reachable when Django starts.
  If the database goes down afterwards, `/api/v1/health/` returns `503` within about 5 seconds
  (`connect_timeout`).
