from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_IDCN = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
_BANK = re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)")

@dataclass(frozen=True)
class RedactionResult:
    text: str
    counts: dict[str, int]


def redact_pii(text: str) -> RedactionResult:
    value = str(text or "")
    counts = {"email": 0, "phone": 0, "id_number": 0, "account_number": 0}
    def sub(pattern, label, key):
        nonlocal value
        value, n = pattern.subn(label, value)
        counts[key] += n
    sub(_EMAIL, "[EMAIL_REDACTED]", "email")
    sub(_PHONE, "[PHONE_REDACTED]", "phone")
    sub(_IDCN, "[ID_REDACTED]", "id_number")
    # Bank/account pattern is intentionally last and conservative; avoid replacing years/scores.
    sub(_BANK, "[ACCOUNT_REDACTED]", "account_number")
    return RedactionResult(text=value, counts=counts)


def minimize_for_model(text: str, *, enabled: bool) -> tuple[str, dict[str, int]]:
    if not enabled:
        return text, {}
    result = redact_pii(text)
    return result.text, result.counts
