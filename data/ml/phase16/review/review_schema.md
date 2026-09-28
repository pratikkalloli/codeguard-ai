# Review record schema

## Queue fields

The CSV queue contains `review_id`, `record_id`, `dataset_partition`, `claim`, `evidence`, `proposed_label`, `reviewer_label`, `reviewer_confidence`, `reviewer_notes`, `source_url`, `source_title`, `fact_key`, `evidence_group`, `data_origin`, `review_status`, and `adjudication_status`; it also contains explicit Reviewer A/B fields, final adjudication fields, and review-priority metadata.

## Reviewer fields

Each slot stores decision, real reviewer identifier, confidence integer 1–5, notes, and timestamp in append-only event history. Canonical decisions are the three target labels; `Reject` and `Needs adjudication` are workflow decisions, not class labels. Reviewer identifiers must be non-empty and A/B identifiers must differ.

## Adjudication fields

`final_adjudicated_label` is blank until an independent adjudicator resolves a reviewed or disputed row to a canonical label. `adjudicator_id` and rationale are required. Reject produces a rejected row without a class label. Agreement does not populate any gold field.

## Status transitions

| Current evidence | review_status | adjudication_status |
|---|---|---|
| No submitted review | pending | pending |
| One decision awaiting the second | pending | awaiting_second_review |
| Both choose same canonical label | reviewed | agreement |
| Different decisions, or a reviewer requests it | disputed | disagreement |
| Both independently reject | rejected | rejected_by_reviewers |
| Independent adjudicator chooses a class | adjudicated | resolved |
| Independent adjudicator rejects | rejected | rejected_by_adjudicator |

Only adjudication populates `final_adjudicated_label`. `verified_label` is a legacy compatibility field and is not treated as gold. The Phase 16 database is `review/reviews.sqlite3`; it is separate from CodeGuard's evaluation history database and is ignored by Git. Review events record timestamps, review mode, and whether the reviewer marked the source as verified.
