# Code architecture

## Overview

`book-to-markdown` is a Python toolchain that converts technical and scientific books from PDF, EPUB, HTML, DOCX, ODT, DjVu, and text into one page-free Markdown file per title. Scripts are grouped by stage into `extract/`, `cleanup/`, and `audit/`, with shared libraries at the repo root and tests under `tests/`.

## Major components

- Extraction CLIs in `extract/`: raw-text PDF extraction, OCR PDF extraction, EPUB structure inspection, EPUB OCR, and the Pandoc semantic filter `semantic_markdown.lua`.
- Shared libraries at the repo root: `markdown_quality.py` and the `pdf_extract/` package used by the PDF extractors.
- Cleaning and repair in `cleanup/`: `clean_markdown.py`, `wrap_malformed_tables.py`, `compare_markdown_candidates.py`, and `mathml_to_latex.py`.
- Validation and auditing in `audit/`: `validate_markdown_v2.py`, `validate_markdown_delivery.py`, `audit_markdown_duplication.py`, `audit_markdown_residue.py`, and `archive_processed_sources.py`.

## Data flow

1. Choose a source format and run the matching extractor in `extract/` (or Pandoc with `extract/semantic_markdown.lua`).
2. Clean and repair the resulting Markdown with `cleanup/clean_markdown.py`.
3. Validate the final file with `audit/validate_markdown_v2.py`.
4. Audit the corpus with the duplication and residue auditors in `audit/` when needed.
5. Archive processed source files with `audit/archive_processed_sources.py`.

## Testing and verification

Tests live in `tests/` and run with `pytest` after `source source_me.sh`, which puts the repo root on `PYTHONPATH` so scripts in `extract/`, `cleanup/`, and `audit/` can import `markdown_quality` and `pdf_extract`.

## Extension points

- Add a new extractor CLI in `extract/` and import `markdown_quality.py` or `pdf_extract/` for shared cleanup behavior.
- Add new audit detectors in `audit/audit_markdown_*.py`.
- Extend the Pandoc filter in `extract/semantic_markdown.lua` for new heading or semantic rules.

## Known gaps

- Packaging or install metadata beyond `pip_requirements.txt` is not present.
- CI/release automation is not represented in docs yet.
