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
	r"^ *\*{0,2}==> *picture *\[\d+ *x *\d+\] *intentionally omitted *<==\*{0,2} *$",
	re.IGNORECASE,
)
PICTURE_TEXT_START_PATTERN = re.compile(
	r"\*{0,2}-+ *Start of picture text *-+\*{0,2}(?:<br */?>)?",
	re.IGNORECASE,
)
PICTURE_TEXT_END_PATTERN = re.compile(
	r"\*{0,2}-+ *End of picture text *-+\*{0,2}(?:<br */?>)?",
	re.IGNORECASE,
)
PICTURE_MARKER_CONTROL_TRANSLATION = str.maketrans("", "", "\t\r\v\f")
RunningHeadOccurrence = dict[str, int | float | str | tuple[float, float, float, float] | tuple[str, ...] | None]


#============================================
def has_exact_line_provenance(
		text: str,
		provenance: list[pdf_extract.models.PageLineProvenance] | None,
	) -> bool:
	"""Return whether source records match every LF-delimited text line."""
	if provenance is None:
		return False
	return [record.text for record in provenance] == text.split("\n")


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
#============================================
def running_head_decisions(
		results: list[pdf_extract.models.PageResult],
		defaults: dict[str, int | float],
	) -> list[pdf_extract.models.RunningHeadDecision]:
	"""Classify only source-attributed occurrences with repeated edge geometry."""
	occurrences: dict[str, list[RunningHeadOccurrence]] = collections.defaultdict(list)
	for result in results:
		original_lines = result.text.split("\n")
		provenance = result.line_provenance
		if not has_exact_line_provenance(result.text, provenance):
			continue
		code_indexes = fenced_code_line_indexes(original_lines)
		lines = [(source_index, line.strip()) for source_index, line in enumerate(original_lines) if line.strip()]
		last_index = len(lines) - 1
		for line_index, (source_index, line) in enumerate(lines):
			record = provenance[source_index]
			if record.bbox is None:
				continue
			if source_index in code_indexes:
				continue
			if is_markdown_pipe_table_row(line):
				continue
			plain_line = re.sub(r"^#{1,6}\s+", "", line).strip("*_` ")
			if PAGE_NUMBER_PATTERN.fullmatch(plain_line):
				continue
			following_record = _following_body_record(provenance, source_index)
			following_y = None
			following_font_size = None
			following_font_names = None
			following_font_flags = None
			if following_record is not None and following_record.bbox is not None:
				following_y = following_record.bbox[1]
				following_font_size = following_record.font_size
				following_font_names = following_record.font_names
				following_font_flags = following_record.font_flags
			edge_distance = min(line_index, last_index - line_index)
			templates = [canonical_template(line), *uppercase_edge_templates(line)]
			for template in dict.fromkeys(templates):
				if not template or len(template) > int(defaults["max_length"]):
					continue
				if is_code_template(template):
					continue
				if "START OF PICTURE TEXT" in template.upper() or "END OF PICTURE TEXT" in template.upper():
					continue
				occurrences[template].append({
					"page": result.page_number,
					"line": source_index,
					"line_id": record.line_id,
					"edge_distance": edge_distance,
					"bbox": record.bbox,
					"font_size": record.font_size,
					"font_names": record.font_names,
					"font_flags": record.font_flags,
					"block_index": record.block_index,
					"following_y": following_y,
					"following_font_size": following_font_size,
					"following_font_names": following_font_names,
					"following_font_flags": following_font_flags,
					"source": record.source,
				})
	decisions: list[pdf_extract.models.RunningHeadDecision] = []
	for template, rows in occurrences.items():
		count = len(rows)
		edge_rows = [row for row in rows if int(row["edge_distance"]) <= int(defaults["edge_distance"])]
		edge_count = len(edge_rows)
		edge_fraction = edge_count / count
		if count < int(defaults["min_recurrence"]):
			continue
		if edge_fraction < float(defaults["edge_fraction"]) or len(edge_rows) < int(defaults["min_recurrence"]):
			continue
		band_rows = [row for row in edge_rows if _has_recurrent_furniture_geometry(row, edge_rows)]
		if len(band_rows) < int(defaults["min_recurrence"]):
			continue
		proven_rows = [row for row in band_rows if _has_positive_furniture_context(row)]
		occurrence_reports: list[dict[str, int | float | str | bool | None]] = []
		furniture_ids = {(int(row["page"]), int(row["line_id"])) for row in proven_rows}
		for row in rows:
			is_furniture = (int(row["page"]), int(row["line_id"])) in furniture_ids
			record_data = row["bbox"]
			occurrence_reports.append({
				"page": int(row["page"]) + 1,
				"line": int(row["line"]) + 1,
				"source_line_id": int(row["line_id"]),
				"source": str(row["source"]),
				"disposition": "delete" if is_furniture else "preserve",
				"reason": "recurrent parity geometry with local body context" if is_furniture else "ambiguous or outside proven furniture group",
				"bbox_x0": record_data[0],
				"bbox_y0": record_data[1],
				"bbox_x1": record_data[2],
				"bbox_y1": record_data[3],
				"font_size": float(row["font_size"]) if row["font_size"] is not None else None,
				"font_names": "|".join(row["font_names"]) if row["font_names"] else None,
				"font_flags": ",".join(str(flag) for flag in row["font_flags"]) if row["font_flags"] else None,
				"block_index": int(row["block_index"]) if row["block_index"] is not None else None,
				"following_y": float(row["following_y"]) if row["following_y"] is not None else None,
				"following_font_size": float(row["following_font_size"]) if row["following_font_size"] is not None else None,
				"following_font_names": "|".join(row["following_font_names"]) if row["following_font_names"] else None,
				"following_font_flags": ",".join(str(flag) for flag in row["following_font_flags"]) if row["following_font_flags"] else None,
			})
		pages = sorted({int(row["page"]) + 1 for row in rows})
		decisions.append(pdf_extract.models.RunningHeadDecision(
			template=template,
			count=count,
			pages=pages,
			edge_fraction=edge_fraction,
			disposition="delete" if furniture_ids else "preserve",
			occurrences=occurrence_reports,
		))
	decisions.sort(key=lambda decision: (-decision.count, decision.template))
	return decisions


