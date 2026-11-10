"""Browser regression checks for the review fixes (run against Vite dev AND the production build).

  python scripts/e2e/regression_checks.py http://localhost:5173      # Vite dev, React Strict Mode
  python scripts/e2e/regression_checks.py http://127.0.0.1:8000      # production build served by Django

Needs: seed_demo data, OCR_MODE=mock on the Django server, Playwright + Microsoft Edge.
Creates a new worker and customer requests; run against a demo database.
"""

import json
import re
import sys
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
TAG = sys.argv[2] if len(sys.argv) > 2 else "run"
OUT = Path(__file__).parent / "shots"
OUT.mkdir(exist_ok=True)
PW = "RozgarDemo#2026"
PHOTO = OUT / "photo.jpg"
PHOTO.write_bytes(b"\xff\xd8\xff" + b"\x00" * 64)  # mock OCR: no fixture keyword -> first free fictional card
PHONE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
results = []
errors = []


def check(label):
    results.append(label)
    print("  ok -", label)


def shot(page, name):
    page.screenshot(path=str(OUT / f"{TAG}-{name}.png"), full_page=True)


def watch(page, label):
    page.on("pageerror", lambda e: errors.append(f"{label}: {e}"))


def api(ctx, method, path, data=None):
    token = ctx.request.get(f"{BASE}/api/v1/auth/csrf/").json()["csrf_token"]
    headers = {"X-CSRFToken": token}
    kw = {"method": method, "headers": headers}
    if data is not None:
        headers["Content-Type"] = "application/json"
        kw["data"] = json.dumps(data)
    r = ctx.request.fetch(f"{BASE}/api/v1{path}", **kw)
    body = r.json() if "json" in (r.headers.get("content-type") or "") else None
    assert r.ok, (method, path, r.status, body)
    return body


