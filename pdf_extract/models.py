"""Data records shared by PDF extraction, cleanup, and reporting."""

import dataclasses


#============================================
def normalize_line_provenance(
		records: list["PageLineProvenance"],
	) -> tuple[str, list["PageLineProvenance"]]:
	"""Normalize exact line records with the same whitespace rules as page text."""
	cleaned_records: list[PageLineProvenance] = []
	for record in records:
		for line in record.text.split("\n"):
			cleaned_records.append(dataclasses.replace(record, text=line.rstrip(" ")))
	while cleaned_records and not cleaned_records[0].text:
		cleaned_records.pop(0)
	while cleaned_records and not cleaned_records[-1].text:
		cleaned_records.pop()
	collapsed_records: list[PageLineProvenance] = []
	blank_count = 0
	for record in cleaned_records:
		if not record.text:
			blank_count += 1
			if blank_count > 2:
				continue
		else:
			blank_count = 0
		collapsed_records.append(record)
	text = "\n".join(record.text for record in collapsed_records)
	return text, collapsed_records


#============================================
@dataclasses.dataclass
class PageLineProvenance:
	"""Describe the extracted source evidence for one exact output line."""
	text: str
	line_id: int
	source: str
	block_index: int | None = None
	bbox: tuple[float, float, float, float] | None = None
	font_size: float | None = None
	font_names: tuple[str, ...] = ()
	font_flags: tuple[int, ...] = ()


#============================================
@dataclasses.dataclass
class PageResult:
	"""Hold extracted text and diagnostics for one PDF page."""
	page_number: int
	text: str
	source: str
	embedded_words: int
	ocr_words: int
	line_provenance: list[PageLineProvenance] | None = None

	#============================================
	def set_text_and_provenance(
			self,
			text: str,
			line_provenance: list[PageLineProvenance] | None,
		) -> None:
		"""Set page text and retain records only when every LF-delimited line matches."""
		lines = text.split("\n")
		if line_provenance is not None and [record.text for record in line_provenance] != lines:
			line_provenance = None
		self.text = text
		self.line_provenance = line_provenance


#============================================
@dataclasses.dataclass
class Removal:
	"""Record text removed by a page-aware pass for the audit sidecar."""
	pass_name: str
	page_number: int
	line_number: int
	text: str
	reason: str
	source_line_id: int | None = None
	source_bbox: tuple[float, float, float, float] | None = None
	source_font_size: float | None = None


#============================================
@dataclasses.dataclass
class RunningHeadDecision:
	"""Describe one recurrent edge-line template and its disposition."""
	template: str
	count: int
	pages: list[int]
	edge_fraction: float
	disposition: str
	heading_level: int | None = None
	promoted_count: int = 0
	occurrences: list[dict[str, int | float | str | bool | None]] = dataclasses.field(default_factory=list)


#============================================
@dataclasses.dataclass
class ConversionResult:
	"""Hold Markdown, quality evidence, and auditable page-cleanup results."""
	pages: list[PageResult]
	markdown_text: str
	extraction_method: str
	warnings: list[str]
	estimated_words: int
	extracted_words: int
	word_ratio: float
	quality_status: str
	heading_count: int
	table_row_count: int
	seams_seen: int
	seams_joined: int
	running_heads: list[RunningHeadDecision]
	synthesized_headings: list[str]
	removals: list[Removal]
	effective_running_head_defaults: dict[str, int | float]
	initial_page_evidence: dict[str, int | float | list[str] | dict[str, int]]
