# Phase 16 quality report

## Review state

- Real reviewer decisions: **0**; independent agreement: unavailable.
- Pending review: **72** (66 internal and 6 external candidates).
- Rejected: **0**; adjudicated: **0**.

## Dataset indicators (separate; no aggregate score)

- Proposal class distribution (not gold labels):
- Contradicted: 28 (42.4% of internal proposals)
- Insufficient Evidence: 10 (15.2% of internal proposals)
- Supported: 28 (42.4% of internal proposals)
- External proposal counts (not gold labels): `{"Contradicted": 2, "Insufficient Evidence": 2, "Supported": 2}`
- Unique source pages: 11; source domains: 1 (docs.python.org).
- Unique fact keys: 41; evidence groups: 11.
- Three most concentrated pages: https://docs.python.org/3/tutorial/datastructures.html (16), https://docs.python.org/3/tutorial/controlflow.html (15), https://docs.python.org/3/library/functions.html (8).
- Exact duplicate rows: 0; normalized-claim label conflicts: 0.
- Near-duplicate pairs at >=0.90 `SequenceMatcher` similarity: 15; cross-split/external group violations: 0.
- Complete source/provenance/license fields: 72/72; incomplete: 0. Evidence passages: 72/72.
- Inherited internal Phase 15 split sizes: {"test": 9, "train": 47, "validation": 10}; source-group split violations: 0.
- External source/fact overlap with internal candidate: 0.

## Topic coverage

- built-ins: 8
- built-ins and sorting: 4
- collections and mutability: 4
- collections and performance: 2
- comprehensions: 2
- data model: 6
- dictionaries: 2
- dictionaries and exceptions: 2
- exceptions: 2
- file handling and exceptions: 2
- functions: 11
- iteration: 7
- loops: 5
- pilot out-of-scope example: 4
- range: 3
- sequences: 2
- sets: 2
- strings: 4

## Source distribution

- `https://docs.python.org/3/tutorial/datastructures.html`: 16 (22.2% of all candidates)
- `https://docs.python.org/3/tutorial/controlflow.html`: 15 (20.8% of all candidates)
- `https://docs.python.org/3/library/functions.html`: 8 (11.1% of all candidates)
- `https://docs.python.org/3/tutorial/classes.html`: 7 (9.7% of all candidates)
- `https://docs.python.org/3/library/stdtypes.html`: 6 (8.3% of all candidates)
- `https://docs.python.org/3/reference/datamodel.html`: 6 (8.3% of all candidates)
- `https://docs.python.org/3/library/functions.html#sorted`: 4 (5.6% of all candidates)
- `https://docs.python.org/3/reference/compound_stmts.html#function-definitions`: 3 (4.2% of all candidates)
- `https://docs.python.org/3/reference/compound_stmts.html#the-for-statement`: 3 (4.2% of all candidates)
- `https://docs.python.org/3/tutorial/errors.html`: 2 (2.8% of all candidates)
- `https://docs.python.org/3/tutorial/inputoutput.html#reading-and-writing-files`: 2 (2.8% of all candidates)

## Interpretation

All labels shown above are synthetic proposals, not gold labels. Source concentration is high because evidence comes from a handful of Python documentation pages. The six external rows are not an independent benchmark until reviewed and adjudicated. No model training is permitted.
