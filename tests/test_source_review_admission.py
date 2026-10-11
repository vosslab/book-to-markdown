"""Protect source-review-based promotion from numeric fidelity cutoffs."""

# Standard Library
import hashlib
import json
import pathlib

# Third-Party
import pytest

# Local
import promote_validated_candidate as promoter


def make_admission(tmp_path: pathlib.Path, basis: str) -> promoter.PromotionConfig:
	"""Write a minimal candidate-bound new-title admission package."""
	stage = tmp_path / "stage"
	stage.mkdir()
	candidate = stage / "candidate.md"
	source = stage / "source.pdf"
	review_path = stage / "review.json"
	candidate.write_text("# Complete enough for independent review\n", encoding="ascii")
	source.write_bytes(b"source bytes")
	candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
	source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
	review = {
		"decision": "ACCEPT",
		"candidate": {"path": str(candidate), "sha256": candidate_sha},
		"source": {"path": str(source), "sha256": source_sha},
		"reviewer": "independent reviewer",
		"scope_checked": ["meaningful content", "structure", "context"],
	}
	review_path.write_text(json.dumps(review), encoding="utf-8")
	fidelity = {"status": "PASS", "basis": basis}
	if basis == "independent_source_review":
		fidelity["review_receipt_path"] = str(review_path)
	elif basis == "direct_source_word_count":
		fidelity.update({"source_words": 1000, "candidate_words": 1})
	elif basis == "complete_source_disposition":
		fidelity["unaccounted_words"] = 0
	manifest = {
		"candidate_sha256": candidate_sha,
		"source_path": str(source),
		"source_sha256": source_sha,
		"source_fidelity": fidelity,
		"table_figure": {"status": "PASS"},
		"lifecycle": {
			"mode": promoter.NEW_TITLE_NO_PREDECESSOR,
			"admission_status": "ACCEPTED",
			"expected_absent_pending": str(tmp_path / "PENDING"),
			"destination": str(tmp_path / "delivery" / "title.md"),
		},
	}
	(stage / "admission_gate.json").write_text(json.dumps(manifest), encoding="utf-8")
	return promoter.PromotionConfig.new_title(
		candidate,
		pathlib.Path(manifest["lifecycle"]["destination"]),
		pathlib.Path(manifest["lifecycle"]["expected_absent_pending"]),
		stage / "validator.py",
	)


def test_independent_review_admits_lossy_word_count_metrics_as_diagnostics(
		tmp_path: pathlib.Path) -> None:
	config = make_admission(tmp_path, "independent_source_review")
	manifest_path = config.candidate.parent / "admission_gate.json"
	manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
	manifest["source_fidelity"].update({
		"source_words": 1000,
		"candidate_words": 1,
		"unaccounted_words": 500,
	})
	manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

	assert promoter.require_admission_gate(config) == manifest["candidate_sha256"]


@pytest.mark.parametrize(
		"basis", ["direct_source_word_count", "complete_source_disposition"],
)
def test_numeric_accounting_cannot_admit_without_independent_review(
		tmp_path: pathlib.Path, basis: str) -> None:
	config = make_admission(tmp_path, basis)

	with pytest.raises(ValueError, match="promotion requires independent source review"):
		promoter.require_admission_gate(config)
