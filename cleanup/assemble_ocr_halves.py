#!/usr/bin/env python3
"""Assemble half-page OCR output into clean, page-free Markdown.

Consumes the PAGE-marker-separated text written by
`extract/pdf_ocr_spread_halves.py` and produces one canonical Markdown file:
per-page gutter/noise cleanup, running-head and page-number stripping, chapter
detection from raw page heads, paragraph joining across page boundaries,
rebuilt front matter and Contents, and ASCII mapping.

Book-specific data (chapters and their normalized detection keys, running
heads, large-print title fragments, front-matter page mapping, intro markers)
comes from a JSON config file, so one engine serves any spread-scanned book:

    {
      "title": "Film Studies",
      "author": "Warren Buckland",
      "date": "1998",
      "source_pdf": "Film_Studies_Teach_Yourself_by_Warren_Buckland_z-lib.org.pdf",
      "blurb": "One-paragraph description placed under the title (optional).",
      "chapters": [
        {"title": "Introduction", "key": "TOSTUDYTHECINEMAWHATANABSURDIDEA"},
        {"title": "1 Film Aesthetics: Formalism and Realism", "key": "FILMAESTHETICSFORMALISMANDREALISM"}
      ],
      "running_heads": ["FILM STUDIES", "FILM AESTHETICS", "INDEX"],
      "title_fragments": ["FORMALISM AND", "REALISM"],
      "front_matter_pages": {"4": "## Dedication", "5": "## Acknowledgements"},
      "intro_markers": ["To study the cinema: what an absurd idea", "Christian Metz"]
    }

Chapter keys are the chapter titles normalized to uppercase with all
non-alphanumeric characters removed. `intro_markers` (optional) identifies the
page where the introduction body starts; front matter precedes it. A chapter
titled "Introduction" is anchored to that page.
"""

import argparse
import json
import pathlib
import re

NOISE_LINE = re.compile(
	r"^[\s\|\_\-~=.,:;'\"!?/\\()\[\]{}<>*#&%$@+^`°©\u00a0]+$"
)
DIGITS_ONLY = re.compile(r"^\d{1,4}$")
FIG_LABEL_RUN = re.compile(r"^(\d+\s+){2,}\d+\s*$")
TRAIL_JUNK = re.compile(r"[\s\|\_\-~=.,:;'\"»«*#&%$@+^`]+\s*$")
LEAD_JUNK = re.compile(r"^[\s\|\_\-~=.,:;»«*#&%$@+^`()\[\]\\/]+")

# 1-3 character OCR debris tokens that never carry prose meaning
JUNK_TOKENS = frozenset(
	"ES EES EE OS EO ED DY E S SS SCC CSC CS C D 0 00 OE SE SO O P PP L LL T TT A AA I II V VV X J F B H M N R W G K Q U Y Z".split()
)