def login(page, username, role):
    page.goto(f"{BASE}/login?role={role}")
    page.get_by_label("یوزر نیم").fill(username)
    page.get_by_label("پاس ورڈ").fill(PW)
    page.get_by_role("button", name="لاگ اِن").click()
    page.wait_for_url(re.compile(r".*/(w|c)$"))


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)

    # 1. Existing worker dashboard loads (the Strict Mode bug left it on the spinner forever).
    ctx = browser.new_context(**PHONE)
    page = ctx.new_page()
    watch(page, "akram")
    login(page, "demo_akram", "worker")
    expect(page.get_by_test_id("availability-status")).to_be_visible(timeout=10000)
    check("worker dashboard renders after login")

    # 2. Switching booking IDs: a slow response for the first booking must not overwrite the second.
    bookings = api(ctx, "GET", "/bookings/?status=COMPLETED")["results"]
    assert len(bookings) >= 2, "demo_akram needs two completed bookings (seed_demo)"
    first, second = bookings[0], bookings[1]
    held = []
    page.route(f"**/api/v1/bookings/{first['id']}/", lambda route: held.append(route))
    page.goto(f"{BASE}/w/bookings/{first['id']}")
    page.wait_for_timeout(500)
    page.evaluate(f"window.history.pushState({{}}, '', '/w/bookings/{second['id']}'); "
                  "window.dispatchEvent(new PopStateEvent('popstate'))")
    expect(page.get_by_test_id("booking-amount")).to_contain_text(f"{float(second['amount']):,.0f}")
    page.unroute(f"**/api/v1/bookings/{first['id']}/")
    outcome = "released late"
    for route in held:
        try:
            route.continue_()  # release the stale response late
        except Exception:  # the client already aborted the superseded request
            outcome = "cancelled by the client on route change"
    page.wait_for_timeout(1500)
    expect(page.get_by_test_id("booking-amount")).to_contain_text(f"{float(second['amount']):,.0f}")
    assert page.url.endswith(f"/w/bookings/{second['id']}")
    check(f"slow response for booking {first['id']} ({outcome}) did not overwrite booking {second['id']}")

    # 3. Failed dashboard request -> visible retry state -> retry recovers.
    page.route("**/api/v1/workers/me/dashboard/", lambda r: r.fulfill(status=500, body="boom"))
    page.goto(f"{BASE}/w")
    expect(page.get_by_test_id("dashboard-error")).to_be_visible(timeout=10000)
    expect(page.get_by_test_id("dashboard-error")).to_contain_text("سرور میں خرابی")
    shot(page, "dashboard-error")
    page.unroute("**/api/v1/workers/me/dashboard/")
    page.get_by_role("button", name="دوبارہ کوشش").click()
    expect(page.get_by_test_id("availability-status")).to_be_visible()
    check("failed dashboard call shows retry, retry recovers")

    page.route("**/api/v1/workers/me/dashboard/", lambda r: r.abort("failed"))
    page.goto(f"{BASE}/w")
    expect(page.get_by_test_id("dashboard-error")).to_contain_text("رابطہ نہیں ہوا")
    page.unroute("**/api/v1/workers/me/dashboard/")
    page.get_by_role("button", name="دوبارہ کوشش").click()
    expect(page.get_by_test_id("availability-status")).to_be_visible()
    check("network failure shows a network message and recovers")

    # 4. Session restore failure is retryable (not treated as signed out).
    page.route("**/api/v1/auth/me/", lambda r: r.fulfill(status=502, body="bad gateway"))
    page.goto(f"{BASE}/w")
    expect(page.get_by_test_id("session-error")).to_be_visible(timeout=10000)
    shot(page, "session-error")
    page.unroute("**/api/v1/auth/me/")
    page.get_by_test_id("session-error").get_by_role("button", name="دوبارہ کوشش").click()
    expect(page.get_by_test_id("availability-status")).to_be_visible()
    check("session restore failure shows retry; retry restores the session")

    # 5. Logout success is shown only after Django confirms.
    page.route("**/api/v1/auth/logout/", lambda r: r.fulfill(status=500, body="nope"))
    page.get_by_role("button", name="لاگ آؤٹ").click()
    expect(page.get_by_role("alert").first).to_be_visible()
    assert page.url.endswith("/w"), page.url
    assert api(ctx, "GET", "/auth/me/")["username"] == "demo_akram"
    page.unroute("**/api/v1/auth/logout/")
    page.get_by_role("button", name="لاگ آؤٹ").click()
    expect(page.get_by_test_id("logged-out")).to_be_visible()
    me = ctx.request.get(f"{BASE}/api/v1/auth/me/")
    assert me.status == 403, me.status
    check("failed logout keeps the session; confirmed logout shows success")
    ctx.close()

    # 6. Worker self-signup -> scan -> profile -> dashboard.
    wctx = browser.new_context(**PHONE)
    w = wctx.new_page()
    watch(w, "new-worker")
    w.goto(f"{BASE}/login?role=worker")
    w.get_by_role("link", name="نیا کاریگر اکاؤنٹ بنائیں").click()
    expect(w.get_by_role("heading", name="کاریگر اکاؤنٹ بنائیں")).to_be_visible()
    username = f"self_{TAG}_{uuid.uuid4().hex[:5]}"
    w.get_by_label("یوزر نیم").fill(username)
    w.get_by_label("پاس ورڈ").fill(PW)
    w.get_by_role("button", name="نیا اکاؤنٹ بنائیں").click()
    w.wait_for_url("**/w/onboard")
    shot(w, "signup-to-onboard")
    w.set_input_files("[data-testid=scan-input]", str(PHOTO))
    expect(w.get_by_test_id("mock-label")).to_be_visible()
    expect(w.get_by_test_id("registry-label")).to_be_visible()
    shot(w, "scan-labels")
    w.get_by_role("button", name="جی ہاں، یہ میں ہوں").click()
    w.get_by_role("button", name="بجلی کا کام").click()
    w.get_by_role("button", name="آگے").click()
    w.get_by_role("button", name="وائرنگ").click()
    w.get_by_role("button", name="آگے").click()
    w.get_by_role("button", name="G-11").click()
    w.get_by_role("button", name="آگے").click()
    display_name = w.get_by_label("آپ کا نام").input_value()
    w.get_by_role("button", name="پروفائل محفوظ کریں").click()
    w.wait_for_url(re.compile(r".*/w$"))
    expect(w.get_by_test_id("availability-status")).to_have_text("آپ کام کے لیے دستیاب ہیں")
    shot(w, "new-worker-dashboard")
    check(f"worker signup -> scan -> profile -> dashboard ({username} as {display_name})")

    # 7. A separate customer can still book this eligible worker.
    cctx = browser.new_context(**PHONE)
    c = cctx.new_page()
    watch(c, "customer")
    login(c, "demo_ayesha", "customer")
    trades = {t["slug"]: t for t in cctx.request.get(f"{BASE}/api/v1/catalog/trades/").json()}
    areas = {a["sector_code"]: a for a in cctx.request.get(f"{BASE}/api/v1/catalog/service-areas/").json()}
    c.get_by_role("button", name="بجلی کا کام").click()
    c.get_by_role("button", name="وائرنگ").click()
    c.get_by_role("button", name="G-11").click()
    expect(c.get_by_test_id("worker-card").filter(has_text=display_name)).to_be_visible()
    job = api(cctx, "POST", "/job-requests/", {"trade": trades["electrical"]["id"], "service_area": areas["G-11"]["id"],
                                               "description": f"Regression {TAG}: switch sparks"})
    quote = api(wctx, "POST", f"/job-requests/{job['id']}/quotes/", {"amount": "1300"})
    c.goto(f"{BASE}/c/requests/{job['id']}")
    c.get_by_test_id("worker-card").filter(has_text=display_name).get_by_role("button", name="منظور کریں").click()
    c.wait_for_url(re.compile(r".*/c/bookings/\d+$"))
    expect(c.get_by_test_id("booking")).to_have_attribute("data-status", "BOOKED")
    check("customer booked the newly onboarded worker")

    # 8. Stale quote: worker drops the trade after quoting -> Accept disabled, API answers 409.
    rctx = browser.new_context()
    api(rctx, "POST", "/auth/login/", {"username": "demo_rashid", "password": PW})
    plumbing_job = api(cctx, "POST", "/job-requests/", {"trade": trades["plumbing"]["id"],
                                                        "service_area": areas["G-11"]["id"],
                                                        "description": f"Regression {TAG}: tap leak"})
    stale = api(rctx, "POST", f"/job-requests/{plumbing_job['id']}/quotes/", {"amount": "800"})
    original = api(rctx, "GET", "/workers/me/")
    edit = {k: original[k] for k in ("display_name", "experience_years", "specialties", "service_areas", "accepting_jobs")}
    api(rctx, "PUT", "/workers/me/", {**edit, "trades": [trades["electrical"]["id"]], "specialties": []})
    try:
        c.goto(f"{BASE}/c/requests/{plumbing_job['id']}")
        button = c.get_by_test_id("worker-card").filter(has_text="Rashid").get_by_role("button")
        expect(button).to_have_text(re.compile("اب یہ کاریگر اس کام کے لیے دستیاب نہیں"))
        expect(button).to_be_disabled()
        shot(c, "stale-quote")
        token = cctx.request.get(f"{BASE}/api/v1/auth/csrf/").json()["csrf_token"]
        r = cctx.request.post(f"{BASE}/api/v1/quotes/{stale['id']}/accept/", headers={"X-CSRFToken": token})
        assert r.status == 409 and r.json()["code"] == "worker_not_eligible", (r.status, r.text())
        check("stale quote: Accept disabled in UI, API returns 409 worker_not_eligible")
    finally:
        api(rctx, "PUT", "/workers/me/", {**edit, "trades": original["trades"]})  # restore demo worker

    browser.close()

print(f"{len(results)} checks passed; page errors: {errors or 'none'}")
