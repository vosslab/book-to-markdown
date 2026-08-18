"""Half-page OCR extraction for two-page-spread PDF scans."""

import os
import pathlib
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed

import fitz


#============================================
def ocr_half(pdf_path: str, page_idx: int, side: str, dpi: int, tesseract: str) -> tuple[int, str, str]:
	"""Render one half of a PDF page and OCR it with Tesseract.

	Args:
		pdf_path: Path to the input PDF file.
		page_idx: Zero-based PDF page index.
		side: 'L' for the left half (odd book page) or 'R' for the right half.
		dpi: Render resolution for the half-page image.
		tesseract: Tesseract binary path.

	Returns:
		tuple[int, str, str]: (page_idx, side, OCR text).
	"""
	document = fitz.open(pdf_path)
	page = document[page_idx]
	width = page.rect.width
	if side == "L":
		clip = fitz.Rect(0, 0, width / 2, page.rect.height)
	else:
		clip = fitz.Rect(width / 2, 0, width, page.rect.height)
	pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False, clip=clip)
	png = os.path.join(tempfile.gettempdir(), f"half_{page_idx}_{side}_{os.getpid()}.png")
	pixmap.save(png)
	document.close()
	env = dict(os.environ)
	env["OMP_THREAD_LIMIT"] = "1"
	result = subprocess.run([tesseract, png, "stdout", "--psm", "4"], capture_output=True, text=True, env=env)
	os.unlink(png)
	return page_idx, side, result.stdout


#============================================
def extract_spread_halves(
	input_path: pathlib.Path,
	output_path: pathlib.Path,
	dpi: int,
	workers: int,
	tesseract: str,
	pages: list[int] | None = None,
) -> None:
	"""OCR every selected PDF page in left/right halves and write book-page order.

	Full-page OCR of a landscape spread scan interleaves the two book pages line
	by line. Splitting each PDF page into left/right halves and OCRing each half
	independently restores book-page order. The output separates book pages with
	`===== PAGE n =====` marker lines (1-based, left half = odd, right = even).
	OMP_THREAD_LIMIT is pinned to 1 per worker; without it, parallel tesseracts
	thrash the CPU (measured: 12/180 halves in 13 minutes vs ~2.4s per half
	with the limit).

	Args:
		input_path: Path to the input spread-scan PDF.
		output_path: Path to write the PAGE-marker-separated text.
		dpi: Render resolution for each half-page image.
		workers: Number of parallel OCR workers.
		tesseract: Tesseract binary path.
		pages: Zero-based PDF page indices, or None for every page.
	"""
	document = fitz.open(input_path)
	page_count = document.page_count
	document.close()
	selected = pages if pages is not None else list(range(page_count))
	jobs = [(i, "L") for i in selected] + [(i, "R") for i in selected]
	results: dict[tuple[int, str], str] = {}
	with ProcessPoolExecutor(max_workers=workers) as executor:
		futures = {
			executor.submit(ocr_half, str(input_path), i, side, dpi, tesseract): (i, side)
			for i, side in jobs
		}
		done = 0
		for future in as_completed(futures):
			page_idx, side, text = future.result()
			results[(page_idx, side)] = text
			done += 1
			if done % 20 == 0:
				print(f"done {done}/{len(jobs)}", flush=True)
	with open(output_path, "w", encoding="utf-8") as out_file:
		for i in range(page_count):
			for side in ("L", "R"):
				book = 2 * i + (1 if side == "L" else 2)
				out_file.write(f"===== PAGE {book} =====\n")
				out_file.write(results.get((i, side), ""))
				out_file.write("\n")
	print(f"WROTE {output_path}", flush=True)
