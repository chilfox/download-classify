"""Bounded document opening excerpts for the approved local model input policy.

No model imports, inference, or movement here. The caller captures a schema and
must use the returned text with that same schema and max_len=None. Results must
show `truncated` to disclose excerpt-based decisions, including NeedsReview.
"""
from __future__ import annotations

import codecs
import io
import logging
import os
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from pypdf import PdfReader, apply_configuration

MAX_READ_BYTES = 64 * 1024
ENCODED_TOKEN_BUDGET = 512
MAX_PDF_PAGES = 20
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_STREAM_BYTES = 1024 * 1024


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
    """Read a bounded opening from UTF-8 documents or text-based PDFs.

    Strict UTF-8 validation applies to the text-file opening, not the unseen tail.
    The extra byte detects oversize and is never included in model input.
    Reject symlinks at open time and non-regular descriptors, even if an entry
    changes after scanning. The caller still checks source stability afterward.
    """
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("Source is not a regular file")
        if path.suffix.lower() == ".pdf":
            return _read_pdf_opening(source)
        data = source.read(MAX_READ_BYTES + 1)
    truncated = len(data) > MAX_READ_BYTES
    opening = data[:MAX_READ_BYTES]
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    text = decoder.decode(opening, final=not truncated)
    return OpeningText(text=text, read_bytes=len(opening), read_truncated=truncated)


@contextmanager
def _reject_pdf_warnings():
    """Treat parser recovery/skipped content as failure, not a complete excerpt.

    pypdf logs some nested-form decoding failures instead of raising them. Only
    observe warnings from this extraction thread; never change logger levels or
    interfere with other readers. Retain only the first warning.
    """
    thread_id = threading.get_ident()
    warnings = []

    class ExtractionWarnings(logging.Handler):
        def emit(self, record):
            if record.thread == thread_id and not warnings:
                warnings.append(record.getMessage()[:500])

    logger = logging.getLogger("pypdf")
    handler = ExtractionWarnings(level=logging.WARNING)
    logger.addHandler(handler)
    try:
        yield
        if warnings:
            raise ValueError(f"PDF text extraction reported incomplete or invalid content: {warnings[0]}")
    finally:
        logger.removeHandler(handler)
        handler.close()


def _read_pdf_opening(source: BinaryIO) -> OpeningText:
    """Extract a bounded prefix without modifying the original PDF.

    Read a bounded snapshot even if the source grows after fstat. Decoder limits
    apply before materializing content, including nested forms. These practical
    limits are not a hard wall-clock deadline or process-memory guarantee.
    """
    snapshot = source.read(MAX_PDF_BYTES + 1)
    if len(snapshot) > MAX_PDF_BYTES:
        raise ValueError("PDF source exceeds the 10 MiB extraction limit")
    with _reject_pdf_warnings(), apply_configuration(
        maximum_declared_stream_length=MAX_PDF_BYTES,
        array_based_stream_maximum_output_length=MAX_PDF_STREAM_BYTES,
        zlib_maximum_output_length=MAX_PDF_STREAM_BYTES,
        lzw_maximum_output_length=MAX_PDF_STREAM_BYTES,
        run_length_maximum_output_length=MAX_PDF_STREAM_BYTES,
        brotli_maximum_output_length=MAX_PDF_STREAM_BYTES,
        stream_decoding_work_maximum_length=4 * MAX_PDF_STREAM_BYTES,
        stream_filters_maximum_length=8,
        xform_maximum_invocations_per_extraction=100,
        jbig2dec_binary=None,
    ):
        try:
            reader = PdfReader(io.BytesIO(snapshot), strict=True)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported")
            page_count = len(reader.pages)
            data = bytearray()
            truncated = page_count > MAX_PDF_PAGES
            for index in range(min(page_count, MAX_PDF_PAGES)):
                page = reader.pages[index]
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > MAX_PDF_STREAM_BYTES:
                    raise ValueError("PDF page content exceeds the 1 MiB extraction limit")
                chunk = (("\n" if data else "") + page.extract_text()).encode("utf-8")
                remaining = MAX_READ_BYTES - len(data)
                data.extend(chunk[:remaining])
                if len(chunk) > remaining or (len(data) == MAX_READ_BYTES and index + 1 < page_count):
                    truncated = True
                    break
        except Exception as error:
            raise ValueError(f"PDF text extraction failed: {error}") from error
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    text = decoder.decode(bytes(data), final=not truncated)
    if not text.strip():
        if truncated:
            raise ValueError("No usable text within PDF extraction limits; unread pages may contain text")
        raise ValueError("No usable text in PDF; OCR is not supported")
    return OpeningText(text, len(text.encode("utf-8")), truncated)


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
