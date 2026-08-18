# Book to Markdown

Convert technical and scientific books into one clean, page-free Markdown file per title. Extraction, cleaning, validation, and auditing scripts turn PDF, EPUB, HTML, DOCX, ODT, DjVu, and text into greppable agent reference text.

<!-- screenshots:begin (managed by screenshot-docs) -->
<!-- screenshots:end -->

## Tools

Scripts are grouped by stage: `extract/`, `cleanup/`, and `audit/`. They import the sibling `markdown_quality` module and the `pdf_extract` package at the repo root, so run them after `source source_me.sh` (which puts the repo root on `PYTHONPATH`).

- **Extract** (`extract/`) - `pdf_raw_text_extraction_to_markdown.py`, `pdf_ocr_text_extraction_to_markdown.py`, `epub_structure.py`, `epub_ocr.py`, `semantic_markdown.lua` (Pandoc filter).
- **Cleanup** (`cleanup/`) - `clean_markdown.py`, `wrap_malformed_tables.py`, `compare_markdown_candidates.py`, `mathml_to_latex.py`.
- **Audit** (`audit/`) - `validate_markdown_v2.py` (preferred), `validate_markdown_delivery.py`, `audit_markdown_duplication.py`, `audit_markdown_residue.py`, `archive_processed_sources.py`.

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
- [docs/USAGE.md](docs/USAGE.md) - workflows, CLI flags, and examples.
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - change history.
