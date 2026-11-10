"""Walk the full two-role flow against a running server and record real
request/response samples as Markdown (docs/api-samples.md).

Run it against a THROWAWAY database seeded with `seed_demo`: it onboards
demo_imran, books a job and files reports. Standard library only.

    python scripts/capture_api_samples.py http://127.0.0.1:8010 docs/api-samples.md
"""

import http.cookiejar
import json
import re
import sys
import uuid
from urllib import error, request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8010"
OUT = sys.argv[2] if len(sys.argv) > 2 else "docs/api-samples.md"
DEMO_PASSWORD = "RozgarDemo#2026"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64  # mock OCR only checks the image header
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64  # stand-in recording (container magic only)
MASK = {"csrf_token", "scan_proof"}

sections = []


class Session:
    def __init__(self, label):
        self.label = label
        self.jar = http.cookiejar.CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.jar))
        self.token = None

    def call(self, method, path, body=None, files=None, title=None, note=None, csrf=True, raw=False):
        headers = {"Accept": "application/json"}
        data = None
        shown = body
        if files:
            boundary = uuid.uuid4().hex
            parts = []
            for k, v in (body or {}).items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
            for field, (name, ctype, content) in files.items():
                parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
                              f'filename="{name}"\r\nContent-Type: {ctype}\r\n\r\n').encode() + content + b"\r\n")
            data = b"".join(parts) + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            shown = {**(body or {}), **{f: f"<{n} ({c}, {len(b)} bytes)>" for f, (n, c, b) in files.items()}}
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if csrf and self.token and method != "GET":
            headers["X-CSRFToken"] = self.token
        req = request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            resp = self.opener.open(req, timeout=30)
        except error.HTTPError as exc:
            resp = exc
        payload = resp.read()
        status = resp.status if hasattr(resp, "status") else resp.code
        ctype = resp.headers.get("Content-Type", "")
        parsed = json.loads(payload) if payload and "json" in ctype else None
        if title:
            record(title, self.label, method, path, shown, status, parsed, ctype, len(payload), note,
                   csrf and method != "GET")
        return status, parsed

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.call("POST", path, body, **kw)

    def refresh_csrf(self, title=None):
        _, body = self.get("/api/v1/auth/csrf/", title=title)
        self.token = body["csrf_token"]

    def login(self, username, title=None):
        self.refresh_csrf()
        status, body = self.post("/api/v1/auth/login/", {"username": username, "password": DEMO_PASSWORD},
                                 title=title)
        assert status == 200, body
        self.refresh_csrf()
        return body


