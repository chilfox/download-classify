"""Bounded UTF-8 opening excerpts for the approved local model input policy.

No model imports, inference, or movement here. The caller captures a schema and
must use the returned text with that same schema and max_len=None. Results must
show `truncated` to disclose excerpt-based decisions, including NeedsReview.
"""
from __future__ import annotations

import codecs
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_READ_BYTES = 64 * 1024
ENCODED_TOKEN_BUDGET = 512


@dataclass(frozen=True)
class OpeningText:
    text: str
    read_bytes: int
    read_truncated: bool


@dataclass(frozen=True)
class PreparedInput:
    text: str
    encoded_tokens: int
    truncated: bool


def read_opening(path: Path) -> OpeningText:
    """Read only a bounded opening; incomplete boundary codepoints are omitted.

    Strict UTF-8 validation applies to the read opening, not the unseen tail.
    The extra byte detects oversize and is never included in model input.
    Filesystem stability and symlink safety are the processing caller's job.
    """
    with path.open("rb") as source:
        data = source.read(MAX_READ_BYTES + 1)
    truncated = len(data) > MAX_READ_BYTES
    opening = data[:MAX_READ_BYTES]
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    text = decoder.decode(opening, final=not truncated)
    return OpeningText(text=text, read_bytes=len(opening), read_truncated=truncated)


def prepare_input(processor: Any, schema: Any, opening: OpeningText) -> PreparedInput:
    """Fit an opening prefix to the complete schema's exact encoder budget.

    Search over Unicode codepoints, never encoded bytes. The actual processor
    counts schema, descriptions, prefix and special tokens. Binary search need
    not find the longest prefix (token counts can be non-monotonic), but every
    accepted prefix is explicitly verified within budget before it is returned.
    """
    def count(text: str) -> int:
        batch = processor.collate_fn_inference([(text, schema.build())], max_len=None)
        return int(batch.input_ids.shape[1])

    if count("") > ENCODED_TOKEN_BUDGET:
        raise ValueError("Category schema alone exceeds the 512 encoded-token input budget")
    text = opening.text
    if not text.strip():
        raise ValueError("No usable UTF-8 text in bounded opening")
    tokens = count(text)
    if tokens <= ENCODED_TOKEN_BUDGET:
        return PreparedInput(text, tokens, opening.read_truncated)
    low, high = 0, len(text)
    while low + 1 < high:
        middle = (low + high) // 2
        if count(text[:middle]) <= ENCODED_TOKEN_BUDGET:
            low = middle
        else:
            high = middle
    excerpt = text[:low]
    tokens = count(excerpt)
    if not excerpt.strip() or tokens > ENCODED_TOKEN_BUDGET:
        raise ValueError("No usable document opening fits the 512 encoded-token input budget")
    return PreparedInput(excerpt, tokens, True)
