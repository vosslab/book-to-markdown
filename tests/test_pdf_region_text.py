"""Tests for explicit positioned-word PDF region inspection."""

import hashlib
import json
import os
import pathlib

import pymupdf
import pytest

import tools.pdf_region_text as pdf_region_text


def make_pdf(path: pathlib.Path) -> bytes:
	"""Create a small source PDF with wrapped words and mixed page geometry."""
	document = pymupdf.open()
	page = document.new_page(width=320, height=420)
	page.insert_text((30, 55), "Wrapped source", fontsize=12)
	page.insert_text((30, 75), "words stay ordered", fontsize=12)
	page.insert_text((190, 120), "Adjacent", fontsize=12)
	page.set_cropbox(pymupdf.Rect(20, 20, 280, 380))
	page.set_rotation(90)
	second_page = document.new_page(width=500, height=300)
	second_page.insert_text((30, 70), "Wide page", fontsize=12)
	document.save(path)
	document.close()
	return path.read_bytes()


def test_rectangle_edges_include_contained_words_and_report_crossings() -> None:
	"""Inclusive perimeter containment and partial overlap are explicit."""
	region = (10.0, 10.0, 20.0, 20.0)
	assert pdf_region_text.contained((10, 10, 20, 20), region)
	assert pdf_region_text.contained((11, 11, 19, 19), region)
	assert not pdf_region_text.contained((9, 11, 12, 12), region)
	assert pdf_region_text.intersects((9, 11, 12, 12), region)
	assert not pdf_region_text.intersects((0, 0, 10, 20), region)


def test_crossing_word_is_reported_separately_from_included_words(tmp_path: pathlib.Path) -> None:
	"""A word cut by the rectangle edge never appears in the included list."""
	document = pymupdf.open()
	page = document.new_page(width=300, height=200)
	page.insert_text((30, 70), "boundaryword", fontsize=12)
	pdf_path = tmp_path / "crossing.pdf"
	document.save(pdf_path)
	document.close()
	pdf_bytes = pdf_path.read_bytes()
	opened = pymupdf.open(stream=pdf_bytes, filetype="pdf")
	word = opened[0].get_text("words", sort=False)[0]
	opened.close()
	rectangle = (word[0], word[1], (word[0] + word[2]) / 2, word[3])
	report = pdf_region_text.extract_region(
		pdf_bytes, 1, rectangle, hashlib.sha256(pdf_bytes).hexdigest(), str(pdf_path)
	)
	assert report["included_words"] == []
	assert [item["text"] for item in report["crossing_words"]] == ["boundaryword"]


def test_original_order_wrapped_words_and_original_geometry_are_reported(
	tmp_path: pathlib.Path,
) -> None:
	"""The output preserves extractor order and records original page geometry."""
	source = tmp_path / "source.pdf"
	pdf_bytes = make_pdf(source)
	opened = pymupdf.open(stream=pdf_bytes, filetype="pdf")
	page = opened[0]
	page.set_rotation(0)
	page.set_cropbox(page.mediabox)
	page_words = page.get_text("words", sort=False)
	opened.close()
	first_word = page_words[0]
	last_word = page_words[4]
	rectangle = (first_word[0] - 1, first_word[1] - 1, last_word[2] + 1, last_word[3] + 30)
	sha = hashlib.sha256(pdf_bytes).hexdigest()
	report = pdf_region_text.extract_region(pdf_bytes, 1, rectangle, sha, str(source))
	assert [word["text"] for word in report["included_words"]] == [
		"Wrapped", "source", "words", "stay", "ordered"
	]
	assert [word["word_id"] for word in report["included_words"]] == [
		int(word[7]) for word in page_words[:5]
	]
	assert report["source_sha256"] == sha
	assert report["original_geometry"]["rotation_degrees"] == 90
	assert report["original_geometry"]["mediabox"] == [0.0, 0.0, 320.0, 420.0]
	assert report["original_geometry"]["cropbox"] == [20.0, 20.0, 280.0, 380.0]
	assert report["coordinate_frame"] == "unrotated original MediaBox-relative top-left PDF points"
	assert source.read_bytes() == pdf_bytes


