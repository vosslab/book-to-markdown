# Changelog

All notable changes to this project are documented in this file.

## 2026-10-11

### Additions and New Features

- Add a reproducible README cleanup demonstration and its terminal-style PNG capture, generated
  from actual cleanup and validation CLI output on an authored sample. Capture verified on
  2026-10-12 at 01:01 UTC: `docs/screenshots/cleanup_demo.png`, 1280 by 800 pixels, about 125 KB.
- Add file-format, development, troubleshooting, related-project, news, and release-history
  documentation. Refresh the README, install/usage guides, architecture, and file map.

### Fixes and Maintenance

- Remove the temporary SWIG warning filters and switch legacy `fitz` imports, calls, and type
  annotations directly to `pymupdf`, without aliases. Tests import the dependency directly.
  Keep the unmodified upstream PyMuPDF dependency; its macOS SWIG warnings remain visible pending
  an upstream wheel fix. Do not maintain a custom dependency build for this warning.
- Split promotion admission/configuration into `audit/promotion_admission.py`, leaving filesystem
  publication in `audit/promote_validated_candidate.py`. Preserve validation ordering, locks,
  predecessor backups, and recovery behavior.
- Split PDF page-aware cleanup into `pdf_extract/page_cleanup.py` and shared records into
  `pdf_extract/models.py`, with normalization and page joining in `pdf_extract/text.py`.
  Update consumers to import each owner directly while preserving
  cleanup ordering, scoring, and reports.
- Extract protected Markdown regions and prose reflow into `cleanup/layout.py`, reducing
  `cleanup/clean_markdown.py` below the source-line warning threshold while preserving pass ordering,
  CLI output, metrics, and removal sidecars. Update the PDF reflow test to use the layout owner.
- Preserve distinct standalone numbered chapter, part, and appendix labels while measuring PDF running heads.
- Measure unresolved line-break hyphens across unprotected blank-line gaps while preserving the
  existing cleaned text and reporting the original prefix line.
- Synchronized shared style guides, tests, and repository support files from the starter template.

### Removals and Deprecations

- Remove two more repository-owned cases (80 lines): the nested CommonMark fence parsing matrix
  and the internal dehyphenation diagnostic sample-cap assertion. Retain ordinary valid/unclosed
  fence checks and cleanup output/metric coverage. The removed tests no longer guard nested fence
  edge cases or the exact diagnostic sample limit; vendored tests remain unchanged.
- Make `mobi` an on-demand AZW3 extra in `pip_extra.txt` instead of a core requirement.
  Load it only during extraction, with an installation message when absent. Remove the two
  mocked unpacking cleanup tests; retain dependency-free AZW3 renderer coverage.
- Remove ten repository-owned test cases, including the parser-default and option-registration
  modules, while retaining content-preservation, admission, and recovery checks.
- Remove duplicated cleanup and validator assertions and custom test module-loading machinery.
  Retain connector and markup preservation through output assertions in existing duplication tests.
- Drop dedicated checks of CLI defaults, pytest option-registration details, terminal report wording,
  and intermediate token representations. Vendored tests and shared dependencies remain unchanged.

### Developer Tests and Notes

- Promotion and PDF module splits pass the full suite (1,277 tests), with no source-size warnings.
  Temporary checks verified preserved promotion/PDF definitions and new-title publication; removed
  those checks after verification. No permanent tests were added for the splits.
- Verified the layout extraction with 77 temporary before/after checks covering pass combinations,
  unchanged helper bodies, CLI output, JSON reports, and removal sidecars; removed the temporary checks.
- Pruning review baseline: all 94 repository-owned cases passed; the full suite reported 1,264
  passes and the existing 1,005-line cleanup module failure in the vendored source-line gate.
- After pruning, collection confirms 84 repository-owned cases across seven modules. All 60 affected
  cases passed; the full suite reported 1,228 passes and only the same source-line gate failure.
- Separately reproduced deduplication changing repeated prose inside fenced content even when the
  auditor reports that content clean. This production defect remains outside test pruning.

## 2026-10-10

### Fixes and Maintenance

- Preserve the ring-above scientific symbol through ASCII cleanup instead of dropping it during
  Unicode compatibility normalization.
- Preserve AZW3 table-cell line breaks as readable separators and leave fenced code unchanged during
  numbered-heading joining.
- Preserve AZW3 preformatted code indentation and explicit table row/cell boundaries in Markdown.
- Disable pytest cache generation so tool tests do not create hidden cache files.
- Preserve explicitly flagged PDF superscript spans as ASCII `^{...}` text during raw extraction.
- Preserve blank-line boundaries between distinct PDF text blocks so cleanup reflows only within
  each block.
- Recover PDF word boundaries represented only by clear glyph-position gaps while preserving
  touching glyphs across style changes.

### Behavior or Interface Changes

- Accept `-UNDATED.md` for identified books whose publication year cannot be verified.
- Require a source-bound independent review for every candidate promotion; word counts and source-disposition totals remain diagnostic evidence, not numeric admission gates.

## 2026-10-09

### Fixes and Maintenance

- Keep Mobipocket unpacking output in a reader-owned temporary directory and remove it after text
  parsing, including when EPUB parsing fails.

## 2026-10-07

