# Disposable PDF fixtures

These synthetic PDFs contain no personal data. Integration tests exercise actual PDF parsing rather than replacing the extractor.

| Fixture | Purpose |
| --- | --- |
| `invoice.pdf` | One-page English invoice; extracted line: `Invoice 1048: Payment of USD 2400 is due September 30, 2026.` |
| `multilingual.pdf` | Three pages: blank, `First page: Invoice payment due.`, then `發票付款期限：請於月底前支付費用。` |
| `blank.pdf` | One blank page without usable text |
| `image-only.pdf` | One page containing an 8-by-8 black image, without text |
| `encrypted.pdf` | Password-protected text; user password `secret`, owner password `owner` |

Fixtures were created with ReportLab 5.0.1 using its invariant-output option. Runtime tests use pypdf to compose additional long, oversized-stream and nested-form PDFs in disposable test folders; ReportLab is not a runtime or test dependency.

The multilingual fixture embeds a subset of **Noto Sans TC**, licensed under the SIL Open Font License 1.1. The complete license is included in `OFL.txt`. The font came from [Google Fonts](https://github.com/google/fonts/tree/main/ofl/notosanstc), file `NotoSansTC[wght].ttf`, SHA-256 `864727d210d54f2537bbe23b3a839436c3992af72de9322af5270897246bd44f`.

These fixtures verify processing behavior, not representative PDF extraction or classification quality.
