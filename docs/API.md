# Roshan Rozgar API contract (v1)

All routes are under `/api/v1/`. Real captured request/response pairs for every step of the flow
are in [api-samples.md](api-samples.md) (regenerate with `scripts/capture_api_samples.py`).

## Conventions

- **Auth:** Django session cookie (`sessionid`, HttpOnly) + CSRF. Call `GET /auth/csrf/`, send the
  token as `X-CSRFToken` on every `POST`/`PUT`/`PATCH`/`DELETE` (login and registration included),
  and fetch a fresh token after login or registration (Django rotates it).
- **Same origin:** use relative URLs. In development Vite proxies `/api` to Django.
- **IDs** are integers and stable. **Statuses**, **error codes**, **actions**, **tags** and **reasons**
  are machine-readable keys; never parse display text.
- **Money:** decimal strings in PKR (`"1500.00"`) with `"currency": "PKR"`.
- **Timestamps:** ISO 8601 with offset, server zone Asia/Karachi (`2026-11-10T14:04:48+05:00`).
- **Lists** marked *paged* return `{"count", "next", "previous", "results"}`; `?page=N&page_size=M`
  (default 20, max 50). Empty result: `{"count": 0, "next": null, "previous": null, "results": []}`.

### Errors

| Kind | Status | Body |
| --- | --- | --- |
| Field validation | 400 | `{"field": ["message", ...]}` |
| Everything else | 400/403/404/409/422/429/503 | `{"detail": "message", "code": "stable_code", ...extra}` |

Codes in use:

| Code | Status | When |
| --- | --- | --- |
| `csrf_failed` | 403 | Missing/stale `X-CSRFToken` |
| `not_authenticated` | 403 | No session |
| `customer_role_required` / `worker_role_required` | 403 | Wrong role for the action |
| `invalid_credentials` | 400 | Login failed (same answer for every cause) |
| `not_found` | 404 | Missing **or not yours** (IDs cannot be probed) |
| `profile_not_found` | 404 | Worker has no profile yet → show onboarding |
| `profile_incomplete` | 403 | Job board before onboarding |
| `id_not_found` / `id_not_registered` | 422 | Scan unreadable / ID not in registry (`retryable: true`) |
| `identity_in_use` | 409 | ID card already linked to another worker |
| `ocr_unavailable` | 503 | OCR provider failed or timed out (`retryable: true`) |
| `throttled` | 429 | Too many scans (default 30/hour) |
| `voice_note_missing` | 404 | No voice note, or the file is gone |
| `quote_exists` | 409 | A different quote already sent (`quote_id` included) |
| `request_not_open` | 409 | Quoting on a booked request |
| `request_already_booked` | 409 | Another quote was accepted first |
| `worker_unavailable` | 409 | Worker busy, paused or profile incomplete |
| `invalid_booking_status` | 409 | Action not valid in the current status (`status` included) |
| `no_active_pin` / `pin_expired` / `pin_locked` | 409 | Ask the customer for a new PIN |
| `pin_incorrect` | 400 | Wrong PIN (`attempts_remaining` included) |
| `pin_issue_throttled` | 429 | More than 5 PINs in 15 minutes |
| `check_in_required` | 409 | Completing before check-in |
| `booking_not_completed` | 409 | Reviewing before completion |
| `review_exists` / `report_exists` | 409 | Duplicate |

## Roles and availability

`role` is `customer` or `worker` (independent of Django staff flags). Public registration always
creates customers; worker accounts are provisioned by staff (Admin or `seed_demo`).

A worker is **available** when all hold: active worker account, profile with ≥1 active trade and ≥1
active service area (`is_complete`), `accepting_jobs = true`, and no booking in `BOOKED` or
`IN_PROGRESS`. Discovery, quoting and acceptance all use this one rule.

## Endpoints

### Health, auth, catalog (Phases 1–2)

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| GET | `/health/` | public | `{"status":"ok","database":"ok"}` or 503 |
| GET | `/auth/csrf/` | public | `{"csrf_token"}` |
| POST | `/auth/register/` | public + CSRF | `{"username","password"}` only → 201 user, signed in |
| POST | `/auth/login/` | public + CSRF | → 200 user |
| GET | `/auth/me/` | session | user `{"id","username","role"}` |
| POST | `/auth/logout/` | CSRF | 204 |
| GET | `/catalog/trades/` | public | `[{"id","slug","name_en","name_ur","icon_key"}]` |
| GET | `/catalog/trades/<trade_id>/specialties/` | public | `[{"id","trade","slug","name_en","name_ur"}]` |
| GET | `/catalog/service-areas/` | public | `[{"id","city","sector_code","name_en","name_ur"}]` |

### Worker onboarding (Phase 3)

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| POST | `/workers/me/scan/` | worker | **multipart field `image`** (JPEG/PNG/WebP, ≤ 5 MB) → 201 `{"mode","simulated","identity":{"name_en","name_ur","id_masked"},"scan_proof","expires_at"}` |
| GET | `/workers/me/` | worker | profile or 404 `profile_not_found` |
| PUT | `/workers/me/` | worker | `{"display_name","experience_years" (0–60),"trades":[ids],"specialties":[ids],"service_areas":[ids],"accepting_jobs","scan_proof"}`; `scan_proof` required to create (201), optional on edit (200) |
| PATCH | `/workers/me/availability/` | worker | `{"accepting_jobs": bool}` → `{"accepting_jobs","is_available"}` |
| GET | `/workers/me/dashboard/` | worker | `profile_status` (`missing`/`incomplete`/`complete`), `is_available`, `active_booking` (booking or null), `completed_jobs`, `rating`, `pending_quotes`, `open_jobs_matching`, `recent_jobs`, `links` |

