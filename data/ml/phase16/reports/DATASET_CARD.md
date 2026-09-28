# Phase 16 dataset card

**Status: pending human validation; not ready for final training.**

- Internal candidate rows: 66 (all synthetic pending review).
- External candidates: 6 (all synthetic pending review).
- Human reviewed: 0; public human-annotated included: 0; actual human verified labels: 0.
- Proposed internal labels: `{"Contradicted": 28, "Insufficient Evidence": 10, "Supported": 28}`.
- Intended users: trained Python/programming reviewers and dataset curators.
- Not for production training or reliability claims until independent reviews, adjudication, licensing, and an external benchmark gate are satisfied.

The dataset is evidence-relative. Supported means the passage directly establishes the claim; Contradicted means it directly conflicts; Insufficient Evidence means the supplied passage establishes neither. All current claims originated as synthetic and no source dataset was imported. See `review/reviewer_guidelines.md` and `reports/LICENSE_AUDIT.md`.
