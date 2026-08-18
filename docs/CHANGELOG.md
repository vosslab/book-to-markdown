# Changelog

All notable changes to this project are documented in this file.

## 2026-08-18

### Added
- Initial migration from `vosslab-skills` book-to-markdown skill toolchain.
- Scripts grouped by stage in `extract/`, `cleanup/`, and `audit/` for extraction, cleaning, validation, auditing, and archiving.
- `tests/` with migrated test suite covering cleanup and audit behavior.

### Changed
- README rewritten for standalone repo audience with tool index and quick-start commands.
- `source_me.sh` now puts the repo root on `PYTHONPATH` so stage-folder scripts can import shared modules.

### Removals and Deprecations
- None yet.
