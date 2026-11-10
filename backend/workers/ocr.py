"""Server-side OCR adapter for ID-card scans.

OCR_MODE=mock (default)
    No network. Returns a fictional ID number chosen by keywords in the
    upload's file name, so every path can be demonstrated. Labelled simulated.
      card-1 .. card-9  -> that fictional registry card (identity.FAKE_REGISTRY)
      (no keyword)      -> the first fictional card not linked to another worker
      blurry            -> no ID number found          (422 id_not_found)
      unregistered      -> ID not in the registry      (422 id_not_registered)
      ocr-error         -> provider failure            (503 ocr_unavailable)

OCR_MODE=live — PicToText (https://pictotext.io/docs/reference/asia/pakistan/id-card)
    POST OCR_ENDPOINT (default https://pictotext.io/api/v1/ocr)
    Authorization: Bearer OCR_API_KEY
    multipart: image=<file>, documentType=pk_id_card
    200 -> JSON with a top-level "idNumber" such as "12345-6789012-3".

The key is read from settings only and never appears in responses, logs or
exceptions. The image is held in memory for the request and never written.
"""

import json
import re
import socket
import uuid
from dataclasses import dataclass
from urllib import error, request

from django.conf import settings


@dataclass
class OcrFailure(Exception):
    """A scan that could not produce an ID number. Fields map 1:1 to the API error."""

    code: str
    status: int
    retryable: bool
    message: str

    def __str__(self):  # never includes provider bodies, keys or image data
        return self.code


def _not_configured():
    return OcrFailure("ocr_not_configured", 503, False,
                      "Card reading is not configured on the server. Please contact staff.")


@dataclass
class OcrResult:
    id_number: str | None  # 13 digits, or None if the card had no readable ID number
    mode: str  # "mock" | "live"
    auto: bool = False  # mock without a fixture keyword: the caller picks a free fictional card

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


def normalize_id_number(value) -> str | None:
    """'00000-0000007-7', '00000 0000007 7', '0000000000077' -> '0000000000077'."""
    if not isinstance(value, str):
        return None
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) == 13 else None


# ------------------------------------------------------------------- mock ---

# card-N -> fictional ID 00000-000000N-N
MOCK_CARDS = {f"card-{n}": f"{n}{n}".rjust(13, "0") for n in range(1, 10)}
MOCK_AUTO_ORDER = ["card-5", "card-6", "card-7", "card-8", "card-9", "card-1", "card-2", "card-3", "card-4"]


def _mock(filename: str) -> OcrResult:
    name = (filename or "").lower()
    if "ocr-error" in name:
        raise OcrFailure("ocr_unavailable", 503, True, "Could not read the card right now. Please try again.")
    if "blurry" in name:
        return OcrResult(None, "mock")
    if "unregistered" in name:
        return OcrResult("0000000000999", "mock")
    for key in sorted(MOCK_CARDS, key=len, reverse=True):
        if key in name:
            return OcrResult(MOCK_CARDS[key], "mock")
    return OcrResult(None, "mock", auto=True)


# ------------------------------------------------------------- PicToText ---

USER_AGENT = "RoshanRozgar/1.0 (server-side; pictotext adapter)"
BAD_IMAGE_REASONS = {"INVALID_IMAGE_TYPE", "IMAGE_TOO_LARGE", "MISSING_IMAGE_FILE"}


def _multipart(fields, file_field, filename, content_type, data):
    boundary = uuid.uuid4().hex
    parts = [
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
        for k, v in fields
    ]
    parts.append(
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\n"
         f"Content-Type: {content_type}\r\n\r\n").encode() + data + b"\r\n"
    )
    return b"".join(parts) + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def _reason(raw: bytes) -> str | None:
    """PicToText error body: {"error": {"code", "message", "status", "details": [{"reason"}]}}."""
    try:
        details = json.loads(raw.decode("utf-8")).get("error", {}).get("details") or []
        return details[0].get("reason") if details else None
    except (ValueError, AttributeError, IndexError, UnicodeDecodeError):
        return None


def _http_failure(status: int, reason: str | None) -> OcrFailure:
    if status == 401:
        return OcrFailure("ocr_auth_rejected", 503, False,
                          "The card-reading service rejected the server's credentials. Please contact staff.")
    if status == 403:
        return OcrFailure("ocr_auth_rejected", 503, False,
                          "The card-reading account is not allowed to scan yet. Please contact staff.")
    if status == 402 or reason == "INSUFFICIENT_CREDITS":
        return OcrFailure("ocr_quota_exceeded", 503, False,
                          "The card-reading quota is used up. Please try again later or contact staff.")
    if status == 429:
        return OcrFailure("ocr_quota_exceeded", 503, True,
                          "Too many card scans right now. Please wait a minute and try again.")
    if status == 400 and reason == "INVALID_DOCUMENT_TYPE":
        return _not_configured()
    if status in (400, 413, 415, 422):
        return OcrFailure("image_rejected", 422, True,
                          "This photo could not be read. Take a clear JPG or PNG photo of the whole card.")
    return OcrFailure("ocr_unavailable", 503, True, "Could not read the card right now. Please try again.")


def _live(data: bytes, kind: str) -> OcrResult:
    key = settings.OCR_API_KEY
    if not key or not settings.OCR_ENDPOINT:
        raise _not_configured()
    body, content_type = _multipart(
        [("documentType", settings.OCR_DOCUMENT_TYPE)], "image", f"card.{'jpg' if kind == 'jpeg' else kind}",
        IMAGE_TYPES[kind], data,
    )
    req = request.Request(settings.OCR_ENDPOINT, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    try:
        with request.urlopen(req, timeout=settings.OCR_TIMEOUT_SECONDS) as resp:
            raw = resp.read(256 * 1024)
    except error.HTTPError as exc:
        raise _http_failure(exc.code, _reason(exc.read(16 * 1024))) from None
    except (TimeoutError, socket.timeout):
        raise OcrFailure("ocr_timeout", 504, True, "Reading the card took too long. Please try again.") from None
    except error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise OcrFailure("ocr_timeout", 504, True, "Reading the card took too long. Please try again.") from None
        raise OcrFailure("ocr_unavailable", 503, True, "Could not reach the card-reading service. Please try again.") from None
    except OSError:
        raise OcrFailure("ocr_unavailable", 503, True, "Could not reach the card-reading service. Please try again.") from None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise OcrFailure("ocr_unavailable", 503, True, "Unexpected answer from the card-reading service.") from None
    id_number = payload.get("idNumber") if isinstance(payload, dict) else None
    return OcrResult(normalize_id_number(id_number), "live")


def read_card(data: bytes, kind: str, filename: str) -> OcrResult:
    if settings.OCR_MODE == "mock":
        return _mock(filename)
    return _live(data, kind)
