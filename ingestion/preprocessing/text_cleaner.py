"""Text post-processing: whitespace normalization, broken-line merging,
repeated header/footer removal, obvious OCR character cleanup, page
joining. Deliberately simple/deterministic -- no ML.

Callers must preserve the original raw_text alongside the cleaned_text
(see schemas.PageRecord) -- this module never mutates its input in place.
"""
from __future__ import annotations

import re
from collections import Counter

_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Common OCR character mix-ups, applied conservatively (only in isolation,
# not blanket replacement, to avoid corrupting legitimate text).
_OCR_FIXUPS = {
    "‘": "'", "’": "'",  # curly quotes
    "“": '"', "”": '"',
    "–": "-", "—": "-",  # en/em dash
    "ﬁ": "fi", "ﬂ": "fl",  # ligatures
}


def clean_text(raw: str) -> str:
    """Clean a single page/document's raw text. Returns a new string;
    never mutates or discards the original raw_text held by the caller.

    Deliberately preserves line breaks (beyond collapsing 3+ blank lines to
    one) rather than reflowing wrapped prose into single paragraphs: source
    documents mix free text with label/value lines and tabular data (e.g.
    formation-tops listings), and collapsing those onto one line would
    destroy the row/line structure that relation_extractor relies on.
    """
    text = raw
    for bad, good in _OCR_FIXUPS.items():
        text = text.replace(bad, good)
    text = _CONTROL_CHARS_RE.sub("", text)
    # Merge hyphenated words split across a line break: "exam-\nple" -> "example"
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def remove_repeated_lines(
    page_texts: list[str], min_page_count: int = 3, repeat_fraction: float = 0.6
) -> list[str]:
    """Detect lines that repeat across a large fraction of pages (typical
    of running headers/footers, e.g. a report title or page numbers) and
    strip them from each page. No-ops below min_page_count pages, since a
    short document doesn't give a reliable repetition signal.
    """
    if len(page_texts) < min_page_count:
        return list(page_texts)

    line_counts: Counter[str] = Counter()
    per_page_lines = [
        [line.strip() for line in text.split("\n") if line.strip()]
        for text in page_texts
    ]
    for lines in per_page_lines:
        for line in set(lines):
            line_counts[line] += 1

    threshold = max(2, int(len(page_texts) * repeat_fraction))
    repeated = {line for line, count in line_counts.items() if count >= threshold}
    if not repeated:
        return list(page_texts)

    cleaned_pages = []
    for lines in per_page_lines:
        kept = [line for line in lines if line not in repeated]
        cleaned_pages.append("\n".join(kept))
    return cleaned_pages


def join_pages(page_texts: list[str]) -> str:
    return "\n\n".join(page_texts)
