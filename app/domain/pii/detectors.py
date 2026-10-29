from __future__ import annotations

from app.domain.pii.rules import SENSITIVE_PATTERNS
from app.domain.pii.validation import is_valid_candidate


def find_sensitive_matches(document_text: str) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    if not document_text:
        return matches

    for category, pattern, _replacement in SENSITIVE_PATTERNS:
        for match in pattern.finditer(document_text):
            candidate = match.group(0).strip()
            if candidate and is_valid_candidate(category, candidate):
                matches.append((category, candidate))
    return matches
