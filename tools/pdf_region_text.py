#!/usr/bin/env python3
"""Export positioned PDF words intersecting an explicit page rectangle."""

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import stat
import sys
from collections.abc import Sequence

import pymupdf


def parse_args() -> argparse.Namespace:
	"""Parse exact source, page, rectangle, stage, and output arguments."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("-s", "--source", dest="source_pdf", required=True)
	parser.add_argument("-p", "--page", dest="page_number", required=True, type=int)
	parser.add_argument("-r", "--rectangle", dest="rectangle", required=True, nargs=4, type=float,
		help="x0 y0 x1 y1 in unrotated MediaBox-relative top-left PDF points")
	parser.add_argument("-d", "--stage", dest="stage_directory", required=True)
	parser.add_argument("-o", "--output", dest="output_name", required=True,
		help="new visible NAME.json leaf inside the existing stage directory")
	args = parser.parse_args()
	return args


def reject_symlink_components(path: pathlib.Path) -> pathlib.Path:
	"""Return an absolute path after refusing symlinks in every component."""
	absolute = path.absolute()
	current = pathlib.Path(absolute.anchor)
	for component in absolute.parts[1:]:
		current = current / component
		if current.is_symlink():
			raise ValueError(f"symlink path component is not allowed: {current}")
	return absolute


def read_source(source_path: pathlib.Path) -> tuple[bytes, str]:
	"""Read a regular PDF without following a source-file symlink."""
	absolute = reject_symlink_components(source_path)
	info = absolute.lstat()
	if not stat.S_ISREG(info.st_mode) or absolute.suffix.lower() != ".pdf":
		raise ValueError("source must be an existing regular PDF file")
	file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
	file_descriptor = os.open(absolute, file_flags)
	with os.fdopen(file_descriptor, "rb") as source_file:
		pdf_bytes = source_file.read()
	source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
	return pdf_bytes, source_sha256


def validate_rectangle(values: Sequence[float]) -> tuple[float, float, float, float]:
	"""Validate a finite, non-empty, non-negative rectangle."""
	if len(values) != 4 or not all(math.isfinite(value) for value in values):
		raise ValueError("rectangle requires four finite coordinates")
	x0, y0, x1, y1 = values
	if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
		raise ValueError("rectangle must have non-negative origin and positive width and height")
	return x0, y0, x1, y1


def intersects(box: Sequence[float], rectangle: Sequence[float]) -> bool:
	"""Return whether two boxes overlap with positive area."""
	x0, y0, x1, y1 = box
	rx0, ry0, rx1, ry1 = rectangle
	return x0 < rx1 and x1 > rx0 and y0 < ry1 and y1 > ry0


def contained(box: Sequence[float], rectangle: Sequence[float]) -> bool:
	"""Return whether a word box lies wholly inside the requested rectangle."""
	x0, y0, x1, y1 = box
	rx0, ry0, rx1, ry1 = rectangle
	return x0 >= rx0 and y0 >= ry0 and x1 <= rx1 and y1 <= ry1


def box_values(box: Sequence[float]) -> list[float]:
	"""Return a four-number box without rounding source coordinates."""
	values = [float(value) for value in box]
	return values


def merge_bounds(boxes: list[list[float]]) -> list[float] | None:
	"""Return the encompassing bounds for observed words, or None."""
	if not boxes:
		return None
	x0 = min(box[0] for box in boxes)
	y0 = min(box[1] for box in boxes)
	x1 = max(box[2] for box in boxes)
	y1 = max(box[3] for box in boxes)
	bounds = [x0, y0, x1, y1]
	return bounds


def build_region_report(
	document: pymupdf.Document,
	page_number: int,
	rectangle: tuple[float, float, float, float],
	source_sha256: str,
	source_path: str,
) -> dict[str, object]:
	"""Extract contained and boundary-crossing words in extractor order."""
	if page_number < 1 or page_number > document.page_count:
		page_count = document.page_count
		raise ValueError(f"page must be between 1 and {page_count}")
	page = document[page_number - 1]
	media_box = box_values(page.mediabox)
	crop_box = box_values(page.cropbox)
	rotation = int(page.rotation)
	if media_box[0] != 0 or media_box[1] != 0:
		raise ValueError("non-zero MediaBox origins are unsupported; coordinates would be ambiguous")
	# PyMuPDF extraction is relative to the visible crop and applies page rotation.
	# In-memory normalization establishes full MediaBox, unrotated top-left points.
	page.set_rotation(0)
	page.set_cropbox(page.mediabox)
	page_bounds = (0.0, 0.0, float(page.rect.width), float(page.rect.height))
	if rectangle[2] > page_bounds[2] or rectangle[3] > page_bounds[3]:
		raise ValueError("rectangle extends beyond the original MediaBox")
	words = page.get_text("words", sort=False)
	contained_words = []
	crossing_words = []
	observed_boxes = []
	for word in words:
		box = box_values(word[:4])
		if contained(box, rectangle):
			contained_words.append({
				"text": word[4],
				"bbox": box,
				"block_id": int(word[5]),
				"line_id": int(word[6]),
				"word_id": int(word[7]),
			})
			observed_boxes.append(box)
		elif intersects(box, rectangle):
			crossing_words.append({
				"text": word[4],
				"bbox": box,
				"block_id": int(word[5]),
				"line_id": int(word[6]),
				"word_id": int(word[7]),
			})
			observed_boxes.append(box)
	report = {
		"evidence_type": "explicit_pdf_region_positioned_words",
	"source_path": source_path,
		"source_sha256": source_sha256,
		"page_number": page_number,
		"coordinate_frame": "unrotated original MediaBox-relative top-left PDF points",
		"requested_rectangle": list(rectangle),
		"original_geometry": {
			"mediabox": media_box,
			"cropbox": crop_box,
			"rotation_degrees": rotation,
		},
		"included_count": len(contained_words),
		"crossing_count": len(crossing_words),
		"observed_text_bounds": merge_bounds(observed_boxes),
		"included_words": contained_words,
		"crossing_words": crossing_words,
		"limitations": "Positioned text inspection only; no row grouping, correction, fidelity, or admission claim.",
	}
	return report


def extract_region(
	pdf_bytes: bytes,
	page_number: int,
	rectangle: tuple[float, float, float, float],
	source_sha256: str,
	source_path: str,
) -> dict[str, object]:
	"""Open exact source bytes and always close the parser document."""
	document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
	try:
		report = build_region_report(document, page_number, rectangle, source_sha256, source_path)
	finally:
		document.close()
	return report


def open_stage_directory(stage_path: pathlib.Path) -> int:
	"""Open an existing visible stage with no-follow directory traversal."""
	absolute = reject_symlink_components(stage_path)
	if any(part.startswith(".") for part in absolute.parts[1:]):
		raise ValueError("hidden stage path components are not allowed")
	if absolute.parent == absolute or absolute.name.startswith("."):
		raise ValueError("stage must be an existing visible title directory")
	directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
	directory_fd = os.open(absolute.anchor, directory_flags)
	try:
		for component in absolute.parts[1:]:
			next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
			os.close(directory_fd)
			directory_fd = next_fd
	except OSError:
		os.close(directory_fd)
		raise
	return directory_fd


def validate_output_name(output_name: str) -> None:
	"""Allow only a visible JSON leaf name."""
	if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.json", output_name):
		raise ValueError("output must be a visible NAME.json leaf without traversal")
	if output_name.startswith(".") or output_name in (".", ".."):
		raise ValueError("hidden output names are not allowed")


def remove_created_report(stage_fd: int, output_name: str, created_identity: tuple[int, int]) -> None:
	"""Remove the output leaf only while it still names the inode created here."""
	try:
		current_info = os.stat(output_name, dir_fd=stage_fd, follow_symlinks=False)
	except FileNotFoundError:
		return
	if (current_info.st_dev, current_info.st_ino) == created_identity:
		os.unlink(output_name, dir_fd=stage_fd)


def write_new_report(stage_fd: int, output_name: str, report: dict[str, object]) -> None:
	"""Create JSON output exclusively within an already-open stage directory."""
	validate_output_name(output_name)
	# ASVS V5.3.2: serialize before creating an exclusive leaf in the trusted stage.
	serialized = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
	file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
	file_descriptor = os.open(output_name, file_flags, 0o600, dir_fd=stage_fd)
	created_info = os.fstat(file_descriptor)
	created_identity = (created_info.st_dev, created_info.st_ino)
	try:
		with os.fdopen(file_descriptor, "w", encoding="ascii", newline="\n") as output_file:
			output_file.write(serialized)
			output_file.flush()
	except BaseException:
		remove_created_report(stage_fd, output_name, created_identity)
		raise


def main() -> None:
	"""Validate inputs and write one new inspection report."""
	args = parse_args()
	stage_fd = None
	try:
		# ASVS V2.2.1: enforce the CLI's page, rectangle, path, and output expectations.
		rectangle = validate_rectangle(args.rectangle)
		validate_output_name(args.output_name)
		stage_fd = open_stage_directory(pathlib.Path(args.stage_directory))
		pdf_bytes, source_sha256 = read_source(pathlib.Path(args.source_pdf))
		source_path = reject_symlink_components(pathlib.Path(args.source_pdf))
		report = extract_region(pdf_bytes, args.page_number, rectangle, source_sha256, str(source_path))
		write_new_report(stage_fd, args.output_name, report)
	except (OSError, ValueError, RuntimeError) as error:
		print(f"pdf_region_text: {error}", file=sys.stderr)
		raise SystemExit(2)
	finally:
		if stage_fd is not None:
			os.close(stage_fd)


if __name__ == "__main__":
	main()
