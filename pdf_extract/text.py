"""Shared Markdown text normalization and page-flattening helpers."""

import re

import markdown_quality
import pdf_extract.models


TERMINAL_PUNCTUATION = ".!?:;"
ABBREVIATION_PATTERN = re.compile(r"(?:Fig|cf|Thm|Prop|Lemma|Cor|Def|e\.g|i\.e|et al|Sec|Eq)\.$")
NUMBERED_SECTION_PATTERN = re.compile(r"^\d{1,2}(\.\d{1,2}){1,3}\.?\s+[A-Z]")
CAPTION_PATTERN = re.compile(r"^(?:FIGURE|Figure|Fig\.|TABLE|Table|Plate)\s*\d")
BLOCK_START_PATTERN = re.compile(r"^(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\||>|```)")


#============================================
def normalize_text(text: str) -> str:
	"""Normalize line endings and excess blank lines without changing content."""
	normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
	normalized_text = re.sub(r"[ \t]+\n", "\n", normalized_text)
	normalized_text = re.sub(r"\n{3,}", "\n\n", normalized_text)
	normalized_text = normalized_text.strip()
	return normalized_text


#============================================
def split_blocks(text: str) -> list[str]:
	"""Split one page into nonempty Markdown blocks."""
	blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
	return blocks


#============================================
def clean_emphasis(text: str) -> str:
	"""Remove lightweight Markdown emphasis before evaluating seam punctuation."""
	plain_text = text.rstrip().strip("*_`")
	return plain_text


#============================================
def tail_is_open(block: str) -> bool:
	"""Return whether a prose tail is eligible to continue onto the next page."""
	plain_block = clean_emphasis(block)
	if not plain_block:
		return False
	if ABBREVIATION_PATTERN.search(plain_block):
		return True
	open_tail = plain_block[-1] not in TERMINAL_PUNCTUATION
	return open_tail


#============================================
def head_can_continue(block: str) -> bool:
	"""Apply the calibrated lowercase prose-head exclusions for a page seam."""
	stripped_block = block.lstrip()
	plain_block = clean_emphasis(stripped_block)
	if not plain_block or BLOCK_START_PATTERN.match(stripped_block):
		return False
	if NUMBERED_SECTION_PATTERN.match(plain_block) or CAPTION_PATTERN.match(plain_block):
		return False
	can_continue = plain_block[0].islower()
	return can_continue


#============================================
def flatten_pages(results: list[pdf_extract.models.PageResult], join_seams: bool) -> tuple[str, int, int]:
	"""Destroy page structure after conservative, page-aware seam joining."""
	output_blocks: list[str] = []
	seams_seen = 0
	seams_joined = 0
	for result in results:
		blocks = split_blocks(result.text)
		if not blocks:
			continue
		if output_blocks:
			seams_seen += 1
			candidate_index = len(output_blocks) - 1
			if CAPTION_PATTERN.match(output_blocks[candidate_index]) and candidate_index > 0:
				candidate_index -= 1
			if join_seams and tail_is_open(output_blocks[candidate_index]) and head_can_continue(blocks[0]):
				output_blocks[candidate_index] += " " + blocks.pop(0)
				seams_joined += 1
		output_blocks.extend(blocks)
	markdown_text = "\n\n".join(output_blocks).strip() + "\n"
	return markdown_text, seams_seen, seams_joined


#============================================
def demote_source_h1s(markdown_text: str) -> str:
	"""Reserve H1 for the canonical PDF metadata title without changing code."""
	lines = markdown_text.splitlines()
	fenced, _unclosed = markdown_quality.fenced_line_numbers(lines)
	for index, line in enumerate(lines):
		if index not in fenced and re.match(r"^#\s+", line):
			lines[index] = "#" + line
	return "\n".join(lines).rstrip() + "\n"
