# Release history

## v26.10 - 2026-10-11

### Highlights

- Add direct canonical publication for independently reviewed Markdown candidates, including
  source-bound admission, title lifecycle reservations, atomic publication, and recovery reporting.
- Add AZW3 extraction for unencrypted Mobipocket/AZW3 v8 HuffDic records and preserve readable
  tables, code, and numbered headings through conversion.
- Improve PDF and OCR conversion by preserving superscripts, glyph-gap word boundaries, paragraph
  boundaries, and distinct chapter, part, and appendix labels while filtering only complete
  running-head lines.
- Separate promotion admission, PDF text cleanup, and Markdown layout responsibilities into focused
  modules while retaining the existing command-line behavior and reports.

### Notable fixes

- Tighten Markdown validation around CommonMark fence boundaries, escaped image-like content,
  nonprinting controls, and source-aware Unicode handling in code blocks.
- Keep promotion artifacts recoverable when snapshot, predecessor-backup, or final lifecycle work
  cannot complete.
- Report unresolved PDF line-break hyphens without changing the cleaned text, including examples
  across protected Markdown boundaries.

### Compatibility notes

- `mobi` is now an optional AZW3 dependency in `pip_extra.txt`. Install it only when extracting
  AZW3 files; the core requirements no longer install it.
- Identified books may use `-UNDATED.md` when a publication year cannot be verified.
- Candidate promotion now requires a source-bound independent review. Word-count and disposition
  totals remain diagnostic evidence rather than admission gates.

### Validation

- The promotion and PDF module splits passed the full suite with 1,277 tests and no source-size
  warnings.
- Temporary before-and-after checks covered Markdown layout pass combinations, command-line output,
  JSON reports, removal sidecars, promotion publication, and PDF definitions; the temporary checks
  were removed after verification.
