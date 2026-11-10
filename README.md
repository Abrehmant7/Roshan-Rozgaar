# Roshan Rozgar (روزگار روشن)

A mobile-first, hyper-local marketplace that connects households in Islamabad with nearby skilled
trade workers — electricians, plumbers, AC technicians, carpenters — built for workers who do not
read or type comfortably.

- **Workers** create their own account (or use one staff provisioned), photograph their ID card
  (OCR reads the ID number, which is matched against a fictional demo registry), pick trades, skills and sectors by tapping icons, and toggle whether they
  are taking work. They browse nearby jobs, listen to voice notes, quote with preset amounts, check
  in with the customer's PIN and mark the job done.
- **Customers** pick a trade and sector, see available verified workers ranked by skill match and
  rating, post a job by typing and/or recording a voice note, compare quotes, accept one, share a
  one-time arrival PIN, and review the job afterwards.
- **Either side** can privately report the other; **staff** manage the catalog and the report queue
  in Django Admin.

The UI is Urdu-first (right-to-left, Noto Nastaliq Urdu) with an English toggle.

## How the five required outcomes are met

| Outcome | How |
| --- | --- |
| 1. Onboarding without a sign-up form | ID-card photo → OCR → fictional registry match → name pre-filled; trades, skills and areas are icon tiles; experience is a +/− stepper. Nothing needs typing. |
| 2. Discovery | Trade + sector tiles → only **available** workers (complete profile, taking jobs, not on a job), specialty matches first, then rating. |
| 3. Communication | Customer posts text and/or a recorded voice note; workers listen in the app and quote with preset amounts and tap-to-choose messages. |
| 4. Booking | Accepting a quote creates a booking in a locked PostgreSQL transaction; one active booking per worker is a DB constraint, so search and the job board update immediately. A 6-digit arrival PIN confirms the worker is at the door. |
| 5. Trust | Reviews (stars + quick tags) only after completion; ratings and completed-job counts are computed from real bookings; private two-way reports go to a staff queue. |

## Use of AI — and what is simulated

