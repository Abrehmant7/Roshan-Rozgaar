"""Fictional identity registry and CNIC helpers for worker onboarding.

EVERYTHING HERE IS FICTIONAL. The registry stands in for a government lookup,
which is out of scope for the hackathon. All numbers use the 00000- prefix,
which is not a real locality code, so no entry can match a real person.

Raw identifiers are never stored or returned: profiles keep only a masked form
and a keyed digest (to stop one ID verifying two worker accounts).
"""

import re

from django.utils.crypto import salted_hmac

# 13-digit CNIC -> registry record
FAKE_REGISTRY = {
    "0000000000011": {"name_en": "Akram Khan", "name_ur": "اکرم خان"},
    "0000000000022": {"name_en": "Naveed Iqbal", "name_ur": "نوید اقبال"},
    "0000000000033": {"name_en": "Rashid Mehmood", "name_ur": "راشد محمود"},
    "0000000000044": {"name_en": "Sajid Hussain", "name_ur": "ساجد حسین"},
    "0000000000055": {"name_en": "Imran Ali", "name_ur": "عمران علی"},
    "0000000000066": {"name_en": "Tariq Javed", "name_ur": "طارق جاوید"},
}

_CNIC_RE = re.compile(r"(?<!\d)(\d{5})[-\s]?(\d{7})[-\s]?(\d)(?!\d)")


def extract_cnic(text: str) -> str | None:
    """Return the first CNIC-shaped number in OCR text as 13 digits, or None."""
    match = _CNIC_RE.search(text or "")
    return "".join(match.groups()) if match else None


def mask_cnic(digits: str) -> str:
    """'0000000000055' -> '*****-****005-5' (last 4 digits visible)."""
    return f"*****-****{digits[9:12]}-{digits[12]}"


def identity_digest(digits: str) -> str:
    return salted_hmac("roshan_rozgar.worker_identity", digits, algorithm="sha256").hexdigest()


def lookup(digits: str) -> dict | None:
    return FAKE_REGISTRY.get(digits)
