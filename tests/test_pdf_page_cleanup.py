"""Behavior checks for PDF page cleanup and provenance."""

import pathlib

import pymupdf
import pytest

import cleanup.layout
import pdf_extract.cleanup
import pdf_extract.models
import pdf_extract.ocr_text
import pdf_extract.page_cleanup
import pdf_extract.raw_text
import pdf_extract.text


def test_native_geometry_keeps_large_chapter_opener_and_removes_small_headers(tmp_path: pathlib.Path) -> None:
	"""Raw span positions distinguish the chapter opener from odd/even page furniture."""
	pdf_path = tmp_path / "running-heads.pdf"
	document = pymupdf.open()
	for page_number in range(6):
		page = document.new_page(width=504, height=666)
		if page_number == 0:
			page.insert_text((84, 90), "Classification of Plants", fontsize=28)
			page.insert_text((72, 130), "The chapter begins with body prose.", fontsize=11)
		else:
			font_size = 9
			x = 72 if page_number % 2 else 330
			page.insert_text((x, 55), "Classification of Plants", fontsize=font_size)
			page.insert_text((72, 82), f"Ordinary running prose page {page_number}.", fontsize=11)
			page.insert_text((250, 640), str(page_number + 20), fontsize=9)
	document.save(pdf_path)
	document.close()
	pages = pdf_extract.raw_text.extract_raw_text(pdf_path, None)
	assert all([record.text for record in page.line_provenance] == page.text.splitlines() for page in pages)
	assert all(record.bbox is not None for page in pages for record in page.line_provenance if record.text)
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	removals: list[pdf_extract.models.Removal] = []
	decisions = pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)
	assert pages[0].text.splitlines()[0] == "Classification of Plants"
	assert len(removals) == 3
	assert all(pages[index].text.startswith("Classification of Plants") for index in (2, 4))
	assert all(not pages[index].text.startswith("Classification of Plants") for index in (1, 3, 5))
	assert any(removal.source_font_size == 28 for removal in removals) is False
	assert all(str(page_number + 20) in pages[page_number].text for page_number in range(1, 6))
	assert all([record.text for record in page.line_provenance] == page.text.splitlines() for page in pages)
	assert decisions[0].occurrences[0]["reason"] == "ambiguous or outside proven furniture group"


#============================================
def test_ocr_geometry_is_retained_for_positioned_text(tmp_path: pathlib.Path) -> None:
	"""OCR extraction retains text-page geometry when the OCR layer supplies it."""
	pdf_path = tmp_path / "ocr-running-head.pdf"
	source = pymupdf.open()
	source_page = source.new_page(width=504, height=666)
	source_page.insert_text((72, 55), "RUNNING HEADER", fontsize=12)
	source_page.insert_text((72, 130), "Scanned body prose", fontsize=12)
	pixmap = source_page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
	image_pdf = pymupdf.open()
	image_page = image_pdf.new_page(width=504, height=666)
	image_page.insert_image(image_page.rect, stream=pixmap.tobytes("png"))
	image_pdf.save(pdf_path)
	source.close()
	image_pdf.close()
	results = pdf_extract.ocr_text.extract_ocr_text(pdf_path, None)
	assert results[0].source == "ocr"
	assert results[0].line_provenance
	assert [record.text for record in results[0].line_provenance] == results[0].text.splitlines()
	assert any(record.bbox is not None for record in results[0].line_provenance if record.text)


#============================================
def test_running_heads_keep_unique_numbered_openers_and_remove_repeated_labels() -> None:
	"""Geometry-backed recurrent labels are removed while varied labels survive."""
	labels = [
		"CHAPTER 1", "CHAPTER 2", "CHAPTER 3", "CHAPTER 4", "CHAPTER 5",
		"CHAPTER 1", "CHAPTER 1", "APPENDIX 1", "APPENDIX 2", "APPENDIX 1",
		"APPENDIX 1",
	]
	pages = [
		pdf_extract.models.PageResult(
			page_number=index,
			text=f"{label}\nUnique prose {chr(65 + index)}.",
			source="raw_text",
			embedded_words=10,
			ocr_words=0,
			line_provenance=[
				pdf_extract.models.PageLineProvenance(label, 0, "raw_text", bbox=(0.1, 0.06, 0.5, 0.08), font_size=8, font_names=("Header-Bold",), font_flags=(20,)),
				pdf_extract.models.PageLineProvenance(f"Unique prose {chr(65 + index)}.", 1, "raw_text", bbox=(0.1, 0.105, 0.8, 0.125), font_size=12, font_names=("Body-Regular",), font_flags=(4,)),
			],
		)
		for index, label in enumerate(labels)
	]
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	removals: list[pdf_extract.models.Removal] = []

	decisions = pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)
	remaining_labels = [
		page.text.splitlines()[0]
		for page in pages
		if page.text.startswith(("CHAPTER ", "APPENDIX "))
	]

	assert remaining_labels == [
		"CHAPTER 2", "CHAPTER 3", "CHAPTER 4", "CHAPTER 5", "APPENDIX 2",
	]
	assert {decision.template for decision in decisions if decision.disposition == "delete"} == {
		"CHAPTER 1", "APPENDIX 1",
	}
	assert all([record.text for record in page.line_provenance] == page.text.splitlines() for page in pages)
	assert all(removal.source_line_id == 0 and removal.source_bbox is not None for removal in removals)


