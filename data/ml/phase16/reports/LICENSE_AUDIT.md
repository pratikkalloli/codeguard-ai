# License and provenance audit — Phase 16

**No third-party dataset was downloaded or copied.** A candidate is not accepted for reuse unless the dataset-level license, redistribution rights, derivative-work terms, attribution, and record-level source terms are clear.

| Candidate | Exact source and license evidence | Decision / rights status |
|---|---|---|
| CodeSimpleQA | [Paper](https://arxiv.org/html/2512.19424v1); the paper's arXiv submission license is not a license to its data. No dataset license or direct dataset artifact was located in the paper. | REVIEW. Rights unknown. Do not copy until authors provide dataset and license terms. |
| CS1QA | [Paper](https://aclanthology.org/2022.naacl-main.148/), The official paper record is the source reviewed; no dataset repository license was verified. Classroom chat data rights need independent confirmation. | EXCLUDE from data. Underlying data terms need independent confirmation. |
| SciClaimEval | [Official task site](https://sciclaimeval.github.io/), [LREC paper](https://aclanthology.org/2026.lrec-1.864/). No dataset redistribution license confirmed in this review. | EXCLUDE; rights also not cleared. |
| CodeQA | [Official repository](https://github.com/jadecxliu/CodeQA) says MIT for repository; paper identifies derived code-summarization sources. | EXCLUDE; source code/data rights are not automatically covered by repository license. |
| CoSQA | [Project repository](https://github.com/Jun-jie-Huang/CoCLR), [ACL paper](https://aclanthology.org/2021.acl-long.442/). Inspected HF mirror did not expose an explicit license. | EXCLUDE; rights unverified and task mismatch. |
| StaQC | [Hugging Face card](https://huggingface.co/datasets/koutch/staqc) states CC BY 4.0 for that distribution; source posts originate from Stack Overflow and carry revision-specific terms under [Stack Overflow licensing](https://stackoverflow.com/help/licensing). | EXCLUDE. Per-record rights/attribution and task mismatch. |
| CoNaLa | [Official project page](https://conala-corpus.github.io/) and paper [ACL Anthology](https://aclanthology.org/P18-1223/); no explicit dataset license located on the project page; Stack Overflow sources have their own terms. | EXCLUDE. Do not redistribute while license is unclear. |
| CodeSearchNet | [Repository](https://github.com/github/CodeSearchNet) uses MIT for repository; sample code retains individual source repository licenses. | EXCLUDE; record-level review required. |
| HumanEval | [Official repository](https://github.com/openai/human-eval), MIT license. | EXCLUDE from this claim dataset; code execution benchmark only. |
| MBPP | [Google Research repository](https://github.com/google-research/google-research/tree/master/mbpp), with dataset text/source provenance requiring separate verification. | EXCLUDE; no claim-evidence labels and data reuse not cleared here. |
| SWE-bench Verified | [SWE-bench repository](https://github.com/SWE-bench/SWE-bench), [human verification description](https://openai.com/index/introducing-swe-bench-verified/). Issues and repository code have upstream-specific terms. | EXCLUDE; human review labels issue/test quality, not truth claims. |
| ExpertQA | [Paper](https://arxiv.org/abs/2309.07852), [original dataset card](https://huggingface.co/datasets/cmalaviya/expertqa); mirror/license metadata can differ. | REVIEW. Verify original license, CS subset and rows before any acquisition. |
| FACTORY | [Hugging Face card](https://huggingface.co/datasets/facebook/FACTORY) reports CC BY-NC 4.0; source materials may have additional terms. | EXCLUDE; noncommercial terms plus task/domain mismatch. |
| SciFact | [Official repository](https://github.com/allenai/scifact) distinguishes CC BY 4.0 annotations and ODC-By 1.0 abstracts. | EXCLUDE; biomedical domain and label gap. |
| FEVER | [Official dataset page](https://fever.ai/dataset/fever.html), [license notice](https://fever.ai/download/fever/license.html): Wikipedia page terms apply, CC BY-SA 3.0 fallback where applicable. | EXCLUDE; out-of-domain and share-alike/source-attribution requirements. |
| SimpleQA | [SimpleQA release article](https://openai.com/index/introducing-simpleqa/), [official code/data repository](https://github.com/openai/simple-evals). | EXCLUDE; not claim+evidence triples for programming. No files copied. |
| SimpleQA Verified | [Epoch AI benchmark review](https://epoch.ai/benchmarks/simple-qa-verified/review) and source links; dataset reuse rights were not cleared for this project. | EXCLUDE; general-domain QA and rights not audited for import. |
| SciFact-Open | [Repository](https://github.com/dwadden/scifact-open); inherits SciFact components and their distinct terms. | EXCLUDE; science domain and no programming behavior. |
| ProCQA / programming QA family | [LREC paper](https://aclanthology.org/2024.lrec-main.1143/); accepted Stack Overflow answers have revision-level licensing. | EXCLUDE; accepted answers are not claim-evidence labels. |

Included CodeGuard synthetic examples quote only short official Python documentation passages already included in Phase 15 and retain source URLs, section, and the [PSF License Version 2](https://docs.python.org/3/license.html) attribution. No source dataset license is inferred from a paper or code-repository license.
