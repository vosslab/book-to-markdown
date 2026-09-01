"""CLI behavior checks for the qualified PDF OCR entry point."""

import importlib.util
import pathlib
import sys
import unittest.mock


REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "extract/pdf_to_markdown.py"
SPEC = importlib.util.spec_from_file_location("pdf_to_markdown_test_module", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_pdf_to_markdown_uses_explicit_output_and_ocr_defaults() -> None:
	"""The compatibility entry point retains the qualified OCR CLI contract."""
	with unittest.mock.patch.object(sys, "argv", [
		"pdf_to_markdown.py", "source.pdf", "--output", "candidate.raw.md", "--pages", "0-3",
	]):
		args = MODULE.parse_args()
	assert args.pdf == "source.pdf"
	assert args.output_file == "candidate.raw.md"
	assert args.pages == "0-3"
	assert args.running_heads and args.page_numbers and args.seams and args.heading_synthesis