#============================================
def test_running_heads_preserve_vertical_tab_inside_source_line() -> None:
	"""An embedded vertical tab stays inside its LF-delimited source line."""
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	pages = []
	for page_number in range(4):
		body = f"Body detail {page_number} before\v\f\x1c\x1d\x1e\x85\u2028\u2029after."
		pages.append(pdf_extract.models.PageResult(
			page_number,
			f"COPYRIGHT NOTICE\n{body}",
			"raw_text",
			10,
			0,
			[
				pdf_extract.models.PageLineProvenance("COPYRIGHT NOTICE", 80, "raw_text",
					bbox=(0.1, 0.06, 0.5, 0.08), font_size=8,
					font_names=("Header-Bold",), font_flags=(20,)),
				pdf_extract.models.PageLineProvenance(body, 81, "raw_text",
					bbox=(0.1, 0.105, 0.8, 0.13), font_size=12,
					font_names=("Body-Regular",), font_flags=(4,)),
			],
		))
	removals: list[pdf_extract.models.Removal] = []

	decisions = pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)
	pdf_extract.page_cleanup.remove_picture_blocks(pages, removals)
	pdf_extract.page_cleanup.remove_edge_page_numbers(pages, removals)
	assert pdf_extract.page_cleanup.synthesize_numbered_headings(pages) == []

	assert len(removals) == 4
	assert all(
		page.text == f"Body detail {page.page_number} before\v\f\x1c\x1d\x1e\x85\u2028\u2029after."
		for page in pages
	)
	assert all([record.text for record in page.line_provenance] == page.text.split("\n") for page in pages)
	assert all(page.line_provenance[0].line_id == 81 for page in pages)
	assert all(removal.source_line_id == 80 for removal in removals)
	assert next(decision for decision in decisions if decision.template == "COPYRIGHT NOTICE").disposition == "delete"

	for page_number, separator in enumerate(("\v", "\f", "\t", "\r"), start=4):
		ambiguous_source_row = f"{separator}20.0 U/L, Negative Test"
		row_page = pdf_extract.models.PageResult(
			page_number,
			"Table heading\n" + ambiguous_source_row + "\nNext row",
			"raw_text",
			10,
			0,
			[
				pdf_extract.models.PageLineProvenance("Table heading", 90, "raw_text"),
				pdf_extract.models.PageLineProvenance(ambiguous_source_row, 91, "raw_text"),
				pdf_extract.models.PageLineProvenance("Next row", 92, "raw_text"),
			],
		)
		assert pdf_extract.page_cleanup.synthesize_numbered_headings([row_page]) == []
		assert row_page.text.split("\n")[1] == ambiguous_source_row
		assert row_page.line_provenance[1].line_id == 91


#============================================
def test_running_heads_preserve_differently_scaled_chapter_and_glossary_openers() -> None:
	"""A repeated title is removed only where page-relative layout marks furniture."""
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	for heading in ("Classification of Plants", "Words to Know"):
		pages: list[pdf_extract.models.PageResult] = []
		for page_number in range(6):
			font_size = 26 if page_number == 0 else 9
			left = 0.1 if page_number % 2 == 0 else 0.62
			line_bbox = (left, 0.09, left + 0.3, 0.09 + font_size / 666)
			text = f"{heading}\nBody prose page {page_number}."
			provenance = [
				pdf_extract.models.PageLineProvenance(heading, 0, "raw_text", bbox=line_bbox, font_size=font_size, font_names=("Header-Bold",), font_flags=(20,)),
				pdf_extract.models.PageLineProvenance(f"Body prose page {page_number}.", 1, "raw_text", bbox=(0.1, 0.12, 0.8, 0.15), font_size=10, font_names=("Body-Regular",), font_flags=(4,)),
			]
			pages.append(pdf_extract.models.PageResult(page_number, text, "raw_text", 10, 0, provenance))
		removals: list[pdf_extract.models.Removal] = []
		decisions = pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)
		assert pages[0].text.splitlines()[0] == heading
		assert len(removals) == 5
		assert all(page.text.splitlines()[0] == "Body prose page " + str(page.page_number) + "." for page in pages[1:])
		assert decisions[0].occurrences[0]["disposition"] == "preserve"
		assert all(removal.source_font_size == 9 for removal in removals)


