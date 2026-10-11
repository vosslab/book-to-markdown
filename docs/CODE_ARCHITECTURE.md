# Code architecture

## Overview

`book-to-markdown` converts technical and scientific books from PDF, EPUB, HTML, DOCX, ODT,
DjVu, and text into one page-free Markdown file per title. Scripts are grouped into `extract/`,
`cleanup/`, and `audit/`, with shared libraries at the repository root and tests under `tests/`.

## Major components

- Extraction CLIs in `extract/`: raw-text PDF extraction, OCR PDF extraction, EPUB structure
  inspection, EPUB OCR, and the Pandoc semantic filter `semantic_markdown.lua`.
- Shared libraries at the repository root: `markdown_quality.py` and the `pdf_extract/` package.
- Cleaning and repair in `cleanup/`: `clean_markdown.py`, `wrap_malformed_tables.py`,
  `compare_markdown_candidates.py`, and `mathml_to_latex.py`.
- Validation and auditing in `audit/`: `validate_markdown_v2.py`,
  `validate_markdown_delivery.py`, `promote_validated_candidate.py`, duplication/residue audits,
  and source archival.

## Data flow

1. Choose a source format and run the matching extractor in `extract/`.
2. Clean and repair Markdown with `cleanup/clean_markdown.py`.
3. Validate the staged candidate with the delivery and v2 validators.
4. Bind validation evidence and an explicit lifecycle in candidate-adjacent `admission_gate.json`.
5. Use `audit/promote_validated_candidate.py` to publish. For repairs to an existing canonical
   book, `DIRECT_CANONICAL_REPLACEMENT` is the primary lifecycle: admission and an independent
   review receipt bind the destination and predecessor path/hash; the promoter rechecks predecessor
   identity and hash under the visible title lock, creates and verifies an exclusive predecessor
   backup, then uses `os.replace` and canonical readback. The canonical path stays present, with no
   PENDING gap. The legacy `SUPERSEDES_PENDING` five-positional lifecycle remains for a real
   PENDING predecessor. `NEW_TITLE_NO_PREDECESSOR` remains for a new title and requires an explicit
   accepted admission status, the expected-absent PENDING path, a destination lock, and verified
   snapshot for atomic no-clobber publication.
6. Canonical hash readback and synchronization establish promotion; the promoter retains the staged
   candidate rather than unlinking its mutable path after commit.
7. A separate receipt owner writes the external receipt and sidecar, then an independent strict
   closure step verifies lifecycle authority and identity before any staged-candidate reclamation.

## Testing and verification

Tests live in `tests/` and run with `pytest` after `source source_me.sh`, which puts the
repository root on `PYTHONPATH` for scripts in `extract/`, `cleanup/`, and `audit/`.

## Extension points

- Add an extractor CLI in `extract/` and import `markdown_quality.py` or `pdf_extract/` for
  shared cleanup behavior.
- Add audit detectors in `audit/audit_markdown_*.py`.
- Extend `extract/semantic_markdown.lua` for heading or semantic rules.
