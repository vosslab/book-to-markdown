#!/usr/bin/env python3
"""Strip page-edge or column-rule pipe prefixes from OCR prose lines.

OCR of scanned books frequently emits a `|` (the page-edge or column rule)
at the start of prose lines. This tool removes those prefixes while leaving
real Markdown tables untouched: a contiguous pipe block that contains a
delimiter row such as `|---|` is a genuine table and is preserved. It never
overwrites its input; the default output is `<input>.pipefixed.md` for review
before acceptance.
"""

import argparse
import pathlib
import re


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse command-line arguments for pipe-artifact repair."""
	parser = argparse.ArgumentParser(description="Strip pipe prefixes from OCR prose while preserving tables")
	parser.add_argument("-i", "--input", required=True, help="Input Markdown file")
	parser.add_argument("-o", "--output", help="Output path; defaults beside input as <input>.pipefixed.md")
	args = parser.parse_args()
	return args


#============================================
def main() -> None:
	"""Repair one Markdown file's pipe-prefixed prose lines."""
	args = parse_args()
	input_path = pathlib.Path(args.input)
	output_path = pathlib.Path(args.output) if args.output else input_path.with_name(input_path.name + ".pipefixed.md")

	lines = input_path.read_text(encoding="utf-8").split("\n")

	delimiter_rows = {i for i, line in enumerate(lines) if re.match(r"^\|[\s:\-]+\|", line)}
	in_table = set()
	for i in delimiter_rows:
		start = i
		while start > 0 and lines[start - 1].startswith("|"):
			start -= 1
		end = i
		while end + 1 < len(lines) and lines[end + 1].startswith("|"):
			end += 1
		in_table.update(range(start, end + 1))

	stripped = 0
	dropped_numbers = 0
	fixed = []
	for i, line in enumerate(lines):
		if line.startswith("|") and i not in in_table:
			content = line[1:]
			if content.startswith(" "):
				content = content[1:]
			if re.match(r"^\d{1,4}$", content.strip()):
				dropped_numbers += 1
				fixed.append("")
			else:
				fixed.append(content)
				stripped += 1
		else:
			fixed.append(line)

	output_path.write_text("\n".join(fixed), encoding="utf-8")
	print(f"pipe prefixes stripped: {stripped}")
	print(f"bare page numbers dropped: {dropped_numbers}")
	print(f"table lines preserved: {len(in_table)}")
	print(f"remaining pipe lines: {sum(1 for line in fixed if line.startswith('|'))}")
	print(f"WROTE {output_path}")


#============================================
if __name__ == "__main__":
	main()
