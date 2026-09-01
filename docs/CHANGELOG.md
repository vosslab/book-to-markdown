# Changelog

All notable changes to this project are documented in this file.

## 2026-08-29

### Fixes and Maintenance
- Restored `extract/pdf_to_markdown.py` as the qualified Tesseract OCR entry point, sharing the established OCR extraction, page cleanup, removal-sidecar, and JSON-evidence behavior.
- Documented the Tesseract environment used by the qualified PDF path and added a CLI-contract test.

## 2026-08-18

### Added
- Initial migration from `vosslab-skills` book-to-markdown skill toolchain.
- Scripts grouped by stage in `extract/`, `cleanup/`, and `audit/` for extraction, cleaning, validation, auditing, and archiving.
- `tests/` with migrated test suite covering cleanup and audit behavior.
- `extract/pdf_ocr_spread_halves.py` + `pdf_extract/spread_ocr.py` - half-page OCR for two-page-spread scans (landscape PDF pages holding two book pages), with OMP_THREAD_LIMIT=1 per worker to avoid tesseract CPU thrashing.
- `cleanup/assemble_ocr_halves.py` - config-driven assembly of half-page OCR output into clean Markdown (running-head/page-number stripping, chapter detection, paragraph joining, front matter + Contents, ASCII mapping); book-specific data comes from a JSON config.
- `cleanup/fix_pipe_artifacts.py` - strips page-edge/column-rule pipe prefixes from OCR prose while preserving real Markdown tables.

### Changed
- README rewritten for standalone repo audience with tool index and quick-start commands.
- `source_me.sh` now puts the repo root on `PYTHONPATH` so stage-folder scripts can import shared modules.

### Removals and Deprecations
- None yet.
