"""OCR text extraction for the PDF to Markdown pipeline."""

import pathlib
import pymupdf

import pdf_extract.cleanup
import pdf_extract.models

#============================================
def extract_ocr_page(
		page: pymupdf.Page,
	) -> tuple[str, list[pdf_extract.models.PageLineProvenance]]:
	"""Extract OCR text and positioned line records from PyMuPDF's OCR text page."""
	try:
		textpage = page.get_textpage_ocr(full=True, dpi=300)
	except RuntimeError as error:
		message = str(error)
		if "Tesseract" in message or "tessdata" in message:
			raise RuntimeError(
				"OCR requires Tesseract with English traineddata. "
				"Install system-wide with: sudo apt install tesseract-ocr tesseract-ocr-eng  "
				"or rootless: download the .debs, extract with dpkg -x, and export "
				"PATH/LD_LIBRARY_PATH/TESSDATA_PREFIX to the extracted prefix."
			) from error
		raise
	page_data = page.get_text("dict", textpage=textpage)
	line_records: list[pdf_extract.models.PageLineProvenance] = []
	block_index = 0
	for block in page_data["blocks"]:
		if block["type"] != 0:
			continue
		block_records: list[pdf_extract.models.PageLineProvenance] = []
		for line in block["lines"]:
			spans = line["spans"]
			line_text = "".join(span["text"] for span in spans)
			if not line_text.strip():
				continue
			page_box = page.rect
			line_box = pymupdf.Rect(line["bbox"]) * page.rotation_matrix
			bbox = None
			if page_box.width and page_box.height:
				bbox = (
					(line_box.x0 - page_box.x0) / page_box.width,
					(line_box.y0 - page_box.y0) / page_box.height,
					(line_box.x1 - page_box.x0) / page_box.width,
					(line_box.y1 - page_box.y0) / page_box.height,
				)
			block_records.append(pdf_extract.models.PageLineProvenance(
				text=line_text,
				line_id=len(line_records) + (1 if line_records else 0) + len(block_records),
				source="ocr",
				block_index=block_index,
				bbox=bbox,
				font_size=max((span["size"] for span in spans), default=None),
				font_names=tuple(dict.fromkeys(span["font"] for span in spans)),
				font_flags=tuple(dict.fromkeys(span["flags"] for span in spans)),
			))
		if block_records:
			if line_records:
				line_records.append(pdf_extract.models.PageLineProvenance("", len(line_records), "ocr"))
			line_records.extend(block_records)
			block_index += 1
	text, line_records = pdf_extract.models.normalize_line_provenance(line_records)
	return text, line_records


#============================================
def extract_ocr_text(input_path: pathlib.Path, pages: list[int] | None) -> list[pdf_extract.models.PageResult]:
	"""Extract each selected page via OCR for image-only scans.

	Args:
		input_path: Path to the input PDF file.
		pages: Zero-based page numbers, or None for every page.

	Returns:
		list[pdf_extract.models.PageResult]: One OCR page result per selected page.
	"""
	document = pymupdf.open(input_path)
	try:
		# Validate page indexes before accessing selected pages.
		page_numbers = pdf_extract.cleanup.get_page_numbers(document, pages)
		embedded_word_counts = [
			len(document[page_number].get_text("words")) for page_number in page_numbers
		]
		results: list[pdf_extract.models.PageResult] = []
		for page_number, embedded_words in zip(page_numbers, embedded_word_counts):
			page = document[page_number]
			text, line_provenance = extract_ocr_page(page)
			ocr_words = pdf_extract.cleanup.count_words(text)
			results.append(
				pdf_extract.models.PageResult(
					page_number, text, "ocr", embedded_words, ocr_words, line_provenance
				)
			)
	finally:
		document.close()
	return results
