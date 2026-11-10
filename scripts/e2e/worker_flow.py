"""Phase 8 browser check: the worker flow in a phone-sized Edge window against the real API.

The customer side is driven through the API in a separate browser context (own cookies).
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).parent / "shots"
OUT.mkdir(exist_ok=True)
PW = "RozgarDemo#2026"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
CARD = OUT / "card-5.png"
CARD.write_bytes(PNG)
PHONE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)

errors = []


def api(ctx, method, path, data=None, multipart=None):
    token = ctx.request.get(f"{BASE}/api/v1/auth/csrf/").json()["csrf_token"]
    headers = {"X-CSRFToken": token}
    kwargs = {"method": method, "headers": headers}
    if data is not None:
        headers["Content-Type"] = "application/json"
        kwargs["data"] = json.dumps(data)
    if multipart is not None:
        kwargs["multipart"] = multipart
    resp = ctx.request.fetch(f"{BASE}/api/v1{path}", **kwargs)
    body = resp.json() if "json" in (resp.headers.get("content-type") or "") else None
    assert resp.ok, (method, path, resp.status, body)
    return body


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)


def watch(page, label):
    page.on("console", lambda m: m.type == "error" and errors.append(f"{label} console: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"{label} pageerror: {e}"))


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    customer = browser.new_context(**PHONE)
    api(customer, "POST", "/auth/login/", {"username": "demo_ayesha", "password": PW})
    trades = {t["slug"]: t for t in customer.request.get(f"{BASE}/api/v1/catalog/trades/").json()}
    areas = {a["sector_code"]: a for a in customer.request.get(f"{BASE}/api/v1/catalog/service-areas/").json()}
    job = api(customer, "POST", "/job-requests/", multipart={
        "trade": str(trades["electrical"]["id"]), "service_area": str(areas["G-11"]["id"]),
        "description": "پنکھا چلانے پر بورڈ سے چنگاری نکلتی ہے", "address_details": "مکان 12، گلی 4 (فرضی)",
        "voice_note": {"name": "rec.webm", "mimeType": "audio/webm", "buffer": WEBM},
    })
    print("customer posted job", job["id"])

    worker = browser.new_context(**PHONE)
    page = worker.new_page()
    watch(page, "worker")
    page.goto(BASE + "/")
    expect(page.get_by_text("میں کاریگر ہوں")).to_be_visible()
    shot(page, "w01-landing")
    page.get_by_text("میں کاریگر ہوں").click()
    page.get_by_label("یوزر نیم").fill("demo_imran")
    page.get_by_label("پاس ورڈ").fill(PW)
    page.get_by_role("button", name="لاگ اِن").click()
    page.wait_for_url("**/w")
    expect(page.get_by_text("پروفائل بنائیں").first).to_be_visible()
    shot(page, "w02-home-no-profile")
    page.get_by_role("link", name="پروفائل بنائیں").click()
    page.wait_for_url("**/w/onboard")
    shot(page, "w03-scan")
    page.set_input_files("[data-testid=scan-input]", str(CARD))
    expect(page.get_by_test_id("mock-label")).to_be_visible()
    expect(page.get_by_text("عمران علی")).to_be_visible()
    shot(page, "w04-scan-result")
    page.get_by_role("button", name="جی ہاں، یہ میں ہوں").click()
    page.get_by_role("button", name="بجلی کا کام").click()
    shot(page, "w05-trades")
    page.get_by_role("button", name="آگے").click()
    page.get_by_role("button", name="وائرنگ").click()
    page.get_by_role("button", name="آگے").click()
    page.get_by_role("button", name="G-11").click()
    shot(page, "w06-areas")
    page.get_by_role("button", name="آگے").click()
    expect(page.get_by_label("آپ کا نام")).to_have_value("عمران علی")
    page.get_by_role("button", name="+1").click()
    page.get_by_role("button", name="+1").click()
    expect(page.get_by_test_id("experience")).to_have_text("3")
    shot(page, "w07-name")
    page.get_by_role("button", name="پروفائل محفوظ کریں").click()
    page.wait_for_url("**/w")
    expect(page.get_by_test_id("availability-status")).to_have_text("آپ کام کے لیے دستیاب ہیں")
    shot(page, "w08-dashboard")

    page.get_by_role("link", name="نئے کام", exact=True).click()
    card = page.get_by_test_id("job-card").filter(has_text="چنگاری").first
    expect(card).to_be_visible()
    shot(page, "w09-board")
    card.click()
    page.get_by_role("button", name="آواز کا پیغام · سنیں").click()
    expect(page.locator("audio")).to_have_count(1)
    expect(page.get_by_text("مکان 12")).to_have_count(0)  # address stays private before booking
    page.get_by_role("button", name="2000").click()
    page.get_by_role("button", name="آج آ سکتا ہوں").click()
    shot(page, "w10-quote-form")
    page.get_by_role("button", name="قیمت بھیجیں").click()
    expect(page.get_by_text("جواب کا انتظار")).to_be_visible()
    shot(page, "w11-quote-sent")

    quotes = api(customer, "GET", f"/job-requests/{job['id']}/quotes/")
    mine = next(q for q in quotes if q["worker"]["display_name"] == "عمران علی")
    assert mine["amount"] == "2000.00" and mine["message"] == "آج آ سکتا ہوں", mine
    booking = api(customer, "POST", f"/quotes/{mine['id']}/accept/")
    print("customer accepted, booking", booking["id"])

    page.get_by_role("link", name="گھر", exact=True).click()
    expect(page.get_by_test_id("availability-status")).to_have_text("آپ ایک کام پر ہیں")
    shot(page, "w12-dashboard-busy")
    page.get_by_text("کام کھولیں").click()
    page.wait_for_url(f"**/w/bookings/{booking['id']}")
    expect(page.get_by_text("مکان 12")).to_be_visible()  # address visible to the assigned worker
    shot(page, "w13-booking")

    pin = api(customer, "POST", f"/bookings/{booking['id']}/pin/")["pin"]
    wrong = "111111" if pin != "111111" else "222222"

    def enter(code):
        for d in code:
            page.get_by_role("button", name=d, exact=True).click()
        page.get_by_role("button", name="پہنچنے کی تصدیق").last.click()

    enter(wrong)
    expect(page.get_by_text("غلط PIN")).to_be_visible()
    shot(page, "w14-wrong-pin")
    enter(pin)
    expect(page.get_by_test_id("booking")).to_have_attribute("data-status", "IN_PROGRESS")
    shot(page, "w15-in-progress")
    page.get_by_role("button", name="کام مکمل ہو گیا").click()
    page.get_by_role("button", name="کام مکمل ہو گیا").click()
    expect(page.get_by_test_id("booking")).to_have_attribute("data-status", "COMPLETED")
    page.get_by_role("button", name="مسئلہ رپورٹ کریں").click()
    page.get_by_role("button", name="ادائیگی کا جھگڑا").click()
    page.get_by_role("button", name="رپورٹ بھیجیں").click()
    expect(page.get_by_text("رپورٹ بھیج دی گئی")).to_be_visible()
    shot(page, "w16-completed-reported")

    page.get_by_role("link", name="گھر", exact=True).click()
    expect(page.get_by_test_id("availability-status")).to_have_text("آپ کام کے لیے دستیاب ہیں")
    page.get_by_role("button", name="English").click()
    expect(page.get_by_test_id("availability-status")).to_have_text("You are available for work")
    shot(page, "w17-dashboard-english")
    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    print("horizontal overflow:", overflow)
    browser.close()

print("console/page errors:", errors or "none")
print("WORKER FLOW OK")
