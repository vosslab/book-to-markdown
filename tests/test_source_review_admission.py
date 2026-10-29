"""Protect source-review-based promotion from numeric fidelity cutoffs."""

# Standard Library
import hashlib
import json
import os
import pathlib
import stat

# Third-Party
import pytest

# Local
import audit.promotion_admission as admission
import promote_validated_candidate as promoter


def make_admission(tmp_path: pathlib.Path, basis: str) -> admission.PromotionConfig:
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
			"mode": admission.NEW_TITLE_NO_PREDECESSOR,
			"admission_status": "ACCEPTED",
			"expected_absent_pending": str(tmp_path / "PENDING"),
			"destination": str(tmp_path / "delivery" / "title.md"),
		},
	}
	(stage / "admission_gate.json").write_text(json.dumps(manifest), encoding="utf-8")
	return admission.PromotionConfig.new_title(
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

	assert admission.require_admission_gate(config) == manifest["candidate_sha256"]


@pytest.mark.parametrize(
		"basis", ["direct_source_word_count", "complete_source_disposition"],
)
def test_numeric_accounting_cannot_admit_without_independent_review(
		tmp_path: pathlib.Path, basis: str) -> None:
	config = make_admission(tmp_path, basis)

	with pytest.raises(ValueError, match="promotion requires independent source review"):
		admission.require_admission_gate(config)


def test_new_title_rejects_initial_dangling_pending_symlink_without_mutation(
		tmp_path: pathlib.Path) -> None:
	config = make_admission(tmp_path, "independent_source_review")
	candidate_sha = hashlib.sha256(config.candidate.read_bytes()).hexdigest()
	pending_target = tmp_path / "missing-pending-target"
	config.expected_absent_pending.symlink_to(pending_target)

	with pytest.raises(ValueError, match="expected absent pending path exists"):
		promoter.promote(config, lambda validator, candidate: 0)

	assert not config.destination.exists()
	assert stat.S_ISLNK(os.lstat(config.expected_absent_pending).st_mode)
	assert os.readlink(config.expected_absent_pending) == str(pending_target)
	assert hashlib.sha256(config.candidate.read_bytes()).hexdigest() == candidate_sha


def test_new_title_rolls_back_owned_canonical_when_pending_symlink_appears_after_link(
		tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
	config = make_admission(tmp_path, "independent_source_review")
	candidate_sha = hashlib.sha256(config.candidate.read_bytes()).hexdigest()
	original_link = promoter.os.link
	pending_target = tmp_path / "missing-pending-target"
	foreign_canonical = b"foreign canonical replacement\n"

	def replace_canonical_then_create_pending(
			source: pathlib.Path, destination: pathlib.Path) -> None:
		original_link(source, destination)
		destination.unlink()
		destination.write_bytes(foreign_canonical)
		config.expected_absent_pending.symlink_to(pending_target)

	monkeypatch.setattr(promoter.os, "link", replace_canonical_then_create_pending)

	with pytest.raises(ValueError, match="expected absent pending path exists"):
		promoter.promote(config, lambda validator, candidate: 0)

	assert config.destination.read_bytes() == foreign_canonical
	assert stat.S_ISLNK(os.lstat(config.expected_absent_pending).st_mode)
	assert os.readlink(config.expected_absent_pending) == str(pending_target)
	assert hashlib.sha256(config.candidate.read_bytes()).hexdigest() == candidate_sha


def test_new_title_with_absent_pending_path_publishes_and_retains_candidate(
		tmp_path: pathlib.Path) -> None:
	config = make_admission(tmp_path, "independent_source_review")
	candidate_bytes = config.candidate.read_bytes()
	pending_path = config.expected_absent_pending

	result = promoter.promote(config, lambda validator, candidate: 0)

	assert config.destination.read_bytes() == candidate_bytes
	assert config.candidate.read_bytes() == candidate_bytes
	assert not os.path.lexists(pending_path)
	assert result["lifecycle_mode"] == admission.NEW_TITLE_NO_PREDECESSOR
	assert result["superseded"] is None