### Fixes and Maintenance

- Bind independent-review source and candidate path labels as well as their hashes before direct
  canonical replacement, and cover recovery handling for a changed completed predecessor backup.
- Report bounded unresolved line-break hyphenation in cleanup output, and map protected spans
  through their final included character when deciding which following prose can be measured.
- Separate cleanup report construction and terminal rendering from the transformation pipeline.
- Remove the unsupported text-rich-page warning from OCR while retaining page validation and
  guaranteed PDF closure on extraction failures.
- Preserve the five-page Genetic Engineering positioned-text prototype in visible corpus
  experiment evidence rather than the reusable tool package.

## 2026-10-06

### Fixes and Maintenance

- Report bounded examples and counts for unresolved PDF line-break hyphenation before Markdown reflow.
- Map protected spans through their final included character, so following prose is eligible for guarded joins and unresolved-hyphen reporting immediately after a quote or code block.
- Remove measured PDF running heads only when the complete edge line matches, preserving longer chapter titles and captions.

## 2026-10-05

### Fixes and Maintenance

- Added direct canonical replacement with source-bound admission and predecessor-hash checks,
  a verified no-clobber predecessor backup, and atomic `os.replace` publication with recovery
  reporting.
- Corrected `audit/validate_markdown_v2.py` indentation to match repository style.
- Removed the unreliable code-fence content/density classifier. The generic validator checks
  fence structure and concrete residue; source-aware review determines whether fenced content
  matches its source.
- Validate fenced code boundaries using markdown-it's CommonMark list nesting and token markup.
- Judge fence closure from markdown-it's mapped opener, content, and recognized closer boundaries so indented marker-like payload lines cannot masquerade as closers.
- Count fenced payload lines with CommonMark CR/LF boundaries so Unicode line separators remain ordinary code content.
- Made `extract/azw3_to_markdown.py` executable for direct invocation.

## 2026-09-28

### Fixes and Maintenance

- Ignore `<img>` text after an odd backslash run; reject raw tags after even runs and
  retain detection of Markdown images and picture-text markers.
- Keep valid currency entities in publication candidates while rejecting replacement
  characters and entities.
- Inspect EPUB XHTML with ordinary DOCTYPE declarations while keeping DTD loading and
  entity resolution disabled and refusing unresolved entity references.
- Store promotion and pending-lifecycle lock files in visible corpus conversion state.
- Keep temporary publication snapshots visibly named.
- Reject nonprinting control characters in Markdown delivery validation.

## 2026-09-27

### Fixes and Maintenance

- Kept source-verified Unicode in fenced and indented code blocks out of the prose-only ASCII delivery check.
- Made the markdown-it delivery validator apply its parsed code-block exclusion before its prose ASCII check.
- Allowed new-title admission to use an accepted, candidate- and source-bound independent review when word counts cannot represent expected cleanup.
- Preserved valid Markdown comparison entities (`&lt;`, `&gt;`) during promotion while continuing to reject replacement and misdecoded currency entities.

## 2026-09-12

### Additions and New Features

- Added `extract/azw3_to_markdown.py` for unencrypted Mobipocket/AZW3 v8 HuffDic text records.

### Fixes and Maintenance

- Synchronized shared style guides, tests, and repository support files from the starter template.

### Developer Tests and Notes

- Added a source-SHA-bound E2E characterization for The Way of the Superior Man.

## 2026-09-08

### Behavior or Interface Changes

- Added explicit `--new-title` promotion for verified candidates with no predecessor while
  preserving the legacy five-positional replacement command.

### Fixes and Maintenance

- Moved validated-candidate promotion ownership into `audit/promote_validated_candidate.py` and
  use same-filesystem, atomic no-clobber link publication for canonical delivery.
- Require explicit accepted new-title admission status, retain staged candidates after verified
  canonical promotion, and share a title-specific PENDING lifecycle reservation with writers.
- Reject cross-device publication against nearest existing destination ancestors before creating
  destination or superseded directories, and rebind the admission SHA after validation under the
  title lock before linking.
- Serialize final lifecycle checks with a canonical-destination title lock, link the canonical from
  a verified same-filesystem snapshot, and remove only invocation-owned canonical links on refusal.
- Preserve staged candidate and predecessor artifacts when predecessor-backup publication becomes
  recovery-required after canonical commit.
- Made verified canonical hash readback and filesystem synchronization the irreversible publication
  point; staged-candidate reclamation is a separate strict-closure lifecycle operation.
- Bound new-title admission-status transitions to the shared title lifecycle reservation, rechecking
  accepted status immediately before canonical linking, and made failed snapshot creation close,
  unlink, and synchronize its temporary artifact.

### Developer Tests and Notes

- Documented and exercised the executable promotion launcher with a disposable direct-invocation E2E.
- Added deterministic final-window regressions for candidate mutation, unexpected PENDING creation,
  and predecessor-backup collision recovery.
- Added admission-status, staged-candidate retention, shared PENDING writer, and legacy interaction
  promotion regressions.
- Added deterministic hard-link path-replacement regressions for both promotion lifecycles.

### Decisions and Failures

- Recorded explicit lifecycle admission and separate receipt/sidecar closure ownership; the
  promoter does not manufacture a predecessor or receipt for a new title.

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
