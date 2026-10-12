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
import sys
import tempfile
from collections import abc
from datetime import datetime

import audit.promotion_admission as admission


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
def transition_admission_status(config: admission.PromotionConfig, status: str) -> None:
	"""Change a new-title admission status under its title lifecycle reservation."""
	if config.mode != admission.NEW_TITLE_NO_PREDECESSOR:
		raise ValueError("only new-title admission status may transition")
	manifest_path = config.candidate.parent / "admission_gate.json"
	with pending_lifecycle_reservation(config.expected_absent_pending):
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		lifecycle = manifest["lifecycle"]
		if lifecycle["mode"] != admission.NEW_TITLE_NO_PREDECESSOR:
			raise ValueError("new-title mode conflicts with admission lifecycle")
		lifecycle["admission_status"] = status
		manifest_path.write_text(json.dumps(manifest), encoding="ascii")
		fsync_file(manifest_path)
		fsync_directory(manifest_path.parent)


#============================================
def subject_superseded_path(config: admission.PromotionConfig) -> pathlib.Path:
	"""Return the legacy subject-scoped predecessor backup destination."""
	if config.predecessor is None or config.superseded_root is None:
		raise ValueError("legacy replacement requires predecessor and superseded root")
	subject = config.destination.parent.name
	root = config.superseded_root
	subject_root = root if root.name == subject else root / subject
	superseded = subject_root / config.predecessor.name
	return superseded


#============================================
def visible_lock_directory(path: pathlib.Path) -> pathlib.Path:
	"""Return the corpus conversion_state lock directory for one workflow path."""
	for parent in path.parents:
		if parent.name == "conversion_state":
			return parent / "locks"
		if parent.name in {
			"SORTED_SUBJECTS_MD",
			"AUDIT_REPAIR",
			"COMPLETED_SOURCE",
			"DUPLICATE_SOURCE",
			"SKIPPED_SOURCE",
		}:
			return parent.parent / "conversion_state" / "locks"
	return path.parent / "locks"


