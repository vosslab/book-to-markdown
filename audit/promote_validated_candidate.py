#!/usr/bin/env python3
"""Promote a validated Markdown candidate through an explicit lifecycle mode.

Usage:
  ./audit/promote_validated_candidate.py \
    CANDIDATE DESTINATION PENDING SUPERSEDED_ROOT VALIDATOR
  ./audit/promote_validated_candidate.py --new-title \
    CANDIDATE DESTINATION EXPECTED_ABSENT_PENDING VALIDATOR
"""

# Standard Library
import contextlib
import dataclasses
import fcntl
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from collections import abc
from datetime import datetime


NEW_TITLE_NO_PREDECESSOR = "NEW_TITLE_NO_PREDECESSOR"
SUPERSEDES_PENDING = "SUPERSEDES_PENDING"
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


@dataclasses.dataclass(frozen=True)
class FileVersion:
	"""Identify one candidate version without trusting its mutable pathname."""
	device: int
	inode: int
	size: int
	modified_ns: int
	changed_ns: int


@dataclasses.dataclass(frozen=True)
class PublicationSnapshot:
	"""Pair admitted publication bytes with the staged candidate version read."""
	snapshot: pathlib.Path
	candidate_version: FileVersion


#============================================
def parse_config(arguments: list[str]) -> PromotionConfig:
	"""Parse the two supported, unambiguous promoter invocations."""
	if arguments and arguments[0] == "--new-title":
		if len(arguments) != 5:
			raise ValueError("usage: --new-title CANDIDATE DESTINATION EXPECTED_ABSENT_PENDING VALIDATOR")
		candidate, destination, pending, validator = map(pathlib.Path, arguments[1:])
		config = PromotionConfig.new_title(candidate, destination, pending, validator)
		return config
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
	"""Reject unresolved glyph and entity degradation before publication."""
	candidate_text = candidate.read_text(encoding="utf-8", errors="replace")
	unresolved_markers = (
		candidate_text.count("[unmapped-PDF-glyph-")
		+ candidate_text.count("[unresolved source glyph]")
	)
	if unresolved_markers:
		raise ValueError("unresolved source glyphs")
	pointless_entities = len(re.findall(r"&lt;|&gt;", candidate_text, flags=re.I))
	degradation_entities = len(re.findall(
		r"&#(?:x?FFFD|0*65533|x?00A2|x?00A3|x?20AC|x?163|x?162);|&(?:cent|pound|euro);",
		candidate_text,
		flags=re.I,
	))
	if pointless_entities or degradation_entities:
		raise ValueError("disallowed entity classes")


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
	if basis == "direct_source_word_count":
		source_words = fidelity["source_words"]
		candidate_words = fidelity["candidate_words"]
		if not isinstance(source_words, int) or source_words <= 0:
			raise ValueError("invalid direct-source word accounting")
		if not isinstance(candidate_words, int) or candidate_words <= 0:
			raise ValueError("invalid direct-source word accounting")
		if abs(candidate_words - source_words) / source_words > 0.01:
			raise ValueError("direct-source word fidelity exceeds 1%")
	elif basis == "complete_source_disposition":
		if fidelity["unaccounted_words"] != 0:
			raise ValueError("incomplete source disposition accounting")
	else:
		raise ValueError("unsupported source-fidelity basis")
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
		raise ValueError("legacy replacement conflicts with admission lifecycle")
	return candidate_sha


#============================================
def default_validator_runner(validator: pathlib.Path, candidate: pathlib.Path) -> int:
	"""Run one validator through the current Python interpreter."""
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
def fsync_file(path: pathlib.Path) -> None:
	"""Flush one published file before source cleanup."""
	file_descriptor = os.open(path, os.O_RDONLY)
	os.fsync(file_descriptor)
	os.close(file_descriptor)


#============================================
def fsync_directory(path: pathlib.Path) -> None:
	"""Flush a directory entry update to its filesystem."""
	directory_descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
	os.fsync(directory_descriptor)
	os.close(directory_descriptor)


#============================================
def file_version(stat_result: os.stat_result) -> FileVersion:
	"""Return the inode and Linux change metadata for one observed file version."""
	version = FileVersion(
		stat_result.st_dev,
		stat_result.st_ino,
		stat_result.st_size,
		stat_result.st_mtime_ns,
		stat_result.st_ctime_ns,
	)
	return version


#============================================
def nearest_existing_ancestor(path: pathlib.Path) -> pathlib.Path:
	"""Return the nearest existing directory at or above one planned path."""
	ancestor = path
	while not ancestor.exists():
		parent = ancestor.parent
		if parent == ancestor:
			raise FileNotFoundError(f"no existing destination ancestor for {path}")
		ancestor = parent
	return ancestor


