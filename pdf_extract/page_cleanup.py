"""Page-aware removal and heading-promotion passes for PDF extraction."""

import argparse
import collections
import re

import pdf_extract.models
import pdf_extract.text


RUNNING_HEAD_MIN_RECURRENCE = 3
RUNNING_HEAD_EDGE_DISTANCE = 2
RUNNING_HEAD_EDGE_FRACTION = 0.70
RUNNING_HEAD_MAX_LENGTH = 90
NUMBERED_HEADING_PATTERN = re.compile(r"^\*{0,2}\d{1,2}(\.\d{1,2}){1,3}\.?\s+[A-Z][^.!?]{2,60}\*{0,2}$")
PAGE_NUMBER_PATTERN = re.compile(r"^(?:\d+|[ivxlcdm]+)$", re.IGNORECASE)
PICTURE_PLACEHOLDER_PATTERN = re.compile(
	r"^\s*\*{0,2}==>\s*picture\s*\[\d+\s*x\s*\d+\]\s*intentionally omitted\s*<==\*{0,2}\s*$",
	re.IGNORECASE,
)
PICTURE_TEXT_START_PATTERN = re.compile(
	r"\*{0,2}-+\s*Start of picture text\s*-+\*{0,2}(?:<br\s*/?>)?",
	re.IGNORECASE,
)
PICTURE_TEXT_END_PATTERN = re.compile(
	r"\*{0,2}-+\s*End of picture text\s*-+\*{0,2}(?:<br\s*/?>)?",
	re.IGNORECASE,
)


#============================================
def canonical_template(line: str) -> str:
	"""Mask digits except in standalone numbered chapter, part, and appendix labels."""
	plain_line = re.sub(r"^#{1,6}\s+", "", line.strip())
	plain_line = plain_line.strip("*_` ")
	if re.fullmatch(r"(?:CHAPTER|PART|APPENDIX)\s+\d+(?:\.\d+)*", plain_line, re.IGNORECASE):
		return plain_line
	# Some PDFs place a recurring chapter label before the first body words on
	# one physical line. Keep that short prefix auditable and removable without
	# discarding the prose after it.
	prefix_match = re.match(r"^(?:(?:CHAPTER|PART|APPENDIX)\s+\d+(?:\.\d+)*)\b", plain_line, re.IGNORECASE)
	if prefix_match is not None:
		plain_line = prefix_match.group(0)
	template = re.sub(r"\d+", "#", plain_line)
	return template


#============================================
def uppercase_edge_templates(line: str) -> list[str]:
	"""Return short all-caps fragments that can be measured as page furniture."""
	plain_line = re.sub(r"^#{1,6}\s+", "", line.strip())
	plain_line = plain_line.replace("**", " ").replace("__", " ")
	matches = re.findall(r"(?<![A-Z0-9])(?:[A-Z][A-Z0-9'&-]*(?![a-z]))(?:\s+[A-Z][A-Z0-9'&-]*(?![a-z]))+(?![A-Z0-9])", plain_line)
	templates = [match.strip() for match in matches if len(match.strip()) <= RUNNING_HEAD_MAX_LENGTH]
	return templates


#============================================
def is_uppercase_template(template: str) -> bool:
	"""Return whether a template is an all-caps multi-word page-furniture fragment."""
	letters = [character for character in template if character.isalpha()]
	return "#" not in template and len(template.split()) >= 2 and bool(letters) and all(character.isupper() for character in letters)


#============================================
def is_markdown_pipe_table_row(line: str) -> bool:
	"""Return whether a line has Markdown pipe-table row structure."""
	stripped_line = line.strip()
	if "|" not in stripped_line:
		return False
	return stripped_line.startswith("|") or stripped_line.endswith("|") or stripped_line.count("|") >= 2


#============================================
def fenced_code_line_indexes(lines: list[str]) -> set[int]:
	"""Return indexes belonging to fenced Markdown code blocks."""
	indexes: set[int] = set()
	active_marker: str | None = None
	for line_index, line in enumerate(lines):
		fence_match = re.match(r"^\s*(`{3,}|~{3,})", line)
		if fence_match is not None:
			indexes.add(line_index)
			marker = fence_match.group(1)[0]
			if active_marker is None:
				active_marker = marker
			elif marker == active_marker:
				active_marker = None
			continue
		if active_marker is not None:
			indexes.add(line_index)
	return indexes


