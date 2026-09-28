# Reviewer guidelines

## Purpose

Independently decide whether a programming claim is supported by the exact supplied passage. Review the text shown; do not silently replace it with outside knowledge. A claim that happens to be true can still be **Insufficient Evidence** if this evidence does not establish it.

## Labels

- **Supported:** the passage directly establishes the claim, with compatible scope and conditions.
- **Contradicted:** the passage directly conflicts with the claim.
- **Insufficient Evidence:** the passage is silent, irrelevant, incomplete, ambiguous, or does not establish either truth or falsity. This does not mean false.
- **Reject:** the record is unsuitable (for example, malformed, ambiguous beyond adjudication, unsupported source rights, duplicate, or not a programming fact). Explain why in notes.
- **Needs adjudication:** evidence or claim ambiguity prevents an independent label. Explain the ambiguity.

## Questions to answer

1. Does the evidence directly support the complete claim?
2. Does the evidence directly contradict the complete claim?
3. Does the evidence fail to establish the claim either way?
4. Is the claim atomic, precise, and unambiguous?
5. Is the evidence relevant, sufficiently scoped, and from the cited source?
6. Does the claim depend on assumptions, version details, context, or external knowledge not present in the evidence?

If both support and contradiction appear possible, the claim combines multiple propositions, or important version/context is missing, choose **Needs adjudication** or **Reject**. Do not force a label. Notes should identify the specific words in claim/evidence that determine your decision.

## Independent review procedure

- Reviewer A and Reviewer B must be different real people. Enter an identifier actually used by each person; never create a fictional identity.
- Each reviewer assesses the evidence independently. The proposed synthetic label is hidden by default to reduce anchoring. If revealed, it is only a suggestion and must not be copied without checking.
- Select confidence from 1 (low) to 5 (high). Explain low confidence and every rejection/escalation.
- Do not reveal or copy one reviewer's notes into the other's decision. The app hides the other slot's response while a second review is pending.
- Matching canonical labels produce `reviewed` / `agreement_pending_adjudication`; differing decisions or a request for adjudication produce `disputed`. Agreement alone is not a gold label.
- Two independent Reject decisions reject a record. A Reject/label disagreement is disputed.
- Review events are appended to a separate SQLite database. Final adjudicated/rejected rows are immutable in this workspace; create a new dataset revision to reopen them.

## External benchmark precautions

The external candidate queue is held separately from internal batches. These records are synthetic and are not a benchmark until independently reviewed and adjudicated. Keep their source pages and fact groups out of training. Do not use the external set to tune a model. Only independent adjudication creates an exported `gold_label`; agreement is an intermediate review state.

## Current queue

The Phase 16/16.5 candidate pool is synthetic and pending review. The current queue size and split are recorded in `data/ml/phase16_5/candidate_statistics.json`. No reviewer identities, reviews, agreement figures, or gold labels are prefilled. Proposals can be replaced by human decisions or rejected; the proposal is never evidence of correctness.
