"""Candidate configuration, content checks, and source-bound promotion admission."""

import dataclasses
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from collections import abc


NEW_TITLE_NO_PREDECESSOR = "NEW_TITLE_NO_PREDECESSOR"
SUPERSEDES_PENDING = "SUPERSEDES_PENDING"
DIRECT_CANONICAL_REPLACEMENT = "DIRECT_CANONICAL_REPLACEMENT"
ValidatorRunner = abc.Callable[[pathlib.Path, pathlib.Path], int]


@dataclasses.dataclass(frozen=True)
class PromotionConfig:
	"""Describe one explicit validated-candidate publication lifecycle."""
	mode: str
	candidate: pathlib.Path
	destination: pathlib.Path
	validator: pathlib.Path
	expected_absent_pending: pathlib.Path
	predecessor: pathlib.Path | None
	superseded_root: pathlib.Path | None
	expected_predecessor_sha256: str | None = None

	@classmethod
	def new_title(
			cls,
			candidate: pathlib.Path,
			destination: pathlib.Path,
			expected_absent_pending: pathlib.Path,
			validator: pathlib.Path,
			) -> "PromotionConfig":
		"""Build the explicit no-predecessor lifecycle configuration."""
		config = cls(
			NEW_TITLE_NO_PREDECESSOR,
			candidate,
			destination,
			validator,
			expected_absent_pending,
			None,
			None,
		)
		return config

	@classmethod
	def supersedes_pending(
			cls,
			candidate: pathlib.Path,
			destination: pathlib.Path,
			predecessor: pathlib.Path,
			superseded_root: pathlib.Path,
			validator: pathlib.Path,
			) -> "PromotionConfig":
		"""Build the preserved legacy predecessor-replacement configuration."""
		config = cls(
			SUPERSEDES_PENDING,
			candidate,
			destination,
			validator,
			predecessor,
			predecessor,
			superseded_root,
		)
		return config

	@classmethod
	def replace_canonical(
			cls,
			candidate: pathlib.Path,
			destination: pathlib.Path,
			superseded_root: pathlib.Path,
			validator: pathlib.Path,
			expected_predecessor_sha256: str,
			) -> "PromotionConfig":
		"""Build a direct, hash-bound canonical replacement configuration."""
		return cls(
			DIRECT_CANONICAL_REPLACEMENT,
			candidate,
			destination,
			validator,
			destination,
			destination,
			superseded_root,
			expected_predecessor_sha256,
		)


#============================================
def parse_config(arguments: list[str]) -> PromotionConfig:
	"""Parse the two supported, unambiguous promoter invocations."""
	if arguments and arguments[0] == "--new-title":
		if len(arguments) != 5:
			raise ValueError("usage: --new-title CANDIDATE DESTINATION EXPECTED_ABSENT_PENDING VALIDATOR")
		candidate, destination, pending, validator = map(pathlib.Path, arguments[1:])
		config = PromotionConfig.new_title(candidate, destination, pending, validator)
		return config
	if arguments and arguments[0] == "--replace-canonical":
		if len(arguments) != 6:
			raise ValueError(
				"usage: --replace-canonical CANDIDATE DESTINATION SUPERSEDED_ROOT "
				"EXPECTED_PREDECESSOR_SHA256 VALIDATOR"
			)
		candidate, destination, superseded_root = map(pathlib.Path, arguments[1:4])
		expected_sha, validator = arguments[4:]
		return PromotionConfig.replace_canonical(
			candidate, destination, superseded_root, pathlib.Path(validator), expected_sha,
		)
	if len(arguments) != 5:
		raise ValueError("usage: CANDIDATE DESTINATION PENDING SUPERSEDED_ROOT VALIDATOR")
	candidate, destination, pending, superseded_root, validator = map(pathlib.Path, arguments)
	config = PromotionConfig.supersedes_pending(
		candidate, destination, pending, superseded_root, validator,
	)
	return config


#============================================
def sha256(path: pathlib.Path) -> str:
	"""Return the complete SHA-256 digest for one regular file."""
	digest = hashlib.sha256(path.read_bytes()).hexdigest()
	return digest


#============================================
def require_clean_content(candidate: pathlib.Path) -> None:
	"""Reject unresolved glyphs and replacement characters or entities."""
	candidate_text = candidate.read_text(encoding="utf-8", errors="replace")
	unresolved_markers = (
		candidate_text.count("[unmapped-PDF-glyph-")
		+ candidate_text.count("[unresolved source glyph]")
	)
	if unresolved_markers:
		raise ValueError("unresolved source glyphs")
	replacement_markers = candidate_text.count("\uFFFD") + len(re.findall(
		r"&#(?:x0*FFFD|0*65533);",
		candidate_text,
		flags=re.I,
	))
	if replacement_markers:
		raise ValueError("replacement characters or entities")


