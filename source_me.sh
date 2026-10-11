# source_me.sh - shell environment for running this repo's Python.
# Usage: source source_me.sh && python3 ...
# This is a bash script sourced into your shell, not run directly.

# Require bash: the checks below and the repo's tab-indented shell style are
# bash-specific. Fail loudly rather than misbehave under another shell.
set | grep -q '^BASH_VERSION=' || echo "use bash for your shell"
set | grep -q '^BASH_VERSION=' || exit 1

# Source ~/.bashrc FIRST, before any repo-specific environment extension below.
# ~/.bashrc applies local shell setup (PATH, etc.) and resets some variables --
# it clears PYTHONPATH (verified). Anything that sets PYTHONPATH must run after
# this line, or ~/.bashrc would wipe it.
source ~/.bashrc

# Python runtime defaults: unbuffered stdout/stderr, and no .pyc/__pycache__
# files written on import.
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# --- Repo-root import path (required) ---------------------------------------
# Scripts live in extract/, cleanup/, and audit/ and import the sibling
# repo-root modules markdown_quality and pdf_extract. Must come after sourcing
# ~/.bashrc, which clears PYTHONPATH.
# Resolve the repository from this sourced file, even outside a Git work tree.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [ -f "$SCRIPT_DIR/markdown_quality.py" ]; then
	REPO_ROOT="$SCRIPT_DIR"
else
	REPO_ROOT="$SCRIPT_DIR/book-to-markdown"
fi
REPO_ROOT="$(cd -- "$REPO_ROOT" && pwd -P)"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
unset SCRIPT_DIR
unset REPO_ROOT