Profile response: `id, display_name, experience_years, trades, specialties, service_areas, accepting_jobs,
is_complete, is_available, verification{name,id_masked,verified_at,simulated}, created_at, updated_at`.
Specialties must belong to a selected trade; inactive catalog IDs are rejected per field.

**Mock OCR fixtures** (`OCR_MODE=mock`, chosen by keywords in the uploaded file name):
`card-1`…`card-6` → fictional registry cards (default `card-5` = Imran Ali), `blurry` → 422
`id_not_found`, `unregistered` → 422 `id_not_registered`, `ocr-error` → 503 `ocr_unavailable`.

### Discovery and requests (Phase 4)

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| GET | `/workers/?trade=<id>&service_area=<id>[&specialty=<id>]` | signed in | *paged* worker cards. Order: specialty match, rating (unrated last), id |
| GET | `/workers/<id>/` | signed in | card + `recent_reviews` (no reviewer identity, no report data) |
| POST | `/job-requests/` | customer | JSON, or **multipart with `voice_note`** (WebM/Ogg/MP4/MP3/AAC/WAV, ≤ 5 MB). Fields `trade`, `service_area`, optional `specialty`, `description` (≤1000), optional `address_details` (≤300, private). Needs description or voice note |
| GET | `/job-requests/` | customer | *paged* own requests, newest first, with `quote_count` |
| GET | `/job-requests/<id>/` | owner / eligible worker / assigned worker | owner also gets `address_details`, `customer`, `quotes`, `booking`; eligible worker gets public fields + `my_quote` |
| GET | `/job-requests/<id>/voice-note/` | same as detail | audio stream, `Cache-Control: private, no-store` |
| GET | `/job-board/` | onboarded worker | *paged* open requests in the worker's active trades and areas, each with `my_quote`; top-level `worker_is_available` |

Worker card: `id, display_name, experience_years, trades, specialties, service_areas, verified,
verification_simulated, rating{average|null, count}, completed_jobs, is_available[, matches_specialty]`.

Request: `id, status, trade{…}, service_area{…}, specialty{…}|null, description, has_voice_note,
voice_note_url, created_at, viewer` (+ private fields above). `status` is `OPEN` until booked, then the
booking status. Once booked, only the owner and the assigned worker can see the request or its audio.

### Quotes, bookings, PIN (Phase 5)

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| POST | `/job-requests/<id>/quotes/` | available eligible worker | `{"amount":"1500.00","message"?}` → 201; identical retry 200 |
| GET | `/job-requests/<id>/quotes/` | owner (all) / worker (own) | quotes with worker cards, cheapest first |
| GET | `/quotes/` | worker | *paged* own quotes with `job_summary` |
| POST | `/quotes/<id>/accept/` | request owner | → 201 booking; same-quote retry 200 |
| GET | `/bookings/[?status=BOOKED,IN_PROGRESS,COMPLETED]` | participant | *paged* own bookings |
| GET | `/bookings/<id>/` | participant | booking |
| POST | `/bookings/<id>/pin/` | customer, `BOOKED` | → 201 `{"pin","expires_at","booking"}`; replaces any earlier PIN |
| POST | `/bookings/<id>/check-in/` | assigned worker, `BOOKED` | `{"pin":"123456"}` → booking `IN_PROGRESS` |
| POST | `/bookings/<id>/complete/` | assigned worker, `IN_PROGRESS` | → `COMPLETED`; retry-safe |

Quote: `id, job_request, amount, currency, message, status (PENDING|ACCEPTED|NOT_SELECTED), created_at[, worker]`.

Booking: `id, status (BOOKED|IN_PROGRESS|COMPLETED), amount, currency, quote_id, booked_at,
checked_in_at, completed_at, viewer (customer|worker), actions, active_pin {expires_at,
attempts_remaining}|null, review|null, my_report|null, worker{card}, customer{id,username}, job_request{…}`.
The PIN itself never appears outside the issue response.

**`actions`** — render only these controls: `issue_pin`, `check_in`, `complete`, `review`, `report`.

### Reviews, reports (Phase 6)

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| GET | `/reviews/tags/` | public | `[{"key","name_en","name_ur"}]` |
| POST | `/bookings/<id>/review/` | booking customer, `COMPLETED` | `{"rating":1-5,"text"?,"tags"?:[keys]}` → 201; once per booking |
| GET | `/reports/reasons/` | public | `[{"key","name_en","name_ur"}]` |
| POST | `/bookings/<id>/reports/` | either participant | `{"reason","details"?}` → 201; subject is the other participant; once per participant |
| GET | `/reports/` | signed in | *paged* reports **you filed** (`status`: OPEN/RESOLVED/DISMISSED) |

Reports are visible only to the reporter and staff (Admin → Marketplace → Reports: filter by status
and reason, "Mark resolved" / "Dismiss" actions record who and when).