def test_wide_page_preserves_media_geometry_and_unicode_text(tmp_path: pathlib.Path) -> None:
	"""Mixed page widths and source Unicode remain inspectable without transliteration."""
	document = pymupdf.open()
	page = document.new_page(width=500, height=300)
	page.insert_text((35, 70), "caf\u00e9", fontsize=12)
	pdf_path = tmp_path / "wide.pdf"
	document.save(pdf_path)
	document.close()
	pdf_bytes = pdf_path.read_bytes()
	opened = pymupdf.open(stream=pdf_bytes, filetype="pdf")
	word = opened[0].get_text("words", sort=False)[0]
	opened.close()
	rectangle = (word[0] - 1, word[1] - 1, word[2] + 1, word[3] + 1)
	report = pdf_region_text.extract_region(
		pdf_bytes, 1, rectangle, hashlib.sha256(pdf_bytes).hexdigest(), str(pdf_path)
	)
	assert report["original_geometry"]["mediabox"] == [0.0, 0.0, 500.0, 300.0]
	assert report["included_words"][0]["text"] == "caf\u00e9"
	assert "\\u00e9" in json.dumps(report, ensure_ascii=True)


@pytest.mark.parametrize(
	"coordinates",
	[
		(0, 0, 0, 1),
		(2, 3, 1, 4),
		(-1, 0, 1, 2),
		(float("nan"), 0, 1, 2),
		(0, 0, float("inf"), 2),
	],
)
def test_invalid_rectangles_are_rejected(coordinates: tuple[float, ...]) -> None:
	"""Rectangles must be finite, non-negative, and have positive dimensions."""
	with pytest.raises(ValueError):
		pdf_region_text.validate_rectangle(list(coordinates))


def test_invalid_page_is_rejected(tmp_path: pathlib.Path) -> None:
	"""Page numbers are one-based and constrained by the source document."""
	source = tmp_path / "one.pdf"
	pdf_bytes = make_pdf(source)
	with pytest.raises(ValueError, match="page must be"):
		pdf_region_text.extract_region(pdf_bytes, 0, (0, 0, 10, 10), "0" * 64, str(source))
	with pytest.raises(ValueError, match="page must be"):
		pdf_region_text.extract_region(pdf_bytes, 3, (0, 0, 10, 10), "0" * 64, str(source))


def test_out_of_page_rectangle_and_nonzero_media_origin_are_rejected(
	tmp_path: pathlib.Path,
) -> None:
	"""Unsupported geometry and rectangles outside MediaBox fail closed."""
	document = pymupdf.open()
	document.new_page(width=200, height=100)
	path = tmp_path / "geometry.pdf"
	document.save(path)
	document.close()
	pdf_bytes = path.read_bytes()
	with pytest.raises(ValueError, match="beyond the original MediaBox"):
		pdf_region_text.extract_region(pdf_bytes, 1, (0, 0, 201, 10), "0" * 64, str(path))

	document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
	document[0].set_mediabox(pymupdf.Rect(-10, 0, 190, 100))
	nonzero_bytes = document.tobytes()
	document.close()
	with pytest.raises(ValueError, match="non-zero MediaBox origins"):
		pdf_region_text.extract_region(nonzero_bytes, 1, (0, 0, 10, 10), "0" * 64, str(path))


def test_output_creation_refuses_existing_and_dangling_symlink(tmp_path: pathlib.Path) -> None:
	"""Exclusive creation refuses both regular files and dangling links."""
	stage = tmp_path / "stage"
	stage.mkdir()
	stage_fd = pdf_region_text.open_stage_directory(stage)
	try:
		pdf_region_text.write_new_report(stage_fd, "report.json", {"ok": True})
		original_content = (stage / "report.json").read_text(encoding="ascii")
		with pytest.raises(FileExistsError):
			pdf_region_text.write_new_report(stage_fd, "report.json", {"ok": False})
		assert (stage / "report.json").read_text(encoding="ascii") == original_content
		(stage / "dangling.json").symlink_to(stage / "missing.json")
		with pytest.raises(FileExistsError):
			pdf_region_text.write_new_report(stage_fd, "dangling.json", {})
	finally:
		os.close(stage_fd)


