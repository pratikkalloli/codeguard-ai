# Phase 17 proxy comparison

This comparison is limited to the public benchmark target `pass_rate >= 0.5`. It is **not** a CodeGuard decision comparison. `Deterministic` is Python AST syntax validity, `ML` thresholds predicted pass rate, and `Combined` requires syntax validity and predicted pass rate >= 0.5. Evidence retrieval and the application's explanation verifier are not applicable to this code-only benchmark.

| Method | Accuracy | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| ML alone | 0.8060 | 0.8075 | 0.9799 | 0.8854 |
| Deterministic syntax alone | 0.7646 | 0.7646 | 1.0000 | 0.8666 |
| Combined proxy | 0.8060 | 0.8075 | 0.9799 | 0.8854 |