| Component | Barrier it removes | Status |
| --- | --- | --- |
| **ID-card OCR** — [PicToText](https://pictotext.io/docs/reference/asia/pakistan/id-card), called server-side by `backend/workers/ocr.py` | Literacy: a worker creates a profile from one photo instead of filling a form. Without it, onboarding falls back to typing a name and ID number. | **Live adapter implements the PicToText contract** (`POST https://pictotext.io/api/v1/ocr`, `Authorization: Bearer <key>`, multipart `image` + `documentType=pk_id_card`, top-level `idNumber`). Verified against the real service up to the account: the key authenticates, but the account currently answers **HTTP 402 `INSUFFICIENT_CREDITS`**, so a successful live read is **unverified** until credits are added. **Mock mode** (`OCR_MODE=mock`) runs the demo and shows a "simulated demo scan" label. Either way, the ID is matched against a **fictional** registry and labelled as such. |
| Urdu read-aloud | Literacy: speaker buttons read headings aloud | Uses the browser's built-in speech synthesis; shown only when the device has an Urdu voice. No external service. |

There is **no speech recognition**: voice notes are recorded and played back for a human to listen
to, not transcribed. Identity verification against government databases is out of scope; the
"registry" is a fictional list (`backend/workers/identity.py`). **AI coding assistant:** Claude
Code (Anthropic, model Claude Opus) wrote and tested this code with the team.

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.13 (3.13.7), Django 5.2 LTS, Django REST Framework 3.18, Psycopg 3 |
| Database | PostgreSQL 17 (official `postgres:17` image via `compose.yaml`) |
| Frontend | React 18, React Router 6, Tailwind CSS 4, Vite 6, lucide-react icons, Noto Nastaliq Urdu (via @fontsource, bundled locally) |
| Auth | Django sessions (HttpOnly cookie) + CSRF, same origin |

Versions are pinned in [backend/requirements.txt](backend/requirements.txt) and
[frontend/package-lock.json](frontend/package-lock.json).

```
backend/
  config/       settings, URLs (API, Admin, built SPA), shared API errors/permissions
  accounts/     User with role customer|worker; session auth endpoints
  catalog/      Trade, Specialty, ServiceArea (+ seed_catalog)
  workers/      WorkerProfile, ID scan (OCR adapter, fictional registry), scan proofs
  marketplace/  JobRequest + voice notes, discovery, Quote, Booking, ArrivalPin, Review,
                Report, worker dashboard, seed_demo
frontend/       React app (worker + customer screens)
docs/           API contract and captured request/response samples
scripts/        API sample capture, browser end-to-end tests
```

## Prerequisites

Python 3.13, Node 20+ (developed on 24.12), and either Docker Desktop or an existing PostgreSQL
16+ server. Commands below are for Windows PowerShell from the repository root.

## Setup

```powershell
# 1. Environment
Copy-Item .env.example .env
# Edit .env: set DJANGO_SECRET_KEY. If something already listens on 5432 (e.g. a native
# PostgreSQL), set DB_PORT=5433 for the Docker database.

# 2. Backend dependencies
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt

# 3. PostgreSQL
docker compose up -d --wait db

# 4. Schema and fictional demo data (idempotent; never overwrites existing data)
python backend\manage.py migrate
python backend\manage.py seed_demo

# 5. Frontend
cd frontend; npm install; npm run build; cd ..
```

If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once or
call `.\.venv\Scripts\python.exe` directly.

**Existing PostgreSQL instead of Docker:** skip step 3, create the role and database once
(`CREATE ROLE roshan_rozgar LOGIN CREATEDB PASSWORD '…'; CREATE DATABASE roshan_rozgar OWNER
roshan_rozgar;`) and point `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` at it.
Process environment variables override `.env`.

## Run

```powershell
python backend\manage.py runserver        # app + API + Admin on http://127.0.0.1:8000/
```

With the frontend built, Django serves everything from one origin: the app at `/`, the API at
`/api/v1/`, Admin at `/admin/`. Restart `runserver` after the first `npm run build`.

For frontend development with hot reload, also run `cd frontend; npm run dev` and open
<http://localhost:5173> — Vite proxies `/api` to Django. Use one host consistently
(`localhost:5173` and `127.0.0.1:5173` are both CSRF-trusted in `.env.example`).

Health check: <http://127.0.0.1:8000/api/v1/health/> → `{"status":"ok","database":"ok"}`.

## Test

```powershell
python backend\manage.py check
python backend\manage.py test accounts catalog workers marketplace   # 107 tests, real PostgreSQL
cd frontend; npm run build; cd ..
```

Pass the app labels when running from the repo root. Tests create a temporary `test_<DB_NAME>`
database (the Compose user has `CREATEDB`). They include PostgreSQL concurrency races (competing
quote acceptances, one worker booked on two requests at once, case-variant signups). Tests always
use mock OCR (`config.test_runner.OfflineOcrRunner`) even when `.env` selects live, so they never
spend PicToText credits; the live adapter is tested against PicToText's documented responses with
the network faked.

Browser end-to-end tests (phone-sized, two independent sessions) drive the real UI and API. They
need Playwright (`pip install playwright`) and Microsoft Edge, and they create data, so run them
against a demo database:

```powershell
python backend\manage.py seed_demo --reset-onboarding
python scripts\e2e\two_role_walkthrough.py http://127.0.0.1:8000
python backend\manage.py seed_demo --reset-onboarding
python scripts\e2e\worker_flow.py http://127.0.0.1:8000
# loading/retry/session/logout/stale-data/signup checks; run against Vite dev AND the build:
python scripts\e2e\regression_checks.py http://localhost:5173 dev
python scripts\e2e\regression_checks.py http://127.0.0.1:8000 prod
```

Run the Django server for these with `OCR_MODE=mock` (e.g. `$env:OCR_MODE="mock"` in PowerShell
before `runserver`); process environment variables override `.env`.

## Demo accounts (local, demo-only)

`seed_demo` creates **fictional** accounts that all use the password `RozgarDemo#2026`
(override with `--password` or `DEMO_PASSWORD`). It refuses to run with `DJANGO_DEBUG` off.

| Username | Role | State |
| --- | --- | --- |
| `demo_ayesha` | customer | no history — use for the live walkthrough |
| `demo_bilal` | customer | completed jobs with reviews; one open carpentry request in G-13 |
| `demo_imran` | worker | **fresh** — onboard live; any photo gives "Imran Ali" (mock card-5) |
| `demo_tariq` | worker | fresh spare — name the photo `card-6.jpg` for "Tariq Javed" |
| `demo_akram` | worker | ready: Electrical (wiring, fans), G-11 / G-13, 4.5★ from 2 jobs |
| `demo_naveed` | worker | ready: AC repair + Electrical, G-11 / I-10, 4★ |
| `demo_rashid` | worker | ready: Plumbing, G-11 / G-13 / I-10, 5★ |
| `demo_sajid` | worker | ready: Carpentry, G-13 / F-10, new worker |
| `demo_staff` | staff | Django Admin: catalog, users, report queue |

To show onboarding again: `python backend\manage.py seed_demo --reset-onboarding` (removes only
the profiles of `demo_imran` and `demo_tariq`).

**New workers** sign up themselves: worker login → "نیا کاریگر اکاؤنٹ بنائیں" (`/register?role=worker`,
API `POST /api/v1/auth/register/worker/`). The server sets the worker role; the account lands on
`/w/onboard` and stays out of discovery and quoting until the ID scan and profile are complete.
Staff can still create workers in **Admin → Users → Add user** (Role = Worker); staff and
superuser flags are only ever set in Admin.

## Live OCR (PicToText) — local settings

Put these in the git-ignored root `.env` (see `.env.example`):

```
OCR_MODE=live
OCR_ENDPOINT=https://pictotext.io/api/v1/ocr
OCR_DOCUMENT_TYPE=pk_id_card
OCR_TIMEOUT_SECONDS=25
OCR_API_KEY=<your PicToText key>
```

Restart `runserver` after editing. `python backend\manage.py check` warns (`workers.W001`) if live
mode has no key. The key is used only in the server's `Authorization` header; it is never returned,
logged, sent to React or committed. Scan errors are explicit: `ocr_not_configured` (no key or bad
document type), `ocr_auth_rejected` (401/403), `ocr_quota_exceeded` (402 credits, 429 rate),
`image_rejected` (400 bad image), `ocr_timeout`, `ocr_unavailable` (5xx/network), `id_not_found`
(no `idNumber`), `id_not_registered` (not in the fictional registry), `identity_in_use`.

Live mode reads real photos, so the number on the card must be one of the fictional registry
numbers (`00000-000000N-N`, N = 1…9, e.g. `00000-0000007-7` → "Faisal Mahmood"). Use a printed or
on-screen **fictional** card marked as a demo — never a real CNIC. Switch back with `OCR_MODE=mock`.

## Demo walkthrough (two phones or two browser windows)

1. **Worker** (`demo_imran`): "میں کاریگر ہوں" → log in → "پروفائل بنائیں" → take/choose any photo →
   the yellow *simulated demo scan* label and "Imran Ali" appear → confirm → tap *Electrical*,
   optionally *Wiring*, tap *G-11* → save. Status: available.
2. **Customer** (`demo_ayesha`): "مجھے کاریگر چاہیے" → log in → tap *Electrical*, *Wiring*, *G-11* —
   Imran (skill match) and Akram/Naveed appear → "کام کی درخواست بھیجیں" → type a line and record a
   voice note (or choose an audio file if the microphone is blocked) → send.
3. **Worker**: *New jobs* → open the request → play the voice note → tap *1500* and a message →
   send quote.
4. **Customer**: *My requests* → the request → *Accept*. Search again: Imran is gone (busy).
5. **Customer**: on the booking, "آمد کا PIN بنائیں" → read the 6 digits to the worker.
6. **Worker**: Home → current job → enter the PIN on the keypad (try a wrong one first) →
   *In progress* → "کام مکمل ہو گیا" twice → completed; Imran is available again.
7. **Customer**: rate 5 stars + a tag; optionally *Report a problem*. **Worker** can report too.
8. **Staff** (`demo_staff` at `/admin/`): *Marketplace → Reports* → filter *Open* → select →
   *Mark selected reports resolved*. *Catalog → Trades → Add* a new trade: it appears in the app
   on reload with no code change.
9. Repeat a booking in another trade (e.g. carpentry with `demo_tariq` in G-13) — same screens.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Required. Also keys the identity digests and PIN digests. |
| `DJANGO_DEBUG` | `true`/`false` (also `1/0`, `yes/no`, `on/off`). Default off. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins (e.g. the Vite dev server). |
| `DJANGO_SECURE_COOKIES` | `true` behind HTTPS (Secure session/CSRF cookies). Default `false`. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL; also initialise the Compose container. |
| `OCR_MODE` | `mock` (default) or `live` (PicToText). |
| `OCR_ENDPOINT`, `OCR_DOCUMENT_TYPE`, `OCR_API_KEY`, `OCR_TIMEOUT_SECONDS` | PicToText endpoint (`https://pictotext.io/api/v1/ocr`), `pk_id_card`, Bearer key (server-side only), timeout (25 s). |
| `OCR_MAX_IMAGE_BYTES`, `OCR_SCAN_RATE`, `SCAN_PROOF_TTL_SECONDS` | Scan limits (5 MB, 30/hour, 10 min). |
| `VOICE_NOTE_MAX_BYTES` | Voice note cap (5 MB). |
| `PIN_TTL_SECONDS`, `PIN_MAX_ATTEMPTS`, `PIN_ISSUE_LIMIT`, `PIN_ISSUE_WINDOW_SECONDS` | Arrival PIN: 15 min, 5 tries, 5 PINs per 15 min. |
| `PRIVATE_MEDIA_ROOT` | Where voice notes are stored (default `backend/private_media/`, never served publicly). |
| `DEMO_PASSWORD` | Password for `seed_demo` accounts. |

## API

Contract: [docs/API.md](docs/API.md) — every route, field, status, action and error code, upload
field names (`image`, `voice_note`) and the CSRF sequence. Real captured request/response pairs:
[docs/api-samples.md](docs/api-samples.md) (regenerate with `scripts/capture_api_samples.py`
against a throwaway database).

Mapping kept from earlier phases: the brief's "job request" is `JobRequest` at
`/api/v1/job-requests/`; worker discovery is `GET /api/v1/workers/`; the worker board is
`GET /api/v1/job-board/`; booking statuses are `BOOKED`, `IN_PROGRESS`, `COMPLETED`, and an
unbooked request reports `OPEN`.

## Seeded and mocked — everything here is fictional

- **Catalog** (`seed_catalog`): Plumbing, Electrical, AC Repair, Carpentry with 3–4 specialties
  each; Islamabad sectors G-11, G-13, I-10, F-10, G-9, I-8. Urdu labels are starter translations.
- **Demo data** (`seed_demo`): the accounts above, four ready worker profiles marked as
  *simulated verification*, four completed past jobs with reviews, one open carpentry request.
- **OCR**: mock mode with fixtures chosen by file-name keyword — `card-1`…`card-9` (fictional
  registry cards), no keyword → the first fictional card not yet linked to another worker,
  `blurry` (unreadable), `unregistered` (not in registry), `ocr-error` (provider failure). All IDs
  use the non-existent `00000-` prefix. The image and raw ID number are never stored, logged or
  returned (only a masked form and a keyed digest). Live mode sends the image to PicToText.
- **Identity registry**: a hard-coded fictional list (9 people), standing in for a government
  lookup. Every match is labelled "fictional demo registry" in the app and `"registry": "fictional"`
  in the API, including when PicToText read the card live.
- **Payments**: none. The agreed price is recorded; money changes hands outside the app.

## Known limitations

- A successful live PicToText read is unverified: the configured account returns HTTP 402
  `INSUFFICIENT_CREDITS` (see *Use of AI*).
- Voice notes are not transcribed or translated; no speech recognition.
- Location is manual sector selection; no maps or distance ranking. One city (Islamabad) is seeded.
- No cancellation flow: a booking stuck in `BOOKED` (e.g. a no-show) is corrected by staff in
  Admin → Bookings; the customer can file a `no_show` report.
- Updates arrive by polling (8–15 s), not push notifications.
- No login rate limiting or lockout (scan, PIN issue and PIN guesses are limited).
- Urdu read-aloud depends on the device having an Urdu voice; many desktop browsers do not.
- No password reset or account deletion flow; login is case-sensitive while usernames are unique
  case-insensitively.
- The Figma prototype was not available to the developer, so the visual design is original and
  only follows the brief's written guidance (mobile-first, Urdu RTL, large tap targets).
- `runserver` needs PostgreSQL reachable at start-up; `/api/v1/health/` reports `503` if it later
  drops. For HTTPS deployment set `DJANGO_DEBUG=false`, `DJANGO_SECURE_COOKIES=true`, proper
  `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS`, serve `/static/` (e.g. `collectstatic`
  behind a web server) and, behind a TLS proxy, `SECURE_PROXY_SSL_HEADER`.

## Credits

Open-source libraries: Django, Django REST Framework, Psycopg, React, React Router, Vite,
Tailwind CSS, lucide-react (ISC), Noto Nastaliq Urdu font (SIL Open Font License, via
@fontsource), Playwright (tests only). No templates or prior-project code were used.
