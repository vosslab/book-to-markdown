"""Behavior checks for PDF text-layer extraction."""

import pathlib

import pymupdf
import pytest

import cleanup.layout
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
def test_raw_text_preserves_source_control_only_lines_and_geometry(
		tmp_path: pathlib.Path,
		monkeypatch: pytest.MonkeyPatch,
	) -> None:
	"""Native tab, CR, VT, and FF lines survive while empty and space-only layout is skipped."""
	controls = ("\t", "\r", "\v", "\f")
	line_texts = ("", "   ", *controls, "Ordinary text")
	lines = []
	for line_index, line_text in enumerate(line_texts):
		characters = [
			{
				"c": character,
				"bbox": (line_index * 10, 20, line_index * 10 + 2, 22),
			}
			for character in line_text
		]
		lines.append({
			"spans": [{
				"chars": characters,
				"bbox": (line_index * 10, 20, line_index * 10 + 2, 22),
				"size": 8,
				"font": "Helvetica",
				"flags": 0,
			}],
		})
	page_data = {"blocks": [{"type": 0, "lines": lines}]}

	class FakePage:
		rect = pymupdf.Rect(0, 0, 100, 100)
		rotation_matrix = pymupdf.Matrix(1, 0, 0, 1, 0, 0)

		def get_text(self, mode: str, flags: int | None = None) -> dict | list:
			return page_data if mode == "rawdict" else []

	class FakeDocument:
		page_count = 1

		def __getitem__(self, page_number: int) -> FakePage:
			return FakePage()

		def close(self) -> None:
			return None

	monkeypatch.setattr(pdf_extract.raw_text.pymupdf, "open", lambda _path: FakeDocument())

	results = pdf_extract.raw_text.extract_raw_text(tmp_path / "source.pdf", [0])
	page = results[0]
	control_records = [record for record in page.line_provenance if record.text in controls]

	assert page.text == "\n".join((*controls, "Ordinary text"))
	assert [record.text for record in control_records] == list(controls)
	assert [record.line_id for record in control_records] == [0, 1, 2, 3]
	assert all(record.bbox is not None for record in control_records)
	assert all(record.source == "raw_text" for record in control_records)
	assert len(page.line_provenance) == 5


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
	assert [record.text for record in results[0].line_provenance] == results[0].text.splitlines()
	assert all(record.bbox is not None for record in results[0].line_provenance if record.text)


#============================================