def test_output_creation_fails_before_creation_on_serialization_error(
	tmp_path: pathlib.Path,
) -> None:
	"""Serialization errors happen before any output leaf is created."""
	stage = tmp_path / "stage"
	stage.mkdir()
	stage_fd = pdf_region_text.open_stage_directory(stage)
	try:
		with pytest.raises(TypeError):
			pdf_region_text.write_new_report(stage_fd, "partial.json", {"invalid": {1}})
		assert not (stage / "partial.json").exists()
	finally:
		os.close(stage_fd)


def test_output_creation_removes_partial_file_after_write_failure(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A write error closes and removes the incomplete output leaf."""
	stage = tmp_path / "stage"
	stage.mkdir()
	stage_fd = pdf_region_text.open_stage_directory(stage)
	original_fdopen = os.fdopen

	class FailingWriter:
		def __init__(self, wrapped: object) -> None:
			self.wrapped = wrapped

		def __enter__(self) -> "FailingWriter":
			return self

		def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
			self.wrapped.close()
			return False

		def write(self, value: str) -> None:
			self.wrapped.write(value[:1])
			raise OSError("simulated write failure")

		def flush(self) -> None:
			return self.wrapped.flush()

		def close(self) -> None:
			return self.wrapped.close()

	def open_failing_writer(*args: object, **kwargs: object) -> FailingWriter:
		return FailingWriter(original_fdopen(*args, **kwargs))

	monkeypatch.setattr(pdf_region_text.os, "fdopen", open_failing_writer)
	try:
		with pytest.raises(OSError, match="simulated write failure"):
			pdf_region_text.write_new_report(stage_fd, "partial.json", {"ok": True})
		assert not (stage / "partial.json").exists()
	finally:
		os.close(stage_fd)


def test_output_cleanup_preserves_a_different_inode(tmp_path: pathlib.Path) -> None:
	"""Cleanup leaves a different inode at the report name untouched."""
	stage = tmp_path / "stage"
	stage.mkdir()
	stage_fd = pdf_region_text.open_stage_directory(stage)
	try:
		foreign = stage / "report.json"
		foreign.write_text("keep", encoding="ascii")
		pdf_region_text.remove_created_report(stage_fd, "report.json", (0, 0))
		assert foreign.read_text(encoding="ascii") == "keep"
	finally:
		os.close(stage_fd)


def test_hidden_traversal_and_symlink_paths_are_rejected(tmp_path: pathlib.Path) -> None:
	"""Source and stage paths reject symlinks; output names reject traversal."""
	stage = tmp_path / "stage"
	stage.mkdir()
	for name in ("../escape.json", ".hidden.json", "nested/name.json", "bad.txt"):
		with pytest.raises(ValueError):
			pdf_region_text.validate_output_name(name)
	linked_stage = tmp_path / "linked"
	linked_stage.symlink_to(stage, target_is_directory=True)
	with pytest.raises(ValueError, match="symlink"):
		pdf_region_text.open_stage_directory(linked_stage)
	source = tmp_path / "source.pdf"
	make_pdf(source)
	linked_source = tmp_path / "linked.pdf"
	linked_source.symlink_to(source)
	with pytest.raises(ValueError, match="symlink"):
		pdf_region_text.read_source(linked_source)


def test_source_is_read_only_and_hash_is_bound_to_exact_bytes(tmp_path: pathlib.Path) -> None:
	"""Inspection hashes the exact bytes opened and leaves the source untouched."""
	source = tmp_path / "source.pdf"
	pdf_bytes = make_pdf(source)
	before = source.stat()
	read_bytes, digest = pdf_region_text.read_source(source)
	assert read_bytes == pdf_bytes
	assert digest == hashlib.sha256(pdf_bytes).hexdigest()
	assert source.stat().st_mtime_ns == before.st_mtime_ns
	assert source.read_bytes() == pdf_bytes
