# Adjudication guidelines

Adjudication is a separate decision by a real third person, independent of Reviewer A and Reviewer B. Enter the adjudicator's actual identifier; the software enforces distinct identifiers but cannot independently verify identity.

1. Read the claim and the exact source passage in full.
2. Read each reviewer's decision and rationale only after both independent reviews are complete or a reviewer explicitly requests adjudication.
3. Re-evaluate against the evidence using the six questions in `reviewer_guidelines.md`.
4. Choose Supported, Contradicted, Insufficient Evidence, or Reject. Do not use a forced tie-break rule.
5. Add a rationale that explains why the evidence directly entails, contradicts, or fails to establish the claim. If rejecting, identify the dataset defect.
6. The adjudicated result becomes `final_adjudicated_label`; a rejected row remains excluded. Only adjudicated rows appear with a gold label in `processed/adjudicated.csv`. The legacy `processed/verified.csv` is intentionally empty.

Insufficient Evidence is evidence-relative and must not be used as a compromise between disagreement. No inter-reviewer agreement statistic is reported until real double reviews exist.
