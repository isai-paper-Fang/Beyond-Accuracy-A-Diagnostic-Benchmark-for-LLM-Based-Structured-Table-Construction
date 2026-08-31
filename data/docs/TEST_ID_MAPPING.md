# Test IDs: data files vs paper

The data files in this repository use the test IDs that existed while the experiment ran. The paper renumbered them to a contiguous `T1`–`T6`. **The two numbering schemes do not agree, and three IDs mean different things in the two places.**

| Paper | Data files | Test | Row-level cells? | Conditions hosted |
|---|---|---|---|---|
| **T1** | `T1` | Summarise each activity and label row completeness | yes | `MISSING_VALUE`, `DISGUISED_MISSING` |
| **T2** | `T3` | Group records by agency and reconcile spending totals | yes | `DUPLICATE_ROW`, `INCORRECT_UNIT` |
| **T3** | `T4` | Count evidence and report budget status | no | `BAIT_NO_NUMBER` |
| **T4** | `T5` | Enumerate target groups, one record per group | yes | `DELIMITER_SPLIT` |
| **T5** | `T6` | Cross-tabulate participation and compute percentages | yes | `STAT_OUTLIER` |
| **T6** | `T7` | Extract supportable claims from each document | no | `TEXT_NUMBER_CONFLICT`, `NO_EVIDENCE` |

There is no `T2` in the data files.

## Where each scheme appears

**Data-file scheme** (`T1 T3 T4 T5 T6 T7`) — the `task` column of every CSV, `documents.json`, `trap_registry.csv`, `run_log.csv`, `manifest.json`, `trap_rules.yaml` (`host_task`), the filenames in `data/raw/` and `data/prompts/`, and the section headings of `C_prompts_v1.md`.

**Paper scheme** (`T1`–`T6`) — the paper, and nothing in this repository.

## Converting

```python
PAPER_FROM_DATA = {"T1": "T1", "T3": "T2", "T4": "T3", "T5": "T4", "T6": "T5", "T7": "T6"}
DATA_FROM_PAPER = {v: k for k, v in PAPER_FROM_DATA.items()}
```

## Two statements that are easy to get wrong

- The paper says *"T3 and T6 request document-level summaries only."* In the data files those are **`T4` and `T7`**.
- The paper says *"the cell-level metric covers four of the six tests."* The four are data-file **`T1`, `T3`, `T5`, `T6`**.

## Why we did not renumber the data

Renumbering would require editing every CSV, both YAML files, all six task bundles, and the names of 72 raw-output files, with no gain in information and a real risk of introducing a mismatch between a filename and its contents. The mapping table is the safer artefact.
