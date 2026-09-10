# Book to Markdown

Convert technical and scientific books into page-free Markdown. Extraction, cleaning, validation,
auditing, and explicit lifecycle promotion keep staged candidates separate from canonical delivery.

<!-- screenshots:begin (managed by screenshot-docs) -->
<!-- screenshots:end -->

## Tools

Scripts are grouped by stage: `extract/`, `cleanup/`, and `audit/`. They import the sibling
`markdown_quality` module and the `pdf_extract` package at the repository root, so run them after
`source source_me.sh`.

- **Extract** (`extract/`) - `pdf_to_markdown.py` (qualified OCR entry point),
  raw-text/OCR PDF extraction, EPUB structure/OCR, and `semantic_markdown.lua`.
- **Cleanup** (`cleanup/`) - `clean_markdown.py`, `wrap_malformed_tables.py`,
  `compare_markdown_candidates.py`, `mathml_to_latex.py`, and related repair helpers.
- **Audit** (`audit/`) - `validate_markdown_v2.py` (preferred),
  `validate_markdown_delivery.py`, `promote_validated_candidate.py`, duplication/residue audits,
  and `archive_processed_sources.py`.

## Quick start

```bash
source source_me.sh
python3 extract/pdf_raw_text_extraction_to_markdown.py book.pdf -o /tmp/book.raw.md
python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md
python3 audit/validate_markdown_v2.py /path/to/delivery-directory
```

## Documentation

- [docs/CODE_ARCHITECTURE.md](docs/CODE_ARCHITECTURE.md) - component and data-flow overview.
- [docs/FILE_STRUCTURE.md](docs/FILE_STRUCTURE.md) - repository layout.
- [docs/INSTALL.md](docs/INSTALL.md) - setup and dependencies.
- [docs/USAGE.md](docs/USAGE.md) - workflows, CLI flags, and promotion commands.
- [docs/HUMAN_GUIDANCE.md](docs/HUMAN_GUIDANCE.md) - durable project guidance.
- [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md) - durable technical decisions.
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - change history.
