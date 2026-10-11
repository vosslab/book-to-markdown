# Usage

Run the toolchain from the repository root after sourcing `source_me.sh`. Scripts are grouped
into `extract/`, `cleanup/`, and `audit/`.

Run tool tests with `source source_me.sh && pytest tests/`. Hygiene tests are read-only by default;
pass `--fix-repo-files` only when you intend their ASCII and whitespace fixers to edit repository
files in place.

## Quick start

- Convert a scanned or degraded PDF through the qualified OCR path:
  - `TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata python3 extract/pdf_to_markdown.py book.pdf -o /tmp/book.raw.md`
  - `python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md`
- Convert a PDF with a text layer:
  - `python3 extract/pdf_raw_text_extraction_to_markdown.py book.pdf -o /tmp/book.raw.md`
  - `python3 cleanup/clean_markdown.py -i /tmp/book.raw.md -o /tmp/book.clean.md`
- Convert supported AZW3 books; preformatted code keeps its indentation and literal heading-like
  lines, and source tables keep their row, cell, and line-break boundaries:
  - `python3 extract/azw3_to_markdown.py book.azw3 -o /tmp/book.raw.md`
- Raw PDF extraction preserves spans that PyMuPDF explicitly flags as superscript using ASCII
  `^{...}` notation. This includes raised citation references; it does not infer general
  mathematical formatting or identify subscripts and fractions.
- ASCII cleanup preserves the ring-above symbol as `&#x02DA;` before Unicode compatibility
  normalization, so a superscript Angstrom unit does not become an empty exponent.
- Raw PDF extraction separates distinct text blocks with blank lines while retaining single
  newlines inside a block, allowing cleanup to join wrapped prose without merging adjacent blocks.
- Validate the result:
  - `python3 audit/validate_markdown_v2.py /path/to/delivery-directory`

Canonical filenames use metadata title words joined by underscores and a
verified publication year (`-YYYY.md`) when available. If bounded source
identity checks establish the title and author but no publication year can be
verified, use `-UNDATED.md`; do not infer a year from a scan or source filename.
An undated filename does not establish a specific edition or complete content.

## Promotion

`audit/promote_validated_candidate.py` is an executable launcher that owns canonical publication.
Run it from the tool repository after sourcing its Python environment:

```bash
cd /Users/vosslab/nsh/book-to-markdown
source source_me.sh && python3 audit/promote_validated_candidate.py \
  --replace-canonical CANDIDATE DESTINATION SUPERSEDED_ROOT \
  EXPECTED_PREDECESSOR_SHA256 \
  /Volumes/Ex2GB/books/book-corpus-conversion-skill/scripts/validate_corpus_book.py
```

Use `DIRECT_CANONICAL_REPLACEMENT` for an existing canonical book that needs
repair. The candidate-adjacent `admission_gate.json` binds the candidate hash,
destination path, and expected predecessor hash. Its independent-review
receipt binds the destination and predecessor path/hash as well as the
candidate and source path/hash; both nested file paths must be absolute and
resolve to the admitted files. It also records an accepted decision, reviewer,
and checked scope. The promoter runs the supplied validator and
`audit/validate_markdown_v2.py` before publication, then rechecks predecessor
identity and hash under a visible title lock. It creates and verifies a
no-clobber `O_EXCL` backup, atomically replaces the canonical file with
`os.replace`, and reads back both canonical and backup hashes. The canonical
path remains present throughout; this mode does not unlink it or create a
PENDING gap.
Locks are visible files in the corpus root's `conversion_state/locks/`;
never create hidden lock files or unlink a lock while promotion may be running.

- Preserve a real PENDING predecessor with the compatible legacy five-positional command:
  ```bash
  ./audit/promote_validated_candidate.py \
    CANDIDATE DESTINATION PENDING SUPERSEDED_ROOT VALIDATOR
  ```
- Publish a verified new title without a predecessor with the explicit command:
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