#============================================
def _has_recurrent_furniture_geometry(
		row: RunningHeadOccurrence,
		rows: list[RunningHeadOccurrence],
	) -> bool:
	"""Check one occurrence against a parity-aware geometry and style group."""
	bbox = row["bbox"]
	if not isinstance(bbox, tuple):
		return False
	y_center = (bbox[1] + bbox[3]) / 2
	if y_center <= 0.14:
		band = "top"
	elif y_center >= 0.86:
		band = "bottom"
	else:
		return False
	band_rows = []
	row_x_center = (bbox[0] + bbox[2]) / 2
	row_width = bbox[2] - bbox[0]
	row_fonts = row["font_names"]
	row_flags = row["font_flags"]
	spatial_rows = []
	for candidate in rows:
		candidate_bbox = candidate["bbox"]
		if not isinstance(candidate_bbox, tuple):
			continue
		candidate_y = (candidate_bbox[1] + candidate_bbox[3]) / 2
		candidate_band = "top" if candidate_y <= 0.14 else "bottom" if candidate_y >= 0.86 else "middle"
		if candidate_band != band:
			continue
		candidate_x = (candidate_bbox[0] + candidate_bbox[2]) / 2
		candidate_width = candidate_bbox[2] - candidate_bbox[0]
		if abs(candidate_x - row_x_center) > 0.08 or abs(candidate_width - row_width) > max(0.06, row_width * 0.6):
			continue
		candidate_fonts = candidate["font_names"]
		candidate_flags = candidate["font_flags"]
		if row_fonts and candidate_fonts and row_fonts != candidate_fonts:
			continue
		if row_flags and candidate_flags and row_flags != candidate_flags:
			continue
		spatial_rows.append(candidate)
	if not spatial_rows:
		return False
	centers = sorted({round((candidate["bbox"][0] + candidate["bbox"][2]) / 2, 1) for candidate in spatial_rows})
	if len(centers) > 1:
		band_rows = [candidate for candidate in spatial_rows if int(candidate["page"]) % 2 == int(row["page"]) % 2]
	else:
		band_rows = spatial_rows
	if len(band_rows) < 2:
		return False
	y_values = sorted((candidate["bbox"][1] + candidate["bbox"][3]) / 2 for candidate in band_rows)
	median_y = y_values[len(y_values) // 2]
	if abs(y_center - median_y) > 0.035:
		return False
	font_sizes = sorted(float(candidate["font_size"]) for candidate in band_rows if candidate["font_size"] is not None)
	if len(font_sizes) >= 2 and row["font_size"] is not None:
		median_size = font_sizes[len(font_sizes) // 2]
		if float(row["font_size"]) > median_size * 2.25 or float(row["font_size"]) < median_size / 2.25:
			return False
	return True


#============================================
def _following_body_record(
		provenance: list[pdf_extract.models.PageLineProvenance],
		line_index: int,
	) -> pdf_extract.models.PageLineProvenance | None:
	"""Return the nearest positioned line below a candidate."""
	current = provenance[line_index]
	if current.bbox is None:
		return None
	later: list[pdf_extract.models.PageLineProvenance] = []
	for index, record in enumerate(provenance):
		if index <= line_index or not record.text.strip() or record.bbox is None:
			continue
		if record.bbox[1] < current.bbox[3]:
			continue
		horizontal_overlap = min(current.bbox[2], record.bbox[2]) - max(
			current.bbox[0], record.bbox[0],
		)
		if horizontal_overlap <= 0:
			continue
		later.append(record)
	return min(later, key=lambda record: record.bbox[1]) if later else None


#============================================
def _has_positive_furniture_context(row: RunningHeadOccurrence) -> bool:
	"""Require a margin/body relationship that distinguishes furniture from ambiguity."""
	bbox = row["bbox"]
	following_y = row["following_y"]
	if not isinstance(bbox, tuple) or not isinstance(following_y, float):
		return False
	line_height = max(0.001, bbox[3] - bbox[1])
	gap = float(following_y) - bbox[3]
	line_size = row["font_size"]
	body_size = row["following_font_size"]
	if line_size is None or body_size is None or float(line_size) > float(body_size):
		return False
	style_contrast = (
		row["font_names"] != row["following_font_names"]
		or row["font_flags"] != row["following_font_flags"]
	)
	if float(line_size) == float(body_size) and not style_contrast:
		return False
	# A small, repeatable gap beneath smaller edge text supports a running-furniture
	# interpretation. Large gaps, matching typography, or missing neighbors remain
	# ambiguous and therefore survive cleanup.
	return 0 <= gap <= line_height * 2.5


#============================================
def remove_running_heads(
		results: list[pdf_extract.models.PageResult],
		removals: list[pdf_extract.models.Removal],
		defaults: dict[str, int | float],
	) -> list[pdf_extract.models.RunningHeadDecision]:
	"""Delete measured running heads and promote only corroborated real headings."""
	decisions = running_head_decisions(results, defaults)
	removal_lines: dict[int, dict[int, pdf_extract.models.RunningHeadDecision]] = collections.defaultdict(dict)
	for decision in decisions:
		for occurrence in decision.occurrences:
			if occurrence["disposition"] != "delete":
				continue
			page_number = int(occurrence["page"]) - 1
			line_number = int(occurrence["line"]) - 1
			removal_lines[page_number][line_number] = decision
	for result in results:
		original_lines = result.text.split("\n")
		provenance = result.line_provenance
		if provenance is not None and not has_exact_line_provenance(result.text, provenance):
			result.line_provenance = None
			continue
		new_lines: list[str] = []
		new_records: list[pdf_extract.models.PageLineProvenance] = []
		for line_index, line in enumerate(original_lines):
			decision = removal_lines[result.page_number].get(line_index)
			if decision is not None:
				record = provenance[line_index] if provenance is not None else None
				removals.append(pdf_extract.models.Removal(
					"running_head",
					result.page_number + 1,
					line_index + 1,
					line.strip(),
					f"recurrent edge geometry: {decision.template}",
					record.line_id if record is not None else None,
					record.bbox if record is not None else None,
					record.font_size if record is not None else None,
				))
				continue
			new_lines.append(line)
			if provenance is not None:
				new_records.append(provenance[line_index])
		new_text = pdf_extract.text.normalize_page_text("\n".join(new_lines))
		if provenance is not None:
			new_text, new_records = pdf_extract.models.normalize_line_provenance(new_records)
			result.set_text_and_provenance(new_text, new_records)
		else:
			result.set_text_and_provenance(new_text, None)
	return decisions


#============================================
def remove_edge_page_numbers(results: list[pdf_extract.models.PageResult], removals: list[pdf_extract.models.Removal]) -> None:
	"""Remove leading and trailing bare Arabic or Roman page-number lines."""
	for result in results:
		provenance = result.line_provenance
		if provenance is not None and not has_exact_line_provenance(result.text, provenance):
			result.line_provenance = None
			continue
		original_lines = result.text.split("\n")
		indexed_lines = list(enumerate(original_lines))
		while indexed_lines and not indexed_lines[0][1].strip(" "):
			indexed_lines.pop(0)
		while indexed_lines and not indexed_lines[-1][1].strip(" "):
			indexed_lines.pop()
		lines = [line for _index, line in indexed_lines]
		removed_indexes: set[int] = set()
		for line_number, line in enumerate(lines, start=1):
			page_number_text = line.strip(" ")
			if line_number not in (1, len(lines)) or not PAGE_NUMBER_PATTERN.fullmatch(page_number_text):
				continue
			original_index = indexed_lines[line_number - 1][0]
			record = provenance[original_index] if provenance is not None else None
			removals.append(pdf_extract.models.Removal(
				"page_number",
				result.page_number + 1,
				line_number,
				page_number_text,
				"edge page number",
				record.line_id if record is not None else None,
				record.bbox if record is not None else None,
				record.font_size if record is not None else None,
			))
			removed_indexes.add(original_index)
		new_lines = [line for index, line in enumerate(original_lines) if index not in removed_indexes]
		new_text = pdf_extract.text.normalize_page_text("\n".join(new_lines))
		if provenance is not None:
			new_records = [record for index, record in enumerate(provenance) if index not in removed_indexes]
			new_text, new_records = pdf_extract.models.normalize_line_provenance(new_records)
			result.set_text_and_provenance(new_text, new_records)
		else:
			result.set_text_and_provenance(new_text, None)


#============================================
def remove_picture_blocks(results: list[pdf_extract.models.PageResult], removals: list[pdf_extract.models.Removal]) -> None:
	"""Remove PyMuPDF image placeholders and picture text without losing captions."""
	for result in results:
		original_text = result.text
		lines = result.text.split("\n")
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
			invalid_end_marker = end_match is None and PICTURE_TEXT_END_PATTERN.search(
				lines[end_index].translate(PICTURE_MARKER_CONTROL_TRANSLATION),
			) is not None
			while end_match is None and not invalid_end_marker and end_index + 1 < len(lines):
				end_index += 1
				end_match = PICTURE_TEXT_END_PATTERN.search(lines[end_index])
				invalid_end_marker = end_match is None and PICTURE_TEXT_END_PATTERN.search(
					lines[end_index].translate(PICTURE_MARKER_CONTROL_TRANSLATION),
				) is not None
			if end_match is None or invalid_end_marker:
				line_index += 1
				continue
			removed_text = "\n".join(lines[line_index:end_index + 1])
			removals.append(pdf_extract.models.Removal("images", result.page_number + 1, line_index + 1, removed_text, "PyMuPDF picture text block"))
			prefix = lines[line_index][:start_match.start()].rstrip(" ")
			suffix = lines[end_index][end_match.end():].lstrip(" ")
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
			page_number_text = line.strip(" ")
			if number_index in picture_lines or not PAGE_NUMBER_PATTERN.fullmatch(page_number_text):
				continue
			for direction in (-1, 1):
				neighbor_index = number_index + direction
				while 0 <= neighbor_index < len(lines) and not lines[neighbor_index].strip(" "):
					if neighbor_index in picture_lines:
						removals.append(pdf_extract.models.Removal("page_number", result.page_number + 1, number_index + 1, page_number_text, "page number adjacent to removed picture content"))
						lines[number_index] = ""
						break
					neighbor_index += direction
				if not lines[number_index]:
					break
		new_text = pdf_extract.text.normalize_page_text("\n".join(lines))
		if new_text != original_text:
			result.set_text_and_provenance(new_text, None)


#============================================
def synthesize_numbered_headings(results: list[pdf_extract.models.PageResult]) -> list[str]:
	"""Promote only the calibrated dotted, multi-level numbered heading shape."""
	synthesized_headings: list[str] = []
	for result in results:
		original_text = result.text
		new_lines: list[str] = []
		page_headings: list[str] = []
		for line in result.text.split("\n"):
			stripped_line = line.strip(" ")
			if NUMBERED_HEADING_PATTERN.fullmatch(stripped_line):
				number_text = stripped_line.strip("*").split(maxsplit=1)[0].rstrip(".")
				level = number_text.count(".") + 1
				heading_line = "#" * level + " " + stripped_line.strip("*")
				new_lines.append(heading_line)
				page_headings.append(heading_line)
			else:
				new_lines.append(line)
		if page_headings:
			new_text = "\n".join(new_lines)
			result.set_text_and_provenance(new_text, result.line_provenance if new_text == original_text else None)
			synthesized_headings.extend(page_headings)
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