#============================================
def require_same_filesystem(source: pathlib.Path, destination_parent: pathlib.Path) -> None:
	"""Reject cross-filesystem publication before destination directories exist."""
	destination_ancestor = nearest_existing_ancestor(destination_parent)
	if os.stat(source).st_dev != os.stat(destination_ancestor).st_dev:
		raise OSError("candidate and canonical destination must share a filesystem")


#============================================
def require_bound_admission(config: PromotionConfig, admitted_sha: str) -> None:
	"""Recheck the validator-bound admission SHA under the publication lock."""
	current_sha = require_admission_gate(config)
	if current_sha != admitted_sha:
		raise ValueError("admission manifest changed after validation")


#============================================
def transition_admission_status(config: PromotionConfig, status: str) -> None:
	"""Change a new-title admission status under its title lifecycle reservation."""
	if config.mode != NEW_TITLE_NO_PREDECESSOR:
		raise ValueError("only new-title admission status may transition")
	manifest_path = config.candidate.parent / "admission_gate.json"
	with pending_lifecycle_reservation(config.expected_absent_pending):
		admission = json.loads(manifest_path.read_text(encoding="utf-8"))
		lifecycle = admission["lifecycle"]
		if lifecycle["mode"] != NEW_TITLE_NO_PREDECESSOR:
			raise ValueError("new-title mode conflicts with admission lifecycle")
		lifecycle["admission_status"] = status
		manifest_path.write_text(json.dumps(admission), encoding="ascii")
		fsync_file(manifest_path)
		fsync_directory(manifest_path.parent)


#============================================
def subject_superseded_path(config: PromotionConfig) -> pathlib.Path:
	"""Return the legacy subject-scoped predecessor backup destination."""
	if config.predecessor is None or config.superseded_root is None:
		raise ValueError("legacy replacement requires predecessor and superseded root")
	subject = config.destination.parent.name
	root = config.superseded_root
	subject_root = root if root.name == subject else root / subject
	superseded = subject_root / config.predecessor.name
	return superseded


#============================================
@contextlib.contextmanager
def promotion_lock(destination: pathlib.Path) -> abc.Iterator[None]:
	"""Hold the shared canonical-destination lock across final publication."""
	destination.parent.mkdir(parents=True, exist_ok=True)
	canonical_title = str(destination.resolve(strict=False)).encode("utf-8")
	lock_name = hashlib.sha256(canonical_title).hexdigest()
	lock_path = destination.parent / f".{lock_name}.promotion.lock"
	with lock_path.open("a+", encoding="ascii") as lock_file:
		fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
		try:
			yield
		finally:
			fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


#============================================
@contextlib.contextmanager
def pending_lifecycle_reservation(pending: pathlib.Path) -> abc.Iterator[None]:
	"""Serialize every title-specific PENDING creation and final lifecycle transition."""
	pending.parent.mkdir(parents=True, exist_ok=True)
	pending_title = str(pending.resolve(strict=False)).encode("utf-8")
	lock_name = hashlib.sha256(pending_title).hexdigest()
	lock_path = pending.parent / f".{lock_name}.pending.lifecycle.lock"
	with lock_path.open("a+", encoding="ascii") as lock_file:
		fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
		try:
			yield
		finally:
			fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


#============================================
def write_all(file_descriptor: int, content: bytes) -> None:
	"""Write every content byte to an already-owned artifact descriptor."""
	position = 0
	while position < len(content):
		written = os.write(file_descriptor, content[position:])
		if written == 0:
			raise OSError("could not write PENDING artifact")
		position += written


#============================================
def create_pending_artifact(
		pending: pathlib.Path, destination: pathlib.Path, content: bytes) -> None:
	"""Create one title-specific PENDING file under the shared no-clobber reservation."""
	with pending_lifecycle_reservation(pending):
		if destination.exists():
			raise FileExistsError(f"canonical destination already exists: {destination}")
		file_descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
		try:
			write_all(file_descriptor, content)
			os.fsync(file_descriptor)
		except OSError:
			owned_version = file_version(os.fstat(file_descriptor))
			os.close(file_descriptor)
			remove_candidate_if_unchanged(pending, owned_version)
			raise
		os.close(file_descriptor)
		fsync_directory(pending.parent)


#============================================
def cleanup_failed_snapshot(
		source_descriptor: int | None,
		snapshot_descriptor: int | None,
		snapshot: pathlib.Path | None,
		) -> None:
	"""Close, unlink, and persist removal of a partially-created owned snapshot."""
	try:
		if source_descriptor is not None:
			os.close(source_descriptor)
	finally:
		try:
			if snapshot_descriptor is not None:
				os.close(snapshot_descriptor)
		finally:
			if snapshot is not None:
				try:
					os.unlink(snapshot)
				except FileNotFoundError:
					pass
				fsync_directory(snapshot.parent)


