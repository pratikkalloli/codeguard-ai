# Label mapping and transformation policy

Canonical labels are evidence-relative:

- **Supported:** the supplied evidence directly establishes the claim.
- **Contradicted:** the supplied evidence directly conflicts with the claim.
- **Insufficient Evidence:** this supplied evidence does not establish either truth or falsity. It is not a synonym for Contradicted.

No external dataset was used, and no external labels were automatically mapped.

| Candidate labels/task | Possible mapping | Status and reason |
|---|---|---|
| CodeSimpleQA factual QA | No direct mapping | `REVIEW_REQUIRED`: correct reference answers could help create future evidence-grounded questions, but questions/answers are not claim/evidence triples with three gold classes. Do not treat all benchmark QA as Supported. |
| FEVER SUPPORTS / REFUTES / NOT ENOUGH INFO | Conceptually SUPPORTS→Supported; REFUTES→Contradicted; NOT ENOUGH INFO→Insufficient Evidence | `REVIEW_REQUIRED`, not applied: Wikipedia domain; evidence IDs must be resolved to text; NEI evidence treatment and licensing need record-level adjudication. |
| SciFact SUPPORT / CONTRADICT | SUPPORT→Supported; CONTRADICT→Contradicted | `REVIEW_REQUIRED`, not applied: no robust third class in its labeled claims; biomedical domain and separate corpus license. |
| FACTORY Factual / NonFactual / Inconclusive / No Verifiable Fact | Factual might be Supported only when source directly entails; NonFactual may be contradiction or unsupported; Inconclusive may be IE; No Verifiable Fact is not necessarily IE | `REVIEW_REQUIRED`, not applied: labels have different unit and evidence semantics, and data is noncommercial and not programming-focused. |
| CodeQA, CS1QA, StaQC, CoNaLa, CoSQA, CodeSearchNet | None | `REVIEW_REQUIRED` mapping prohibited: these label answer relevance, code correspondence, or generated code correctness, not claim truth against evidence. |
| HumanEval, MBPP, SWE-bench | None | Execution/test outcome is a separate code correctness signal; it is not an explanation claim label. |
| ExpertQA | No mapping until schema/domain inspection | `REVIEW_REQUIRED`: check claim-level support, correctness, and source reliability semantics separately, and establish a license-cleared programming-specific subset. |

Synthetic Phase 15 `SUPPORTED/CONTRADICTED/INSUFFICIENT_EVIDENCE` labels are retained only as **proposed_label** for human review. They are not gold labels. A reviewer's decision can replace or reject the proposal. External candidates have no `gold_label` until independently reviewed and, where disputed, adjudicated.
