# Install

One paragraph: "installed" means the toolchain scripts in `extract/`, `cleanup/`, and `audit/` are present, dependencies are installed, and `python3 <folder>/<script>.py --help` runs from the repo root.

## Requirements

- Python 3.12 via `source source_me.sh && python3`
- `pip_requirements.txt` dependencies: `PyMuPDF`, `lxml`, `PyYAML`, `markdown-it-py`
- System tools for some extractors: `pandoc`, Tesseract OCR with English traineddata, optional `djvulibre-bin`

## Install steps

- Clone or obtain the repository source.
- Run `source source_me.sh` to set the Python environment and put the repo root on `PYTHONPATH`.
- Install Python dependencies with `pip install -r pip_requirements.txt`.

## Verify install

Run:

```bash
source source_me.sh
python3 cleanup/clean_markdown.py --help
python3 audit/validate_markdown_v2.py --help
```

## Known gaps

- Editable install or package entry points are not provided.
- macOS/Linux/Windows matrix is not documented yet.