#============================================
def create_admitted_snapshot(
		candidate: pathlib.Path,
		destination_parent: pathlib.Path,
		admitted_sha: str,
		) -> PublicationSnapshot:
	"""Copy admitted bytes into a distinct same-filesystem link source."""
	source_descriptor: int | None = None
	snapshot_descriptor: int | None = None
	snapshot: pathlib.Path | None = None
	try:
		snapshot_descriptor, snapshot_name = tempfile.mkstemp(
			prefix=f".{candidate.name}.", suffix=".promotion.snapshot", dir=destination_parent,
		)
		snapshot = pathlib.Path(snapshot_name)
		source_descriptor = os.open(candidate, os.O_RDONLY)
		candidate_version = file_version(os.fstat(source_descriptor))
		while True:
			block = os.read(source_descriptor, 1024 * 1024)
			if not block:
				break
			write_all(snapshot_descriptor, block)
		os.fsync(snapshot_descriptor)
	except OSError:
		cleanup_failed_snapshot(source_descriptor, snapshot_descriptor, snapshot)
		raise
	os.close(source_descriptor)
	source_descriptor = None
	os.close(snapshot_descriptor)
	snapshot_descriptor = None
	if snapshot is None:
		raise RuntimeError("snapshot creation returned no path")
	if sha256(snapshot) != admitted_sha:
		remove_snapshot(snapshot)
		raise ValueError("candidate changed before immutable publication snapshot")
	publication_snapshot = PublicationSnapshot(snapshot, candidate_version)
	return publication_snapshot


#============================================
def remove_owned_canonical_link(destination: pathlib.Path, snapshot: pathlib.Path) -> None:
	"""Remove a canonical only when this invocation linked the snapshot inode."""
	try:
		destination_stat = os.stat(destination)
	except FileNotFoundError:
		return
	if os.path.samestat(destination_stat, os.stat(snapshot)):
		os.unlink(destination)
		fsync_directory(destination.parent)


#============================================
def remove_candidate_if_unchanged(candidate: pathlib.Path, expected: FileVersion) -> None:
	"""Remove only the unchanged staged pathname, never a replacement symlink."""
	try:
		current = file_version(os.lstat(candidate))
	except FileNotFoundError:
		return
	if current != expected:
		return
	os.unlink(candidate)
	fsync_directory(candidate.parent)


#============================================
def remove_snapshot(snapshot: pathlib.Path) -> None:
	"""Remove one temporary publication snapshot after its terminal outcome."""
	if snapshot.exists():
		os.unlink(snapshot)
		fsync_directory(snapshot.parent)


#============================================
def require_new_title_publication_preconditions(config: PromotionConfig) -> None:
	"""Require final new-title lifecycle absence before canonical linking."""
	if config.expected_absent_pending.exists():
		raise ValueError("expected absent pending path exists")
	if config.destination.exists():
		raise FileExistsError(f"canonical destination already exists: {config.destination}")


#============================================
def require_replacement_publication_preconditions(
		config: PromotionConfig, superseded: pathlib.Path) -> None:
	"""Require final replacement lifecycle sources and destinations under the title lock."""
	if config.predecessor is None or not config.predecessor.is_file():
		raise ValueError("pending predecessor artifact must exist")
	if config.destination.exists():
		raise FileExistsError(f"canonical destination already exists: {config.destination}")
	if superseded.exists():
		raise FileExistsError(f"superseded destination already exists: {superseded}")


#============================================
def verify_canonical_commit(destination: pathlib.Path, admitted_sha: str) -> None:
	"""Read back and durably acknowledge the irreversible canonical publication."""
	fsync_file(destination)
	if sha256(destination) != admitted_sha:
		raise OSError("published canonical hash differs from admitted candidate")
	fsync_file(destination)
	fsync_directory(destination.parent)


#============================================
def cleanup_recovery_evidence(
		destination: pathlib.Path, candidate: pathlib.Path, action: str, error: OSError,
		) -> dict[str, str]:
	"""Describe a recoverable post-commit cleanup failure without exposing error text."""
	evidence = {
		"status": "RECOVERY_REQUIRED",
		"canonical": str(destination),
		"candidate": str(candidate),
		"action": action,
		"error_type": type(error).__name__,
	}
	return evidence


