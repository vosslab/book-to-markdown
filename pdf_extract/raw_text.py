"""Raw text-layer extraction for the PDF to Markdown pipeline."""

import pathlib

import pymupdf

import pdf_extract.cleanup
import pdf_extract.models
import pdf_extract.text


# The archived PDF's omitted word gaps measure 0.15 em; require a clear 0.1-em gap.
WORD_GAP_EM = 0.1


#============================================
def _is_geometric_word_gap(
		previous_char: dict,
		current_char: dict,
		font_size: float,
	) -> bool:
	"""Return whether adjacent PDF glyphs have a clear inter-word gap."""
	if previous_char["c"].isspace() or current_char["c"].isspace():
		return False
	gap = current_char["bbox"][0] - previous_char["bbox"][2]
	return gap > font_size * WORD_GAP_EM


#============================================
def _join_line_spans(
		spans: list[dict],
	) -> str:
	"""Join span characters while restoring clear spaces omitted by the PDF text layer."""
	parts: list[str] = []
	previous_char: dict | None = None
	previous_font_size = 0.0
	for span in spans:
		characters = span["chars"]
		if not characters:
			continue
		font_size = span["size"]
		gap_font_size = max(previous_font_size, font_size)
		if previous_char is not None and _is_geometric_word_gap(
				previous_char,
				characters[0],
				gap_font_size,
			):
			parts.append(" ")
		span_parts: list[str] = []
		for character_index, character in enumerate(characters):
			if character_index > 0 and _is_geometric_word_gap(characters[character_index - 1], character, font_size):
				span_parts.append(" ")
			span_parts.append(character["c"])
		span_text = "".join(span_parts)
		if span["flags"] & pymupdf.TEXT_FONT_SUPERSCRIPT and span_text.strip():
			leading_space = span_text[:len(span_text) - len(span_text.lstrip())]
			trailing_space = span_text[len(span_text.rstrip()):]
			content = span_text.strip()
			span_text = leading_space + "^{" + content + "}" + trailing_space
		parts.append(span_text)
		previous_char = characters[-1]
		previous_font_size = font_size
	return "".join(parts)


#============================================
def extract_raw_text(input_path: pathlib.Path, pages: list[int] | None) -> list[pdf_extract.models.PageResult]:
	"""Extract each selected page from its PDF text layer without OCR.

	Args:
		input_path: Path to the input PDF file.
		pages: Zero-based page numbers, or None for every page.

	Returns:
		list[pdf_extract.models.PageResult]: One page result per selected page.
	"""
	document = pymupdf.open(input_path)
	page_numbers = pdf_extract.cleanup.get_page_numbers(document, pages)
	results: list[pdf_extract.models.PageResult] = []
	for page_number in page_numbers:
		page = document[page_number]
		page_data = page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_TEXT)
		text_blocks: list[str] = []
		for block in page_data["blocks"]:
			if block["type"] != 0:
				continue
			lines: list[str] = []
			for line in block["lines"]:
				lines.append(_join_line_spans(line["spans"]))
			block_text = "\n".join(lines)
			if block_text.strip():
				text_blocks.append(block_text)
		page_text = "\n\n".join(text_blocks)
		text = pdf_extract.text.normalize_text(page_text)
		embedded_words = len(page.get_text("words"))
		results.append(pdf_extract.models.PageResult(page_number, text, "raw_text", embedded_words, 0))
	document.close()
	return results
