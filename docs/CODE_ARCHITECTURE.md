# Code architecture

## Overview

`book-to-markdown` converts technical and scientific books into one page-free Markdown file per
title. The Python command-line tools form an extraction, cleanup, audit, and promotion pipeline.
They run from the repository root after [`source_me.sh`](../source_me.sh) makes the root importable.

## Major components

- [`extract/`](../extract/) contains format-specific command-line entry points. PDF commands use
  the shared [`pdf_extract/`](../pdf_extract/) package; EPUB tools inspect or repair archive
  structure; [`azw3_to_markdown.py`](../extract/azw3_to_markdown.py) decodes supported AZW3 input.
- [`pdf_extract/models.py`](../pdf_extract/models.py) defines page, removal, running-head, and
  conversion records. [`raw_text.py`](../pdf_extract/raw_text.py) reads a PDF text layer and
  restores explicit superscripts; [`ocr_text.py`](../pdf_extract/ocr_text.py) obtains OCR text;
  [`spread_ocr.py`](../pdf_extract/spread_ocr.py) handles two-page scans.
- [`pdf_extract/text.py`](../pdf_extract/text.py) normalizes page text and joins eligible page
  seams. [`page_cleanup.py`](../pdf_extract/page_cleanup.py) identifies running heads, edge page
  numbers, picture blocks, and numbered headings. [`cleanup.py`](../pdf_extract/cleanup.py)
  coordinates conversion, scoring, report data, and removal sidecars.
- [`cleanup/clean_markdown.py`](../cleanup/clean_markdown.py) applies the auditable Markdown
  cleanup pipeline. [`cleanup/layout.py`](../cleanup/layout.py) protects Markdown structure and
  reflows ordinary prose; [`reporting.py`](../cleanup/reporting.py) renders the cleanup report.
  The remaining cleanup commands repair tables and pipe artifacts, combine OCR halves, compare
  candidates, or convert MathML.
- [`markdown_quality.py`](../markdown_quality.py) supplies Markdown-aware helpers shared by
  extraction, cleanup, and audit code.
- [`audit/`](../audit/) validates staged Markdown, detects duplication and residue, archives
  processed sources, and promotes accepted candidates. [`promotion_admission.py`](../audit/promotion_admission.py)
  owns lifecycle configuration, admission evidence, and validator invocation; [`promote_validated_candidate.py`](../audit/promote_validated_candidate.py)
  owns locks, snapshots, backups, atomic publication, and readback verification.

## Data flow

1. An entry point in [`extract/`](../extract/) reads a source format and writes staged Markdown or
   page-marked text. PDF paths create per-page records before flattening pages.
2. [`pdf_extract/text.py`](../pdf_extract/text.py) joins eligible page seams, while
   [`pdf_extract/page_cleanup.py`](../pdf_extract/page_cleanup.py) records page-aware removals.
   [`pdf_extract/cleanup.py`](../pdf_extract/cleanup.py) writes Markdown, report JSON, and a
   removal sidecar for PDF conversions.
3. [`cleanup/clean_markdown.py`](../cleanup/clean_markdown.py) applies conservative cleanup
   passes. Each removal is recorded and the command can measure or skip individual passes for
   comparison.
4. [`audit/validate_markdown_v2.py`](../audit/validate_markdown_v2.py) and
   [`audit/validate_markdown_delivery.py`](../audit/validate_markdown_delivery.py) validate a
   staged candidate. The duplication and residue commands provide additional diagnostic evidence.
5. [`audit/promote_validated_candidate.py`](../audit/promote_validated_candidate.py) reads the
   candidate-adjacent admission record through [`audit/promotion_admission.py`](../audit/promotion_admission.py),
   revalidates the admitted content, and publishes it with the selected lifecycle.

## Testing and verification

- [`tests/`](../tests/) contains the pytest suite, including import, style, security, source-size,
  and behavior tests. Run it with `source source_me.sh && pytest tests/`.
- [`pytest.ini`](../pytest.ini) disables pytest's cache provider. [`tests/conftest.py`](../tests/conftest.py)
  configures test-time warning behavior.
- [`docs/E2E_TESTS.md`](E2E_TESTS.md) describes the separately scoped end-to-end evidence lane.

## Extension points

- Add a source-format entry point under [`extract/`](../extract/) and reuse the relevant
  [`pdf_extract/`](../pdf_extract/) module or [`markdown_quality.py`](../markdown_quality.py)
  helper instead of duplicating page or Markdown logic.
- Add a cleanup pass to [`cleanup/clean_markdown.py`](../cleanup/clean_markdown.py) when it belongs
  in the ordered cleanup pipeline. Put reusable protected-span or reflow behavior in
  [`cleanup/layout.py`](../cleanup/layout.py).
- Add a page-aware PDF transformation to [`pdf_extract/page_cleanup.py`](../pdf_extract/page_cleanup.py)
  and preserve its removal record in the conversion result.
- Add a new diagnostic under [`audit/`](../audit/) when it produces evidence distinct from the
  structural validators. Extend admission policy in
  [`audit/promotion_admission.py`](../audit/promotion_admission.py), while publication mechanics
  remain in [`audit/promote_validated_candidate.py`](../audit/promote_validated_candidate.py).

## Known gaps

- Verify an end-to-end sample for each supported source format before claiming uniform conversion
  quality across PDF, EPUB, and AZW3 inputs.
