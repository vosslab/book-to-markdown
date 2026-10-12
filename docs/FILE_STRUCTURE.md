# File structure

## Top-level layout

- `extract/` - source-to-Markdown extraction scripts and the Pandoc filter.
- `cleanup/` - cleaning and repair scripts, with Markdown layout helpers in
  [layout.py](../cleanup/layout.py) and report rendering in `reporting.py`.
- `audit/` - validation, auditing, archival, and canonical-promotion scripts.
- `markdown_quality.py` - shared Markdown cleaning utilities.
- `pdf_extract/` - PDF extraction helpers used by extractors.
  `models.py` holds shared records; `page_cleanup.py` holds page-aware cleanup passes; `text.py`
  handles normalization and page seams; `cleanup.py` coordinates conversion, scoring, and reports.
- `tests/` - pytest suite.
- `docs/` - project documentation.
- `devel/` - repository maintenance and developer tooling.
- `source_me.sh` - environment setup that puts the repository root on `PYTHONPATH`.
- `pip_requirements.txt` - runtime dependencies.
- `README.md` - landing page and quick-start map.
- `AGENTS.md` - agent-specific guidance.

## Key audit tools

- `audit/validate_markdown_v2.py` - preferred structural validator.
- `audit/validate_markdown_delivery.py` - delivery validator.
- `audit/promote_validated_candidate.py` - explicit lifecycle, same-filesystem no-clobber promoter.
- `audit/promotion_admission.py` - promotion configuration and source-bound validation gates.

## Documentation map

- `README.md` - project overview, tool index, and quick start.
- `docs/CHANGELOG.md` - change history.
- `docs/INSTALL.md` - setup and dependency installation.
- `docs/USAGE.md` - run commands, CLI flags, and workflows.
- `docs/CODE_ARCHITECTURE.md` - component and data-flow overview.
- `docs/HUMAN_GUIDANCE.md` - durable user guidance.
- `docs/DESIGN_DECISIONS.md` - durable technical decisions.

## Generated artifacts

- Tool outputs such as `.md`, `.json`, and `.removed.md` sidecars are created in `/tmp` or
  user-chosen paths.
- No build artifacts are checked into the repository.