#============================================
def is_code_template(template: str) -> bool:
	"""Return whether a recurring fragment has strong code syntax."""
	if not any(character.isalpha() for character in template):
		return True
	if re.fullmatch(r"\[[A-Za-z0-9_.-]+\]", template) is not None:
		return True
	return re.search(r"[{};]|::|->|=>|\s=\s|--[A-Za-z]", template) is not None


#============================================
def is_single_word_section_template(template: str) -> bool:
	"""Return whether a template can be an all-caps section label."""
	return template.isalpha() and template.isupper()


#============================================
def template_prefix_pattern(template: str) -> re.Pattern[str]:
	"""Build a digit-aware prefix match for a recurring page-furniture template."""
	escaped = re.escape(template).replace(r"\#", r"\d+")
	pattern = re.compile(r"^\s*(?:#{1,6}\s+)?(?:\*{1,3}|_{1,3}|`{1,3})?" + escaped
		+ r"(?:\*{1,3}|_{1,3}|`{1,3})?(?=\s|$)", re.IGNORECASE)
	return pattern


#============================================
def template_pattern(template: str) -> re.Pattern[str]:
	"""Build the safe line match for a measured running-head template."""
	if is_uppercase_template(template):
		escaped = re.escape(template).replace(r"\ ", r"\s+")
		return re.compile(r"(?<![A-Za-z0-9])" + escaped + r"(?![A-Za-z0-9])")
	return template_prefix_pattern(template)


#============================================
def full_template_pattern(template: str) -> re.Pattern[str]:
	"""Build an exact unmarked-line match for evidence-backed heading promotion."""
	escaped = re.escape(template).replace(r"\#", r"\d+").replace(r"\ ", r"\s+")
	pattern = re.compile(r"^\s*(?:\*{1,3}|_{1,3}|`{1,3})?" + escaped
		+ r"(?:\*{1,3}|_{1,3}|`{1,3})?\s*$", re.IGNORECASE)
	return pattern


#============================================
def running_head_decisions(
		results: list[pdf_extract.models.PageResult],
		defaults: dict[str, int | float],
	) -> list[pdf_extract.models.RunningHeadDecision]:
	"""Classify recurrent short edge templates using the measured three-way rule."""
	occurrences: dict[str, list[tuple[int, int, int, int | None]]] = collections.defaultdict(list)
	for result in results:
		original_lines = result.text.splitlines()
		code_indexes = fenced_code_line_indexes(original_lines)
		lines = [(source_index, line.strip()) for source_index, line in enumerate(original_lines) if line.strip()]
		last_index = len(lines) - 1
		for line_index, (source_index, line) in enumerate(lines):
			if source_index in code_indexes:
				continue
			if is_markdown_pipe_table_row(line):
				continue
			plain_line = re.sub(r"^#{1,6}\s+", "", line).strip("*_` ")
			if PAGE_NUMBER_PATTERN.fullmatch(plain_line):
				continue
			edge_distance = min(line_index, last_index - line_index)
			heading_match = re.match(r"^(#{1,6})\s+", line)
			heading_level = len(heading_match.group(1)) if heading_match is not None else None
			heading_text = line[heading_match.end():] if heading_match is not None else ""
			templates = [canonical_template(line), *uppercase_edge_templates(line)]
			for template in dict.fromkeys(templates):
				if not template or len(template) > int(defaults["max_length"]):
					continue
				if is_code_template(template):
					continue
				if "START OF PICTURE TEXT" in template.upper() or "END OF PICTURE TEXT" in template.upper():
					continue
				template_heading_level = heading_level
				if heading_level is not None and full_template_pattern(template).fullmatch(heading_text) is None:
					template_heading_level = None
				occurrences[template].append((result.page_number, edge_distance, line_index, template_heading_level))
	decisions: list[pdf_extract.models.RunningHeadDecision] = []
	for template, rows in occurrences.items():
		count = len(rows)
		edge_count = sum(1 for _page, distance, _line, _level in rows if distance <= int(defaults["edge_distance"]))
		edge_fraction = edge_count / count
		if count < int(defaults["min_recurrence"]):
			continue
		heading_levels = {level for _page, _distance, _line, level in rows if level is not None}
		heading_count = sum(1 for _page, _distance, _line, level in rows if level is not None)
		heading_fraction = heading_count / count
		# A real heading can be fused with page furniture on one page. Recurrence at
		# the measured edge boundary is stronger evidence than a single marker, but
		# not than a consistently marked majority of real section headings.
		if edge_fraction >= float(defaults["edge_fraction"]):
			if len(heading_levels) == 1 and heading_fraction >= 0.5:
				disposition = "promote"
				heading_level = next(iter(heading_levels))
			elif is_single_word_section_template(template):
				if len(heading_levels) != 1:
					continue
				disposition = "promote"
				heading_level = next(iter(heading_levels))
			else:
				disposition = "delete"
				heading_level = None
		elif len(heading_levels) == 1:
			disposition = "promote"
			heading_level = next(iter(heading_levels))
		else:
			continue
		pages = sorted({page + 1 for page, _distance, _line, _level in rows})
		decisions.append(pdf_extract.models.RunningHeadDecision(
			template=template,
			count=count,
			pages=pages,
			edge_fraction=edge_fraction,
			disposition=disposition,
			heading_level=heading_level,
		))
	decisions.sort(key=lambda decision: (-decision.count, decision.template))
	return decisions


