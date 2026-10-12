# Usage

Run the command-line toolchain from the repository root after loading `source_me.sh`. Extractors
write staged Markdown; cleanup and audits prepare and assess it before explicit canonical promotion.

## Quick start

Extract a PDF that has a text layer, clean the result, then validate the delivery directory:

```bash
source source_me.sh
python3 extract/pdf_raw_text_extraction_to_markdown.py book.pdf -o /tmp/book.raw.md
python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md
python3 audit/validate_markdown_v2.py /path/to/delivery-directory
```

For an image-only or degraded PDF, use the OCR entry point instead:

```bash
source source_me.sh
python3 extract/pdf_to_markdown.py book.pdf -o /tmp/book.raw.md
python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md
```

Use the optional AZW3 route for an unencrypted AZW3 book after installing `pip_extra.txt`:

```bash
source source_me.sh
python3 extract/azw3_to_markdown.py book.azw3 -o /tmp/book.raw.md
```

## Common commands

- `extract/pdf_raw_text_extraction_to_markdown.py PDF -o OUTPUT` extracts a PDF text layer.
- `extract/pdf_to_markdown.py PDF -o OUTPUT` runs the qualified Tesseract OCR pipeline.
- `cleanup/clean_markdown.py -i INPUT -o OUTPUT` repairs and normalizes extracted Markdown.
- `cleanup/clean_markdown.py -i INPUT --measure` reports pass measurements without writing Markdown.
- `cleanup/clean_markdown.py -i INPUT --skip PASS` disables one named cleanup pass; repeat the
  flag to skip more than one pass.
- `audit/validate_markdown_v2.py INPUT --json-report REPORT` validates a Markdown file or
  delivery directory and writes machine-readable results.

Use `--help` on a command for its full options. PDF extractors accept `--pages` for a zero-based
page subset. OCR extractors also accept the `--skip-running-heads`, `--skip-page-numbers`,
`--skip-seams`, and `--skip-heading-synthesis` controls.

## Inputs and outputs

- PDF text-layer and OCR extraction write page-free Markdown. Raw text extraction preserves
  explicitly flagged superscript spans as ASCII `^{...}` notation and separates text blocks with
  blank lines.
- Cleanup accepts extracted Markdown or text and writes cleaned Markdown beside the input unless
  `-o` selects another path. Its optional JSON report is written beside the output by default.
- AZW3 extraction writes Markdown from recovered reading XHTML. Preformatted code and source-table
  structure are retained.
- Canonical filenames use metadata title words joined by underscores and a verified year as
  `-YYYY.md`. Use `-UNDATED.md` only when bounded identity checks establish the title and author
  but cannot verify a publication year.

## Promotion

`audit/promote_validated_candidate.py` publishes a candidate only after the candidate-adjacent
`admission_gate.json`, its independent-review receipt, the supplied validator, and
`audit/validate_markdown_v2.py` all agree. It retains the staged candidate, keeps visible title
locks under `conversion_state/locks/`, and reads back hashes after publication.

Replace an existing canonical book with its expected predecessor hash:

```bash
source source_me.sh && python3 audit/promote_validated_candidate.py \
  --replace-canonical CANDIDATE DESTINATION SUPERSEDED_ROOT EXPECTED_PREDECESSOR_SHA256 VALIDATOR
```

Publish a new title that has no predecessor:

```bash
source source_me.sh && python3 audit/promote_validated_candidate.py \
  --new-title CANDIDATE DESTINATION EXPECTED_ABSENT_PENDING VALIDATOR
```

Preserve a real PENDING predecessor with the compatible five-positional invocation:

```bash
source source_me.sh && python3 audit/promote_validated_candidate.py \
  CANDIDATE DESTINATION PENDING SUPERSEDED_ROOT VALIDATOR
```

Direct replacement requires the `DIRECT_CANONICAL_REPLACEMENT` lifecycle in the admission data.
The promoter creates and verifies a no-clobber backup, atomically replaces the canonical file, and
never creates a PENDING gap. New-title promotion requires the admitted absent-PENDING path and
does not create a superseded artifact. Publication is not strict closure: the separate receipt
owner writes and verifies the external receipt and its newline-terminated SHA-256 sidecar.

## Audits

- `audit/audit_markdown_duplication.py` detects repeated OCR prose; `--dedup` writes a separate
  copy and never overwrites the input.
- `audit/audit_markdown_residue.py` scans Markdown files or directories for residue and supports
  `--json-report`.
- `audit/archive_processed_sources.py` archives processed source files after validation.

## Known gaps

- TODO: add a documented end-to-end example with a public, redistributable source book.
