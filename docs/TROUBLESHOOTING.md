# Troubleshooting

These notes cover observed setup and validation issues in the command-line book conversion tools.

## Imports and optional dependencies

- Run commands from the checkout after `source source_me.sh`; it sets Python 3.12 and the
  repository module search path. See [INSTALL.md](INSTALL.md).
- Install `pip_extra.txt` only when AZW3 extraction needs `mobi`. The extractor reports the
  installation command when the extra is absent.
- PyMuPDF is the package name and `pymupdf` is the import name. The old `fitz` import came from
  PyMuPDF; uninstalling a separate package named `fitz` does not remove or repair PyMuPDF.

## PyMuPDF SWIG warnings

- On this macOS/Python 3.12 environment, PyMuPDF 1.28.2 emits deprecation warnings for
  `SwigPyPacked`, `SwigPyObject`, and `swigvarlink` lacking `__module__` metadata.
- The final `sys:1` warning occurs during interpreter shutdown, after pytest's summary.
  These warnings come from compiled dependency bindings, not deprecated method calls in this repo.
- The repository leaves warnings visible and uses the unmodified upstream package. It does not
  maintain warning filters, a patched dependency, or a custom native build.
- Track [PyMuPDF issue 3931](https://github.com/pymupdf/PyMuPDF/issues/3931) for upstream context.
  After a dependency update, rerun `source source_me.sh && pytest tests/` to check actual behavior.

## Candidate validation failures

- Run `python3 audit/validate_markdown_v2.py PATH --json-report /tmp/validation.json` for a
  machine-readable list of file, line, and issue codes; confirm options in [USAGE.md](USAGE.md).
- A valid candidate needs a canonical title/year filename and exactly one H1 outside code.
  Use `-UNDATED.md` only when the book is identified but its year cannot be verified.
- Inspect unresolved glyphs and ambiguous line-break hyphens against the source. A structural
  validator pass cannot replace source review.