#============================================
def test_running_heads_preserve_fully_indistinguishable_recurrence() -> None:
	"""Repeated edge text without distinguishing local context remains ambiguous."""
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	pages = [
		pdf_extract.models.PageResult(
			index,
			"Shared Chapter Title\nBody prose below the title.",
			"raw_text",
			10,
			0,
			[
				pdf_extract.models.PageLineProvenance(
					"Shared Chapter Title", 0, "raw_text", bbox=(0.1, 0.04, 0.9, 0.07),
					font_size=12, font_names=("Times-Roman",), font_flags=(4,), block_index=0,
				),
				pdf_extract.models.PageLineProvenance(
					"Body prose below the title.", 1, "raw_text", bbox=(0.1, 0.2, 0.9, 0.22),
					font_size=12, font_names=("Times-Roman",), font_flags=(4,), block_index=1,
				),
			],
		)
		for index in range(5)
	]
	removals: list[pdf_extract.models.Removal] = []
	decisions = pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)

	assert not removals
	assert all(page.text.startswith("Shared Chapter Title") for page in pages)
	assert decisions[0].disposition == "preserve"
	assert {row["reason"] for row in decisions[0].occurrences} == {"ambiguous or outside proven furniture group"}


#============================================
@pytest.mark.parametrize(
	("header_bbox", "body_bbox"),
	[
		((0.08, 0.04, 0.42, 0.07), (0.58, 0.08, 0.94, 0.11)),
		((0.58, 0.04, 0.92, 0.07), (0.08, 0.08, 0.42, 0.11)),
	],
)
def test_running_heads_preserve_heading_when_below_text_is_in_adjacent_column(
		header_bbox: tuple[float, float, float, float],
		body_bbox: tuple[float, float, float, float],
	) -> None:
	"""Text in another column cannot serve as local body evidence for deletion."""
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	pages = [
		pdf_extract.models.PageResult(
			index,
			"Shared Chapter Title\nAdjacent-column body prose.",
			"raw_text",
			10,
			0,
			[
				pdf_extract.models.PageLineProvenance(
					"Shared Chapter Title", 0, "raw_text", bbox=header_bbox,
					font_size=8, font_names=("Header-Bold",), font_flags=(20,), block_index=0,
				),
				pdf_extract.models.PageLineProvenance(
					"Adjacent-column body prose.", 1, "raw_text", bbox=body_bbox,
					font_size=12, font_names=("Body-Regular",), font_flags=(4,), block_index=1,
				),
			],
		)
		for index in range(5)
	]
	removals: list[pdf_extract.models.Removal] = []
	decisions = pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)

	assert removals == []
	assert all(page.text.startswith("Shared Chapter Title") for page in pages)
	assert decisions[0].disposition == "preserve"
	assert {row["reason"] for row in decisions[0].occurrences} == {"ambiguous or outside proven furniture group"}


#============================================
def test_running_heads_preserve_alignment_and_style_outliers() -> None:
	"""A lone occurrence outside the recurrent x/font group remains with the body."""
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	pages = []
	for index in range(6):
		is_alignment_outlier = index == 0
		is_style_outlier = index == 1
		font = 14 if is_style_outlier else 8
		font_name = "Chapter-Display" if is_style_outlier else "Header-Bold"
		bbox = (0.6, 0.04, 0.98, 0.07) if is_alignment_outlier else (0.1, 0.04, 0.48, 0.07)
		pages.append(pdf_extract.models.PageResult(
			index,
			"Aligned Shared Label\nBody prose starts nearby.",
			"raw_text", 10, 0,
			[
				pdf_extract.models.PageLineProvenance("Aligned Shared Label", 0, "raw_text", bbox=bbox,
					font_size=font, font_names=(font_name,), font_flags=(20,), block_index=0),
				pdf_extract.models.PageLineProvenance("Body prose starts nearby.", 1, "raw_text", bbox=(0.1, 0.105, 0.8, 0.125),
					font_size=12, font_names=("Body-Regular",), font_flags=(4,), block_index=1),
			],
		))
	removals: list[pdf_extract.models.Removal] = []
	decisions = pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)

	assert len(removals) == 4
	assert pages[0].text.startswith("Aligned Shared Label")
	assert pages[1].text.startswith("Aligned Shared Label")
	assert all(not page.text.startswith("Aligned Shared Label") for page in pages[2:])
	assert decisions[0].occurrences[0]["disposition"] == "preserve"