def masked(value):
    if isinstance(value, dict):
        return {k: ("<redacted>" if k in MASK else masked(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [masked(v) for v in value]
    return value


def trim(value, depth=0):
    """Keep samples readable: long lists show the first two items."""
    if isinstance(value, list) and len(value) > 2 and depth > 0:
        return [trim(v, depth + 1) for v in value[:2]] + [f"... {len(value) - 2} more"]
    if isinstance(value, list):
        return [trim(v, depth + 1) for v in value[:3]] + ([f"... {len(value) - 3} more"] if len(value) > 3 else [])
    if isinstance(value, dict):
        return {k: trim(v, depth + 1) for k, v in value.items()}
    return value


def record(title, who, method, path, body, status, parsed, ctype, size, note, sends_csrf):
    lines = [f"### {title}", "", f"`{method} {path}` — as **{who}**"
             + (" — header `X-CSRFToken`" if sends_csrf else ""), ""]
    if note:
        lines += [note, ""]
    if body is not None:
        lines += ["Request:", "```json", json.dumps(masked(body), ensure_ascii=False, indent=2), "```", ""]
    lines += [f"Response: **{status}**" + ("" if parsed is not None else f" `{ctype}`, {size} bytes")]
    if parsed is not None:
        lines += ["```json", json.dumps(trim(masked(parsed)), ensure_ascii=False, indent=2), "```"]
    sections.append("\n".join(lines) + "\n")


def main():
    anon = Session("anonymous")
    anon.get("/api/v1/health/", title="Health")
    anon.refresh_csrf(title="CSRF bootstrap")
    anon.post("/api/v1/auth/login/", {"username": "demo_ayesha", "password": DEMO_PASSWORD}, csrf=False,
              title="Login without X-CSRFToken is rejected")

    _, trades = anon.get("/api/v1/catalog/trades/", title="Catalog: trades")
    trade = {t["slug"]: t for t in trades}
    _, specs = anon.get(f"/api/v1/catalog/trades/{trade['electrical']['id']}/specialties/",
                        title="Catalog: specialties of one trade")
    _, areas = anon.get("/api/v1/catalog/service-areas/", title="Catalog: service areas")
    area = {a["sector_code"]: a for a in areas}
    wiring = next(s for s in specs if s["slug"] == "wiring")

    worker = Session("worker demo_imran")
    worker.login("demo_imran", title="Login (worker)")
    worker.get("/api/v1/auth/me/", title="Current user")
    worker.get("/api/v1/workers/me/", title="Worker profile before onboarding")
    worker.post("/api/v1/workers/me/scan/", files={"image": ("blurry.jpg", "image/jpeg", b"\xff\xd8\xff" + PNG)},
                title="ID scan: unreadable photo (mock fixture `blurry`)")
    _, scan = worker.post("/api/v1/workers/me/scan/", files={"image": ("card.png", "image/png", PNG)},
                          title="ID scan (mock OCR, fictional card)",
                          note="Multipart field `image`. `scan_proof` is single-use and expires in 10 minutes.")
    _, profile = worker.call("PUT", "/api/v1/workers/me/", {
        "display_name": "Imran Electric", "experience_years": 7, "trades": [trade["electrical"]["id"]],
        "specialties": [wiring["id"]], "service_areas": [area["G-11"]["id"], area["G-13"]["id"]],
        "scan_proof": scan["scan_proof"]}, title="Create worker profile with the scan proof")
    worker.call("PATCH", "/api/v1/workers/me/availability/", {"accepting_jobs": True},
                title="Set accepting-jobs preference")

    customer = Session("customer docs_customer")
    customer.refresh_csrf()
    customer.post("/api/v1/auth/register/", {"username": f"docs_customer_{uuid.uuid4().hex[:6]}",
                                             "password": DEMO_PASSWORD}, title="Register (always a customer)")
    customer.refresh_csrf()
    customer.get(f"/api/v1/workers/?trade={trade['electrical']['id']}&service_area={area['G-11']['id']}"
                 f"&specialty={wiring['id']}", title="Discover available workers")
    customer.get(f"/api/v1/workers/{profile['id']}/", title="Public worker profile")
    _, job = customer.post("/api/v1/job-requests/", {
        "trade": trade["electrical"]["id"], "service_area": area["G-11"]["id"], "specialty": wiring["id"],
        "description": "Switchboard sparks when the fan is switched on", "address_details": "House 1, Street 1 (demo)",
    }, files={"voice_note": ("recording.webm", "audio/webm", WEBM)},
        title="Post a job request with a voice note",
        note="Multipart; JSON also works without `voice_note`. Needs `description` or `voice_note`.")
    customer.get("/api/v1/job-requests/", title="My requests (customer)")

    worker.get("/api/v1/job-board/", title="Job board (worker)")
    worker.get(f"/api/v1/job-requests/{job['id']}/", title="Request detail as an eligible worker")
    worker.get(job["voice_note_url"], title="Play the voice note")
    _, quote = worker.post(f"/api/v1/job-requests/{job['id']}/quotes/", {"amount": "1500", "message": "Can come at 5pm"},
                           title="Send a quote")
    worker.post(f"/api/v1/job-requests/{job['id']}/quotes/", {"amount": "1700"},
                title="Different second quote is a conflict")

    customer.get(f"/api/v1/job-requests/{job['id']}/quotes/", title="Quotes on my request (owner)")
    _, booking = customer.post(f"/api/v1/quotes/{quote['id']}/accept/", title="Accept a quote")
    url = f"/api/v1/bookings/{booking['id']}/"
    worker.get("/api/v1/workers/me/dashboard/", title="Worker dashboard while booked")
    _, issued = customer.post(f"{url}pin/", title="Issue arrival PIN (customer)",
                              note="The PIN appears only in this response. Sample PIN is from a throwaway database.")
    wrong = "000000" if issued["pin"] != "000000" else "111111"
    worker.post(f"{url}check-in/", {"pin": wrong}, title="Check in with a wrong PIN")
    worker.post(f"{url}check-in/", {"pin": issued["pin"]}, title="Check in with the PIN (worker)")
    worker.post(f"{url}complete/", title="Complete the job (worker)")
    customer.post(f"{url}review/", {"rating": 5, "text": "Quick and tidy.", "tags": ["on_time", "clean_work"]},
                  title="Review the completed booking")
    customer.post(f"{url}reports/", {"reason": "other", "details": "Demo report"}, title="Report (customer)")
    worker.post(f"{url}reports/", {"reason": "payment_dispute"}, title="Report (worker)")
    customer.get("/api/v1/reports/", title="My filed reports")
    customer.get(url, title="Booking detail after completion (customer)")
    anon.get("/api/v1/reviews/tags/", title="Review quick tags")
    anon.get("/api/v1/reports/reasons/", title="Report reasons")
    worker.post("/api/v1/auth/logout/", title="Logout")
    worker.get("/api/v1/auth/me/", title="After logout")

    header = (
        "# API samples (generated)\n\n"
        "Captured by `scripts/capture_api_samples.py` from a real server on a throwaway database seeded with\n"
        "`seed_demo`. Everything is fictional. CSRF tokens and scan proofs are redacted; long lists are trimmed.\n"
        "The contract and error codes are described in [API.md](API.md).\n\n"
    )
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(header + "\n".join(sections))
    print(f"wrote {len(sections)} samples to {OUT}")


if __name__ == "__main__":
    main()
