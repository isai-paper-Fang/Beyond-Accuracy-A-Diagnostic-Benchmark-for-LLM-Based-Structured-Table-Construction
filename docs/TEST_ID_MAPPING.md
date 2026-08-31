# Test IDs

**The data files and the paper now use the same test IDs, `T1`–`T6`.** If you are only reading the data, you do not need the rest of this page.

| Test | What the system is asked to do | Row-level cells? | Conditions hosted |
|---|---|---|---|
| `T1` | Summarise each activity and label row completeness | yes | `MISSING_VALUE`, `DISGUISED_MISSING` |
| `T2` | Group records by agency and reconcile spending totals | yes | `DUPLICATE_ROW`, `INCORRECT_UNIT` |
| `T3` | Count evidence and report budget status | no | `BAIT_NO_NUMBER` |
| `T4` | Enumerate target groups, one record per group | yes | `DELIMITER_SPLIT` |
| `T5` | Cross-tabulate participation and compute percentages | yes | `STAT_OUTLIER` |
| `T6` | Extract supportable claims from each document | no | `TEXT_NUMBER_CONFLICT`, `NO_EVIDENCE` |

The cell-level metric covers the four row-level tests: `T1`, `T2`, `T4`, `T5`. The three conditions hosted by `T3` and `T6` therefore appear only in the diagnostic evaluation.

---

## Historical note: the old IDs

While the experiment ran, the six tests carried non-contiguous IDs inherited from an earlier design that had a seventh test. They were renumbered to a contiguous `T1`–`T6` for this release.

| Now | While the experiment ran |
|---|---|
| `T1` | `T1` |
| `T2` | `T3` |
| `T3` | `T4` |
| `T4` | `T5` |
| `T5` | `T6` |
| `T6` | `T7` |

```python
NEW_FROM_OLD = {"T1": "T1", "T3": "T2", "T4": "T3", "T5": "T4", "T6": "T5", "T7": "T6"}
OLD_FROM_NEW = {v: k for k, v in NEW_FROM_OLD.items()}
```

**Two documents were deliberately not renumbered**, because they are dated records of decisions made before the data existed and rewriting them would falsify that record:

- `preregistration.md`
- `trap_spec.md`

Both still use the old IDs throughout. Use the table above when reading either of them. Byte-identical copies of every other file that was renumbered are kept in `frozen/`; see [`INTEGRITY.md`](INTEGRITY.md).

Everything else in this repository — every CSV `task` column, `documents.json`, `trap_registry.csv`, `run_log.csv`, `manifest.json`, `trap_rules.yaml`, the filenames in `data/raw/` and `data/prompts/`, the task bundles, the section headings of `C_prompts_v1.md`, and all other documentation — uses `T1`–`T6`.

One name that is not a test ID: `test_scorer.py` uses `T1`…`T9` as local Python variables for its unit-test fixtures. They are not test IDs and were not renumbered.