#============================================
def test_running_head_geometry_uses_page_relative_bounds_and_preserves_rotation_outliers(
		tmp_path: pathlib.Path,
	) -> None:
	"""Page size changes normalize cleanly while rotated outliers stay for review."""
	pdf_path = tmp_path / "varied-running-head-bounds.pdf"
	document = pymupdf.open()
	page_specs = [(504, 666, 0), (595, 842, 0), (504, 666, 90), (595, 842, 0), (504, 666, 180)]
	for page_number, (width, height, rotation) in enumerate(page_specs):
		page = document.new_page(width=width, height=height)
		page.insert_text((width * 0.1, height * 0.08), "RUNNING LABEL", fontsize=8)
		page.insert_text((width * 0.1, height * 0.12), f"Body line {page_number}", fontsize=12)
		page.set_rotation(rotation)
	document.save(pdf_path)
	document.close()

	pages = pdf_extract.raw_text.extract_raw_text(pdf_path, None)
	removals: list[pdf_extract.models.Removal] = []
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)

	assert len(removals) == 3
	assert all(not pages[index].text.startswith("RUNNING LABEL") for index in (0, 1, 3))
	assert pages[2].text.startswith("RUNNING LABEL")
	assert pages[4].text.startswith("RUNNING LABEL")


#============================================
def test_running_heads_preserve_ambiguous_metadata_free_and_non_edge_text() -> None:
	"""Missing layout, TOC text, and near-edge headings remain available to readers."""
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	metadata_free = [
		pdf_extract.models.PageResult(index, "Repeated Heading\nBody text", "raw_text", 5, 0)
		for index in range(4)
	]
	removals: list[pdf_extract.models.Removal] = []
	pdf_extract.page_cleanup.remove_running_heads(metadata_free, removals, defaults)
	assert all(page.text.startswith("Repeated Heading") for page in metadata_free)
	assert removals == []

	lines = ["Table of Contents", "Chapter 2", "1. Introduction", "2. Methods"]
	pages: list[pdf_extract.models.PageResult] = []
	for page_number in range(4):
		provenance = [
			pdf_extract.models.PageLineProvenance(line, line_number, "raw_text", bbox=(0.1, 0.25 + 0.08 * line_number, 0.8, 0.28 + 0.08 * line_number), font_size=12)
			for line_number, line in enumerate(lines)
		]
		pages.append(pdf_extract.models.PageResult(page_number, "\n".join(lines), "raw_text", 10, 0, provenance))
	removals = []
	pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)
	assert removals == []
	assert all(page.text == "\n".join(lines) for page in pages)

	heading = "Words to Know"
	heading_pages: list[pdf_extract.models.PageResult] = []
	for page_number in range(5):
		if page_number == 0:
			text = "==> picture [100 x 80] intentionally omitted <==\n" + heading + "\nGlossary definitions follow."
			provenance = [
				pdf_extract.models.PageLineProvenance("==> picture [100 x 80] intentionally omitted <==", 0, "raw_text", bbox=(0.1, 0.08, 0.4, 0.2)),
				pdf_extract.models.PageLineProvenance(heading, 1, "raw_text", bbox=(0.1, 0.24, 0.7, 0.29), font_size=22),
				pdf_extract.models.PageLineProvenance("Glossary definitions follow.", 2, "raw_text", bbox=(0.1, 0.34, 0.8, 0.37), font_size=11),
			]
		else:
			text = heading + "\nGlossary entry continues."
			provenance = [
				pdf_extract.models.PageLineProvenance(heading, 0, "raw_text", bbox=(0.1, 0.06, 0.6, 0.08), font_size=9),
				pdf_extract.models.PageLineProvenance("Glossary entry continues.", 1, "raw_text", bbox=(0.1, 0.105, 0.8, 0.125), font_size=11),
			]
		heading_pages.append(pdf_extract.models.PageResult(page_number, text, "raw_text", 10, 0, provenance))
	removals = []
	pdf_extract.page_cleanup.remove_running_heads(heading_pages, removals, defaults)
	assert heading in heading_pages[0].text
	assert len(removals) == 4


