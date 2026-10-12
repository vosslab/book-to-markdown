#!/usr/bin/env python3
"""Print a reproducible cleanup demonstration for the README screenshot."""

import pathlib
import subprocess
import sys
import tempfile


def main() -> None:
	"""Run the real cleanup and validation CLIs against an authored sample."""
	repo = pathlib.Path(__file__).resolve().parent.parent
	before = (
		"# Signal pathway\n\n"
		"The receptor binds the\nligand and activates the\nresponse.\n\n"
		"<!-- OCR note\nremove this\n-->\n\n"
		"Figure 1. A membrane receptor.\n"
	)
	with tempfile.TemporaryDirectory(prefix="book_markdown_demo_") as temporary:
		root = pathlib.Path(temporary)
		source = root / "before.md"
		output = root / "Signal_Pathway-UNDATED.md"
		source.write_text(before, encoding="ascii")
		# ASVS 1.2.5: Invoke CLI arguments directly without a shell.
		subprocess.run(
			[sys.executable, str(repo / "cleanup/clean_markdown.py"),
				"-i", str(source), "-o", str(output)],
			check=True, capture_output=True, text=True,
		)
		validation = subprocess.run(
			[sys.executable, str(repo / "audit/validate_markdown_v2.py"), str(output)],
			check=True, capture_output=True, text=True,
		)
		after = output.read_text(encoding="ascii")
		print("BOOK TO MARKDOWN  /  CLEANUP DEMO")
		print("Authored sample; output produced by the real CLI.\n")
		print("$ python3 cleanup/clean_markdown.py -i before.md -o Signal_Pathway-UNDATED.md")
		print("\nBEFORE\n" + "-" * 76)
		print(before.rstrip())
		print("\nAFTER\n" + "-" * 76)
		print(after.rstrip())
		print("\n$ python3 audit/validate_markdown_v2.py Signal_Pathway-UNDATED.md")
		print(validation.stdout.rstrip())
		print("\nAlso written: a JSON report and a removed-text Markdown sidecar.")


if __name__ == "__main__":
	main()