#============================================
def remove_running_heads(
		results: list[pdf_extract.models.PageResult],
		removals: list[pdf_extract.models.Removal],
		defaults: dict[str, int | float],
	) -> list[pdf_extract.models.RunningHeadDecision]:
	"""Delete measured running heads and promote only corroborated real headings."""
	decisions = running_head_decisions(results, defaults)
	patterns = [(decision, full_template_pattern(decision.template)) for decision in decisions if decision.disposition == "delete"]
	promotion_patterns = [(decision, full_template_pattern(decision.template)) for decision in decisions if decision.disposition == "promote" and decision.heading_level is not None]
	for result in results:
		original_lines = result.text.splitlines()
		code_indexes = fenced_code_line_indexes(original_lines)
		nonblank_indexes = [index for index, line in enumerate(original_lines) if line.strip()]
		edge_indexes = set(nonblank_indexes[:int(defaults["edge_distance"]) + 1])
		edge_indexes.update(nonblank_indexes[-int(defaults["edge_distance"]) - 1:])
		new_lines: list[str] = []
		for line_number, line in enumerate(original_lines, start=1):
			remaining_line = line
			line_index = line_number - 1
			if line_index in edge_indexes and line_index not in code_indexes and not is_markdown_pipe_table_row(remaining_line):
				for decision, pattern in patterns:
					match = pattern.fullmatch(remaining_line)
					if match is None:
						continue
					removed_text = match.group().strip()
					remaining_line = ""
					removals.append(pdf_extract.models.Removal("running_head", result.page_number + 1, line_number, removed_text, f"recurrent edge template: {decision.template}"))
			if line_index not in edge_indexes and line_index not in code_indexes and not is_markdown_pipe_table_row(remaining_line):
				for decision, pattern in promotion_patterns:
					if re.match(r"^\s*#{1,6}\s+", remaining_line) or pattern.fullmatch(remaining_line) is None:
						continue
					heading_text = remaining_line.strip().strip("*_` ")
					remaining_line = f"{'#' * decision.heading_level} {heading_text}"
					decision.promoted_count += 1
					break
			if remaining_line:
				new_lines.append(remaining_line)
		result.text = pdf_extract.text.normalize_text("\n".join(new_lines))
	return decisions


#============================================
def remove_edge_page_numbers(results: list[pdf_extract.models.PageResult], removals: list[pdf_extract.models.Removal]) -> None:
	"""Remove leading and trailing bare Arabic or Roman page-number lines."""
	for result in results:
		lines = result.text.splitlines()
		while lines and not lines[0].strip():
			lines.pop(0)
		while lines and not lines[-1].strip():
			lines.pop()
		for line_number, line in enumerate(lines, start=1):
			if line_number not in (1, len(lines)) or not PAGE_NUMBER_PATTERN.fullmatch(line.strip()):
				continue
			removals.append(pdf_extract.models.Removal("page_number", result.page_number + 1, line_number, line.strip(), "edge page number"))
			lines[line_number - 1] = ""
		result.text = pdf_extract.text.normalize_text("\n".join(lines))


