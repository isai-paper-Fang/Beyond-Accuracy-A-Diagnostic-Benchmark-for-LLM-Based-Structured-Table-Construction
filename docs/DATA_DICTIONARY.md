# Data dictionary

Every `task` column in every file uses the test IDs `T1`–`T6`, the same IDs the paper uses. Two frozen documents, `preregistration.md` and `trap_spec.md`, still carry the older non-contiguous IDs; [`TEST_ID_MAPPING.md`](TEST_ID_MAPPING.md) maps between them.

---

## `data/documents/D###.md` — 150 files

One synthetic quarterly report each: title block, introductory paragraph, nine-column activity table, one to three footnotes. Six to nine activity rows per document, 1,009 rows in total. 135 documents carry exactly one scored diagnostic condition; 15 carry none and act as controls.

## `data/documents.json`

The same corpus in structured form: `doc_id`, `task`, `trap_type`, `rows[]`, and `trap` (the condition's parameters). This is what the scorer and the analysis read.

## `data/ground_truth_cells.csv` — 9,081 rows

The reference answer for every row-level cell.

| Column | Meaning |
|---|---|
| `doc_id` | document |
| `task` | data-file test ID |
| `row_key` | activity code, e.g. `2567-พช-757` |
| `column` | Thai column name |
| `field_type` | `ข้อความ` / `เงินบาท` / `จำนวนนับ` / `ร้อยละ` — selects the tolerance |
| `value_correct` | the reference value |

Cells are matched by `(doc_id, row_key, column)`, never by position.

## `data/trap_registry.csv` — 135 rows

**The reference pairs.** One row per condition position. This file is what makes the diagnostic evaluation possible; without it only RQ1 can be reproduced.

| Column | Meaning |
|---|---|
| `doc_id`, `task`, `trap_type` | which condition, where |
| `row_key`, `column` | the position inside the document (`;`-separated when several rows are involved) |
| `correct` | the expected behaviour, in words |
| `if_trapped` | the mishandling the condition targets, in words |
| `gt_correct_agg` / `gt_trapped_agg` | **the reference pair** for aggregate-based rules |
| `gt_correct_rowcount` / `gt_trapped_rowcount` | the reference pair for row-count rules |
| `gt_correct_share` / `gt_trapped_share` | the reference pair for share-based rules |
| `distractor_key`, `distractor_value` | the plausible-but-wrong alternative planted in the document |
| `sentinel`, `sentinel_is_numeric` | for `DISGUISED_MISSING` |
| `outlier_value`, `threshold` | for `STAT_OUTLIER` |
| `duplicate_of`, `variant_kind` | for `DUPLICATE_ROW` — which row it duplicates, and how the surface form differs |
| `unit_org` | for `INCORRECT_UNIT` — the agency whose rows use the other unit |
| `requires_note`, `note` | whether the condition needs the justification field, and why |

Not every column applies to every condition; unused cells are empty.

## `data/raw/R###_<Model>_<Task>_rep<N>.txt` — 54 files

The verbatim response of each run: 3 systems × 6 tests × 3 sentence forms. A fourth system was dropped before analysis and is not part of this release (`docs/COLLECTION_PROTOCOL.md`). Nothing has been edited — the files include the free-text reasoning that preceded the JSON block.

## `data/scores_cells.csv` — 81,729 rows

One row per reference cell per run.

| Column | Meaning |
|---|---|
| `run_id`, `model`, `task`, `rep`, `doc_id`, `row_key`, `column` | identifiers |
| `parse_status` | `ok` if the run's JSON parsed |
| `present_cell` | 1 if the system returned this cell at all → **coverage** |
| `correct_cell` | 1 if the returned value matches the reference within tolerance → **conditional accuracy**, computed over `present_cell == 1` |

Coverage denominators are per system: 6,912 = 2,304 reference cells per sentence form × 3 forms, over the four row-level tests.

## `data/scores_traps_fixed.csv` — 1,215 rows

One row per condition observation: 3 systems × 9 conditions × 15 documents × 3 sentence forms.

| Column | Meaning |
|---|---|
| `run_id`, `model`, `task`, `rep`, `doc_id`, `trap_type` | identifiers |
| `parse_status` | `ok` if the run's JSON parsed |
| `trap_hit` | 1 if the targeted failure occurred |
| `rules_fired` | which rule(s) fired, `;`-separated — empty when `trap_hit = 0` |
| `overmerge` | `DUPLICATE_ROW` only — merged rows that should have stayed separate |
| `overjudge` | `STAT_OUTLIER` only — declared the value wrong instead of flagging it |
| `false_alarm` | `STAT_OUTLIER` only — flagged a legitimate value |
| `oversplit` | `DELIMITER_SPLIT` only — split a field that should stay whole |
| `detected_but_included` | `DISGUISED_MISSING` only — noticed the sentinel and used it anyway |

Secondary flags are populated only for the condition they belong to and are blank elsewhere. They are reported descriptively and never counted as failures.

⚠️ `data/scores_traps.csv` is the **uncorrected** version. See [`SCORER_CORRECTION.md`](SCORER_CORRECTION.md).

## `data/human_key.csv`, `human_rater_A.csv`, `human_rater_B.csv` — 100 rows each

The scorer-validation sample, drawn across all nine conditions. `human_key.csv` holds the scorer's verdict (`trap_hit`); the two rater files hold each rater's independent verdict, recorded without seeing the scorer's output. Raters agreed with each other on 100/100 and with the scorer on 99/100 (κ = 0.974).

## `run_log.csv` — 72 rows

One row per run. The columns that matter for interpreting the results:

| Column | Meaning |
|---|---|
| `ชื่อรุ่นบนหน้าจอ` | **the model name the interface displayed** — `GPT-5.6`, `sonnet 5`, `Gemini 3.5 Flash-Lite` |
| `แชตใหม่` / `ปิด memory` / `ปิด custom instructions` / `ปิด web search และ tools` | protocol compliance |
| `ผลถูกตัดกลางคัน` | whether the response was truncated |
| `prompt_file`, `bundle_file`, `raw_file` | provenance of the run |

## `data/triage_raw.csv`

Per-run completeness triage: expected vs returned record counts, and `ความครบ%`. Runs below 80% are the three partial runs the sensitivity analysis removes.

## `data/manifest.json`

Generator settings and corpus statistics, including `"seed": 20260815` and a hash of the lexicon. `tie_out.py` checks a regenerated corpus against it.

## `data/findings_allowlist.json`

The set of claims the corpus actually supports, used by `NO_EVIDENCE` to decide whether a reported claim is licensed by the document.

## Derived files

`summary_rq1.csv`, `summary_rq2.csv`, `summary_rq3.csv`, `sensitivity_traps.csv`, `model_m1.csv`, `model_m2.csv`, and `figs/` are all regenerated by `reproduce.sh`. The copies in the repository were produced from the uncorrected scores and should not be read directly.
