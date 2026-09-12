# Design decisions

<!-- VENDORED HEADER: START -->
Record each durable decision about how this code and repository are shaped, once it is settled, with
the reasoning a later reader needs. Guidance Neil Voss states belongs in
[HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md), dated history in `docs/CHANGELOG.md`, open discussion in
`docs/active_plans/decisions/`. [PROPAGATED HEADER - ENTRIES BELOW ARE YOURS]
<!-- VENDORED HEADER: END -->

## 2026-09-08 explicit promotion lifecycle

Promotion lifecycle is an explicit admission mode, not an inference from a missing file.
New-title admission receives and verifies the exact expected-absent PENDING path instead
of fabricating a placeholder. This preserves a meaningful negative precondition, avoids
invented hashes, and keeps replacement provenance limited to real predecessors.

New-title admission also requires the literal `admission_status: "ACCEPTED"`; missing or failed
admission states are refusals, not inferred permission to publish.

The PENDING creator and both promotion lifecycle branches share one title-specific flock
reservation. Writers perform exclusive PENDING creation and canonical absence checking under that
reservation; promoters retain it through their final lifecycle transition. Each owner compensates
only its own inode or canonical hard link, so an unreserved late conflict removes no unrelated file.

Canonical hash readback and filesystem synchronization are the promotion outcome. Both promotion
branches retain their staged candidate after that outcome. The promoter cannot safely reclaim a
mutable candidate pathname: even an `lstat` identity check has a replacement window before unlink.
Stage reclamation therefore belongs to an explicit later strict-closure lifecycle that verifies its
authority and target identity independently of canonical publication.
