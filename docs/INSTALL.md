# Install

Installation prepares the repository's command-line extractors, cleanup tools, and audits to run
from the repository root. The tools are scripts, not an installable Python package.

## Requirements

- Python 3.12. Use `source source_me.sh && python3` for every repository command.
- Runtime packages listed in `pip_requirements.txt`: PyMuPDF, lxml, PyYAML, and markdown-it-py.
- Tesseract with English traineddata for OCR workflows. Text-layer PDF extraction does not need it.
- Pandoc for Pandoc conversion workflows and the `cleanup/mathml_to_latex.py` backend.
- The optional `mobi` package only when extracting unencrypted AZW3 books.

## Install steps

1. Clone or otherwise obtain this repository, then change to its root.
2. Load the repository environment and install the standard runtime dependencies:

   ```bash
   source source_me.sh
   python3 -m pip install -r pip_requirements.txt
   ```

3. Install the AZW3 decoder only when that workflow is needed:

   ```bash
   source source_me.sh
   python3 -m pip install -r pip_extra.txt
   ```

4. Install development dependencies only when running the test suite:

   ```bash
   source source_me.sh
   python3 -m pip install -r pip_requirements-dev.txt
   ```

`source_me.sh` loads local shell setup, sets the repository root on `PYTHONPATH`, and selects the
configured Python 3.12 runtime. PyMuPDF is imported in source code as `pymupdf`.

## Verify install

Run these commands from the repository root:

```bash
source source_me.sh && python3 cleanup/clean_markdown.py --help
source source_me.sh && python3 audit/validate_markdown_v2.py --help
```

After installing `pip_requirements-dev.txt`, verify the test suite with:

```bash
source source_me.sh && pytest tests/
```

For AZW3 support, verify both its command line and installed optional decoder:

```bash
source source_me.sh && python3 extract/azw3_to_markdown.py --help
source source_me.sh && python3 -c "import mobi"
```

## Troubleshooting

- AZW3 extraction reports its missing optional dependency and gives the exact `pip_extra.txt`
  installation command.
- PyMuPDF can emit SWIG metadata deprecation warnings on macOS during import. They originate in
  its compiled dependency; this project neither filters those warnings nor patches or custom-builds
  PyMuPDF.
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for supported diagnosis steps.

## Known gaps

- TODO: document the supported macOS/Linux/Windows matrix.
- TODO: verify a maintained PyMuPDF release that removes the macOS SWIG warnings without a local
  patch or warning filter.
