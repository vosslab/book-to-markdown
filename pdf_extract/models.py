"""Data records shared by PDF extraction, cleanup, and reporting."""

import dataclasses


#============================================
@dataclasses.dataclass
class PageResult:
	"""Hold extracted text and diagnostics for one PDF page."""
	page_number: int
	text: str
	source: str
	embedded_words: int
	ocr_words: int


#============================================
@dataclasses.dataclass
class Removal:
	"""Record text removed by a page-aware pass for the audit sidecar."""
	pass_name: str
	page_number: int
	line_number: int
	text: str
	reason: str


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
