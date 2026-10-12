# File formats

This guide distinguishes source documents, staged Markdown, diagnostic sidecars, and publication
evidence. Commands are documented in [USAGE.md](USAGE.md).

## Source and candidate files

- PDF extraction has separate text-layer and OCR entry points in `extract/`. AZW3 extraction
  supports unencrypted Mobipocket/AZW3 v8 HuffDic input and requires the optional `mobi` extra.
- EPUB helpers inspect source structure or recover text; Pandoc's semantic filter supports
  document-conversion workflows. Source support depends on the selected tool and installed extras.
- A staged candidate is a UTF-8 Markdown file before cleanup. Cleanup writes ASCII Markdown,
  using entities and textual notation for supported scientific characters.
- Canonical delivery uses one book per Markdown file with exactly one H1 and a filename such as
  `Signal_Pathway-2026.md` or `Signal_Pathway-UNDATED.md`. Source fidelity is a separate requirement.

## Cleanup diagnostics

- `cleanup/clean_markdown.py -i INPUT -o OUTPUT` writes the cleaned Markdown to `OUTPUT`.
- The default JSON report is `OUTPUT.report.json`; `--json-report` selects another path.
- Removed text is recorded in `OUTPUT.removed.md` for inspection.
- `--measure` reports metrics without writing the cleaned Markdown or removal sidecar.
  Keep reports beside staged work, outside canonical delivery directories.

## Publication evidence

- `admission_gate.json` beside the candidate binds its SHA-256 digest to source-fidelity and
  table/figure gates, an independent review receipt, and the declared lifecycle.
- Direct replacement additionally binds the destination and predecessor SHA-256. The independent
  review records candidate/source paths and hashes, destination, predecessor identity, reviewer,
  checked scope, and an accepted decision.
- [audit/promotion_admission.py](../audit/promotion_admission.py) is the authoritative validation
  contract. [USAGE.md](USAGE.md) describes each invocation and lifecycle.
- The promoter reports publication as JSON and retains the staged candidate after success.
  Source review and later staged-candidate reclamation remain separate operations.
