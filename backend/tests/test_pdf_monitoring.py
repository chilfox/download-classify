from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.tests.test_monitoring import BlockingModel, Model, wait_for

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "pdf"
INVOICE = "Invoice 1048: Payment of USD 2400 is due September 30, 2026."


class InvoiceModel(Model):
    def classify(self, opening, categories):
        if opening.text.strip() != INVOICE:
            raise ValueError("Expected the invoice's extracted text")
        return super().classify(opening, categories)


def test_new_pdf_moves_original_bytes_using_extracted_text(tmp_path):
    content = (FIXTURES / "invoice.pdf").read_bytes()
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, InvoiceModel(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        (tmp_path / "invoice.PDF").write_bytes(content)
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved"
        assert row["suggestion"] == "Work"
        assert row["truncated"] is False
        assert row["recorded"] is True
        assert (tmp_path / "Work" / "invoice.PDF").read_bytes() == content
        assert not (tmp_path / "invoice.PDF").exists()
        assert not list(tmp_path.rglob("*.txt"))


def test_pdf_collision_preserves_both_original_documents(tmp_path):
    content = (FIXTURES / "invoice.pdf").read_bytes()
    (tmp_path / "Work").mkdir()
    existing = tmp_path / "Work" / "invoice.pdf"
    existing.write_bytes(b"Existing document")
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, InvoiceModel(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        (tmp_path / "invoice.pdf").write_bytes(content)
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved"
        assert row["destination"] == str(tmp_path / "Work" / "invoice (1).pdf")
        assert (tmp_path / "Work" / "invoice (1).pdf").read_bytes() == content
        assert existing.read_bytes() == b"Existing document"


def test_pdf_page_limit_discloses_excerpt_and_ignores_unread_tail(tmp_path):
    writer = PdfWriter()
    page = PdfReader(FIXTURES / "invoice.pdf").pages[0]
    for _ in range(21):
        writer.add_page(page)
    path = tmp_path / "long.pdf"
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        writer.write(path)
        content = path.read_bytes()
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved"
        assert row["truncated"] is True
        assert "Opening excerpt only" in row["reason"]
        assert (tmp_path / "Work" / "long.pdf").read_bytes() == content


@pytest.mark.parametrize("boundary", ["source", "stream"])
def test_pdf_resource_limit_failure_preserves_source_and_continues_monitoring(tmp_path, boundary):
    path = tmp_path / "limited.pdf"
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        if boundary == "source":
            content = (FIXTURES / "invoice.pdf").read_bytes() + b" " * (10 * 1024 * 1024)
            path.write_bytes(content)
        else:
            writer = PdfWriter()
            page = writer.add_blank_page(width=612, height=792)
            stream = DecodedStreamObject()
            stream.set_data(b" " * (1024 * 1024 + 1))
            page.replace_contents(stream.flate_encode())
            writer.write(path)
            content = path.read_bytes()
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "failed"
        assert "limit" in row["reason"].lower()
        assert row["scores"] is None and row["suggestion"] is None
        assert path.read_bytes() == content
        (tmp_path / "later.txt").write_text("New document")
        rows = wait_for(client, lambda rows: len(rows) == 2)
        assert rows[1]["outcome"] == "moved"
        assert (tmp_path / "Work" / "later.txt").read_text() == "New document"


@pytest.mark.parametrize("name, reason", [
    ("encrypted.pdf", "Encrypted"),
    ("blank.pdf", "No usable text in PDF"),
    ("image-only.pdf", "OCR is not supported"),
    ("malformed.pdf", "PDF text extraction failed"),
])
def test_unusable_pdf_fails_without_classification_or_repeated_attempts(tmp_path, name, reason):
    class UnexpectedInference(Model):
        def classify(self, opening, categories):
            raise AssertionError("Unusable PDFs must not reach inference")

    content = b"%PDF broken" if name == "malformed.pdf" else (FIXTURES / name).read_bytes()
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, UnexpectedInference(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        path = tmp_path / name
        path.write_bytes(content)
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "failed"
        assert reason in row["reason"]
        assert row["scores"] is None and row["suggestion"] is None
        assert row["destination"] is None
        assert path.read_bytes() == content
        (tmp_path / "after.zip").write_bytes(b"unsupported")
        rows = wait_for(client, lambda rows: len(rows) == 2)
        assert rows[1]["outcome"] == "skipped"
        assert client.get("/results").json() == rows


def test_pdf_nested_form_decode_failure_does_not_classify_partial_text(tmp_path):
    writer = PdfWriter()
    page = writer.add_page(PdfReader(FIXTURES / "invoice.pdf").pages[0])
    form = DecodedStreamObject()
    form.set_data(b" " * (1024 * 1024 + 1))
    encoded = form.flate_encode()
    encoded[NameObject("/Type")] = NameObject("/XObject")
    encoded[NameObject("/Subtype")] = NameObject("/Form")
    encoded[NameObject("/BBox")] = ArrayObject([NumberObject(n) for n in [0, 0, 612, 792]])
    encoded[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): page["/Resources"]["/Font"]})
    page["/Resources"][NameObject("/XObject")] = DictionaryObject({NameObject("/Limited"): writer._add_object(encoded)})
    stream = DecodedStreamObject()
    stream.set_data(page.get_contents().get_data() + b"\n/Limited Do\n")
    page.replace_contents(stream.flate_encode())
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        path = tmp_path / "nested-limit.pdf"
        writer.write(path)
        content = path.read_bytes()
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "failed"
        assert "PDF text extraction" in row["reason"]
        assert row["scores"] is None and row["suggestion"] is None
        assert path.read_bytes() == content


def test_empty_pdf_prefix_does_not_claim_unread_pages_have_no_text(tmp_path):
    writer = PdfWriter()
    for _ in range(20):
        writer.add_blank_page(width=612, height=792)
    writer.add_page(PdfReader(FIXTURES / "invoice.pdf").pages[0])
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        path = tmp_path / "late-text.pdf"
        writer.write(path)
        content = path.read_bytes()
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "failed"
        assert "unread pages may contain text" in row["reason"]
        assert path.read_bytes() == content


@pytest.mark.parametrize("mode, clear, outcome, suggestion", [
    ("automatic", True, "moved", "Work"),
    ("automatic", False, "needs-review", "NeedsReview"),
    ("suggestions-only", True, "suggestion-only", "Work"),
    ("suggestions-only", False, "suggestion-only", "NeedsReview"),
])
def test_multilingual_pdf_after_blank_page_uses_existing_modes_and_thresholds(tmp_path, mode, clear, outcome, suggestion):
    class MultilingualModel(Model):
        def classify(self, opening, categories):
            if opening.text.strip() != "First page: Invoice payment due.\n\n發票付款期限：請於月底前支付費用。":
                raise ValueError("Expected page-ordered English and Traditional Chinese text")
            scores = {"Work": 0.9 if clear else 0.5, "Personal": 0.1, "Research": 0.1}
            return scores, opening.read_truncated, 100

    content = (FIXTURES / "multilingual.pdf").read_bytes()
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, MultilingualModel(), poll_interval=0.01, mode=mode)) as client:
        client.post("/monitor/start").raise_for_status()
        path = tmp_path / "multilingual.pdf"
        path.write_bytes(content)
        row = wait_for(client, bool)[0]
        assert row["outcome"] == outcome
        assert row["suggestion"] == suggestion
        assert row["truncated"] is False
        if mode == "automatic":
            assert (tmp_path / suggestion / path.name).read_bytes() == content
            assert not path.exists()
        else:
            assert path.read_bytes() == content
            assert row["destination"] is None and row["recorded"] is None
            assert not (tmp_path / "movements.jsonl").exists()
        assert not list(tmp_path.rglob("*.txt"))


