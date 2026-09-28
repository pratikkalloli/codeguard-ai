# Public raw dataset files

Selected Phase 17 source: NVIDIA, [OpenCodeReasoning-2](https://huggingface.co/datasets/nvidia/OpenCodeReasoning-2), revision `eadf535931451525f3e5621d0f960c240bc62fd9`.

The `opencodereasoning2/train/python/` folder contains three contiguous original Parquet shards from the Python subset. Their byte lengths and SHA-256 checksums are in `DATASET_METADATA.json`. The source dataset card identifies the collection as CC BY 4.0 and cautions that upstream datasets have their own terms. All sampled rows carry `apache-2.0`; the preprocessor preserves each row’s license/source and filters to an explicit permissive-license allow-list. Attribution is retained in the dataset research/selection documents and reports.

`opencodereasoning/` is an earlier exploratory download of the first three shards from NVIDIA's original OpenCodeReasoning release. It was not used for training and is retained as raw research material. `metadata/` retains public Hugging Face API and network-probe responses used during dataset selection.

The Phase 17 model learns only to estimate the source-provided `pass_rate` from code shape/code text and metadata. No generated critique or `right`/`wrong` judgement is used as a feature or a CodeGuard label.