#============================================
@contextlib.contextmanager
def promotion_lock(destination: pathlib.Path) -> abc.Iterator[None]:
	"""Hold the shared canonical-destination lock across final publication."""
	lock_directory = visible_lock_directory(destination)
	lock_directory.mkdir(parents=True, exist_ok=True)
	canonical_title = str(destination.resolve(strict=False)).encode("utf-8")
	lock_name = hashlib.sha256(canonical_title).hexdigest()
	lock_path = lock_directory / f"promotion-{lock_name}.lock"
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
	lock_directory = visible_lock_directory(pending)
	lock_directory.mkdir(parents=True, exist_ok=True)
	pending_title = str(pending.resolve(strict=False)).encode("utf-8")
	lock_name = hashlib.sha256(pending_title).hexdigest()
	lock_path = lock_directory / f"lifecycle-{lock_name}.lock"
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
	snapshot_prefix = candidate.name.lstrip(".") or "candidate"
	try:
		snapshot_descriptor, snapshot_name = tempfile.mkstemp(
			prefix=f"{snapshot_prefix}.", suffix=".promotion.snapshot", dir=destination_parent,
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
	if admission.sha256(snapshot) != admitted_sha:
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
def require_new_title_publication_preconditions(config: admission.PromotionConfig) -> None:
	"""Require final new-title lifecycle absence before canonical linking."""
	if config.expected_absent_pending.exists():
		raise ValueError("expected absent pending path exists")
	if config.destination.exists():
		raise FileExistsError(f"canonical destination already exists: {config.destination}")


#============================================
def require_replacement_publication_preconditions(
		config: admission.PromotionConfig, superseded: pathlib.Path) -> None:
	"""Require final replacement lifecycle sources and destinations under the title lock."""
	if config.predecessor is None or not config.predecessor.is_file():
		raise ValueError("pending predecessor artifact must exist")
	if config.destination.exists():
		raise FileExistsError(f"canonical destination already exists: {config.destination}")
	if superseded.exists():
		raise FileExistsError(f"superseded destination already exists: {superseded}")


#============================================
def copy_predecessor_backup(
		predecessor: pathlib.Path, backup: pathlib.Path, expected_sha: str,
		expected_version: FileVersion) -> None:
	"""Create and durably verify a no-clobber copy of the exact canonical predecessor."""
	backup.parent.mkdir(parents=True, exist_ok=True)
	flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
	backup_descriptor = os.open(backup, flags, 0o644)
	source_descriptor: int | None = None
	owned_version: FileVersion | None = None
	try:
		try:
			# Keep descriptor identity capture inside cleanup scope: even this first
			# metadata read can fail after O_EXCL has created the backup pathname.
			owned_version = file_version(os.fstat(backup_descriptor))
			try:
				source_descriptor = os.open(predecessor, os.O_RDONLY)
				if file_version(os.fstat(source_descriptor)) != expected_version:
					raise ValueError("canonical predecessor inode changed before backup")
				digest = hashlib.sha256()
				while True:
					block = os.read(source_descriptor, 1024 * 1024)
					if not block:
						break
					digest.update(block)
					write_all(backup_descriptor, block)
				if digest.hexdigest() != expected_sha:
					raise ValueError("canonical predecessor hash changed before backup")
				os.fsync(backup_descriptor)
			except (OSError, ValueError):
				owned_version = file_version(os.fstat(backup_descriptor))
				raise
			owned_version = file_version(os.fstat(backup_descriptor))
		finally:
			if source_descriptor is not None:
				os.close(source_descriptor)
			os.close(backup_descriptor)
		if admission.sha256(backup) != expected_sha:
			raise OSError("superseded backup readback hash mismatch")
		fsync_directory(backup.parent)
	except (OSError, ValueError) as error:
		if owned_version is None:
			raise OSError(
				f"replacement backup recovery required; ownership could not be verified; "
				f"inspect {backup}; canonical remains at {predecessor}"
			) from error
		try:
			if file_version(os.lstat(backup)) == owned_version:
				os.unlink(backup)
				fsync_directory(backup.parent)
		except FileNotFoundError:
			pass
		except OSError as cleanup_error:
			raise OSError(
				f"replacement backup recovery required; inspect {backup}; "
				f"canonical remains at {predecessor}"
			) from cleanup_error
		else:
			try:
				file_version(os.lstat(backup))
			except FileNotFoundError:
				pass
			else:
				raise OSError(
					f"replacement backup recovery required; changed backup left at {backup}; "
					f"canonical remains at {predecessor}"
				) from error
		raise


#============================================
def require_verified_predecessor_backup(
		backup: pathlib.Path, expected_sha: str, expected_version: FileVersion,
		) -> None:
	"""Require the retained backup to keep its copied identity and exact bytes."""
	if file_version(os.lstat(backup)) != expected_version:
		raise ValueError(f"replacement backup changed; inspect {backup}")
	if admission.sha256(backup) != expected_sha:
		raise ValueError(f"replacement backup hash changed; inspect {backup}")
	if file_version(os.lstat(backup)) != expected_version:
		raise ValueError(f"replacement backup changed during verification; inspect {backup}")


#============================================
def publish_direct_replacement(
		config: admission.PromotionConfig, admitted_sha: str, predecessor_version: FileVersion,
		) -> tuple[pathlib.Path, dict[str, str] | None]:
	"""Back up and atomically replace the exact admitted canonical predecessor."""
	if config.expected_predecessor_sha256 is None:
		raise ValueError("direct replacement requires an expected predecessor hash")
	backup = subject_superseded_path(config)
	require_same_filesystem(config.candidate, config.destination.parent)
	with promotion_lock(config.destination):
		current = file_version(os.lstat(config.destination))
		if current != predecessor_version:
			raise ValueError("canonical predecessor inode changed after admission")
		if admission.sha256(config.destination) != config.expected_predecessor_sha256:
			raise ValueError("canonical predecessor hash changed after admission")
		admission.require_bound_admission(config, admitted_sha)
		publication_snapshot = create_admitted_snapshot(
			config.candidate, config.destination.parent, admitted_sha,
		)
		published = False
		backup_version: FileVersion | None = None
		checking_backup = False
		try:
			if file_version(os.lstat(config.destination)) != predecessor_version:
				raise ValueError("canonical predecessor inode changed before replacement")
			if admission.sha256(config.destination) != config.expected_predecessor_sha256:
				raise ValueError("canonical predecessor hash changed before replacement")
			if backup.exists():
				raise FileExistsError(f"superseded destination already exists: {backup}")
			copy_predecessor_backup(
				config.destination, backup, config.expected_predecessor_sha256,
				predecessor_version,
			)
			backup_version = file_version(os.lstat(backup))
			if file_version(os.lstat(config.destination)) != predecessor_version:
				raise ValueError("canonical predecessor inode changed before atomic replacement")
			if admission.sha256(config.destination) != config.expected_predecessor_sha256:
				raise ValueError("canonical predecessor hash changed before atomic replacement")
			checking_backup = True
			require_verified_predecessor_backup(
				backup, config.expected_predecessor_sha256, backup_version,
			)
			checking_backup = False
			os.replace(publication_snapshot.snapshot, config.destination)
			published = True
			fsync_directory(config.destination.parent)
			verify_canonical_commit(config.destination, admitted_sha)
			checking_backup = True
			require_verified_predecessor_backup(
				backup, config.expected_predecessor_sha256, backup_version,
			)
			checking_backup = False
		except (OSError, ValueError) as error:
			remove_snapshot(publication_snapshot.snapshot)
			if published:
				recovery = cleanup_recovery_evidence(
					config.destination, config.candidate,
					"replacement_backup_integrity" if checking_backup else "replacement_readback",
					error,
				)
				if checking_backup:
					recovery["backup"] = str(backup)
				return backup, recovery
			if backup.exists() and backup_version is None:
				raise error
			if backup.exists():
				try:
					require_verified_predecessor_backup(
						backup, config.expected_predecessor_sha256, backup_version,
					)
				except (OSError, ValueError) as backup_error:
					raise OSError(
						f"replacement blocked; canonical remains at {config.destination}; "
						f"inspect backup conflict at {backup}"
					) from backup_error
				raise OSError(
					f"replacement failed; canonical remains at {config.destination}; "
					f"verified predecessor backup is {backup}"
				) from error
			raise
		return backup, None


#============================================
def verify_canonical_commit(destination: pathlib.Path, admitted_sha: str) -> None:
	"""Read back and durably acknowledge the irreversible canonical publication."""
	fsync_file(destination)
	if admission.sha256(destination) != admitted_sha:
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
		config: admission.PromotionConfig, admitted_sha: str) -> tuple[pathlib.Path | None, dict[str, str] | None]:
	"""Link-publish one new canonical without a fabricated predecessor artifact."""
	require_same_filesystem(config.candidate, config.destination.parent)
	with pending_lifecycle_reservation(config.expected_absent_pending):
		with promotion_lock(config.destination):
			admission.require_bound_admission(config, admitted_sha)
			publication_snapshot = create_admitted_snapshot(
				config.candidate, config.destination.parent, admitted_sha,
			)
			canonical_created = False
			try:
				require_new_title_publication_preconditions(config)
				admission.require_bound_admission(config, admitted_sha)
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
		config: admission.PromotionConfig, admitted_sha: str) -> tuple[pathlib.Path, dict[str, str] | None]:
	"""Link-publish canonical before performing recoverable legacy cleanup."""
	if config.predecessor is None:
		raise ValueError("legacy replacement requires a predecessor")
	superseded = subject_superseded_path(config)
	require_same_filesystem(config.candidate, config.destination.parent)
	require_same_filesystem(config.predecessor, superseded.parent)
	with pending_lifecycle_reservation(config.predecessor):
		with promotion_lock(config.destination):
			superseded.parent.mkdir(parents=True, exist_ok=True)
			admission.require_bound_admission(config, admitted_sha)
			publication_snapshot = create_admitted_snapshot(
				config.candidate, config.destination.parent, admitted_sha,
			)
			canonical_created = False
			try:
				require_replacement_publication_preconditions(config, superseded)
				admission.require_bound_admission(config, admitted_sha)
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
		config: admission.PromotionConfig,
		validator_runner: admission.ValidatorRunner = admission.default_validator_runner,
		) -> dict[str, object]:
	"""Validate and atomically publish one configured candidate lifecycle."""
	if not config.candidate.is_file():
		raise ValueError("candidate artifact must exist")
	predecessor_version: FileVersion | None = None
	if config.mode == admission.SUPERSEDES_PENDING:
		if config.predecessor is None or not config.predecessor.is_file():
			raise ValueError("pending predecessor artifact must exist")
	elif config.mode == admission.DIRECT_CANONICAL_REPLACEMENT:
		if not config.destination.is_file() or config.expected_predecessor_sha256 is None:
			raise ValueError("direct replacement requires an existing canonical predecessor")
		predecessor_version = file_version(os.lstat(config.destination))
		if admission.sha256(config.destination) != config.expected_predecessor_sha256:
			raise ValueError("canonical predecessor hash does not match admission")
	elif config.mode != admission.NEW_TITLE_NO_PREDECESSOR:
		raise ValueError(f"unsupported lifecycle mode: {config.mode}")
	admission.require_clean_content(config.candidate)
	admission.require_admission_gate(config)
	admission.require_validators(config, validator_runner)
	admitted_sha = admission.require_admission_gate(config)
	if config.mode == admission.NEW_TITLE_NO_PREDECESSOR:
		superseded, cleanup = publish_new_title(config, admitted_sha)
	elif config.mode == admission.DIRECT_CANONICAL_REPLACEMENT:
		if predecessor_version is None:
			raise RuntimeError("predecessor version was not captured")
		superseded, cleanup = publish_direct_replacement(config, admitted_sha, predecessor_version)
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
		"predecessor_sha256": config.expected_predecessor_sha256,
		"replacement_status": (
			"RECOVERY_REQUIRED" if cleanup is not None and
			config.mode == admission.DIRECT_CANONICAL_REPLACEMENT else
			("REPLACED" if config.mode == admission.DIRECT_CANONICAL_REPLACEMENT else None)
		),
		"superseded_sha256": (
			admission.sha256(superseded) if superseded is not None and superseded.is_file() else None
		),
	}
	return result


#============================================
def main() -> None:
	"""Adapt command-line arguments to the explicit promoter configuration."""
	config = admission.parse_config(sys.argv[1:])
	result = promote(config)
	print(json.dumps(result))


if __name__ == "__main__":
	main()
