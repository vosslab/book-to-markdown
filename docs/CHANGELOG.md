# Changelog

All notable changes to this project are documented in this file.

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
