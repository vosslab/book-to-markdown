## Coding Style
See Python coding style in docs/PYTHON_STYLE.md.
See Markdown style in docs/MARKDOWN_STYLE.md.
See repo style in docs/REPO_STYLE.md.
When making edits, document them in docs/CHANGELOG.md.

## Python Environment
AI agents (Codex/Claude) must run Python using `source source_me.sh && python3` (use Python 3.12 only).
On this user's macOS (Homebrew Python 3.12), Python modules are installed to `/opt/homebrew/lib/python3.12/site-packages/`.

## Corpus Work Boundary
For conversion or review work in the book corpus, treat this repository as read-only and write
outputs only to absolute paths under the corpus's visible staging directory. Edit this tools
repository only for explicitly assigned tool-maintenance tasks. Routine tests and development work
remain available when they are part of the assigned task.
