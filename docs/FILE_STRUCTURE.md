# File structure

## Top-level layout

- `extract/` - source-to-Markdown extraction scripts and the Pandoc filter.
- `cleanup/` - cleaning and repair scripts.
- `audit/` - validation, auditing, and archiving scripts.
- `markdown_quality.py` - shared Markdown cleaning utilities (imported by scripts in all stage folders).
- `pdf_extract/` - PDF extraction helpers used by the extractors.
- `tests/` - pytest suite.
- `docs/` - project documentation.
- `devel/` - repo maintenance and developer tooling.
- `source_me.sh` - environment setup; puts the repo root on `PYTHONPATH`.
- `pip_requirements.txt` - runtime dependencies.
- `README.md` - landing page and quick-start map.
- `AGENTS.md` - agent-specific guidance.

## Key subtrees

- `extract/semantic_markdown.lua` - Pandoc Lua filter for EPUB/HTML semantic heading cleanup.
- `pdf_extract/` - PDF extraction helpers (cleanup, OCR, raw text) imported by the PDF-to-Markdown scripts.

## Generated artifacts

- Tool outputs such as `.md`, `.json`, and `.removed.md` sidecars are created in `/tmp` or user-chosen paths.
- No build artifacts are checked into the repo.

## Documentation map

- `README.md` - project overview, tool index, and quick start.
- `docs/CHANGELOG.md` - change history.
- `docs/INSTALL.md` - setup and dependency install.
- `docs/USAGE.md` - run commands, CLI flags, and workflows.
- `docs/CODE_ARCHITECTURE.md` - component and data-flow overview.

## Where to add new work

- Code: `extract/`, `cleanup/`, or `audit/` by stage; shared logic at the repo root.
- Tests: `tests/`.
- Docs: `docs/`.
- Repo maintenance tooling: `devel/`.
