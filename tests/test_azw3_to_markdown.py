"""Temporary extraction cleanup checks for the AZW3 reader."""

import pathlib
import unittest.mock

import extract.azw3_to_markdown
import pytest


def configure_extraction(monkeypatch: pytest.MonkeyPatch, outcome: str) -> list[pathlib.Path]:
	"""Replace package unpacking with a visible EPUB and record its owned root."""
	output_roots = []
	monkeypatch.setattr(extract.azw3_to_markdown, "huffdic_header", lambda path: None)

	def unpack(source: str, output: str, epubver: str) -> None:
		root = pathlib.Path(output)
		output_roots.append(root)
		(root / "mobi8").mkdir()
		(root / "mobi8" / "source.epub").write_bytes(b"epub")

	monkeypatch.setattr(extract.azw3_to_markdown.mobi.kindleunpack, "unpackBook", unpack)
	if outcome == "error":
		monkeypatch.setattr(
			extract.azw3_to_markdown,
			"epub_spine_html",
			unittest.mock.Mock(side_effect=ValueError("invalid EPUB")),
		)
	else:
		monkeypatch.setattr(extract.azw3_to_markdown, "epub_spine_html", lambda path: "<p>text</p>")
	return output_roots


def test_azw3_extraction_removes_owned_temporary_files_on_success(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""The reader returns text and removes package output after successful parsing."""
	output_roots = configure_extraction(monkeypatch, "success")
	text = extract.azw3_to_markdown.extract_azw3_text(tmp_path / "source.azw3")
	assert text == "<p>text</p>"
	assert len(output_roots) == 1
	assert not output_roots[0].exists()


def test_azw3_extraction_removes_owned_temporary_files_on_parser_error(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""The reader removes package output when EPUB parsing fails."""
	output_roots = configure_extraction(monkeypatch, "error")
	try:
		extract.azw3_to_markdown.extract_azw3_text(tmp_path / "source.azw3")
	except ValueError as error:
		assert str(error) == "invalid EPUB"
	else:
		raise AssertionError("expected EPUB parsing to fail")
	assert len(output_roots) == 1
	assert not output_roots[0].exists()
