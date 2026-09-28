# Phase 15 — Programming claim-evidence dataset

**Status: NOT READY for model training or reliability claims.** The dataset build and quality checks are implemented. Every included example is synthetic and pending independent Python-expert review; no examples are human verified.

## Scope and safeguards

- Built separately under `data/ml/research_dataset/`; the prior pilot, prior candidate, production inference path, trained model files, and evaluation reports were not edited by the builder.
- This is a data-only phase. No model was trained and no production artifact was regenerated.
- Existing source-grounded synthetic candidate examples were carried forward when they had a source URL and evidence passage. One legacy source-less example was excluded rather than assigning it provenance retroactively.
- Added 30 controlled support/contradiction examples from 15 short official Python documentation excerpts, plus six evidence-relative insufficient-evidence examples. The external set contains four controlled examples and two insufficient-evidence examples from a separate Python Data Model page.
- All records are marked `data_origin=synthetic`, `review_status=pending_expert_review`. “Source checked” means the claim wording was checked against an official excerpt; it does not mean a human annotation or independent adjudication.

## Public dataset research

No located public dataset met all requirements at once: programming domain, explicit claim and evidence text, mappable Supported/Contradicted/Insufficient Evidence labels, and suitable traceable licensing.

| Candidate | Assessment | Decision |
|---|---|---|
| [FEVER](https://fever.ai/dataset/fever.html) | Large three-way evidence-based fact verification, but Wikipedia domain; evidence references need resolution and source terms carry attribution/share-alike obligations. | Excluded as out of domain. |
| [SciFact](https://github.com/allenai/scifact) | Scientific claims and sentence evidence; claim annotations and abstract corpus have distinct licenses; the released labeled set does not provide a robust insufficient-evidence class. | Excluded as biomedical and incomplete label fit. |
| [StaQC](https://huggingface.co/datasets/koutch/staqc) | Python/SQL question and code-snippet pairs; the “standalone answer” annotation is not claim-evidence truth. Underlying Stack Overflow revisions have their own terms. | Excluded; incompatible task labels. |
| [CoNaLa](https://conala-corpus.github.io/) | Natural-language intents paired with Python snippets; project page did not establish an explicit dataset redistribution license. | Excluded; label/task and license mismatch. |
| [CodeSearchNet](https://github.com/github/CodeSearchNet) | Code/docstring pairs across languages; underlying repository samples carry per-record licensing. | Excluded; no evidence-verification labels. |

The included short evidence excerpts are from [official Python documentation](https://docs.python.org/3/) under the [Python Software Foundation License Version 2](https://docs.python.org/3/license.html). Each row retains a source URL, title, section, proposition identifier, and attribution. No third-party dataset rows were incorporated.

## Dataset and splits

- Internal dataset: **66 rows**, all synthetic — 28 Supported, 28 Contradicted, 10 Insufficient Evidence.
- Internal grouped splits: **47 train / 10 validation / 9 test**. Every split has all three labels. Source-page groups are kept intact; exact duplicate and normalized-claim label conflicts are zero.
- Six pairs were not added to the internal data: the external test has **6 synthetic rows** — two Supported, two Contradicted, and two Insufficient Evidence — drawn only from `reference/datamodel.html`, which is absent from all internal data.
- Near-duplicate candidates use normalized claim text and a 0.90 `SequenceMatcher` similarity threshold. Candidate pairs are recorded in metadata and must remain in the same source-page group or the builder fails.
- Group isolation protects source-page evidence and templated claim families. Because this dataset is tiny and templated, held-out rows are not a reliable estimate of natural-world model performance.

## Outputs

- `data/ml/research_dataset/raw/` — proposition manifest and note that no external raw corpora were downloaded.
- `data/ml/research_dataset/processed/` — canonical CSV and train, validation, test, and external test CSVs.
- Dataset metadata, source inventory, statistics, dataset card, data dictionary, and license attribution.
- Quality report and deterministic SVG class/source distribution plots.
- Builder: `src/codeguard/ml/research_dataset.py`; tests: `tests/test_research_dataset.py`.

## Quality, reproducibility, and limits

The builder checks canonical schema, allowed labels and origins, nonempty provenance and license fields, evidence for support/contradiction labels, duplicate and conflicting-label conditions, near duplicates, group isolation, label coverage per split, and complete source isolation of the external page. Split allocation uses a fixed seed. Rebuilding to a clean destination must produce identical row and split records.

All 66 internal and six external records require independent expert review and adjudication. Contradictions are constructed polarity pairs and may be lexically easy. The Insufficient Evidence label means that only this provided passage does not establish the claim; it does not mean the claim is false. The data is not representative of varied AI-generated explanations, is not human labeled, and must not be used to claim classifier quality. Acquire independently reviewed programming-domain claim/evidence examples and a human-adjudicated external set before training or performance evaluation.

## Verification

Verification performed for this phase:

- Research dataset builder completed and wrote the files listed above.
- Full offline `unittest` suite: **70 run, 65 passed, five Docker integration tests skipped** by their default opt-in guard. The new dataset tests passed, including an independent rebuild comparison for reproducibility.
- `compileall`: passed; `pip check`: no broken requirements.
- Streamlit `AppTest`: zero app exceptions.
- `pytest` is not installed in the project virtual environment; the existing full `unittest` suite was used instead.
- Docker-specific integration behavior remains unverified in this run. No Docker execution test was opted in.
- Production artifact SHA-256 values match the before-phase values recorded during inspection; no production training was run.

A successful build and passing tests do not imply the dataset is ready for model training.
