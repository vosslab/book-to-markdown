# News

## v26.10 - 2026-10-11

### Highlights

- Safer direct publication now promotes independently reviewed Markdown candidates with atomic
  publication and recovery reporting.
- PDF, OCR, and AZW3 conversion preserve more useful document structure, including superscripts,
  code, table boundaries, and numbered labels.
- Markdown cleanup and PDF processing were split into focused modules without changing their
  command-line behavior.

### Upgrade notes

- Install the optional `mobi` package from `pip_extra.txt` before extracting AZW3 files. Core
  installation no longer includes it.
