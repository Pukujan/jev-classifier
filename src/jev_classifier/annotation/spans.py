"""Byte-accurate span picking for human annotation (#90).

The metric compares integer offsets against a reference claim graph
(``claim_metric_v1``, ``span_containment_v1``), so a character index is a silent
defect on any non-ASCII source: it agrees with the reference until the first
multi-byte character and then diverges without an error. This repository has
shipped that defect class before, so every offset here is a UTF-8 **byte**
offset -- computed as ``len(source_text[:char_index].encode("utf-8"))`` and
verified by round-trip before it is returned.

Fail closed: a quote that is absent raises, and a quote that occurs more than
once raises as ambiguous rather than guessing an occurrence. An annotator who
means a specific occurrence passes it explicitly.

Scope: this module maps a quote to offsets. It does not read files, decide what
is worth annotating, or call a model.
"""

from __future__ import annotations


class SpanError(ValueError):
    """Raised when a quote cannot be located unambiguously in its source."""

    def __init__(self, message: str, *, kind: str = "not_found") -> None:
        super().__init__(message)
        self.kind = kind


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise SpanError(f"{label} must be a string", kind="schema_error")
    return value


def _occurrences(source_text: str, quote: str) -> list[int]:
    """Character indices of every non-overlapping occurrence of ``quote``."""
    indices: list[int] = []
    cursor = 0
    while True:
        found = source_text.find(quote, cursor)
        if found < 0:
            return indices
        indices.append(found)
        cursor = found + 1


def _select_index(indices: list[int], quote: str, occurrence: int | None) -> int:
    if occurrence is None:
        if not indices:
            raise SpanError(f"quote {quote!r} does not appear in the source", kind="not_found")
        if len(indices) > 1:
            raise SpanError(
                f"quote {quote!r} appears {len(indices)} times; pass occurrence=<1-based "
                f"index> to choose one rather than guessing",
                kind="ambiguous_match",
            )
        return indices[0]
    if not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence < 1:
        raise SpanError(
            f"occurrence must be a 1-based positive integer, got {occurrence!r}",
            kind="schema_error",
        )
    if occurrence > len(indices):
        raise SpanError(
            f"occurrence {occurrence} requested but quote {quote!r} appears "
            f"{len(indices)} time(s)",
            kind="occurrence_out_of_range",
        )
    return indices[occurrence - 1]


def pick_span(source_text: str, quote: str, *, occurrence: int | None = None) -> tuple[int, int]:
    """Return the UTF-8 ``(byte_start, byte_end)`` of ``quote`` in ``source_text``.

    ``occurrence`` is 1-based and optional. Without it, a quote that appears
    zero times raises ``kind="not_found"`` and one that appears more than once
    raises ``kind="ambiguous_match"`` -- never a guessed occurrence.

    The returned offsets satisfy
    ``source_text.encode("utf-8")[start:end].decode("utf-8") == quote``.
    """
    source = _require_str(source_text, "source_text")
    text = _require_str(quote, "quote")
    if not text:
        # An empty quote matches everywhere, so it is ambiguous by construction.
        raise SpanError("quote must be non-empty", kind="empty_quote")

    char_index = _select_index(_occurrences(source, text), text, occurrence)
    char_end = char_index + len(text)
    byte_start = len(source[:char_index].encode("utf-8"))
    byte_end = len(source[:char_end].encode("utf-8"))

    expected = text.encode("utf-8")
    if source.encode("utf-8")[byte_start:byte_end] != expected:
        raise SpanError(
            "internal error: computed offsets do not slice back to the quote",
            kind="round_trip",
        )
    return byte_start, byte_end
