#!/usr/bin/env bash
# Reproduce every number reported in the paper, from the raw model outputs.
#
# Usage:  bash reproduce.sh
#
# Three trap-score files exist and they are not interchangeable:
#   data/scores_traps_uncorrected.csv  historical  produced by the scorer before
#                                      the NO_EVIDENCE bug was fixed. Never
#                                      overwritten. Kept so the fix is auditable.
#   data/scores_traps_fixed.csv        canonical   what the paper reports.
#                                      Never overwritten.
#   data/scores_traps.csv              scratch     whatever step 1 just produced.
#                                      Overwritten on every run.
#
# Steps:
#   1. score    re-score data/raw/ -> data/scores_cells.csv, data/scores_traps.csv
#   2. audit    (a) uncorrected vs fixed  -> must differ in exactly 4 rows
#               (b) fresh    vs fixed     -> must be identical
#   3. analyse  RQ1 (GEE), RQ2 (Fisher+BH), RQ3 (stability), sensitivity
#
# See docs/SCORER_CORRECTION.md.

set -euo pipefail
cd "$(dirname "$0")"

echo "=============================================================="
echo "1/3  Scoring the raw outputs"
echo "=============================================================="
python score_all.py

echo
echo "=============================================================="
echo "2/3  Auditing the trap-score files"
echo "=============================================================="
python - <<'PY'
import csv, pathlib, sys
d = pathlib.Path("data")
def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return {(r["run_id"], r["doc_id"]): r for r in csv.DictReader(f)}
for name in ("scores_traps_uncorrected.csv", "scores_traps_fixed.csv", "scores_traps.csv"):
    if not (d / name).exists():
        sys.exit(f"data/{name} is missing")
unc, fix, new = load(d/"scores_traps_uncorrected.csv"), load(d/"scores_traps_fixed.csv"), load(d/"scores_traps.csv")

a = [k for k in unc if unc[k]["trap_hit"] != fix[k]["trap_hit"]]
print(f"(a) uncorrected vs fixed : {len(unc)} rows compared, {len(a)} differ   (expected 4)")
for k in sorted(a):
    r = unc[k]
    print(f"      {r['run_id']}  {r['doc_id']}  {r['trap_type']:14} {r['model']:8} {r['trap_hit']} -> {fix[k]['trap_hit']}")

b = [k for k in new if new[k]["trap_hit"] != fix[k]["trap_hit"]]
print(f"(b) fresh re-score vs fixed : {len(new)} rows compared, {len(b)} differ   (expected 0)")
for k in sorted(b)[:10]:
    r = new[k]
    print(f"      {r['run_id']}  {r['doc_id']}  {r['trap_type']:14} {r['model']:8} {r['trap_hit']} vs {fix[k]['trap_hit']}")

if len(a) != 4 or len(b) != 0:
    sys.exit("AUDIT FAILED — the score files are not in the expected state")
print("audit passed")
PY

echo
echo "=============================================================="
echo "3/3  Analysis (reading the CORRECTED trap scores)"
echo "=============================================================="
cp data/scores_traps.csv data/_scratch_scores_traps.csv
cp data/scores_traps_fixed.csv data/scores_traps.csv
python analysis.py | tee analysis_output.txt
cp data/_scratch_scores_traps.csv data/scores_traps.csv
rm -f data/_scratch_scores_traps.csv

echo
echo "=============================================================="
echo "Expected headline numbers"
echo "=============================================================="
cat <<'TXT'
                          ChatGPT   Claude   Gemini
  coverage                  0.989    0.880    0.698
  conditional accuracy      0.939    0.909    0.946
  overall failure rate      0.136    0.133    0.336
  SD across sentence forms  0.028    0.115    0.334

  all pairwise accuracy comparisons: Holm-adjusted p = 1.000
  within-test SD 0.159  vs  between-system SD 0.160   (ratio 0.99)
  unstable positions: 10 / 21 / 74 of 135 per system
  scorer spot check: two people agree 100/100 with each other, 99/100 with the scorer
TXT
echo
echo "Full analysis output written to analysis_output.txt"
