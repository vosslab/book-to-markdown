# Usage

Run the toolchain from the repository root after sourcing `source_me.sh`. Scripts are grouped
into `extract/`, `cleanup/`, and `audit/`.

## Quick start

- Convert a scanned or degraded PDF through the qualified OCR path:
  - `TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata python3 extract/pdf_to_markdown.py book.pdf -o /tmp/book.raw.md`
  - `python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md`
- Convert a PDF with a text layer:
  - `python3 extract/pdf_raw_text_extraction_to_markdown.py book.pdf -o /tmp/book.raw.md`
  - `python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md`
- Validate the result:
  - `python3 audit/validate_markdown_v2.py /path/to/delivery-directory`

## Promotion

`audit/promote_validated_candidate.py` is an executable launcher that owns canonical publication. The
candidate-adjacent `admission_gate.json` must bind the candidate SHA-256, passing source-fidelity
and table/figure gates, and the declared lifecycle. The promoter runs the supplied validator and
`audit/validate_markdown_v2.py` before publication.

- Preserve a real predecessor with the unchanged five-positional command:
  ```bash
  ./audit/promote_validated_candidate.py \
    CANDIDATE DESTINATION PENDING SUPERSEDED_ROOT VALIDATOR
  ```
- Publish a verified new title without a predecessor only with the explicit command:
  ```bash
  ./audit/promote_validated_candidate.py --new-title \
    CANDIDATE DESTINATION EXPECTED_ABSENT_PENDING VALIDATOR
  ```

For `NEW_TITLE_NO_PREDECESSOR`, the gate records literal `destination`,
`expected_absent_pending`, and `admission_status: "ACCEPTED"` values. The promoter requires every
value to match its admission and invocation before it publishes a verified same-filesystem snapshot
with atomic no-clobber linking. It creates no SUPERSEDED artifact. Replacement mode retains its
subject-scoped predecessor backup. Once canonical hash readback and filesystem synchronization pass,
the canonical readback is the promotion outcome. Both lifecycle branches retain the staged candidate;
the promoter never reclaims that mutable pathname after commit. A later strict-closure owner may reclaim
staging only as a separate explicit operation after verifying its lifecycle authority and target identity.
Canonical delivery remains intact when later backup, predecessor, or snapshot cleanup needs recovery.

### PENDING writer contract

Every title-specific PENDING writer uses `create_pending_artifact(pending, destination, content)`
from `audit/promote_validated_candidate.py`; it does not write the PENDING pathname directly. The
shared operation locks the title-specific PENDING lifecycle, refuses if canonical `destination`
already exists, creates PENDING with `O_CREAT | O_EXCL`, and fsyncs the created file and parent
directory. New-title promotion and legacy replacement take the same reservation before their final
lifecycle checks and retain it through the canonical transition.

New-title admission-status transitions use `transition_admission_status()` under that same
title-specific reservation. The promoter rechecks accepted admission after snapshotting and immediately
before canonical linking, so a revoked gate cannot enter the final publication transition.

The creator owns only the PENDING inode returned by its exclusive create. If its write fails, it
removes only that unchanged inode; it never removes another writer's PENDING or a canonical file.
The promoter owns only the canonical hard link it created, and compensates that link if an
unreserved conflicting PENDING appears during the final transition. A writer that acquires the
reservation after canonical publication refuses rather than recreating PENDING. This protocol
defines the ownership boundary; a timing gap is not an admission rule.

Promotion is not strict closure. A separate receipt owner must write and verify the external
receipt and its newline-terminated `sha256sum` sidecar before a title is reported closed. The
separate closure lifecycle owns any safe staged-candidate reclamation; it is not an implicit side
effect of publication. See [HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md) and
[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md).

## Audit

- `audit/validate_markdown_v2.py` - block-aware Markdown validator (preferred).
- `audit/validate_markdown_delivery.py` - legacy validator.
- `audit/promote_validated_candidate.py` - explicit no-clobber lifecycle promoter.
- `audit/audit_markdown_duplication.py` - detect OCR doubling/stutter.
- `audit/audit_markdown_residue.py` - scan for extraction residue and bad characters.
- `audit/archive_processed_sources.py` - archive processed source files after validation.
