"""Server-side OCR adapter for ID-card scans.

OCR_MODE=mock (default)
    No network. Returns fixture text chosen by keywords in the upload's file
    name, so every path can be demonstrated. Results are labelled simulated.
      card-1 .. card-6  -> fictional registry cards (default: card-5)
      blurry            -> text with no ID number         (422 id_not_found)
      unregistered      -> ID not in the fake registry    (422 id_not_registered)
      ocr-error         -> provider failure               (503 ocr_unavailable)

OCR_MODE=live
    POSTs the image as multipart (field OCR_IMAGE_FIELD) to OCR_ENDPOINT with
    the key in header OCR_API_KEY_HEADER, and reads the text from the JSON
    response at OCR_TEXT_FIELD (dotted path, e.g. "result.text"). The image is
    held in memory only for the request and never written or logged.
"""

import json
import uuid
from dataclasses import dataclass
from urllib import error, request

from django.conf import settings


class OcrError(Exception):
    """The OCR provider could not produce text. Safe to retry."""


@dataclass
class OcrResult:
    text: str
    mode: str  # "mock" | "live"

    @property
    def simulated(self) -> bool:
        return self.mode == "mock"


IMAGE_TYPES = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def detect_image_type(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def _card_text(number: str) -> str:
    return (
        "ISLAMIC REPUBLIC OF PAKISTAN\nNATIONAL IDENTITY CARD\n"
        f"Identity Number\n{number}\nDEMO FIXTURE - NOT A REAL CARD"
    )


MOCK_FIXTURES = {
    # card-N carries fictional ID 00000-000000N-N (see identity.FAKE_REGISTRY)
    **{f"card-{n}": _card_text(f"00000-000000{n}-{n}") for n in range(1, 7)},
    "blurry": "ISLAMIC REPUBLIC OF PAKISTAN\nNATIONAL IDENTITY CARD\n(unreadable)",
    "unregistered": _card_text("00000-0000099-9"),
}
MOCK_DEFAULT = "card-5"


def _mock(filename: str) -> OcrResult:
    name = (filename or "").lower()
    if "ocr-error" in name:
        raise OcrError("Simulated provider failure.")
    for key in sorted(MOCK_FIXTURES, key=len, reverse=True):
        if key in name:
            return OcrResult(MOCK_FIXTURES[key], "mock")
    return OcrResult(MOCK_FIXTURES[MOCK_DEFAULT], "mock")


def _multipart(field: str, filename: str, content_type: str, data: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def _dig(payload, dotted: str):
    for part in dotted.split("."):
        if isinstance(payload, list) and part.isdigit():
            payload = payload[int(part)]
        elif isinstance(payload, dict):
            payload = payload.get(part)
        else:
            return None
    return payload


def _live(data: bytes, kind: str) -> OcrResult:
    body, content_type = _multipart(settings.OCR_IMAGE_FIELD, f"card.{kind}", IMAGE_TYPES[kind], data)
    headers = {"Content-Type": content_type, "Accept": "application/json"}
    if settings.OCR_API_KEY:
        headers[settings.OCR_API_KEY_HEADER] = settings.OCR_API_KEY
    req = request.Request(settings.OCR_ENDPOINT, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=settings.OCR_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        # Never include the response body or image in the error.
        raise OcrError(type(exc).__name__) from None
    text = _dig(payload, settings.OCR_TEXT_FIELD)
    if not isinstance(text, str):
        raise OcrError("Unexpected provider response shape.")
    return OcrResult(text, "live")


def read_card(data: bytes, kind: str, filename: str) -> OcrResult:
    if settings.OCR_MODE == "mock":
        return _mock(filename)
    return _live(data, kind)
