"""Behavior checks for the technical-book Markdown cleanup helpers."""

import importlib.util
import io
import pathlib
import sys
from contextlib import redirect_stdout


REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "cleanup/clean_markdown.py"
SPEC = importlib.util.spec_from_file_location("clean_markdown_test_module", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_cleanup_keeps_formula_and_code_angle_semantics() -> None:
	"""HTML conversion preserves math while code-like angles remain visible."""
	input_text = "vector<pt> x<sup>ij</sup> H<sub>2</sub> <math><msup><mi>x</mi><mi>n</mi></msup></math>\n"
	cleaned, _removals, _metrics = MODULE.clean_text(input_text, {"figure-debris", "reflow"}, 5, 15)
	assert "vector&lt;pt&gt; x^{ij} H_2 x^n" in cleaned


def test_cleanup_removes_image_text_but_keeps_caption() -> None:
	"""The image pass discards embedded label text but retains the figure caption."""
	input_text = "[Start Picture-Text]\naxis labels and pixels\n[End Picture-Text]\nFigure 3. A caption.\n"
	cleaned, _removals, _metrics = MODULE.clean_text(input_text, {"figure-debris", "reflow", "ascii"}, 5, 15)
	assert cleaned == "Figure 3. A caption."


def test_cleanup_keeps_distinct_scientific_symbol_meaning() -> None:
	"""Greek variants and operators remain readable in ASCII-safe output."""
	cleaned, _removals, _metrics = MODULE.clean_text("\u03f5 \u03d1 \u2209 \u00bc\n", {"figure-debris", "reflow"}, 5, 15)
	assert cleaned == "&epsiv; &thetasym; &notin; &frac14;"


def test_ascii_safe_preserves_ring_above_as_scientific_notation() -> None:
	"""A superscript ring remains visible instead of becoming an empty exponent."""
	assert MODULE.ascii_safe("A^{\u02da}") == "A^{&#x02DA;}"


def test_cleanup_repairs_single_line_fenced_payload() -> None:
	"""A one-line pseudo-fence cannot protect the rest of the document."""
	input_text = "before\n``` payload ```\nafter <b>visible</b>\n"
	cleaned, _removals, _metrics = MODULE.clean_text(input_text, {"figure-debris", "reflow"}, 5, 15)
	assert "` payload `" in cleaned
	assert "after visible" in cleaned


def test_cleanup_splits_prose_from_closing_fence() -> None:
	"""A PDF seam cannot leave later prose trapped in a code block."""
	input_text = "```\nSELECT 1;\n``` where the query returns one row.\n\n## Next\n"
	cleaned, _removals, _metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert "```\nwhere the query returns one row." in cleaned
	fenced, unclosed = MODULE.markdown_quality.fenced_line_numbers(cleaned.splitlines())
	assert fenced and unclosed is None


def test_cleanup_replaces_table_break_without_splitting_row() -> None:
	"""A br tag inside a pipe cell stays on one Markdown table row."""
	input_text = "| Value | Meaning |\n| --- | --- |\n| u8<br>i32 | numeric types |\n"
	cleaned, _removals, _metrics = MODULE.clean_text(input_text, {"figure-debris", "reflow"}, 5, 15)
	assert "| u8 / i32 | numeric types |" in cleaned


def test_cleanup_replaces_table_break_between_inline_code_spans() -> None:
	"""Inline code protection cannot leave active br markup in a pipe cell."""
	input_text = "| Name | Alias |\n| --- | --- |\n| `varbit`<br>`[n]` | bits |\n"
	cleaned, _removals, _metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert "| `varbit` / `[n]` | bits |" in cleaned


def test_cleanup_preserves_epub_code_indented_with_nonbreaking_spaces() -> None:
	"""EPUB indentation is normalized before code-sensitive reflow."""
	input_text = "Example:\n\n\u00a0\u00a0\u00a0\u00a0fn main() {\n\u00a0\u00a0\u00a0\u00a0    println!(\"hi\");\n"
	cleaned, _removals, _metrics = MODULE.clean_text(input_text, {"figure-debris"}, 5, 15)
	assert "\n\n    fn main() {\n        println!(\"hi\");" in cleaned


def test_cleanup_handles_entity_escaped_epub_markup() -> None:
	"""Escaped EPUB containers and images are removed without changing code-like angles."""
	input_text = (
		"&lt;div id=&quot;chapter&quot;&gt;\nReadable Thing<T> text\n&lt;/div&gt;\n"
		"&lt;img src=&quot;figure.png&quot; /&gt;\n"
		"Vec&lt;T&gt; &lt;https://example.com&gt;\n"
		"```html\n&lt;div&gt;literal example&lt;/div&gt;\n```\n"
	)
	cleaned, removals, _metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert "Readable Thing&lt;T&gt; text" in cleaned
	assert "&lt;div id=" not in cleaned
	assert "figure.png" not in cleaned
	assert "Vec&lt;T&gt; &lt;https://example.com&gt;" in cleaned
	assert "&lt;div&gt;literal example&lt;/div&gt;" in cleaned
	assert any(item.pass_name == "images" for item in removals)


def test_cleanup_preserves_recognized_html_tags_inside_inline_code() -> None:
	"""Inline code remains technical text rather than active HTML cleanup input."""
	input_text = "Use `<div>` and ``<span title=`x`>`` as literal examples.\n"
	cleaned, _removals, _metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert "`<div>` and ``<span title=`x`>``" in cleaned


def test_cleanup_keeps_figure_caption_without_publisher_asset_label() -> None:
	"""A complete publisher figure block becomes caption prose."""
	input_text = "<figure>css5 1004<h6>Figure 10-4. Floating left</h6></figure>\n"
	cleaned, _removals, _metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert cleaned == "Figure 10-4. Floating left"


def test_cleanup_converts_epub_pre_wrappers_to_fenced_code() -> None:
	"""Publisher pre wrappers disappear while their command listing stays code."""
	input_text = (
		"&lt;pre class=\"programlisting\"&gt;\n\n$ podman info\n\n&lt;/pre&gt;\n"
		"\n1. Step:\n\n    <pre class=\"programlisting\">\n\n"
		"    ExecStart=/usr/bin/podman run\n\n    </pre>\n"
	)
	cleaned, _removals, _metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert "~~~~text\n\n$ podman info\n\n~~~~" in cleaned
	assert "    ~~~~text\n\n    ExecStart=/usr/bin/podman run\n\n    ~~~~" in cleaned
	assert "<pre" not in cleaned and "&lt;pre" not in cleaned


def test_cleanup_removes_publisher_html_comments() -> None:
	"""Hidden build instructions cannot become visible Markdown headings."""
	input_text = "Before.\n\n<!-- regenerate\n# copy the output here\n-->\n\nAfter.\n"
	cleaned, _removals, _metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert "copy the output" not in cleaned
	assert "Before." in cleaned and "After." in cleaned


def test_cleanup_converts_superscript_inside_quote() -> None:
	"""Citation markup in quoted reference content becomes plain Markdown."""
	input_text = "> Source<sup>[1](#note)</sup>.\n> <sup>1</sup> Note.\n"
	cleaned, _removals, _metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert "<sup>" not in cleaned
	assert "[1](#note)" in cleaned


def test_unresolved_hyphenation_is_reported_before_reflow() -> None:
	"""A unique split is measured while the cleaned text retains its current wording."""
	cleaned, _removals, metrics = MODULE.clean_text(
		"intro-\nduction\n", {"figure-debris", "ascii"}, 5, 15,
	)
	assert cleaned == "intro- duction\n"
	assert metrics["unresolved_dehyphenation_candidates"] == 1
	assert metrics["unresolved_dehyphenation_examples"] == [
		{"line": 1, "prefix": "intro", "continuation": "duction"},
	]
	stream = io.StringIO()
	with redirect_stdout(stream):
		MODULE.cleanup.reporting.print_report(MODULE.cleanup.reporting.build_report(
			pathlib.Path("input.md"), pathlib.Path("output.md"), metrics, set(),
			MODULE.argparse.Namespace(measure_only=False, measure=False, debris_min_lines=5, debris_caption_window=15),
			False, MODULE.PASS_NAMES,
		))
	assert "Unresolved line-break hyphens: 1 candidates" in stream.getvalue()
	assert "Line 1: intro- / duction" in stream.getvalue()


def test_corroborated_hyphenation_is_joined_and_not_reported() -> None:
	"""A corroborated split is repaired before unresolved candidates are measured."""
	cleaned, _removals, metrics = MODULE.clean_text(
		"introduction\nintro-\nduction\n", {"figure-debris", "ascii"}, 5, 15,
	)
	assert cleaned == "introduction introduction\n"
	assert metrics["unresolved_dehyphenation_candidates"] == 0
	assert metrics["unresolved_dehyphenation_examples"] == []


def test_ambiguous_compound_is_reported_but_retained() -> None:
	"""A plausible scientific compound remains unchanged and is surfaced for review."""
	cleaned, _removals, metrics = MODULE.clean_text(
		"protein-\nbinding\n", {"figure-debris", "ascii"}, 5, 15,
	)
	assert cleaned == "protein- binding\n"
	assert metrics["unresolved_dehyphenation_candidates"] == 1
	assert metrics["unresolved_dehyphenation_examples"][0]["prefix"] == "protein"


def test_unresolved_hyphenation_across_blank_gaps_is_reported_but_retained() -> None:
	"""Blank paragraph gaps do not hide unresolved words or change their output."""
	input_text = "protein-\n\n\nbinding\n\ntrans-\n\ncription\n"
	cleaned, _removals, metrics = MODULE.clean_text(
		input_text, {"figure-debris", "ascii"}, 5, 15,
	)
	assert cleaned == "protein-\n\nbinding\n\ntrans-\n\ncription\n"
	assert metrics["unresolved_dehyphenation_candidates"] == 2
	assert metrics["unresolved_dehyphenation_examples"] == [
		{"line": 1, "prefix": "protein", "continuation": "binding"},
		{"line": 6, "prefix": "trans", "continuation": "cription"},
	]


def test_unresolved_hyphenation_does_not_cross_protected_blank_gaps() -> None:
	"""Protected spans and Markdown boundaries stop blank-gap measurement."""
	input_text = (
		"---\nmeta-\n\ncontinued\n---\n\n"
		"ordinary-\n\ncontinued\n\n"
		"```text\ncode-\n\nvalue\n```\n\n"
		"> quoted-\n\n> text\n\n"
		"    indented-\n\n    code\n"
	)
	count, examples = MODULE.measure_unresolved_dehyphenation(input_text)
	assert count == 1
	assert examples == [
		{"line": 7, "prefix": "ordinary", "continuation": "continued"},
	]


def test_unresolved_hyphenation_ignores_protected_structures() -> None:
	"""Code, tables, inline code, and block quotes do not enter the review metric."""
	input_text = (
		"```text\ncode-\nvalue\n```\n\n"
		"| first- |\n| second |\n\n"
		"`inline-\ncode`\n\n"
		"> quoted-\n> text\n\n"
		"ordinary-\ntext\n"
	)
	_cleaned, _removals, metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert metrics["unresolved_dehyphenation_candidates"] == 1
	assert metrics["unresolved_dehyphenation_examples"] == [
		{"line": 15, "prefix": "ordinary", "continuation": "text"},
	]


def test_unresolved_hyphenation_after_protected_span_is_counted() -> None:
	"""A quote or code block ending at a newline leaves following prose eligible."""
	input_text = (
		"> quoted-\n> text\nordinary-\ntext\n"
		"```text\ncode-\nvalue\n```\nregular-\nwords\n"
	)
	_cleaned, _removals, metrics = MODULE.clean_text(
		input_text, {"figure-debris", "ascii"}, 5, 15,
	)
	assert metrics["unresolved_dehyphenation_candidates"] == 2
	assert metrics["unresolved_dehyphenation_examples"] == [
		{"line": 3, "prefix": "ordinary", "continuation": "text"},
		{"line": 9, "prefix": "regular", "continuation": "words"},
	]


def test_guarded_dehyphenation_after_protected_span_can_join() -> None:
	"""Corroborated prose after a quote remains eligible for a guarded join."""
	input_text = "introduction\n> quoted-\n> text\nintro-\nduction\n"
	cleaned, _removals, metrics = MODULE.clean_text(
		input_text, {"figure-debris", "ascii"}, 5, 15,
	)
	assert cleaned == "introduction\n\n> quoted-\n> text\nintroduction\n"
	assert metrics["unresolved_dehyphenation_candidates"] == 0
	assert metrics["unresolved_dehyphenation_examples"] == []


def test_unresolved_hyphenation_examples_are_bounded() -> None:
	"""Large inputs retain the full count and a fixed-size bounded sample."""
	input_text = ("a" * 60 + "-\n" + "b" * 60 + "\n") * 10
	_cleaned, _removals, metrics = MODULE.clean_text(
		input_text, {"figure-debris", "reflow", "ascii"}, 5, 15,
	)
	assert metrics["unresolved_dehyphenation_candidates"] == 10
	examples = metrics["unresolved_dehyphenation_examples"]
	assert len(examples) == MODULE.DEHYPHENATION_EXAMPLE_LIMIT
	assert all(
		len(example[part]) <= MODULE.DEHYPHENATION_EXAMPLE_PART_LENGTH
		for example in examples
		for part in ("prefix", "continuation")
	)