#============================================
def require_admission_gate(config: PromotionConfig) -> str:
	"""Verify candidate-bound content gates and return its admitted SHA-256."""
	manifest_path = config.candidate.parent / "admission_gate.json"
	admission = json.loads(manifest_path.read_text(encoding="utf-8"))
	candidate_sha = admission["candidate_sha256"]
	if candidate_sha != sha256(config.candidate):
		raise ValueError("admission manifest candidate hash mismatch")
	fidelity = admission["source_fidelity"]
	table_figure = admission["table_figure"]
	if fidelity["status"] != "PASS" or table_figure["status"] != "PASS":
		raise ValueError("source fidelity or table/figure gate not passed")
	basis = fidelity["basis"]
	if basis == "independent_source_review":
		source = admission["source_path"]
		source_sha = admission["source_sha256"]
		source_path = pathlib.Path(source)
		if sha256(source_path) != source_sha:
			raise ValueError("admission source hash mismatch")
		review_path = pathlib.Path(fidelity["review_receipt_path"])
		if not review_path.is_absolute():
			review_path = config.candidate.parent / review_path
		review = json.loads(review_path.read_text(encoding="utf-8"))
		if review.get("decision") != "ACCEPT":
			raise ValueError("independent source review is not accepted")
		review_candidate = review.get("candidate", {})
		review_source = review.get("source", {})
		if review_candidate.get("sha256") != candidate_sha:
			raise ValueError("independent review candidate hash mismatch")
		if review_source.get("sha256") != source_sha:
			raise ValueError("independent review source hash mismatch")
		if config.mode == DIRECT_CANONICAL_REPLACEMENT:
			candidate_label_value = review_candidate.get("path")
			if not isinstance(candidate_label_value, str) or not candidate_label_value:
				raise ValueError("independent review candidate path is missing")
			candidate_label = pathlib.Path(candidate_label_value)
			if not candidate_label.is_absolute():
				raise ValueError("independent review candidate path must be absolute")
			if candidate_label.resolve() != config.candidate.resolve():
				raise ValueError("independent review candidate path mismatch")
			source_label_value = review_source.get("path")
			if not isinstance(source_label_value, str) or not source_label_value:
				raise ValueError("independent review source path is missing")
			source_label = pathlib.Path(source_label_value)
			if not source_label.is_absolute():
				raise ValueError("independent review source path must be absolute")
			if source_label.resolve() != source_path.resolve():
				raise ValueError("independent review source path mismatch")
		if not review.get("reviewer") or not review.get("scope_checked"):
			raise ValueError("independent review receipt lacks reviewer or scope")
	else:
		raise ValueError("promotion requires independent source review")
	lifecycle = admission.get("lifecycle")
	if config.mode == NEW_TITLE_NO_PREDECESSOR:
		if not isinstance(lifecycle, dict):
			raise ValueError("new title requires a lifecycle declaration")
		if lifecycle["mode"] != NEW_TITLE_NO_PREDECESSOR:
			raise ValueError("new-title mode conflicts with admission lifecycle")
		if "admission_status" not in lifecycle or lifecycle["admission_status"] != "ACCEPTED":
			raise ValueError("new-title admission status is not accepted")
		if lifecycle["expected_absent_pending"] != str(config.expected_absent_pending):
			raise ValueError("admission expected pending path does not match invocation")
		if lifecycle["destination"] != str(config.destination):
			raise ValueError("admission destination does not match invocation")
	elif lifecycle is not None and lifecycle["mode"] != SUPERSEDES_PENDING:
		if config.mode != DIRECT_CANONICAL_REPLACEMENT or lifecycle["mode"] != DIRECT_CANONICAL_REPLACEMENT:
			raise ValueError("replacement conflicts with admission lifecycle")
	if config.mode == DIRECT_CANONICAL_REPLACEMENT:
		if not isinstance(lifecycle, dict) or lifecycle.get("mode") != DIRECT_CANONICAL_REPLACEMENT:
			raise ValueError("direct replacement requires a lifecycle declaration")
		if lifecycle.get("destination") != str(config.destination):
			raise ValueError("admission destination does not match invocation")
		if lifecycle.get("expected_predecessor_sha256") != config.expected_predecessor_sha256:
			raise ValueError("admission predecessor hash does not match invocation")
		if fidelity["basis"] != "independent_source_review":
			raise ValueError("direct replacement requires independent source review")
		review_path = pathlib.Path(fidelity["review_receipt_path"])
		if not review_path.is_absolute():
			review_path = config.candidate.parent / review_path
		review = json.loads(review_path.read_text(encoding="utf-8"))
		predecessor = review.get("predecessor", {})
		if review.get("destination") != str(config.destination):
			raise ValueError("independent review destination mismatch")
		if predecessor.get("sha256") != config.expected_predecessor_sha256:
			raise ValueError("independent review predecessor hash mismatch")
		if predecessor.get("path") != str(config.destination):
			raise ValueError("independent review predecessor path mismatch")
	return candidate_sha


#============================================
def default_validator_runner(validator: pathlib.Path, candidate: pathlib.Path) -> int:
	"""Run one validator through the current Python interpreter."""
	# ASVS 1.2.5: Pass validator paths as arguments without invoking a shell.
	result = subprocess.run([sys.executable, str(validator), str(candidate)], check=False)
	returncode = result.returncode
	return returncode


#============================================
def require_validators(config: PromotionConfig, validator_runner: ValidatorRunner) -> None:
	"""Require the supplied delivery validator and repository v2 validator."""
	mandatory_validator = pathlib.Path(__file__).with_name("validate_markdown_v2.py")
	validators = [config.validator]
	if config.validator != mandatory_validator:
		validators.append(mandatory_validator)
	for validator in validators:
		if validator_runner(validator, config.candidate) != 0:
			raise ValueError(f"validator failed: {validator}")


#============================================
def require_bound_admission(config: PromotionConfig, admitted_sha: str) -> None:
	"""Recheck the validator-bound admission SHA under the publication lock."""
	current_sha = require_admission_gate(config)
	if current_sha != admitted_sha:
		raise ValueError("admission manifest changed after validation")
