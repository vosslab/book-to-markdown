#!/usr/bin/env python3
"""OCR a two-page-spread PDF into book-page-ordered text via half-page OCR."""

import argparse
import os
import pathlib

import pdf_extract.cleanup
import pdf_extract.spread_ocr


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse command-line arguments for spread-scan OCR."""
	parser = argparse.ArgumentParser(description="OCR a two-page-spread PDF into book-page-ordered text")
	parser.add_argument("pdf", help="Input PDF file (landscape two-page spreads)")
	parser.add_argument("output", help="Output text path (PAGE-marker separated)")
	parser.add_argument("--dpi", type=int, default=200, help="Render resolution for OCR (default 200)")
	parser.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 1), help="Parallel OCR workers (default 6)")
	parser.add_argument("--pages", help="Zero-based PDF page subset, such as 0-5 or 0,5,10 (default: all)")
	parser.add_argument("--tesseract", default="tesseract", help="Tesseract binary path (default: tesseract on PATH)")
	args = parser.parse_args()
	return args


#============================================
def main() -> None:
	"""Convert one spread-scan PDF via half-page OCR into book-page order."""
	args = parse_args()
	input_path = pathlib.Path(args.pdf)
	output_path = pathlib.Path(args.output)
	pages = pdf_extract.cleanup.parse_pages(args.pages)
	pdf_extract.spread_ocr.extract_spread_halves(
		input_path, output_path, args.dpi, args.workers, args.tesseract, pages)


#============================================
if __name__ == "__main__":
	main()
