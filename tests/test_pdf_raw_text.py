"""Behavior checks for PDF text-layer extraction."""

import pathlib

import pymupdf

import cleanup.layout
import pdf_extract.models
import pdf_extract.page_cleanup
import pdf_extract.raw_text


#============================================
def test_raw_text_preserves_explicit_superscript_and_ordinary_layout(tmp_path: pathlib.Path) -> None:
	"""Raised spans gain ASCII exponent markup while ordinary text and lines remain readable."""
	pdf_path = tmp_path / "superscript.pdf"
	document = pymupdf.open()
	page = document.new_page()
	page.insert_text((72, 100), "Ordinary prose 10 ")
	raised_x = 72 + pymupdf.get_text_length("Ordinary prose 10 ")
	page.insert_text((raised_x, 97), "9")
	citation_x = raised_x + pymupdf.get_text_length("9")
	page.insert_text((citation_x, 100), " citation 7")
	page.insert_text((72, 130), "Next line has spaced text")
	document.save(pdf_path)
	document.close()

	results = pdf_extract.raw_text.extract_raw_text(pdf_path, None)

	assert len(results) == 1
	assert results[0].text == "Ordinary prose 10 ^{9} citation 7\n\nNext line has spaced text"


#============================================
def test_raw_text_recovers_geometric_word_gap_without_splitting_styled_word(
		tmp_path: pathlib.Path,
	) -> None:
	"""A missing PDF space is restored while touching glyphs across font spans remain joined."""
	pdf_path = tmp_path / "geometric-word-gap.pdf"
	document = pymupdf.open()
	page = document.new_page()
	page.insert_text((72, 100), "processes,mimicking", fontsize=10, fontname="tiro")
	content_xref = page.get_contents()[0]
	content = document.xref_stream(content_xref)
	joined_hex = "processes,mimicking".encode("ascii").hex().encode("ascii")
	split_hex = (
			b"processes,".hex().encode("ascii")
			+ b"> -149 <"
			+ b"mimicking".hex().encode("ascii")
		)
	assert b"<" + joined_hex + b">" in content
	document.update_stream(content_xref, content.replace(b"<" + joined_hex + b">", b"<" + split_hex + b">", 1))
	page.insert_text((72, 130), "gene", fontsize=10, fontname="tiro")
	styled_start = 72 + pymupdf.get_text_length("gene", fontname="tiro", fontsize=10)
	page.insert_text((styled_start, 130), "alogy", fontsize=10, fontname="tiit")
	page.insert_text((72, 160), "AVATARoffice x=2", fontsize=10, fontname="tiro")
	document.save(pdf_path)
	document.close()

	results = pdf_extract.raw_text.extract_raw_text(pdf_path, None)

	assert "processes, mimicking" in results[0].text
	assert "genealogy" in results[0].text
	assert "gene alogy" not in results[0].text
	assert "AVATARoffice x=2" in results[0].text


#============================================
def test_raw_text_preserves_block_boundary_for_cleaner_reflow(tmp_path: pathlib.Path) -> None:
	"""Separate PDF blocks survive reflow while wrapped lines within a block join."""
	pdf_path = tmp_path / "block-boundaries.pdf"
	document = pymupdf.open()
	page = document.new_page()
	page.insert_text((72, 100), "Abstract")
	page.insert_textbox(
		pymupdf.Rect(72, 120, 400, 170),
		"Wrapped prose starts\nand continues within one text block.",
	)
	document.save(pdf_path)
	document.close()

	results = pdf_extract.raw_text.extract_raw_text(pdf_path, None)
	cleaned = cleanup.layout.reflow(results[0].text)

	assert results[0].text == "Abstract\n\nWrapped prose starts\nand continues within one text block."
	assert cleaned == "Abstract\n\nWrapped prose starts and continues within one text block.\n"
	assert results[0].source == "raw_text"


#============================================
def test_running_heads_keep_unique_numbered_openers_and_remove_repeated_labels() -> None:
	"""Distinct chapter and appendix labels survive while recurrent labels are removed."""
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