#============================================
def test_running_heads_preserve_line_records_through_edge_number_removal() -> None:
	"""Page number deletion keeps exact line records paired with surviving text."""
	page = pdf_extract.models.PageResult(
		page_number=0,
		text="42\n\nRunning Header\n\nBody text",
		source="raw_text",
		embedded_words=5,
		ocr_words=0,
		line_provenance=[
			pdf_extract.models.PageLineProvenance("42", 0, "raw_text", bbox=(0.4, 0.96, 0.5, 0.98)),
			pdf_extract.models.PageLineProvenance("", 1, "raw_text"),
			pdf_extract.models.PageLineProvenance("Running Header", 2, "raw_text", bbox=(0.1, 0.05, 0.5, 0.07)),
			pdf_extract.models.PageLineProvenance("", 3, "raw_text"),
			pdf_extract.models.PageLineProvenance("Body text", 4, "raw_text", bbox=(0.1, 0.2, 0.5, 0.22)),
		],
	)
	removals: list[pdf_extract.models.Removal] = []
	pdf_extract.page_cleanup.remove_edge_page_numbers([page], removals)
	assert page.text == "Running Header\n\nBody text"
	assert [record.text for record in page.line_provenance] == page.text.splitlines()
	assert [record.line_id for record in page.line_provenance] == [2, 3, 4]
	assert removals[0].source_line_id == 0
	assert removals[0].source_bbox == (0.4, 0.96, 0.5, 0.98)


#============================================
def test_page_number_cleanup_preserves_controls_and_valid_number_provenance() -> None:
	"""Only ASCII-space layout surrounds bare numbers; decoded controls remain content."""
	for control in ("\t", "\r", "\v", "\f"):
		for text, lines in (
			(f"{control}23\nBody", [f"{control}23", "Body"]),
			(f"23{control}\nBody", [f"23{control}", "Body"]),
			(f"{control}\n23\nBody", [control, "23", "Body"]),
			(f"Body\n23\n{control}", ["Body", "23", control]),
		):
			provenance = [
				pdf_extract.models.PageLineProvenance(line, index + 10, "raw_text")
				for index, line in enumerate(lines)
			]
			page = pdf_extract.models.PageResult(0, text, "raw_text", 2, 0, provenance)
			removals: list[pdf_extract.models.Removal] = []

			pdf_extract.page_cleanup.remove_edge_page_numbers([page], removals)

			assert page.text == text
			assert page.line_provenance == provenance
			assert removals == []

	page = pdf_extract.models.PageResult(
		0,
		" \n 23 \nBody\n ix \n ",
		"raw_text",
		2,
		0,
		[
			pdf_extract.models.PageLineProvenance(
				" ", 10, "raw_text",
			),
			pdf_extract.models.PageLineProvenance(
				" 23 ", 11, "raw_text", bbox=(0.4, 0.96, 0.5, 0.98), font_size=9,
			),
			pdf_extract.models.PageLineProvenance("Body", 12, "raw_text"),
			pdf_extract.models.PageLineProvenance(
				" ix ", 13, "raw_text", bbox=(0.4, 0.02, 0.5, 0.04), font_size=9,
			),
			pdf_extract.models.PageLineProvenance(" ", 14, "raw_text"),
		],
	)
	removals = []

	pdf_extract.page_cleanup.remove_edge_page_numbers([page], removals)

	assert page.text == "Body"
	assert [record.line_id for record in page.line_provenance] == [12]
	assert [removal.text for removal in removals] == ["23", "ix"]
	assert [removal.source_line_id for removal in removals] == [11, 13]
	assert [removal.source_bbox for removal in removals] == [
		(0.4, 0.96, 0.5, 0.98), (0.4, 0.02, 0.5, 0.04),
	]
	assert [removal.source_font_size for removal in removals] == [9, 9]
	page_without_provenance = pdf_extract.models.PageResult(
		0, "23\nBody", "raw_text", 2, 0,
	)
	removals = []

	pdf_extract.page_cleanup.remove_edge_page_numbers([page_without_provenance], removals)

	assert page_without_provenance.text == "Body"
	assert removals[0].text == "23"
	assert removals[0].source_line_id is None


#============================================
def test_page_number_cleanup_discards_malformed_provenance_without_mutating_page(
	) -> None:
	"""Malformed records are cleared while original text, including page numbers, stays intact."""
	text = "23\nBody"
	wrong_records = [
		pdf_extract.models.PageLineProvenance("Wrong", 1, "raw_text"),
		pdf_extract.models.PageLineProvenance("Body", 2, "raw_text"),
	]
	short_records = [pdf_extract.models.PageLineProvenance("23", 1, "raw_text")]
	long_records = [
		pdf_extract.models.PageLineProvenance("23", 1, "raw_text"),
		pdf_extract.models.PageLineProvenance("Body", 2, "raw_text"),
		pdf_extract.models.PageLineProvenance("Extra", 3, "raw_text"),
	]
	for malformed_records in (wrong_records, short_records, long_records):
		page = pdf_extract.models.PageResult(
			0, text, "raw_text", 2, 0, malformed_records.copy(),
		)
		removals: list[pdf_extract.models.Removal] = []

		pdf_extract.page_cleanup.remove_edge_page_numbers([page], removals)

		assert page.text == text
		assert page.line_provenance is None
		assert removals == []


