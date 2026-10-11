"""Protect Markdown structure during cleanup and ordinary prose reflow."""

import re
import collections.abc

import markdown_quality


#============================================
def protected_spans(
		text: str, protect_indented: bool = True, protect_quotes: bool = True) -> list[tuple[int, int]]:
	"""Return verbatim front matter, code, and quote spans for destructive passes."""
	lines = text.splitlines(keepends=True)
	spans = markdown_quality.inline_code_spans(text)
	offset = 0
	index = 0
	if lines and lines[0].strip() == "---":
		end = 1
		while end < len(lines) and lines[end].strip() not in {"---", "..."}:
			end += 1
		if end < len(lines):
			length = sum(len(line) for line in lines[:end + 1])
			spans.append((0, length))
			index = end + 1
		offset = sum(len(line) for line in lines[:index])
	in_fence = False
	fence_marker = ""
	span_start = 0
	for line in lines[index:]:
		stripped = line.lstrip()
		fence = re.match(r"(`{3,}|~{3,})", stripped)
		if fence and not in_fence:
			in_fence = True
			fence_marker = fence.group(1)[0]
			span_start = offset
		elif in_fence and fence and fence.group(1)[0] == fence_marker:
			spans.append((span_start, offset + len(line)))
			in_fence = False
		elif not in_fence and (
			(protect_indented and line.startswith(("    ", "\t")))
			or (protect_quotes and stripped.startswith(">"))
		):
			spans.append((offset, offset + len(line)))
		offset += len(line)
	if in_fence:
		spans.append((span_start, len(text)))
	return merge_spans(spans)


#============================================
def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
	"""Merge touching source spans so chunked transformations stay simple."""
	merged: list[tuple[int, int]] = []
	for start, end in sorted(spans):
		if merged and start <= merged[-1][1]:
			merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
		else:
			merged.append((start, end))
	return merged


#============================================
def transform_unprotected(
	text: str, transform: collections.abc.Callable[[str, int], str], protect_indented: bool = True,
	protect_quotes: bool = True) -> str:
	"""Apply a text transformer around source regions that must remain verbatim."""
	chunks: list[str] = []
	offset = 0
	for start, end in protected_spans(text, protect_indented, protect_quotes):
		base_line = text.count("\n", 0, start) + 1
		chunks.append(transform(text[offset:start], base_line))
		chunks.append(text[start:end])
		offset = end
	base_line = text.count("\n", 0, offset) + 1
	chunks.append(transform(text[offset:], base_line))
	output = "".join(chunks)
	return output


#============================================
def protected_line(line: str, in_fence: bool) -> bool:
	"""Identify structures whose layout must not be rewritten."""
	stripped = line.lstrip()
	protected = in_fence or line.startswith("|") or line.startswith(("    ", "\t"))
	protected = protected or stripped.startswith(("#", "- ", "* ", "+ ", ">"))
	protected = protected or bool(re.match(r"\d+[.)]\s", stripped))
	return protected


#============================================
def protected_line_indices(text: str) -> set[int]:
	"""Map protected character spans to lines they actually contain."""
	protected_lines: set[int] = set()
	for start, end in protected_spans(text):
		if end <= start:
			continue
		start_line = text.count("\n", 0, start)
		end_line = text.count("\n", 0, end - 1)
		protected_lines.update(range(start_line, end_line + 1))
	return protected_lines


#============================================
def reflow(text: str) -> str:
	"""Join ordinary extracted prose lines while preserving Markdown structures."""
	lines = text.splitlines()
	protected_source_lines: set[int] = set()
	for start, end in protected_spans(text):
		protected_source_lines.update(range(text.count("\n", 0, start), text.count("\n", 0, end) + 1))
	blocks: list[str] = []
	paragraph: list[str] = []
	protected_block: list[str] = []
	in_fence = False
	setext_lines = {
		index - 1 for index, line in enumerate(lines)
		if index and re.fullmatch(r"\s*(?:=+|-+)\s*", line) is not None and lines[index - 1].strip()
	}
	def flush() -> None:
		if paragraph:
			blocks.append(" ".join(" ".join(paragraph).split()))
			paragraph.clear()
	def flush_protected() -> None:
		if protected_block:
			blocks.append("\n".join(protected_block))
			protected_block.clear()
	for index, line in enumerate(lines):
		if line.strip().startswith("```"):
			flush()
			protected_block.append(line)
			in_fence = not in_fence
			continue
		if not line.strip():
			flush()
			flush_protected()
			continue
		if index in protected_source_lines or index in setext_lines or re.fullmatch(r"\s*(?:=+|-+)\s*", line) is not None or protected_line(line, in_fence):
			flush()
			protected_block.append(line.rstrip())
		else:
			flush_protected()
			paragraph.append(line.strip())
	flush()
	flush_protected()
	output = "\n\n".join(blocks).strip() + "\n"
	return output
