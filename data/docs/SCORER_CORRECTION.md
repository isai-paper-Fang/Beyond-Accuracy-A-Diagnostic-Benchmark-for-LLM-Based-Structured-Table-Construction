# The scorer correction

Two trap-score files ship with this repository. This document says exactly how they differ and which one the paper uses.

| File | Status |
|---|---|
| `data/scores_traps.csv` | output of an earlier scorer version — **do not use for analysis** |
| `data/scores_traps_fixed.csv` | corrected — **this is what the paper reports** |

## The diff

The two files have the same 1,215 rows and the same columns. They differ in **4 rows**, all of them `NO_EVIDENCE` observations from one system, where `trap_hit` changes from `1` to `0`. No `rules_fired` value changes anywhere.

```
rows compared                    1215
rows where trap_hit differs         4
  NO_EVIDENCE / Claude  1 → 0       4
rows where rules_fired differs      0
```

Reproduce the diff:

```bash
python - <<'PY'
import csv
a={(r['run_id'],r['doc_id']):r for r in csv.DictReader(open('data/scores_traps.csv',encoding='utf-8-sig'))}
b={(r['run_id'],r['doc_id']):r for r in csv.DictReader(open('data/scores_traps_fixed.csv',encoding='utf-8-sig'))}
d=[k for k in a if a[k]['trap_hit']!=b[k]['trap_hit']]
print(len(d), [(a[k]['trap_type'],a[k]['model'],a[k]['trap_hit'],b[k]['trap_hit']) for k in d])
PY
```

## What the four rows change

Four rows out of 1,215 is 0.3% of the data, but they fall on a claim the paper makes explicitly.

| Quantity | Uncorrected | Corrected |
|---|---|---|
| `NO_EVIDENCE`, Claude | 4/45 = 0.089 | 0/45 = 0.000 |
| Claude overall failure rate | 58/405 = 0.143 | 54/405 = 0.133 |
| Claude SD across sentence forms | 0.128 | 0.115 |
| Claude unstable positions | 25/135 = 0.185 | 21/135 = 0.156 |
| Conditions with **no** failure in any run | 2 | **3** |

The last row matters most. The paper states that `NO_EVIDENCE`, `INCORRECT_UNIT`, and `DELIMITER_SPLIT` produced no failure in any run, and then argues that a zero rate is evidence about one mechanism rather than about correctness. That set of three conditions exists only in the corrected file.

## Why both files are kept

Deleting the uncorrected file would make the correction unverifiable. Keeping it without this document would leave two contradictory files with no explanation. Both are here, and the corrected one is the only one any analysis should read.

## The scripts still read the wrong file

`analysis.py`, `make_figures.py`, and `instability_examples.py` each contain a line of the form

```python
tr = pd.read_csv(D / "scores_traps.csv")
```

`reproduce.sh` overrides this. If you run those scripts directly, change the filename to `scores_traps_fixed.csv` first.
