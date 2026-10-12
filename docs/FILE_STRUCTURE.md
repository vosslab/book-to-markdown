# File structure

## Top-level layout

```text
book-to-markdown/
+- audit/          Validation, diagnostic, archival, and promotion commands
+- cleanup/        Markdown cleanup pipeline and repair commands
+- devel/          Repository-maintenance scripts
+- docs/           Project and contributor documentation
+- extract/        Source-format extraction commands and Pandoc filter
+- pdf_extract/    Shared PDF extraction and page-cleanup package
+- tests/          Pytest suite and test-only helpers
+- tools/          Optional standalone user utilities
+- markdown_quality.py
+- pip_requirements.txt
+- pip_extra.txt
+- pytest.ini
+- source_me.sh
+- AGENTS.md
`- README.md
```

## Key subtrees

- [`extract/`](../extract/) contains PDF text-layer, full-page OCR, spread OCR, EPUB, and AZW3
  commands. [`semantic_markdown.lua`](../extract/semantic_markdown.lua) is its Pandoc filter.
- [`cleanup/`](../cleanup/) holds the Markdown cleanup command, its layout and reporting helpers,
  and standalone repair tools. [`clean_markdown.py`](../cleanup/clean_markdown.py) owns pass
  ordering; [`layout.py`](../cleanup/layout.py) owns protected regions and reflow.
- [`pdf_extract/`](../pdf_extract/) supplies shared PDF processing. [`models.py`](../pdf_extract/models.py)
  defines records; [`raw_text.py`](../pdf_extract/raw_text.py),
  [`ocr_text.py`](../pdf_extract/ocr_text.py), and [`spread_ocr.py`](../pdf_extract/spread_ocr.py)
  obtain text; [`text.py`](../pdf_extract/text.py) joins pages; [`page_cleanup.py`](../pdf_extract/page_cleanup.py)
  transforms page artifacts; [`cleanup.py`](../pdf_extract/cleanup.py) coordinates conversion and
  reporting.
- [`audit/`](../audit/) contains validators, diagnostic audits, processed-source archiving, and
  promotion. [`promotion_admission.py`](../audit/promotion_admission.py) holds admission policy;
  [`promote_validated_candidate.py`](../audit/promote_validated_candidate.py) holds publication
  mechanics.
- [`tests/`](../tests/) contains behavior tests and repository checks. Its ignored `_temp/`
  directory is reserved for temporary verification work.
- [`devel/`](../devel/) contains changelog, version, release, link-repair, graphification, and
  documentation-maintenance commands. [`readme_demo.py`](../devel/readme_demo.py) generates the
  cleanup transcript; [`capture_readme_demo.sh`](../devel/capture_readme_demo.sh) renders its
  README image.
- The `docs/screenshots/` directory stores repository-owned documentation images, including
  `cleanup_demo.png`.

## Dependencies and configuration

- [`source_me.sh`](../source_me.sh) prepares the shell environment for repository Python commands.
- [`pip_requirements.txt`](../pip_requirements.txt) declares runtime dependencies. PyMuPDF is
  imported as `pymupdf` by PDF modules.
- [`pip_extra.txt`](../pip_extra.txt) holds the on-demand `mobi` dependency used only by
  [`extract/azw3_to_markdown.py`](../extract/azw3_to_markdown.py).
- [`pytest.ini`](../pytest.ini) configures pytest. [`tests/conftest.py`](../tests/conftest.py)
  applies test-session configuration.

## Generated artifacts

- PDF conversion commands write Markdown, a JSON report, and a `.removed.md` removal sidecar to
  caller-selected output paths.
- [`cleanup/clean_markdown.py`](../cleanup/clean_markdown.py) writes cleaned Markdown and a
  sidecar beside its selected output path.
- [`audit/promote_validated_candidate.py`](../audit/promote_validated_candidate.py) writes
  publication snapshots and predecessor backups in the destination corpus under its lifecycle
  rules.
- [`.gitignore`](../.gitignore) excludes local caches, generated outputs, reports, and temporary
  test work from version control.

## Documentation map

- [`README.md`](../README.md) is the newcomer landing page and quick-start route.
- [`INSTALL.md`](INSTALL.md) records environment and dependency setup.
- [`USAGE.md`](USAGE.md) documents workflows, command examples, and promotion operations.
- [`DEVELOPMENT.md`](DEVELOPMENT.md) records verification commands and README-image regeneration.
- [`FILE_FORMATS.md`](FILE_FORMATS.md) distinguishes source, staged, diagnostic, and publication
  files.
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) covers observed environment and validation failures.
- [`CODE_ARCHITECTURE.md`](CODE_ARCHITECTURE.md) explains module responsibilities and data flow.
- [`HUMAN_GUIDANCE.md`](HUMAN_GUIDANCE.md) records durable user direction.
- [`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) records settled technical decisions.
- [`CHANGELOG.md`](CHANGELOG.md) records dated changes.

## Where to add work

- Put a new source converter in [`extract/`](../extract/) and shared PDF behavior in
  [`pdf_extract/`](../pdf_extract/).
- Put Markdown cleanup behavior in [`cleanup/`](../cleanup/) and validation or lifecycle behavior
  in [`audit/`](../audit/).
- Put pytest coverage in [`tests/`](../tests/) only when it protects a stable, meaningful behavior.
- Put durable reference documentation in `docs/`, maintainer utilities in
  [`devel/`](../devel/), and optional user-facing utilities in [`tools/`](../tools/).
