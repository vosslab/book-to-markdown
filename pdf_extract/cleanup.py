"""Shared page-aware cleanup, scoring, and reporting for the PDF extraction tools."""

import collections
import dataclasses
import pathlib
import re

import pymupdf

import pdf_extract.models
import pdf_extract.page_cleanup
import pdf_extract.text

# Defaults measured on eight technical/scientific books on 2026-08-08. They are
# starting diagnostics, not claims about narrative, non-English, or image-only PDFs.
LOW_TEXT_WORDS = 8
MIN_AVERAGE_CHARS_PER_PAGE = 100
MIN_WORD_RATIO = 0.85
SAMPLE_LIMIT = 4
CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]")

#============================================
def parse_pages(pages_text: str | None) -> list[int] | None:
	"""Parse comma-separated zero-based page numbers and inclusive ranges."""
	if pages_text is None:
		return None
	page_numbers: list[int] = []
	for item in pages_text.split(","):
		item = item.strip()
		if not item:
			continue
		if "-" in item:
			start_text, end_text = item.split("-", maxsplit=1)
			page_numbers.extend(range(int(start_text), int(end_text) + 1))
		else:
			page_numbers.append(int(item))
	page_numbers = sorted(set(page_numbers))
	return page_numbers

#============================================
def get_page_numbers(document: pymupdf.Document, pages: list[int] | None) -> list[int]:
	"""Return selected zero-based page numbers after validating their bounds."""
	page_numbers = list(range(document.page_count)) if pages is None else pages
	for page_number in page_numbers:
		if page_number < 0 or page_number >= document.page_count:
			raise ValueError(f"Page {page_number} is outside the PDF page range")
	return page_numbers

#============================================
def count_words(text: str) -> int:
	"""Count human-readable word tokens in extracted text."""
	word_count = len(re.findall(r"\w+", text))
	return word_count

#============================================
def estimate_source_words(results: list[pdf_extract.models.PageResult]) -> int:
	"""Estimate source words using the best available word-layer count per page."""
	estimated_words = sum(max(result.embedded_words, result.ocr_words) for result in results)
	return estimated_words

#============================================
def calculate_word_ratio(extracted_words: int, estimated_words: int) -> float:
	"""Calculate extracted words divided by estimated source words."""
	word_ratio = extracted_words / estimated_words if estimated_words else 0.0
	return word_ratio

#============================================
def get_quality_status(word_ratio: float, average_chars: int, has_controls: bool) -> str:
	"""Return REVIEW only for calibrated gross-extraction evidence."""
	if word_ratio < MIN_WORD_RATIO or average_chars < MIN_AVERAGE_CHARS_PER_PAGE or has_controls:
		quality_status = "REVIEW"
	else:
		quality_status = "OK"
	return quality_status

#============================================
def count_headings(text: str) -> int:
	"""Count Markdown headings for extractor comparison evidence."""
	heading_count = len(re.findall(r"(?m)^#{1,6}\s+", text))
	return heading_count

#============================================
def count_table_rows(text: str) -> int:
	"""Count Markdown pipe rows as a conservative table-preservation signal."""
	table_rows = sum(1 for line in text.splitlines() if line.strip().startswith("|"))
	return table_rows

#============================================
def score_pages(results: list[pdf_extract.models.PageResult]) -> dict[str, int | float | bool | str]:
	"""Measure gross extraction quality without declaring mathematical text corrupt."""
	text = "\n\n".join(result.text for result in results)
	page_count = len(results)
	estimated_words = estimate_source_words(results)
	extracted_words = count_words(text)
	average_chars = len(text) // page_count if page_count else 0
	word_ratio = calculate_word_ratio(extracted_words, estimated_words)
	has_controls = bool(CONTROL_PATTERN.search(text))
	paragraphs = pdf_extract.text.split_blocks(text)
	nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
	repeated_lines = sum(count - 1 for count in collections.Counter(nonempty_lines).values() if count > 1)
	quality_status = get_quality_status(word_ratio, average_chars, has_controls)
	score: dict[str, int | float | bool | str] = {
		"pages": page_count,
		"characters": len(text),
		"average_chars_per_page": average_chars,
		"estimated_words": estimated_words,
		"extracted_words": extracted_words,
		"word_ratio": word_ratio,
		"heading_count": count_headings(text),
		"table_row_count": count_table_rows(text),
		"paragraph_count": len(paragraphs),
		"mean_paragraph_words": extracted_words / len(paragraphs) if paragraphs else 0.0,
		"repeated_line_count": repeated_lines,
		"control_characters": has_controls,
		"quality_status": quality_status,
	}
	return score