#============================================
def test_convert_pages_skips_page_number_cleanup_for_malformed_provenance(
		tmp_path: pathlib.Path,
	) -> None:
	"""Page-number cleanup preserves text when conversion disables running-head cleanup."""
	pdf_path = tmp_path / "malformed-page-number-provenance.pdf"
	document = pymupdf.open()
	document.new_page()
	document.set_metadata({"title": "Malformed Provenance", "author": "A. Teacher"})
	document.save(pdf_path)
	document.close()
	text = "23\nBody"
	page = pdf_extract.models.PageResult(
		0,
		text,
		"raw_text",
		2,
		0,
		[pdf_extract.models.PageLineProvenance("Wrong", 1, "raw_text")],
	)

	result = pdf_extract.cleanup.convert_pages(
		pdf_path, [page], "raw_text", False, True, False, False, {},
	)

	assert page.text == text
	assert page.line_provenance is None
	assert result.markdown_text.endswith("23\nBody\n")


#============================================
def test_picture_cleanup_does_not_treat_source_controls_as_page_furniture() -> None:
	"""Picture adjacency and text-boundary trimming preserve decoded source controls."""
	placeholder = "==> picture [1 x 1] intentionally omitted <=="
	pages = [
		pdf_extract.models.PageResult(
			0, f"Body\n\t23\n{placeholder}\nTail", "raw_text", 3, 0,
		),
		pdf_extract.models.PageResult(
			1, f"Body\n23\n\v\n{placeholder}\nTail", "raw_text", 3, 0,
		),
		pdf_extract.models.PageResult(
			2,
			"Before\t------ Start of picture text ------hidden"
			"------ End of picture text ------\vAfter",
			"raw_text",
			3,
			0,
		),
		pdf_extract.models.PageResult(
			3, f"Body\n 23 \n{placeholder}\nTail", "raw_text", 3, 0,
		),
	]
	removals: list[pdf_extract.models.Removal] = []

	pdf_extract.page_cleanup.remove_picture_blocks(pages, removals)

	assert "\t23" in pages[0].text
	assert "23\n\v" in pages[1].text
	assert pages[2].text == "Before\t\vAfter"
	assert "23" not in pages[3].text
	assert [removal.pass_name for removal in removals] == [
		"images", "images", "images", "images", "page_number",
	]


#============================================
def test_picture_cleanup_declines_control_bearing_marker_layout() -> None:
	"""Picture marker recognition accepts ASCII spaces and preserves source controls."""
	placeholder = "==> picture [1 x 1] intentionally omitted <=="
	start = "------ Start of picture text ------"
	end = "------ End of picture text ------"
	pages: list[pdf_extract.models.PageResult] = []
	for control in ("\t", "\r", "\v", "\f"):
		cases = (
			control + placeholder,
			placeholder + control,
			placeholder.replace("picture", control + "picture"),
			"Before------" + control + "Start of picture text ------hidden" + end + "After",
			"Before" + start + "hidden------" + control + "End of picture text ------After",
		)
		pages.extend(
			pdf_extract.models.PageResult(index, text, "raw_text", 0, 0)
			for index, text in enumerate(cases, start=len(pages))
		)
	original_texts = [page.text for page in pages]
	removals: list[pdf_extract.models.Removal] = []

	pdf_extract.page_cleanup.remove_picture_blocks(pages, removals)

	assert [page.text for page in pages] == original_texts
	assert removals == []


#============================================
def test_picture_cleanup_stops_at_control_bearing_end_before_later_valid_span() -> None:
	"""An ambiguous end marker does not let a start consume a later picture span."""
	text = (
		"Before\n------ Start of picture text ------hidden\n"
		"------\tEnd of picture text ------\nBetween\n"
		"------ Start of picture text ------valid body\n"
		"------ End of picture text ------\nAfter"
	)
	page = pdf_extract.models.PageResult(0, text, "raw_text", 0, 0)
	removals: list[pdf_extract.models.Removal] = []

	pdf_extract.page_cleanup.remove_picture_blocks([page], removals)

	assert "------ Start of picture text ------hidden" in page.text
	assert "------\tEnd of picture text ------" in page.text
	assert "Between" in page.text
	assert "valid body" not in page.text
	assert "After" in page.text
	assert len(removals) == 1
	assert removals[0].text == (
		"------ Start of picture text ------valid body\n------ End of picture text ------"
	)


