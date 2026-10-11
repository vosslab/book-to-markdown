"""Behavior checks for the Markdown duplication and residue audit tools."""

import importlib


DUP = importlib.import_module("audit_markdown_duplication")
RESIDUE = importlib.import_module("audit_markdown_residue")


def test_content_segments_drop_equation_speech() -> None:
	"""Single-letter math tokens are dropped and short tokens never register."""
	segments = DUP.content_segments("big R big R and mu m mu m")
	assert all(DUP.line_duplicates(segment) == [] for segment in segments)


def test_content_segments_drop_publisher_imprint() -> None:
	"""Title-page imprints such as a repeated press line do not report as stutter."""
	segments = DUP.content_segments("Princeton University Press Princeton University Press")
	assert all(DUP.line_duplicates(segment) == [] for segment in segments)


def test_dedupe_line_preserves_idiom_and_case() -> None:
	"""Idioms stay untouched and the first occurrence keeps its capitalization."""
	text = "One by one, research group to research group, Very difficult Very difficult to read"
	deduped, removed = DUP.dedupe_line(text)
	assert removed == 1
	assert deduped == "One by one, research group to research group, Very difficult to read"


def test_audit_skips_code_and_table_content() -> None:
	"""Duplication inside fenced code and pipe tables is not flagged."""
	text = "# Title\n\n```\ntoken token token token\n```\n\n| left | left |\n"
	result = DUP.audit_markdown(text)
	assert result.status == "CLEAN"


def test_glossary_definition_label_is_not_stutter() -> None:
	"""A bold definition term restated at the start of its entry is not duplication."""
	text = "- **Network monitoring:** Network monitoring takes advantage of the architecture\n"
	assert DUP.audit_markdown(text).status == "CLEAN"


def test_dedupe_preserves_link_and_offsets() -> None:
	"""Links and bold markup survive removal of duplicated prose."""
	prefix = "See [this guide](http://example.com) and **bold** then "
	line = prefix + "very difficult very difficult to read"
	deduped, removed = DUP.dedupe_line(line)
	assert removed == 1
	assert deduped == prefix + "very difficult to read"


def test_audit_counts_bigram_trigram_and_fourgram() -> None:
	"""Each n-gram size reports its own count."""
	text = "very difficult very difficult\n" \
		"double bonds separated double bonds separated\n" \
		"primer extension method locate primer extension method locate\n"
	result = DUP.audit_markdown(text)
	assert result.bigram_dup == 1
	assert result.trigram_dup == 1
	assert result.fourgram_dup == 1


def test_count_residue_detects_garbled_classes() -> None:
	"""Replacement chars, setext garbage, and dot leaders are each counted."""
	text = "clean\ufffd line\n\n=====\n\n.... .... .... .... .... .... ....\n"
	counts = RESIDUE.count_residue(text)
	assert counts.fffd == 1
	assert counts.setext_garbage_lines == 1
	assert counts.dot_leader_runs == 1
