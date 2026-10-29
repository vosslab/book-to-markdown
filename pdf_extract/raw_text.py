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
		line_records: list[pdf_extract.models.PageLineProvenance] = []
		block_index = 0
		for block in page_data["blocks"]:
			if block["type"] != 0:
				continue
			block_records: list[pdf_extract.models.PageLineProvenance] = []
			for line in block["lines"]:
				spans = line["spans"]
				line_text = _join_line_spans(spans)
				if not line_text or not line_text.strip(" "):
					continue
				boxes = [span["bbox"] for span in spans if span.get("bbox")]
				box = pymupdf.Rect(boxes[0]) if boxes else None
				for span_box in boxes[1:]:
					box.include_rect(span_box)
				page_box = page.rect
				rotated_box = box * page.rotation_matrix if box is not None else None
				bbox = None
				if rotated_box is not None and page_box.width and page_box.height:
					bbox = (
						(rotated_box.x0 - page_box.x0) / page_box.width,
						(rotated_box.y0 - page_box.y0) / page_box.height,
						(rotated_box.x1 - page_box.x0) / page_box.width,
						(rotated_box.y1 - page_box.y0) / page_box.height,
					)
				block_records.append(pdf_extract.models.PageLineProvenance(
					text=line_text,
					line_id=len(line_records) + (1 if line_records else 0) + len(block_records),
					source="raw_text",
					block_index=block_index,
					bbox=bbox,
					font_size=max((span["size"] for span in spans), default=None),
					font_names=tuple(dict.fromkeys(span["font"] for span in spans)),
					font_flags=tuple(dict.fromkeys(span["flags"] for span in spans)),
				))
			if block_records:
				if line_records:
					line_records.append(pdf_extract.models.PageLineProvenance("", len(line_records), "raw_text"))
				line_records.extend(block_records)
				block_index += 1
		text, line_records = pdf_extract.models.normalize_line_provenance(line_records)
		embedded_words = len(page.get_text("words"))
		result = pdf_extract.models.PageResult(page_number, text, "raw_text", embedded_words, 0, line_records)
		results.append(result)
	document.close()
	return results