#============================================
def test_picture_control_marker_boundary_survives_pdf_conversion(tmp_path: pathlib.Path) -> None:
	"""Composed PDF cleanup keeps controls around and inside unproven picture markers."""
	placeholder = "==> picture [1 x 1] intentionally omitted <=="
	start = "------ Start of picture text ------"
	end = "------ End of picture text ------"
	lines = ["Body before"]
	for control in ("\t", "\r", "\v", "\f"):
		lines.extend((
			control + placeholder,
			placeholder + control,
			placeholder.replace("picture", control + "picture"),
			"Before------" + control + "Start of picture text ------hidden" + end + "After",
			"Before" + start + "hidden------" + control + "End of picture text ------After",
		))
	lines.extend((
		placeholder,
		"Outside\t" + start + "hidden" + end + "\vAfter",
		"Body after",
	))
	page_text = "\n".join(lines)
	pdf_path = tmp_path / "picture-marker-controls.pdf"
	document = pymupdf.open()
	document.new_page()
	document.set_metadata({"title": "Picture Marker Controls", "author": "A. Teacher"})
	document.save(pdf_path)
	document.close()
	page = pdf_extract.models.PageResult(0, page_text, "raw_text", 0, 0)

	result = pdf_extract.cleanup.convert_pages(
		pdf_path, [page], "raw_text", False, False, False, False, {},
	)

	for control in ("\t", "\r", "\v", "\f"):
		assert control + placeholder in result.markdown_text
		assert placeholder + control in result.markdown_text
		assert placeholder.replace("picture", control + "picture") in result.markdown_text
		assert "Before------" + control + "Start of picture text" in result.markdown_text
		assert "hidden------" + control + "End of picture text" in result.markdown_text
	assert "Outside\t\vAfter" in result.markdown_text
	assert all(removal.pass_name == "images" for removal in result.removals)
	assert len(result.removals) == 2


#============================================
def test_running_heads_invalidate_misaligned_line_provenance() -> None:
	"""Malformed source records are discarded without changing page text."""
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}
	text = "Running Header\nBody text"
	records = [
		pdf_extract.models.PageLineProvenance("Running Header", 1, "raw_text"),
		pdf_extract.models.PageLineProvenance("Body text", 2, "raw_text"),
	]
	misaligned_records = [
		records[:1],
		records + [pdf_extract.models.PageLineProvenance("Extra", 3, "raw_text")],
		[
			pdf_extract.models.PageLineProvenance("Wrong header", 1, "raw_text"),
			records[1],
		],
	]
	pages = [
		pdf_extract.models.PageResult(index, text, "raw_text", 5, 0, provenance)
		for index, provenance in enumerate(misaligned_records)
	]
	removals: list[pdf_extract.models.Removal] = []

	pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)

	assert all(page.text == text for page in pages)
	assert all(page.line_provenance is None for page in pages)
	assert removals == []


#============================================
def test_pdf_page_pipeline_preserves_control_glyphs_before_heading_synthesis() -> None:
	"""Page cleanup retains source glyphs and rejects CR-prefixed table rows as headings."""
	pages: list[pdf_extract.models.PageResult] = []
	for page_number, separator in enumerate(("\v", "\f", "\t", "\r")):
		row = f"{separator}20.0 U/L, Negative Test"
		pages.append(pdf_extract.models.PageResult(
			page_number,
			"Table heading\n" + row + "\nNext row",
			"raw_text",
			10,
			0,
			[
				pdf_extract.models.PageLineProvenance("Table heading", 100, "raw_text"),
				pdf_extract.models.PageLineProvenance(row, 101, "raw_text"),
				pdf_extract.models.PageLineProvenance("Next row", 102, "raw_text"),
			],
		))
	removals: list[pdf_extract.models.Removal] = []
	defaults: dict[str, int | float] = {
		"min_recurrence": 3,
		"edge_distance": 2,
		"edge_fraction": 0.70,
		"max_length": 90,
	}

	pdf_extract.page_cleanup.remove_running_heads(pages, removals, defaults)
	pdf_extract.page_cleanup.remove_picture_blocks(pages, removals)
	pdf_extract.page_cleanup.remove_edge_page_numbers(pages, removals)
	synthesized = pdf_extract.page_cleanup.synthesize_numbered_headings(pages)

	assert synthesized == []
	for page_number, separator in enumerate(("\v", "\f", "\t", "\r")):
		assert pages[page_number].text == f"Table heading\n{separator}20.0 U/L, Negative Test\nNext row"
		assert [record.line_id for record in pages[page_number].line_provenance] == [100, 101, 102]
		assert pages[page_number].line_provenance[1].text.startswith(separator)