ASCII_MAP = {
	"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
	"\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
	"\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",
	"\u00e9": "e", "\u00e8": "e", "\u00ea": "e", "\u00eb": "e",
	"\u00e0": "a", "\u00e2": "a", "\u00e4": "a", "\u00e5": "a",
	"\u00e7": "c", "\u00ee": "i", "\u00ef": "i", "\u00f4": "o",
	"\u00f6": "o", "\u00f9": "u", "\u00fb": "u", "\u00fc": "u",
	"\u00e1": "a", "\u00ed": "i", "\u00f3": "o", "\u00fa": "u",
	"\u00e6": "ae", "\u0153": "oe", "\u00df": "ss", "\u00c9": "E",
	"\u00c8": "E", "\u00c0": "A", "\u00c7": "C", "\u00c1": "A",
	"\u00d6": "O", "\u00dc": "U", "\u00c4": "A", "\u00c5": "A",
	"\u00fd": "y", "\u00a7": "&sect;", "\u00a9": "&copy;", "\u00b0": "&deg;",
	"\u00a5": "&yen;", "\u00bb": "", "\u00ab": "", "\u2022": "*",
	"\u2026": "...", "\u00b7": "|",
}
SENTENCE_END = (".", "!", "?", ":", ";", "\u201d", "\u2019", '"')


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse command-line arguments for half-OCR assembly."""
	parser = argparse.ArgumentParser(description="Assemble half-page OCR text into clean Markdown")
	parser.add_argument("-i", "--input", required=True, help="PAGE-marker-separated halves text from pdf_ocr_spread_halves.py")
	parser.add_argument("-o", "--output", required=True, help="Output Markdown path")
	parser.add_argument("-c", "--config", required=True, help="Book config JSON (chapters, running heads, front matter)")
	args = parser.parse_args()
	return args


#============================================
def norm(s: str) -> str:
	"""Uppercase a string and remove all non-alphanumeric characters."""
	return re.sub(r"[^A-Za-z0-9]", "", s.upper())


#============================================
def is_noise_line(line: str) -> bool:
	"""Return True for gutter noise, page numbers, figure label runs, and debris."""
	s = line.strip()
	if not s:
		return True
	if NOISE_LINE.match(s):
		return True
	if DIGITS_ONLY.match(s):
		return True
	if FIG_LABEL_RUN.match(s):
		return True
	if len(s) == 1:
		return True
	if len(s) <= 3 and s.upper() in JUNK_TOKENS:
		return True
	return False


#============================================
def clean_line(line: str) -> str:
	"""Strip leading/trailing gutter characters and collapse whitespace."""
	s = re.sub(r"^[\s\|\_\-~]+", "", line)
	s = re.sub(r"[\s\|\_\-~]+$", "", s)
	s = s.strip()
	s = re.sub(r"\s+", " ", s)
	return s


#============================================
def build_furniture_lead(running_heads: list[str]) -> re.Pattern[str]:
	"""Build the embedded page-furniture regex from the configured running heads.

	Matches a running head (optionally preceded by a page number and pipe, or
	followed by a page number) glued to the start of an OCR line, such as
	"2 FILM STUDIES ...", "INTRODUCTION 3 ...", or "144 | FILM STUDIES".
	"""
	alternatives = "|".join(
		re.escape(head).replace(r"\ ", r"\s*") for head in sorted(running_heads, key=len, reverse=True)
	)
	return re.compile(
		r"^(?:&?\s*)?(?:[\d\)(©|&y ]*\s*(?:\|\s*)?)?(?:"
		+ alternatives
		+ r")[,.:;]?\s*\d{0,3}\s*(?=[A-Za-z]|\s|$)"
	)


#============================================
def strip_furniture(s: str, furniture_lead: re.Pattern[str]) -> str:
	"""Remove an embedded running head and page number from the start of a line."""
	stripped = furniture_lead.sub("", s)
	if stripped != s:
		return stripped.strip()
	return s


#============================================
def looks_like_running_head(s: str, running_heads: list[str]) -> bool:
	"""Return True when a standalone line is a known running head."""
	up = s.upper().strip(" .,:;-_")
	return up in running_heads


#============================================
def is_title_fragment(s: str, title_fragments: list[str]) -> bool:
	"""Return True for large-print chapter title fragments on chapter pages."""
	up = s.upper().strip(" .,:;-_|")
	if up in title_fragments:
		return True
	up2 = re.sub(r"^[\d\)(©|&y )]+", "", up).strip(" |")
	return up2 in title_fragments


#============================================
def load_config(config_path: pathlib.Path) -> dict[str, object]:
	"""Load and validate the book config JSON."""
	config = json.loads(config_path.read_text(encoding="utf-8"))
	for required in ("title", "author", "date", "chapters", "running_heads"):
		if required not in config:
			raise ValueError(f"config missing required key: {required}")
	return config


#============================================
def main() -> None:
	"""Assemble one half-page OCR output into clean Markdown."""
	args = parse_args()
	config = load_config(pathlib.Path(args.config))
	running_heads = config["running_heads"]
	title_fragments = config.get("title_fragments", [])
	chapters = config["chapters"]
	furniture_lead = build_furniture_lead(running_heads)

	raw = pathlib.Path(args.input).read_text(encoding="utf-8")
	chunks = re.split(r"^===== PAGE (\d+) =====\s*", raw, flags=re.M)
	pages = []
	for i in range(1, len(chunks), 2):
		num = int(chunks[i])
		text = chunks[i + 1] if i + 1 < len(chunks) else ""
		pages.append((num, text.split("\n")))
	print(f"book pages: {len(pages)}")

	cleaned_pages = []
	for num, lines in pages:
		out = []
		for line in lines:
			if is_noise_line(line):
				continue
			cl = clean_line(line)
			if not cl:
				continue
			if looks_like_running_head(cl, running_heads):
				continue
			cl = strip_furniture(cl, furniture_lead)
			cl = LEAD_JUNK.sub("", cl)
			cl = TRAIL_JUNK.sub("", cl).rstrip()
			if not cl:
				continue
			if looks_like_running_head(cl, running_heads):
				continue
			out.append(cl)
		cleaned_pages.append((num, out))

	intro_markers = config.get("intro_markers", [])
	intro_num = None
	if intro_markers:
		for num, lines in pages:
			head = " ".join(l for l in lines if l.strip())[:400]
			if all(marker in head for marker in intro_markers):
				intro_num = num
				break
	if intro_num is None:
		intro_num = min(n for n, _ in pages)
	print(f"intro body start: {intro_num}")

	starts = {}
	for num, lines in pages:
		if num < intro_num:
			continue
		head_raw = " ".join(l for l in lines[:16] if l.strip())
		head_norm = norm(head_raw)
		for chapter in chapters:
			title = chapter["title"]
			key = chapter["key"]
			if title in starts:
				continue
			if key == "INDEX":
				if "INDEX" in head_norm and "INDEXHTML" not in head_norm:
					starts[title] = num
			elif key in head_norm:
				starts[title] = num
	print("detected starts:", json.dumps(starts, indent="\t"))
	for chapter in chapters:
		if chapter["title"].upper() == "INTRODUCTION":
			starts[chapter["title"]] = intro_num
			break

	pages_by_num = dict(cleaned_pages)
	ordered_nums = sorted(n for n, _ in cleaned_pages)
	body_nums = [n for n in ordered_nums if n >= intro_num]
	heading_plan = {}
	for chapter in chapters:
		title = chapter["title"]
		if title in starts:
			heading_plan.setdefault(starts[title], []).append(("##", title))

	def flush_para(buf: list[str], out: list[str]) -> None:
		if buf:
			out.append(" ".join(buf))
			buf.clear()

	body = []
	buf = []
	prev_end_punct = False
	for num in body_nums:
		lines = pages_by_num[num]
		page_headings = heading_plan.get(num, [])
		if page_headings:
			flush_para(buf, body)
			for level, title in page_headings:
				body.append(f"{level} {title}")
		for line in lines:
			if not line:
				continue
			if page_headings and is_title_fragment(line, title_fragments):
				continue
			starts_lower = line[0].islower() and not prev_end_punct
			if buf and starts_lower:
				buf[-1] = buf[-1] + " " + line
			else:
				flush_para(buf, body)
				buf.append(line)
			prev_end_punct = line.rstrip().endswith(SENTENCE_END)
		if buf and buf[-1].rstrip().endswith(SENTENCE_END):
			flush_para(buf, body)
	flush_para(buf, body)

	header = [
		"---",
		f'title: "{config["title"]}"',
		f'author: "{config["author"]}"',
		f'date: "{config["date"]}"',
	]
	if config.get("source_pdf"):
		header.append(f'source_pdf: "{config["source_pdf"]}"')
	header.extend(["---", "", f'# {config["title"]}', ""])
	if config.get("imprint"):
		header.extend([config["imprint"], ""])
	if config.get("blurb"):
		header.extend([config["blurb"], ""])

	front_matter_pages = config.get("front_matter_pages", {})
	for page_text, heading in front_matter_pages.items():
		lines = pages_by_num.get(int(page_text), [])
		if lines:
			header.append(heading)
			header.append("")
			header.extend(lines)
			header.append("")

	contents = ["## Contents", ""]
	for chapter in chapters:
		if chapter["title"] in starts:
			contents.append(f"- {chapter['title']}")
	contents.append("")

	final = header + contents + body
	text = "\n".join(final)
	text = re.sub(r"\n{3,}", "\n\n", text)

	out_lines = []
	for line in text.split("\n"):
		if re.fullmatch(r"\d{1,4}", line.strip()) and out_lines:
			prev = out_lines[-1]
			if prev and not prev.startswith("#") and not prev.rstrip().endswith(SENTENCE_END + (")",)):
				out_lines[-1] = prev.rstrip() + " " + line.strip()
				continue
			continue
		out_lines.append(line)
	text = "\n".join(out_lines)

	text = "".join(ASCII_MAP.get(char, char) for char in text)
	text = re.sub(r" {2,}", " ", text)

	pathlib.Path(args.output).write_text(text, encoding="utf-8")
	print(f"WROTE {args.output} chars {len(text)}")


#============================================
if __name__ == "__main__":
	main()
