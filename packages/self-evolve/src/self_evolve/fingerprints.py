from __future__ import annotations

import re


def build_fingerprint(domain: str, statement: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", statement.lower()).strip("-")
    return f"{domain}:{normalized}"
