# Usage

One paragraph: run the toolchain from the repo root after sourcing `source_me.sh`; scripts are grouped into `extract/`, `cleanup/`, and `audit/`.

## Quick start

- Convert a PDF with real text layer:
  - `python3 extract/pdf_raw_text_extraction_to_markdown.py book.pdf -o /tmp/book.raw.md`
  - `python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md`
- Validate the result:
  - `python3 audit/validate_markdown_v2.py /path/to/delivery-directory`
- Audit duplication:
  - `python3 audit/audit_markdown_duplication.py /path/to/delivery-dir --json-report /tmp/audit.duplication.json`

## Extract

- `extract/pdf_raw_text_extraction_to_markdown.py` - PDF text-layer extraction.
- `extract/pdf_ocr_text_extraction_to_markdown.py` - OCR extraction for image-only PDFs.
- `extract/epub_structure.py` - inspect and repair EPUB heading structure.
- `extract/epub_ocr.py` - OCR scanned EPUB packages.
- `extract/semantic_markdown.lua` - Pandoc Lua filter for EPUB/HTML semantics.

## Cleanup

- `cleanup/clean_markdown.py` - repair flat Markdown or converter output.
- `cleanup/wrap_malformed_tables.py` - protect malformed pipe blocks for repair.
- `cleanup/compare_markdown_candidates.py` - compare two Markdown candidates.
- `cleanup/mathml_to_latex.py` - convert MathML to LaTeX.

## Audit

- `audit/validate_markdown_v2.py` - block-aware Markdown validator (preferred).
- `audit/validate_markdown_delivery.py` - legacy validator.
- `audit/audit_markdown_duplication.py` - detect OCR doubling/stutter.
- `audit/audit_markdown_residue.py` - scan for extraction residue and bad characters.
- `audit/archive_processed_sources.py` - archive processed source files after validation.

## Examples

- EPUB via Pandoc plus cleaner:
  - `pandoc book.epub --from epub --to gfm --wrap=none --standalone --lua-filter=extract/semantic_markdown.lua --metadata title="Title" --metadata date="YYYY-MM-DD" --metadata source="book.epub" --metadata shift-headings=true -o /tmp/book.raw.md`
  - `python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md`
- MathML conversion:
  - `python3 cleanup/mathml_to_latex.py --markdown book.md --lines 120:180 --in-place`

## Inputs and outputs

- Inputs: PDF, EPUB, HTML, DOCX, ODT, Markdown, text, DjVu.
- Outputs: cleaned Markdown files, JSON reports, removed-text sidecars, deduped review copies, archived sources under `COMPLETED_SOURCE/`.

## Known gaps

- Full CLI flag reference is not centralized in one file yet.
