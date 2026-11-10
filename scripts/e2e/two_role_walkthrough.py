"""Phase 9 live walkthrough: worker and customer in independent phone-sized sessions,
entirely through the UI, in carpentry (non-plumbing). Staff moderates in Admin."""

import re
import sys
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).parent / "shots"
OUT.mkdir(exist_ok=True)
PW = "RozgarDemo#2026"
CARD6 = OUT / "card-6.jpg"
CARD6.write_bytes(b"\xff\xd8\xff" + b"\x00" * 64)
AUDIO = OUT / "fallback-note.webm"
AUDIO.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 64)
PHONE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
errors = []
step_no = [0]


def shot(page, name):
    step_no[0] += 1
    page.screenshot(path=str(OUT / f"f{step_no[0]:02d}-{name}.png"), full_page=True)


def watch(page, label):
    page.on("pageerror", lambda e: errors.append(f"{label} pageerror: {e}"))
    page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text
            and errors.append(f"{label} console: {m.text}"))


def nav(page, label):
    page.get_by_role("link", name=label, exact=True).click()


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True,
                                args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])

    # ---------------- worker onboarding (fresh account demo_tariq) ----------------
    wctx = browser.new_context(**PHONE)
    w = wctx.new_page()
    watch(w, "worker")
    w.goto(BASE + "/login?role=worker")
    w.get_by_label("یوزر نیم").fill("demo_tariq")
    w.get_by_label("پاس ورڈ").fill(PW)
    w.get_by_role("button", name="لاگ اِن").click()
    w.get_by_role("link", name="پروفائل بنائیں").click()
    w.set_input_files("[data-testid=scan-input]", str(CARD6))
    expect(w.get_by_test_id("mock-label")).to_be_visible()
    expect(w.get_by_text("طارق جاوید")).to_be_visible()
    w.get_by_role("button", name="جی ہاں، یہ میں ہوں").click()
    w.get_by_role("button", name="بڑھئی کا کام").click()
    w.get_by_role("button", name="آگے").click()
    w.get_by_role("button", name="دروازے اور کھڑکی کی فٹنگ").click()
    w.get_by_role("button", name="آگے").click()
    w.get_by_role("button", name="G-13").click()
    w.get_by_role("button", name="آگے").click()
    w.get_by_role("button", name="پروفائل محفوظ کریں").click()
    expect(w.get_by_test_id("availability-status")).to_have_text("آپ کام کے لیے دستیاب ہیں")
    print("worker onboarded")

    # ---------------- customer registers, searches, posts text + recorded voice ----------------
    cctx = browser.new_context(**PHONE, permissions=["microphone"])
    c = cctx.new_page()
    watch(c, "customer")
    c.goto(BASE + "/")
    c.get_by_text("مجھے کاریگر چاہیے").click()
    c.get_by_role("link", name="نیا اکاؤنٹ بنائیں").click()
    username = f"walk_{uuid.uuid4().hex[:6]}"
    c.get_by_label("یوزر نیم").fill(username)
    c.get_by_label("پاس ورڈ").fill(PW)
    c.get_by_role("button", name="نیا اکاؤنٹ بنائیں").click()
    c.wait_for_url("**/c")
    c.get_by_role("button", name="بڑھئی کا کام").click()
    c.get_by_role("button", name="دروازے اور کھڑکی کی فٹنگ").click()
    c.get_by_role("button", name="G-13").click()
    tariq = c.get_by_test_id("worker-card").filter(has_text="طارق جاوید")
    expect(tariq).to_be_visible()
    expect(tariq.get_by_text("یہی مہارت")).to_be_visible()
    expect(c.get_by_test_id("worker-card").first).to_contain_text("طارق جاوید")  # specialty match ranks first
    shot(c, "customer-search")
    find_url = c.url
    c.get_by_role("link", name="کام کی درخواست بھیجیں").click()
    c.get_by_label("کام بتائیں").fill("الماری کا دروازہ قبضے سے نکل گیا ہے")
    c.get_by_role("button", name="آواز ریکارڈ کریں").click()
    c.wait_for_timeout(2500)
    c.get_by_role("button", name=re.compile("روکیں")).click()
    expect(c.get_by_test_id("recorder").locator("audio")).to_have_count(1)
    c.get_by_label("پتہ اور آنے کا طریقہ").fill("فلیٹ 3، بلاک بی (فرضی)")
    shot(c, "customer-new-request")
    c.get_by_role("button", name="درخواست بھیجیں").click()
    c.wait_for_url(re.compile(r".*/c/requests/\d+$"))
    request_url = c.url
    expect(c.get_by_text("ابھی کوئی قیمت نہیں آئی")).to_be_visible()
    print("customer posted", request_url)

    # ---------------- worker: board, playback of the real recording, quote ----------------
    nav(w, "نئے کام")
    card = w.get_by_test_id("job-card").filter(has_text="الماری کا دروازہ")
    expect(card).to_be_visible()
    card.click()
    with w.expect_response(lambda r: "/voice-note/" in r.url) as audio:
        w.get_by_role("button", name="آواز کا پیغام · سنیں").click()
    assert audio.value.status == 200 and audio.value.headers["content-type"].startswith("audio/"), audio.value.status
    print("worker played voice note:", audio.value.headers["content-type"], len(audio.value.body()), "bytes")
    expect(w.get_by_text("فلیٹ 3")).to_have_count(0)
    w.get_by_role("button", name="1500").click()
    w.get_by_role("button", name="کل صبح آ سکتا ہوں").click()
    w.get_by_role("button", name="قیمت بھیجیں").click()
    expect(w.get_by_text("جواب کا انتظار")).to_be_visible()

    # ---------------- customer: quotes, accept ----------------
    c.goto(request_url)
    expect(c.get_by_test_id("quote-amount").first).to_be_visible()
    shot(c, "customer-quotes")
    c.get_by_test_id("worker-card").filter(has_text="طارق جاوید").get_by_role("button", name="منظور کریں").click()
    c.wait_for_url(re.compile(r".*/c/bookings/\d+$"))
    booking_url = c.url
    expect(c.get_by_test_id("booking")).to_have_attribute("data-status", "BOOKED")

    # busy everywhere
    c.goto(find_url)
    expect(c.get_by_test_id("worker-card").filter(has_text="طارق جاوید")).to_have_count(0)
    nav(w, "گھر")
    expect(w.get_by_test_id("availability-status")).to_have_text("آپ ایک کام پر ہیں")
    print("search and dashboard reflect the booking")

    # ---------------- PIN, check-in, completion ----------------
    c.goto(booking_url)
    c.get_by_role("button", name="آمد کا PIN بنائیں").click()
    pin = c.get_by_test_id("issued-pin").locator("p.num").inner_text().strip()
    assert re.fullmatch(r"\d{6}", pin), pin
    shot(c, "customer-pin")
    w.get_by_text("کام کھولیں").click()
    expect(w.get_by_text("فلیٹ 3")).to_be_visible()
    for d in pin:
        w.get_by_role("button", name=d, exact=True).click()
    w.get_by_role("button", name="پہنچنے کی تصدیق").last.click()
    expect(w.get_by_test_id("booking")).to_have_attribute("data-status", "IN_PROGRESS")
    w.get_by_role("button", name="کام مکمل ہو گیا").click()
    w.get_by_role("button", name="کام مکمل ہو گیا").click()
    expect(w.get_by_test_id("booking")).to_have_attribute("data-status", "COMPLETED")
    w.get_by_role("button", name="مسئلہ رپورٹ کریں").click()
    w.get_by_role("button", name="ادائیگی کا جھگڑا").click()
    w.get_by_role("button", name="رپورٹ بھیجیں").click()
    expect(w.get_by_text("رپورٹ بھیج دی گئی")).to_be_visible()
    print("worker checked in, completed, reported")

    # ---------------- customer: review + report ----------------
    c.reload()
    expect(c.get_by_test_id("booking")).to_have_attribute("data-status", "COMPLETED")
    c.get_by_role("radio", name="5").click()
    c.get_by_role("button", name="وقت پر آئے").click()
    c.get_by_role("button", name="ریٹنگ بھیجیں").click()
    expect(c.get_by_text("آپ کی ریٹنگ")).to_be_visible()
    c.get_by_role("button", name="مسئلہ رپورٹ کریں").click()
    c.get_by_role("button", name="کچھ اور").click()
    c.get_by_role("button", name="رپورٹ بھیجیں").click()
    expect(c.get_by_text("رپورٹ بھیج دی گئی")).to_be_visible()
    shot(c, "customer-reviewed-reported")

    # availability returns with the new rating
    c.goto(find_url)
    back = c.get_by_test_id("worker-card").filter(has_text="طارق جاوید")
    expect(back).to_contain_text("5.0")
    shot(c, "customer-search-after")
    nav(w, "گھر")
    expect(w.get_by_test_id("availability-status")).to_have_text("آپ کام کے لیے دستیاب ہیں")
    shot(w, "worker-home-after")
    print("availability and rating returned")

    # ---------------- staff: report queue in Admin ----------------
    sctx = browser.new_context(viewport={"width": 1280, "height": 900})
    s = sctx.new_page()
    s.goto(BASE + "/admin/login/")
    s.fill("#id_username", "demo_staff")
    s.fill("#id_password", PW)
    s.click("input[type=submit]")
    s.goto(BASE + "/admin/marketplace/report/?status__exact=OPEN")
    rows = s.locator("#result_list tbody tr")
    expect(rows.filter(has_text=username)).to_have_count(2)  # both directions for this booking
    shot(s, "staff-report-queue")
    for i in range(rows.filter(has_text=username).count()):
        rows.filter(has_text=username).nth(i).locator("input.action-select").check()
    s.select_option("select[name=action]", "mark_resolved")
    s.click("button[name=index]")
    expect(s.get_by_text("report(s) marked resolved")).to_be_visible()
    print("staff resolved the reports in Admin")

    # ---------------- microphone denied -> file upload fallback ----------------
    plain = p.chromium.launch(channel="msedge", headless=True)
    dctx = plain.new_context(**PHONE)
    d = dctx.new_page()
    watch(d, "customer-nomic")
    d.goto(BASE + "/login?role=customer")
    d.get_by_label("یوزر نیم").fill("demo_ayesha")
    d.get_by_label("پاس ورڈ").fill(PW)
    d.get_by_role("button", name="لاگ اِن").click()
    d.wait_for_url("**/c")
    d.goto(BASE + "/c/new?" + find_url.split("?", 1)[1])
    d.get_by_role("button", name="آواز ریکارڈ کریں").click()
    expect(d.get_by_role("alert")).to_contain_text("مائیک")
    d.set_input_files("[data-testid=audio-file]", str(AUDIO))
    expect(d.get_by_test_id("recorder").locator("audio")).to_have_count(1)
    shot(d, "mic-denied-fallback")
    d.get_by_role("button", name="درخواست بھیجیں").click()
    d.wait_for_url(re.compile(r".*/c/requests/\d+$"))
    expect(d.get_by_role("button", name="آواز کا پیغام · سنیں")).to_be_visible()
    print("mic denied -> file fallback posted a voice-only request")
    overflow = [pg.evaluate("document.documentElement.scrollWidth > window.innerWidth") for pg in (w, c, d)]
    print("horizontal overflow (worker, customer, nomic):", overflow)
    plain.close()
    browser.close()

print("errors:", errors or "none")
print("FULL WALKTHROUGH OK")