#============================================
def bounded_samples(values: list[str]) -> list[str]:
	"""Keep terminal and JSON evidence inspectable for a book-sized run."""
	unique_values = list(dict.fromkeys(values))
	return unique_values[:SAMPLE_LIMIT]

#============================================
def page_evidence(results: list[pdf_extract.models.PageResult]) -> dict[str, int | float | list[str] | dict[str, int]]:
	"""Measure compact page-level debris evidence without transforming the pages."""
	lines = [line.strip() for result in results for line in result.text.splitlines() if line.strip()]
	edge_page_numbers: list[str] = []
	non_ascii: list[str] = []
	short_lines: list[str] = []
	recognized_tags: list[str] = []
	for result in results:
		page_lines = [line.strip() for line in result.text.splitlines() if line.strip()]
		if page_lines:
			for line in (page_lines[0], page_lines[-1]):
				if pdf_extract.page_cleanup.PAGE_NUMBER_PATTERN.fullmatch(line):
					edge_page_numbers.append(f"page {result.page_number + 1}: {line}")
		for line in page_lines:
			if len(line) <= 12:
				short_lines.append(line)
			if any(ord(character) > 127 for character in line):
				non_ascii.append(line)
			for tag in re.findall(r"</?([A-Za-z][A-Za-z0-9-]*)\b[^<>]*>", line):
				recognized_tags.append(tag.lower())
	repeated = collections.Counter(lines)
	repeated_lines = [line for line, count in repeated.most_common() if count > 1]
	evidence: dict[str, int | float | list[str] | dict[str, int]] = {
		"edge_page_number_lines": len(edge_page_numbers),
		"edge_page_number_samples": bounded_samples(edge_page_numbers),
		"non_ascii_lines": len(non_ascii),
		"non_ascii_samples": bounded_samples(non_ascii),
		"short_lines": len(short_lines),
		"short_line_fraction": len(short_lines) / len(lines) if lines else 0.0,
		"short_line_samples": bounded_samples(short_lines),
		"recognized_tags": dict(collections.Counter(recognized_tags).most_common(SAMPLE_LIMIT)),
		"repeated_line_count": sum(count - 1 for count in repeated.values() if count > 1),
		"repeated_line_samples": bounded_samples(repeated_lines),
	}
	return evidence

#============================================
def build_frontmatter(input_path: pathlib.Path) -> str:
	"""Build a small YAML metadata block from PDF document metadata."""
	document = pymupdf.open(input_path)
	metadata = document.metadata
	document.close()
	title = metadata["title"].strip() if metadata["title"] else input_path.stem
	author = metadata["author"].strip() if metadata["author"] else "unknown"
	title = title.replace('"', "'")
	author = author.replace('"', "'")
	frontmatter = "---\n"
	frontmatter += f'title: "{title}"\n'
	frontmatter += f'author: "{author}"\n'
	frontmatter += f'source_pdf: "{input_path.name}"\n'
	frontmatter += "---\n\n"
	frontmatter += f"# {title}\n\n"
	return frontmatter

#============================================
def build_warnings(results: list[pdf_extract.models.PageResult], score: dict[str, int | float | bool | str]) -> list[str]:
	"""Build diagnostics that preserve reviewable output instead of raising errors."""
	warnings: list[str] = []
	if not results:
		warnings.append("No pages were selected.")
		return warnings
	if str(score["quality_status"]) == "REVIEW":
		warnings.append("Gross extraction evidence requires a source-page spot check.")
	if bool(score["control_characters"]):
		warnings.append("Control or replacement characters remain in extracted text.")
	empty_pages = [result.page_number + 1 for result in results if not result.text]
	if empty_pages:
		warnings.append(f"Empty pages after extraction: {format_page_list(empty_pages)}.")
	low_text_pages = [result.page_number + 1 for result in results if result.text and count_words(result.text) < LOW_TEXT_WORDS]
	if low_text_pages:
		warnings.append(f"Low-text pages after extraction: {format_page_list(low_text_pages)}.")
	return warnings

#============================================
def format_page_list(page_numbers: list[int]) -> str:
	"""Format a page-number list for a compact human report."""
	if not page_numbers:
		page_text = "none"
	elif len(page_numbers) <= 20:
		page_text = ", ".join(str(page_number) for page_number in page_numbers)
	else:
		page_text = ", ".join(str(page_number) for page_number in page_numbers[:20])
		page_text += f", ... ({len(page_numbers)} total)"
	return page_text

