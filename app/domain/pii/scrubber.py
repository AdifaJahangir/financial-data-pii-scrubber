from __future__ import annotations

import re

from dataclasses import dataclass, field

from app.domain.pii.rules import SENSITIVE_PATTERNS
from app.domain.pii.validation import is_valid_candidate


@dataclass
class ScrubResult:
    text: str
    redacted_count: int = 0
    warnings: list[str] = field(default_factory=list)
    safe_to_send: bool = True


class ScrubbingFailureError(RuntimeError):
    """Raised when document sanitization cannot safely proceed."""


def scrub_document_text(document_text: str) -> ScrubResult:
    if not isinstance(document_text, str) or not document_text.strip():
        return ScrubResult(
            text="",
            warnings=["Document text is missing, invalid, or empty."],
            safe_to_send=False,
        )

    try:
        sanitized = document_text
                # Fail closed if email-like text is malformed.
        malformed_email_pattern = re.compile(
            r"(?i)(?<![\w.+-])[\w.+-]+@[\w.-]+(?![\w.-])"
        )

        valid_email_pattern = re.compile(
            r"(?i)^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        )

        for match in malformed_email_pattern.finditer(sanitized):
            candidate = match.group(0)
            if not valid_email_pattern.fullmatch(candidate):
                return ScrubResult(
                    text="",
                    redacted_count=0,
                    warnings=[
                        "Malformed email-like text detected; "
                        "document was not marked safe to send."
                    ],
                    safe_to_send=False,
                )
        redacted_count = 0

        for category, pattern, replacement in SENSITIVE_PATTERNS:
            ambiguous = False

            def replace_match(match, category_name=category, token=replacement):
                nonlocal redacted_count, ambiguous

                # Every rule must provide exactly one capture group
                # containing the sensitive value.
                if match.lastindex != 1:
                    ambiguous = True
                    return match.group(0)

                candidate = match.group(1).strip()
                if not candidate or not is_valid_candidate(
                    category_name, candidate
                ):
                    ambiguous = True
                    return match.group(0)

                redacted_count += 1
                return token

            sanitized = pattern.sub(replace_match, sanitized)

            if ambiguous:
                return ScrubResult(
                    text="",
                    redacted_count=redacted_count,
                    warnings=[
                        f"Ambiguous {category} pattern detected; "
                        "document was not marked safe to send."
                    ],
                    safe_to_send=False,
                )

        # Final detector pass: do not approve output if any rule
        # still matches a valid sensitive candidate.
        for category, pattern, _replacement in SENSITIVE_PATTERNS:
            for match in pattern.finditer(sanitized):
                if match.lastindex != 1:
                    return ScrubResult(
                        text="",
                        redacted_count=redacted_count,
                        warnings=["Final safety check could not validate a pattern."],
                        safe_to_send=False,
                    )

                candidate = match.group(1).strip()
                if candidate and is_valid_candidate(category, candidate):
                    return ScrubResult(
                        text="",
                        redacted_count=redacted_count,
                        warnings=[
                            "Sensitive information may remain after scrubbing."
                        ],
                        safe_to_send=False,
                    )

        if not sanitized.strip():
            return ScrubResult(
                text="",
                redacted_count=redacted_count,
                warnings=["Scrubbed output is empty."],
                safe_to_send=False,
            )

        return ScrubResult(
            text=sanitized.strip(),
            redacted_count=redacted_count,
            warnings=[],
            safe_to_send=True,
        )

    except Exception:
        return ScrubResult(
            text="",
            redacted_count=0,
            warnings=["Scrubbing failed; raw document content was not returned."],
            safe_to_send=False,
        )
