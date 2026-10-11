"""Protect the data-safety contract of direct canonical replacement."""

# Standard Library
import hashlib
import json
import os
import pathlib

# Third-Party
import pytest

# Local
import promote_validated_candidate as promoter


def make_replacement(tmp_path: pathlib.Path) -> tuple[
		promoter.PromotionConfig, pathlib.Path, pathlib.Path, pathlib.Path, bytes, bytes]:
	"""Create a valid isolated admission for the real direct replacement path."""
	stage = tmp_path / "stage"
	destination = tmp_path / "SORTED_SUBJECTS_MD" / "biology" / "sample.md"
	backup_root = tmp_path / "superseded"
	candidate = stage / "sample.md"
	source = stage / "source.txt"
	review_path = stage / "review.json"
	manifest_path = stage / "admission_gate.json"
	old_bytes = b"# Previous title\n\nPrevious content.\n"
	candidate_bytes = b"# Updated title\n\nUpdated content.\n"
	destination.parent.mkdir(parents=True)
	stage.mkdir()
	destination.write_bytes(old_bytes)
	candidate.write_bytes(candidate_bytes)
	source.write_bytes(b"source material\n")
	old_sha = hashlib.sha256(old_bytes).hexdigest()
	candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
	source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
	review = {
		"decision": "ACCEPT",
		"candidate": {"path": str(candidate), "sha256": candidate_sha},
		"source": {"path": str(source), "sha256": source_sha},
		"destination": str(destination),
		"predecessor": {"path": str(destination), "sha256": old_sha},
		"reviewer": "independent reviewer",
		"scope_checked": ["complete source", "candidate"],
	}
	review_path.write_text(json.dumps(review), encoding="utf-8")
	manifest = {
		"candidate_sha256": candidate_sha,
		"source_path": str(source),
		"source_sha256": source_sha,
		"source_fidelity": {
			"status": "PASS",
			"basis": "independent_source_review",
			"review_receipt_path": str(review_path),
		},
		"table_figure": {"status": "PASS"},
		"lifecycle": {
			"mode": promoter.DIRECT_CANONICAL_REPLACEMENT,
			"destination": str(destination),
			"expected_predecessor_sha256": old_sha,
		},
	}
	manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
	config = promoter.PromotionConfig.replace_canonical(
		candidate, destination, backup_root, tmp_path / "validator.py", old_sha,
	)
	backup = promoter.subject_superseded_path(config)
	return config, candidate, destination, backup, old_bytes, candidate_bytes


def run_real_promoter(config: promoter.PromotionConfig) -> dict[str, object]:
	"""Skip only external validator processes while executing real promotion code."""
	def validators_pass(validator: pathlib.Path, candidate: pathlib.Path) -> int:
		return 0

	return promoter.promote(config, validators_pass)


def test_direct_replacement_retains_predecessor_and_candidate_binding(
		tmp_path: pathlib.Path) -> None:
	config, candidate, destination, backup, old_bytes, candidate_bytes = make_replacement(tmp_path)

	result = run_real_promoter(config)

	assert destination.read_bytes() == candidate_bytes
	assert backup.read_bytes() == old_bytes
	assert candidate.read_bytes() == candidate_bytes
	assert result["replacement_status"] == "REPLACED"
	assert result["superseded_sha256"] == hashlib.sha256(old_bytes).hexdigest()


def test_stale_predecessor_is_rejected_before_any_promotion_mutation(
		tmp_path: pathlib.Path) -> None:
	config, candidate, destination, backup, old_bytes, candidate_bytes = make_replacement(tmp_path)
	destination.write_bytes(b"a newer canonical version\n")

	with pytest.raises(ValueError, match="predecessor hash does not match admission"):
		run_real_promoter(config)

	assert destination.read_bytes() == b"a newer canonical version\n"
	assert candidate.read_bytes() == candidate_bytes
	assert not backup.exists()


@pytest.mark.parametrize(
		("receipt_file", "path_state"),
		[
			("candidate", "missing"),
			("source", "missing"),
			("candidate", "relative"),
			("source", "relative"),
			("candidate", "mismatch"),
			("source", "mismatch"),
		],
)
def test_independent_review_rejects_wrong_path_label_before_mutation(
		tmp_path: pathlib.Path, receipt_file: str, path_state: str,
		) -> None:
	config, candidate, destination, backup, old_bytes, candidate_bytes = make_replacement(tmp_path)
	review_path = candidate.parent / "review.json"
	review = json.loads(review_path.read_text(encoding="utf-8"))
	if path_state == "missing":
		del review[receipt_file]["path"]
	elif path_state == "relative":
		review[receipt_file]["path"] = "different-file-with-same-hash.txt"
	else:
		review[receipt_file]["path"] = str(tmp_path / "different-file-with-same-hash.txt")
	review_path.write_text(json.dumps(review), encoding="utf-8")

	if path_state == "missing":
		error = f"independent review {receipt_file} path is missing"
	elif path_state == "relative":
		error = f"independent review {receipt_file} path must be absolute"
	else:
		error = f"independent review {receipt_file} path mismatch"
	with pytest.raises(ValueError, match=error):
		run_real_promoter(config)

	assert destination.read_bytes() == old_bytes
	assert candidate.read_bytes() == candidate_bytes
	assert not backup.exists()