#============================================
def result_report(input_path: pathlib.Path, output_path: pathlib.Path, result: pdf_extract.models.ConversionResult) -> dict:
	"""Build a JSON-compatible report used for stdout and optional machine comparison."""
	running_heads = [dataclasses.asdict(decision) for decision in result.running_heads]
	removal_counts = collections.Counter(removal.pass_name for removal in result.removals)
	removal_samples: dict[str, list[dict[str, int | float | str | list[float] | None]]] = {}
	for removal in result.removals:
		if len(removal_samples.setdefault(removal.pass_name, [])) >= SAMPLE_LIMIT:
			continue
		removal_samples[removal.pass_name].append({
			"page": removal.page_number,
			"line": removal.line_number,
			"text": removal.text,
			"reason": removal.reason,
			"source_line_id": removal.source_line_id,
			"source_bbox": list(removal.source_bbox) if removal.source_bbox is not None else None,
			"source_font_size": removal.source_font_size,
		})
	report = {
		"pdf": str(input_path),
		"markdown": str(output_path),
		"pages_converted": len(result.pages),
		"extraction_method": result.extraction_method,
		"quality_status": result.quality_status,
		"estimated_words": result.estimated_words,
		"extracted_words": result.extracted_words,
		"word_ratio": result.word_ratio,
		"headings": result.heading_count,
		"table_rows": result.table_row_count,
		"seams_seen": result.seams_seen,
		"seams_joined": result.seams_joined,
		"running_heads": running_heads,
		"effective_running_head_defaults": result.effective_running_head_defaults,
		"page_evidence": result.initial_page_evidence,
		"synthesized_headings": result.synthesized_headings,
		"removal_counts": dict(removal_counts),
		"removal_samples": removal_samples,
		"warnings": result.warnings,
	}
	return report

#============================================
def print_report(report: dict, measure_only: bool = False) -> None:
	"""Print aggregate evidence plus bounded samples for manager review."""
	print(f"PDF: {report['pdf']}")
	if measure_only:
		print("Markdown: (measure only - no output file written)")
	else:
		print(f"Markdown: {report['markdown']}")
	print(f"Pages converted: {report['pages_converted']}")
	print(f"Extraction method: {report['extraction_method']}")
	print(f"Quality status: {report['quality_status']}")
	print(f"Extracted/estimated words: {float(report['word_ratio']):.1%}")
	print(f"Headings: {report['headings']}; pipe table rows: {report['table_rows']}")
	print(f"Seams: {report['seams_joined']} joined of {report['seams_seen']} seen")
	print(f"Removal counts: {report['removal_counts'] or 'none'}")
	evidence = report["page_evidence"]
	print("Page evidence: "
		f"{evidence['edge_page_number_lines']} edge page numbers; "
		f"{evidence['non_ascii_lines']} non-ASCII lines; "
		f"{evidence['short_lines']} short lines; "
		f"{evidence['repeated_line_count']} repeated lines")
	if evidence["recognized_tags"]:
		print(f"Recognized tags (sample): {evidence['recognized_tags']}")
	running_heads = report["running_heads"]
	if running_heads:
		print("Running-head templates (sample):")
		for decision in running_heads[:SAMPLE_LIMIT]:
			action_evidence = ""
			if decision["disposition"] == "promote":
				action_evidence = f", {decision['promoted_count']} promoted at H{decision['heading_level']}"
			print(f"- {decision['disposition']}: {decision['template']} "
				f"({decision['count']}, {decision['edge_fraction']:.0%} edge{action_evidence})")
	if report["removal_samples"]:
		print("Removal samples:")
		for pass_name, samples in report["removal_samples"].items():
			for sample in samples:
				print(f"- {pass_name}, page {sample['page']} line {sample['line']}: {sample['text']}")
	if report["warnings"]:
		print("Warnings:")
		for warning in report["warnings"]:
			print(f"- {warning}")

