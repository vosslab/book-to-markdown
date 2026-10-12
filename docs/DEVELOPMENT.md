# Development

Use these commands to verify repository changes and refresh the documentation demonstration.
The tools run directly from a checkout rather than an installed application package.

## Verify changes

- Use Python 3.12 through `source source_me.sh` from the repository root.
- Run `source source_me.sh && pytest tests/` for the full suite.
- Hygiene checks are read-only by default. Use `--fix-repo-files` only when you intend to edit files.
- Follow [PYTHON_STYLE.md](PYTHON_STYLE.md), [PYTEST_STYLE.md](PYTEST_STYLE.md), and
  [MARKDOWN_STYLE.md](MARKDOWN_STYLE.md); record changes in [CHANGELOG.md](CHANGELOG.md).
- Keep one-time checks in ignored `tests/_temp/` and remove them when the work is complete.

## Refresh the README image

- [devel/readme_demo.py](../devel/readme_demo.py) creates an authored Markdown sample in a temporary
  directory and runs the actual cleanup and validation CLIs. It deletes its temporary artifacts.
- [devel/capture_readme_demo.sh](../devel/capture_readme_demo.sh) renders that transcript to
  [screenshots/cleanup_demo.png](screenshots/cleanup_demo.png). This is a terminal-style rendering
  of actual output, not a GUI screenshot or an extraction from a published book.
- Capture requires ImageMagick's `magick` command and macOS's `/System/Library/Fonts/Menlo.ttc`.
  These are documentation tools, not runtime dependencies.
- Run from the repository root:

```bash
source source_me.sh
python3 devel/readme_demo.py
bash devel/capture_readme_demo.sh
```

- Inspect the regenerated PNG before committing. The capture is 1280 by 800 pixels; keep text
  unclipped and the PNG below 1 MB. Its README embed stays inside the managed screenshot block.
- The demonstration's validator pass proves structural validity of this sample. It does not
  establish source fidelity or authorize canonical publication.