#============================================
def test_pdf_text_boundaries_preserve_source_controls_and_normalize_layout() -> None:
	"""LF and ordinary spaces define layout while source control glyphs remain content."""
	controls = "\t\r\v\f"
	page_text = f"{controls}Heading  \n\n\tBody line  \n\n\v\n\nTail\t"
	page = pdf_extract.text.normalize_page_text(page_text)
	blocks = pdf_extract.text.split_blocks(page)
	provenance_text, records = pdf_extract.models.normalize_line_provenance([
		pdf_extract.models.PageLineProvenance("\tHeading  ", 11, "raw_text"),
		pdf_extract.models.PageLineProvenance("\r\v\f", 12, "raw_text"),
	])

	assert page == f"{controls}Heading\n\n\tBody line\n\n\v\n\nTail\t"
	assert blocks == [f"{controls}Heading", "\tBody line", "\v", "Tail\t"]
	assert provenance_text == "\tHeading\n\r\v\f"
	assert [record.line_id for record in records] == [11, 12]
	assert pdf_extract.text.split_blocks("Heading\n\nBody\n\n") == ["Heading", "Body"]
	assert pdf_extract.text.normalize_text("First\r\nSecond\rThird") == "First\nSecond\nThird"
	first_page = pdf_extract.models.PageResult(0, "\t\r\v\fFirst", "raw_text", 1, 0)
	last_page = pdf_extract.models.PageResult(1, "Last\t\r\v\f", "raw_text", 1, 0)
	flattened, seams_seen, seams_joined = pdf_extract.text.flatten_pages(
		[first_page, last_page], False,
	)
	assert flattened == "\t\r\v\fFirst\n\nLast\t\r\v\f\n"
	assert (seams_seen, seams_joined) == (1, 0)
	control_only = pdf_extract.models.PageResult(0, controls, "raw_text", 0, 0)
	assert pdf_extract.text.flatten_pages([control_only], False) == (controls + "\n", 0, 0)
	assert pdf_extract.text.flatten_pages([], False) == ("\n", 0, 0)
	assert pdf_extract.text.flatten_pages(
		[
			pdf_extract.models.PageResult(0, "A phrase ends", "raw_text", 3, 0),
			pdf_extract.models.PageResult(1, "across the page boundary.", "raw_text", 4, 0),
		],
		True,
	) == ("A phrase ends across the page boundary.\n", 1, 1)


#============================================
def test_pdf_conversion_and_written_output_preserve_boundary_controls(
		tmp_path: pathlib.Path,
	) -> None:
	"""PDF conversion and UTF-8 output retain controls through final H1 demotion."""
	controls = "\t\r\v\f"
	pdf_path = tmp_path / "boundary-controls.pdf"
	document = pymupdf.open()
	document.new_page()
	document.set_metadata({"title": "Boundary Controls", "author": "A. Teacher"})
	document.save(pdf_path)
	document.close()
	pages = [pdf_extract.models.PageResult(
		0, f"{controls}\n\n# Source Heading\n\nBody\n\nTail{controls}", "raw_text", 0, 0,
	)]
	result = pdf_extract.cleanup.convert_pages(
		pdf_path, pages, "raw_text", False, False, False, False, {},
	)
	output_path = tmp_path / "boundary-controls.md"
	output_path.write_text(result.markdown_text, encoding="utf-8")

	assert result.markdown_text.startswith('---\ntitle: "Boundary Controls"')
	assert f"{controls}\n\n## Source Heading\n\nBody\n\nTail{controls}\n" in result.markdown_text
	assert output_path.read_bytes() == result.markdown_text.encode("utf-8")
	control_page = pdf_extract.models.PageResult(0, controls, "raw_text", 0, 0)
	control_result = pdf_extract.cleanup.convert_pages(
		pdf_path, [control_page], "raw_text", False, False, False, False, {},
	)
	assert control_result.markdown_text.endswith(controls + "\n")
	control_output_path = tmp_path / "control-only.md"
	control_output_path.write_text(control_result.markdown_text, encoding="utf-8")
	assert control_output_path.read_bytes().endswith(controls.encode("utf-8") + b"\n")
	empty_page = pdf_extract.models.PageResult(0, " \n\n ", "raw_text", 0, 0)
	empty_result = pdf_extract.cleanup.convert_pages(
		pdf_path, [empty_page], "raw_text", False, False, False, False, {},
	)
	assert empty_result.markdown_text.endswith("\n")
	assert pdf_extract.text.flatten_pages(
		[
			pdf_extract.models.PageResult(0, "Open prose", "raw_text", 2, 0),
			pdf_extract.models.PageResult(1, "continues here.", "raw_text", 3, 0),
		],
		True,
	) == ("Open prose continues here.\n", 1, 1)