#============================================
def write_removal_sidecar(output_path: pathlib.Path, removals: list[pdf_extract.models.Removal]) -> pathlib.Path:
	"""Write every page-aware removal to a recoverable Markdown sidecar."""
	sidecar_path = pathlib.Path(str(output_path) + ".removed.md")
	groups: dict[str, list[pdf_extract.models.Removal]] = collections.defaultdict(list)
	for removal in removals:
		groups[removal.pass_name].append(removal)
	lines = ["# Removed page-aware content", "", "This sidecar preserves every removal for audit and recovery.", ""]
	for pass_name in sorted(groups):
		lines.append(f"## {pass_name}")
		lines.append("")
		for removal in groups[pass_name]:
			lines.append(f"- page {removal.page_number}, source line {removal.line_number}: {removal.reason}")
			if removal.source_line_id is not None:
				lines.append(f"  - extracted line id: {removal.source_line_id}")
			if removal.source_bbox is not None:
				bbox_text = ", ".join(f"{value:.4f}" for value in removal.source_bbox)
				lines.append(f"  - normalized page bbox: {bbox_text}")
			if removal.source_font_size is not None:
				lines.append(f"  - source font size: {removal.source_font_size:g}")
			lines.append("```text")
			lines.append(removal.text)
			lines.append("```")
			lines.append("")
	if not removals:
		lines.append("No page-aware content was removed.")
	sidecar_text = "\n".join(lines) + "\n"
	sidecar_path.write_text(sidecar_text, encoding="utf-8")
	return sidecar_path

#============================================
def convert_pages(
	input_path: pathlib.Path,
	pages: list[pdf_extract.models.PageResult],
	extraction_method: str,
	running_heads: bool,
	page_numbers: bool,
	seams: bool,
	heading_synthesis: bool,
	running_head_defaults: dict[str, int | float],
) -> pdf_extract.models.ConversionResult:
	"""Run page-aware flattening passes on already-extracted pages."""
	initial_evidence = page_evidence(pages)
	removals: list[pdf_extract.models.Removal] = []
	running_head_report: list[pdf_extract.models.RunningHeadDecision] = []
	if running_heads:
		running_head_report = pdf_extract.page_cleanup.remove_running_heads(pages, removals, running_head_defaults)
	pdf_extract.page_cleanup.remove_picture_blocks(pages, removals)
	if page_numbers:
		pdf_extract.page_cleanup.remove_edge_page_numbers(pages, removals)
	synthesized_headings = pdf_extract.page_cleanup.synthesize_numbered_headings(pages) if heading_synthesis else []
	markdown_text, seams_seen, seams_joined = pdf_extract.text.flatten_pages(pages, seams)
	markdown_text = pdf_extract.text.demote_source_h1s(markdown_text)
	markdown_text = build_frontmatter(input_path) + markdown_text
	final_score = score_pages(pages)
	warnings = build_warnings(pages, final_score)
	conversion_result = pdf_extract.models.ConversionResult(
		pages=pages,
		markdown_text=markdown_text,
		extraction_method=extraction_method,
		warnings=warnings,
		estimated_words=int(final_score["estimated_words"]),
		extracted_words=int(final_score["extracted_words"]),
		word_ratio=float(final_score["word_ratio"]),
		quality_status=str(final_score["quality_status"]),
		heading_count=count_headings(markdown_text),
		table_row_count=int(final_score["table_row_count"]),
		seams_seen=seams_seen,
		seams_joined=seams_joined,
		running_heads=running_head_report,
		synthesized_headings=synthesized_headings,
		removals=removals,
		effective_running_head_defaults=running_head_defaults,
		initial_page_evidence=initial_evidence,
	)
	return conversion_result

#============================================
def measure_pages(
	pages: list[pdf_extract.models.PageResult],
	extraction_method: str,
	running_head_defaults: dict[str, int | float],
) -> pdf_extract.models.ConversionResult:
	"""Measure already-extracted pages without applying page-cleanup transforms."""
	initial_evidence = page_evidence(pages)
	final_score = score_pages(pages)
	warnings = build_warnings(pages, final_score)
	markdown_text = "\n\n".join(result.text for result in pages)
	measurement = pdf_extract.models.ConversionResult(
		pages=pages,
		markdown_text=markdown_text,
		extraction_method=extraction_method,
		warnings=warnings,
		estimated_words=int(final_score["estimated_words"]),
		extracted_words=int(final_score["extracted_words"]),
		word_ratio=float(final_score["word_ratio"]),
		quality_status=str(final_score["quality_status"]),
		heading_count=int(final_score["heading_count"]),
		table_row_count=int(final_score["table_row_count"]),
		seams_seen=0,
		seams_joined=0,
		running_heads=[],
		synthesized_headings=[],
		removals=[],
		effective_running_head_defaults=running_head_defaults,
		initial_page_evidence=initial_evidence,
	)
	return measurement