def test_pdf_text_limit_keeps_a_unicode_safe_prefix(tmp_path):
    class UnicodeModel(Model):
        def classify(self, opening, categories):
            assert opening.text.startswith("發票付款期限：請於月底前支付費用。\n")
            assert "\ufffd" not in opening.text
            assert 65000 < len(opening.text.encode("utf-8")) <= 65536
            return super().classify(opening, categories)

    writer = PdfWriter()
    page = writer.add_page(PdfReader(FIXTURES / "multilingual.pdf").pages[2])
    stream = DecodedStreamObject()
    stream.set_data(page.get_contents().get_data() * 2000)
    page.replace_contents(stream.flate_encode())
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, UnicodeModel(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        path = tmp_path / "long-unicode.pdf"
        writer.write(path)
        content = path.read_bytes()
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved"
        assert row["truncated"] is True
        assert (tmp_path / "Work" / path.name).read_bytes() == content


def test_pdf_monitoring_preserves_baseline_and_excludes_temporary_nested_and_symlink_files(tmp_path):
    content = (FIXTURES / "invoice.pdf").read_bytes()
    (tmp_path / "baseline.pdf").write_bytes(content)
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, InvoiceModel(), poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / "invoice.pdf").write_bytes(content)
        (tmp_path / "link.pdf").symlink_to(tmp_path / "nested" / "invoice.pdf")
        temporary_names = ["~$draft.pdf", "draft.pdf.part", "draft.pdf.crdownload"]
        for name in temporary_names:
            (tmp_path / name).write_bytes(content)
        (tmp_path / ".new.pdf").write_bytes(content)
        row = wait_for(client, bool)[0]
        assert row["filename"] == ".new.pdf" and row["outcome"] == "moved"
        assert (tmp_path / "Work" / ".new.pdf").read_bytes() == content
        client.post("/monitor/stop").raise_for_status()
        assert client.get("/results").json() == [row]
        assert (tmp_path / "baseline.pdf").read_bytes() == content
        assert (tmp_path / "nested" / "invoice.pdf").read_bytes() == content
        assert (tmp_path / "link.pdf").is_symlink()
        for name in temporary_names:
            assert (tmp_path / name).read_bytes() == content


def test_pdf_changed_during_inference_discards_stale_scores_and_retries(tmp_path):
    class ChangingModel(BlockingModel):
        def classify(self, opening, categories):
            super().classify(opening, categories)
            if opening.text.strip() == INVOICE:
                return {"Work": 0.9, "Personal": 0.1, "Research": 0.1}, False, 100
            return {"Work": 0.1, "Personal": 0.9, "Research": 0.1}, False, 100

    model = ChangingModel()
    updated = (FIXTURES / "multilingual.pdf").read_bytes()
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, model, poll_interval=0.01)) as client:
        client.post("/monitor/start").raise_for_status()
        path = tmp_path / "changing.pdf"
        path.write_bytes((FIXTURES / "invoice.pdf").read_bytes())
        try:
            assert model.entered.wait(2)
            path.write_bytes(updated)
            assert client.get("/results").json() == []
        finally:
            model.release.set()
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved" and row["suggestion"] == "Personal"
        assert (tmp_path / "Personal" / path.name).read_bytes() == updated
        assert not (tmp_path / "Work").exists()