#============================================
def publish_new_title(
		config: PromotionConfig, admitted_sha: str) -> tuple[pathlib.Path | None, dict[str, str] | None]:
	"""Link-publish one new canonical without a fabricated predecessor artifact."""
	require_same_filesystem(config.candidate, config.destination.parent)
	with pending_lifecycle_reservation(config.expected_absent_pending):
		with promotion_lock(config.destination):
			require_bound_admission(config, admitted_sha)
			publication_snapshot = create_admitted_snapshot(
				config.candidate, config.destination.parent, admitted_sha,
			)
			canonical_created = False
			try:
				require_new_title_publication_preconditions(config)
				require_bound_admission(config, admitted_sha)
				os.link(publication_snapshot.snapshot, config.destination)
				canonical_created = True
				if config.expected_absent_pending.exists():
					raise ValueError("expected absent pending path exists")
				verify_canonical_commit(config.destination, admitted_sha)
			except (OSError, ValueError):
				if canonical_created:
					remove_owned_canonical_link(config.destination, publication_snapshot.snapshot)
				remove_snapshot(publication_snapshot.snapshot)
				raise
			cleanup = None
			try:
				remove_snapshot(publication_snapshot.snapshot)
			except OSError as error:
				if cleanup is None:
					cleanup = cleanup_recovery_evidence(
						config.destination, config.candidate, "snapshot_cleanup", error,
					)
		return None, cleanup


#============================================
def publish_replacement(
		config: PromotionConfig, admitted_sha: str) -> tuple[pathlib.Path, dict[str, str] | None]:
	"""Link-publish canonical before performing recoverable legacy cleanup."""
	if config.predecessor is None:
		raise ValueError("legacy replacement requires a predecessor")
	superseded = subject_superseded_path(config)
	require_same_filesystem(config.candidate, config.destination.parent)
	require_same_filesystem(config.predecessor, superseded.parent)
	with pending_lifecycle_reservation(config.predecessor):
		with promotion_lock(config.destination):
			superseded.parent.mkdir(parents=True, exist_ok=True)
			require_bound_admission(config, admitted_sha)
			publication_snapshot = create_admitted_snapshot(
				config.candidate, config.destination.parent, admitted_sha,
			)
			canonical_created = False
			try:
				require_replacement_publication_preconditions(config, superseded)
				require_bound_admission(config, admitted_sha)
				os.link(publication_snapshot.snapshot, config.destination)
				canonical_created = True
				verify_canonical_commit(config.destination, admitted_sha)
			except (OSError, ValueError):
				if canonical_created:
					remove_owned_canonical_link(config.destination, publication_snapshot.snapshot)
				remove_snapshot(publication_snapshot.snapshot)
				raise
			cleanup: dict[str, str] | None = None
			try:
				os.link(config.predecessor, superseded)
				fsync_file(superseded)
				fsync_directory(superseded.parent)
			except OSError as error:
				cleanup = cleanup_recovery_evidence(
					config.destination, config.candidate, "predecessor_backup", error,
				)
			if cleanup is None:
				try:
					os.unlink(config.predecessor)
					fsync_directory(config.predecessor.parent)
				except OSError as error:
					cleanup = cleanup_recovery_evidence(
						config.destination, config.candidate, "predecessor_cleanup", error,
					)
			try:
				remove_snapshot(publication_snapshot.snapshot)
			except OSError as error:
				if cleanup is None:
					cleanup = cleanup_recovery_evidence(
						config.destination, config.candidate, "snapshot_cleanup", error,
					)
	return superseded, cleanup


#============================================
def promote(
		config: PromotionConfig,
		validator_runner: ValidatorRunner = default_validator_runner,
		) -> dict[str, object]:
	"""Validate and atomically publish one configured candidate lifecycle."""
	if not config.candidate.is_file():
		raise ValueError("candidate artifact must exist")
	if config.mode == SUPERSEDES_PENDING:
		if config.predecessor is None or not config.predecessor.is_file():
			raise ValueError("pending predecessor artifact must exist")
	elif config.mode != NEW_TITLE_NO_PREDECESSOR:
		raise ValueError(f"unsupported lifecycle mode: {config.mode}")
	require_clean_content(config.candidate)
	require_admission_gate(config)
	require_validators(config, validator_runner)
	admitted_sha = require_admission_gate(config)
	if config.mode == NEW_TITLE_NO_PREDECESSOR:
		superseded, cleanup = publish_new_title(config, admitted_sha)
	else:
		superseded, cleanup = publish_replacement(config, admitted_sha)
	result: dict[str, object] = {
		"promoted": True,
		"timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
		"destination": str(config.destination),
		"superseded": str(superseded) if superseded is not None else None,
		"lifecycle_mode": config.mode,
		"expected_absent_pending": str(config.expected_absent_pending),
		"cleanup": cleanup,
	}
	return result


#============================================
def main() -> None:
	"""Adapt command-line arguments to the explicit promoter configuration."""
	config = parse_config(sys.argv[1:])
	result = promote(config)
	print(json.dumps(result))


if __name__ == "__main__":
	main()