def test_existing_backup_is_never_clobbered(tmp_path: pathlib.Path) -> None:
	config, candidate, destination, backup, old_bytes, candidate_bytes = make_replacement(tmp_path)
	backup.parent.mkdir(parents=True)
	backup.write_bytes(b"operator recovery evidence\n")

	with pytest.raises(FileExistsError, match="superseded destination already exists"):
		run_real_promoter(config)

	assert destination.read_bytes() == old_bytes
	assert backup.read_bytes() == b"operator recovery evidence\n"
	assert candidate.read_bytes() == candidate_bytes


@pytest.mark.parametrize("failure", ["backup_write", "backup_readback"])
def test_precommit_backup_failure_preserves_canonical_and_cleans_owned_partial_backup(
		tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, failure: str,
		) -> None:
	config, candidate, destination, backup, old_bytes, candidate_bytes = make_replacement(tmp_path)
	original_open = promoter.os.open
	original_write = promoter.os.write
	backup_descriptors: set[int] = set()

	def track_backup_open(path: str | bytes | os.PathLike[str], flags: int,
			mode: int = 0o777) -> int:
		descriptor = original_open(path, flags, mode)
		if pathlib.Path(path) == backup:
			backup_descriptors.add(descriptor)
		return descriptor

	def fail_backup_write(descriptor: int, content: bytes) -> int:
		if failure == "backup_write" and descriptor in backup_descriptors:
			raise OSError("injected backup write failure")
		return original_write(descriptor, content)

	original_sha256 = promoter.sha256

	def fail_backup_readback(path: pathlib.Path) -> str:
		if failure == "backup_readback" and path == backup and path.exists():
			if path.read_bytes() == old_bytes:
				raise OSError("injected backup readback failure")
		return original_sha256(path)

	monkeypatch.setattr(promoter.os, "open", track_backup_open)
	monkeypatch.setattr(promoter.os, "write", fail_backup_write)
	monkeypatch.setattr(promoter, "sha256", fail_backup_readback)

	with pytest.raises(OSError):
		run_real_promoter(config)

	assert destination.read_bytes() == old_bytes
	assert candidate.read_bytes() == candidate_bytes
	assert not backup.exists()


def test_atomic_replace_failure_keeps_canonical_and_verified_recovery_backup(
		tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
	config, candidate, destination, backup, old_bytes, candidate_bytes = make_replacement(tmp_path)

	def fail_replace(source: str | bytes | os.PathLike[str],
			target: str | bytes | os.PathLike[str]) -> None:
		raise OSError("injected atomic replacement failure")

	monkeypatch.setattr(promoter.os, "replace", fail_replace)

	with pytest.raises(OSError, match="verified predecessor backup"):
		run_real_promoter(config)

	assert destination.read_bytes() == old_bytes
	assert backup.read_bytes() == old_bytes
	assert candidate.read_bytes() == candidate_bytes


def test_mutated_completed_backup_blocks_replace_and_retains_conflict_evidence(
		tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
	config, candidate, destination, backup, old_bytes, candidate_bytes = make_replacement(tmp_path)
	original_verify = promoter.require_verified_predecessor_backup
	mutated_bytes = b"tampered recovery evidence\n"

	def mutate_completed_backup(path: pathlib.Path, expected_sha: str,
			expected_version: promoter.FileVersion) -> None:
		backup.write_bytes(mutated_bytes)
		original_verify(path, expected_sha, expected_version)

	monkeypatch.setattr(
		promoter, "require_verified_predecessor_backup", mutate_completed_backup,
	)

	with pytest.raises(OSError, match="canonical remains at .*inspect backup conflict"):
		run_real_promoter(config)

	assert destination.read_bytes() == old_bytes
	assert backup.read_bytes() == mutated_bytes
	assert candidate.read_bytes() == candidate_bytes


@pytest.mark.parametrize("failure", ["canonical_fsync", "canonical_readback"])
def test_postcommit_failure_reports_committed_state_and_retains_recovery_evidence(
		tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, failure: str,
		) -> None:
	config, candidate, destination, backup, old_bytes, candidate_bytes = make_replacement(tmp_path)
	original_fsync_file = promoter.fsync_file
	original_sha256 = promoter.sha256

	def fail_commit_fsync(path: pathlib.Path) -> None:
		if failure == "canonical_fsync" and path == destination:
			raise OSError("injected canonical fsync failure")
		original_fsync_file(path)

	def fail_commit_readback(path: pathlib.Path) -> str:
		if (failure == "canonical_readback" and path == destination
				and path.read_bytes() == candidate_bytes):
			raise OSError("injected canonical readback failure")
		return original_sha256(path)

	monkeypatch.setattr(promoter, "fsync_file", fail_commit_fsync)
	monkeypatch.setattr(promoter, "sha256", fail_commit_readback)

	result = run_real_promoter(config)

	assert destination.read_bytes() == candidate_bytes
	assert backup.read_bytes() == old_bytes
	assert candidate.read_bytes() == candidate_bytes
	assert result["replacement_status"] == "RECOVERY_REQUIRED"
	assert result["cleanup"]["canonical"] == str(destination)