#============================================
def remove_picture_blocks(results: list[pdf_extract.models.PageResult], removals: list[pdf_extract.models.Removal]) -> None:
	"""Remove PyMuPDF image placeholders and picture text without losing captions."""
	for result in results:
		lines = result.text.splitlines()
		picture_lines: set[int] = set()
		line_index = 0
		while line_index < len(lines):
			if PICTURE_PLACEHOLDER_PATTERN.fullmatch(lines[line_index]):
				removals.append(pdf_extract.models.Removal("images", result.page_number + 1, line_index + 1, lines[line_index], "PyMuPDF picture placeholder"))
				picture_lines.add(line_index)
				lines[line_index] = ""
				line_index += 1
				continue
			start_match = PICTURE_TEXT_START_PATTERN.search(lines[line_index])
			if start_match is None:
				line_index += 1
				continue
			end_index = line_index
			end_match = PICTURE_TEXT_END_PATTERN.search(lines[end_index], start_match.end())
			while end_match is None and end_index + 1 < len(lines):
				end_index += 1
				end_match = PICTURE_TEXT_END_PATTERN.search(lines[end_index])
			if end_match is None:
				line_index += 1
				continue
			removed_text = "\n".join(lines[line_index:end_index + 1])
			removals.append(pdf_extract.models.Removal("images", result.page_number + 1, line_index + 1, removed_text, "PyMuPDF picture text block"))
			prefix = lines[line_index][:start_match.start()].rstrip()
			suffix = lines[end_index][end_match.end():].lstrip()
			for picture_line in range(line_index, end_index + 1):
				picture_lines.add(picture_line)
				lines[picture_line] = ""
			if line_index == end_index:
				lines[line_index] = prefix + suffix
			else:
				lines[line_index] = prefix
				lines[end_index] = suffix
			line_index = end_index + 1
		for number_index, line in enumerate(lines):
			if number_index in picture_lines or not PAGE_NUMBER_PATTERN.fullmatch(line.strip()):
				continue
			for direction in (-1, 1):
				neighbor_index = number_index + direction
				while 0 <= neighbor_index < len(lines) and not lines[neighbor_index].strip():
					if neighbor_index in picture_lines:
						removals.append(pdf_extract.models.Removal("page_number", result.page_number + 1, number_index + 1, line.strip(), "page number adjacent to removed picture content"))
						lines[number_index] = ""
						break
					neighbor_index += direction
				if not lines[number_index]:
					break
		result.text = pdf_extract.text.normalize_text("\n".join(lines))


#============================================
def synthesize_numbered_headings(results: list[pdf_extract.models.PageResult]) -> list[str]:
	"""Promote only the calibrated dotted, multi-level numbered heading shape."""
	synthesized_headings: list[str] = []
	for result in results:
		new_lines: list[str] = []
		for line in result.text.splitlines():
			stripped_line = line.strip()
			if NUMBERED_HEADING_PATTERN.fullmatch(stripped_line):
				number_text = stripped_line.strip("*").split(maxsplit=1)[0].rstrip(".")
				level = number_text.count(".") + 1
				heading_line = "#" * level + " " + stripped_line.strip("*")
				new_lines.append(heading_line)
				synthesized_headings.append(heading_line)
			else:
				new_lines.append(line)
		result.text = pdf_extract.text.normalize_text("\n".join(new_lines))
	return synthesized_headings


#============================================
def effective_running_head_defaults(args: argparse.Namespace) -> dict[str, int | float]:
	"""Return the small measured override surface, with defaults visible in reports."""
	defaults: dict[str, int | float] = {
		"min_recurrence": RUNNING_HEAD_MIN_RECURRENCE,
		"edge_distance": RUNNING_HEAD_EDGE_DISTANCE,
		"edge_fraction": RUNNING_HEAD_EDGE_FRACTION,
		"max_length": RUNNING_HEAD_MAX_LENGTH,
	}
	for key in defaults:
		value = getattr(args, "running_head_" + key)
		if value is not None:
			defaults[key] = value
	return defaults
