# A Diagnostic Benchmark for LLM-Based Structured Table Construction

Replication package for the paper *Beyond Accuracy: A Diagnostic Benchmark for LLM-Based Structured Table Construction*.

The benchmark places **nine controlled data-quality defects** ("diagnostic conditions") into synthetic Thai administrative reports. Because a generator creates the documents, the correct table is known exactly for every document, and every condition carries a deterministic scoring rule. The same model output is therefore scored twice: once cell by cell for correctness, once condition by condition for the specific failure the condition targets.

---

## ⚠️ Read this before running anything

**1. Three trap-score files exist and they are not interchangeable.**
`data/scores_traps_fixed.csv` is what the paper reports. `data/scores_traps_uncorrected.csv` is the output of an earlier scorer version that mislabelled four `NO_EVIDENCE` observations, kept only so the correction is auditable. `data/scores_traps.csv` is scratch — whatever the last `score_all.py` run produced. It is not committed and does not exist in a fresh clone; step 1 of `reproduce.sh` creates it and every later run overwrites it. `docs/SCORER_CORRECTION.md` documents the diff.

**2. The scripts as shipped read the scratch file.**
`analysis.py`, `make_figures.py`, and `instability_examples.py` all read `scores_traps.csv`. Run `reproduce.sh`, which points them at the corrected file, or apply the one-line change yourself.

**3. `figs/` ships empty and `summary_*.csv` are regenerated.**
`reproduce.sh` writes them.

**4. `data/lockfile.json` will report differences.**
That is expected. Every one of them is listed and explained in **[`docs/INTEGRITY.md`](docs/INTEGRITY.md)**.

---

## What is in here

| Path | What it is | Needed to… |
|---|---|---|
| `data/documents/` | 150 synthetic reports, Markdown | inspect the corpus by eye |
| `data/documents.json` | the same corpus, structured | re-score, regenerate prompts |
| `C_prompts_v1.md` | the 18 canonical prompts (6 tests × 3 sentence forms) | see the exact wording |
| `data/prompts/` | the prompt file used by each individual run | trace any run back to its input |
| `data/ground_truth_cells.csv` | 9,081 reference cells | reproduce RQ1 |
| `data/trap_registry.csv` | **the reference pairs** — correct value *and* the value a specific mishandling produces, for all 135 condition positions | reproduce RQ2 |
| `data/raw/` | the 54 raw model outputs, verbatim (3 systems × 6 tests × 3 sentence forms) | re-score without re-running any model |
| `data/scores_cells.csv` · `data/scores_traps_fixed.csv` | our scoring output | check you reproduce our numbers |
| `frozen/` | byte-identical copies of the eight files that were renumbered, as they stood before | verify `data/lockfile.json` |
| `data/human_key.csv` · `data/human_rater_A.csv` · `data/human_rater_B.csv` | the 100-item scorer spot check | reproduce κ = 0.974 |
| `run_log.csv` | per-run record: model name shown on screen, prompt and bundle used, hygiene flags. Four columns are empty in this release — see `docs/COLLECTION_PROTOCOL.md` | know exactly which services were tested |
| `trap_rules.yaml` | the scoring rule for each condition | see what each rule does and does not catch |
| `scorer.py` · `score_all.py` | the scorer | re-score the raw outputs |
| `analysis.py` | GEE, Fisher + BH, stability, sensitivity | reproduce every number in the paper |
| `generator.py` · `A_คลังคำ_v1.yaml` · `manifest.json` | corpus generator (seed `20260815`) | regenerate the corpus from scratch |

## Reproduce

```bash
pip install -r requirements.txt
bash reproduce.sh
```

`reproduce.sh` runs three steps and prints what each one should produce:

1. **Re-score** the 54 raw outputs → `data/scores_cells.csv`, `data/scores_traps.csv`
2. **Audit** the score files → the uncorrected file must differ from the corrected one in exactly 4 rows, and the fresh re-score must match the corrected one in all 1,215. The script exits non-zero if either check fails.
3. **Analyse** → RQ1 (GEE), RQ2 (Fisher + BH), RQ3 (stability), sensitivity checks

Expected headline numbers:

| | ChatGPT | Claude | Gemini |
|---|---|---|---|
| Coverage | 0.989 | 0.880 | 0.698 |
| Conditional accuracy | 0.939 | 0.909 | 0.946 |
| Overall failure rate | 0.136 | 0.133 | 0.336 |
| SD across sentence forms | 0.028 | 0.115 | 0.334 |

All three pairwise accuracy comparisons give Holm-adjusted *p* = 1.000.

## Regenerate the corpus instead of using ours

```bash
python generator.py          # writes data/documents/, documents.json, ground_truth_cells.csv, trap_registry.csv
python make_prompts.py       # writes data/prompts/
python tie_out.py            # checks the generated corpus against manifest.json
```

The generator is seeded (`manifest.json` → `"seed": 20260815`). `tie_out.py` verifies that a regenerated corpus matches the one released here.

## Run the experiment on new models

The raw outputs in `data/raw/` came from web interfaces, not APIs. `docs/COLLECTION_PROTOCOL.md` gives the exact procedure we followed — new chat per run, memory off, custom instructions off, tools off, and what we recorded for each run. Drop new outputs into `data/raw/` as `R###_<Model>_<Task>_rep<N>.txt`, using the test IDs `T1`–`T6`, and re-run `reproduce.sh`.

## What this benchmark does not tell you

- It does not estimate how often these defects occur in real reports. The corpus is synthetic and has not been validated against operational documents.
- It does not rank systems. Conditions are confounded with tests, and the three services tested were not matched in tier.
- It covers three deployed systems. A fourth was dropped before analysis because its interface could not produce comparable output; `docs/COLLECTION_PROTOCOL.md` says why, and it is not part of this release.
- A failure rate of zero means the specific error a condition defines did not occur. It does not mean the output was correct. `docs/CONDITIONS.md` states, for each condition, what its rule does **not** catch.

## Documentation

- [`docs/TEST_ID_MAPPING.md`](docs/TEST_ID_MAPPING.md) — the six tests, and the older IDs two frozen documents still use
- [`docs/INTEGRITY.md`](docs/INTEGRITY.md) — what `data/lockfile.json` proves, and every difference it reports
- [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) — every column of every CSV
- [`docs/CONDITIONS.md`](docs/CONDITIONS.md) — the nine conditions: prompt wording → expected behaviour → scoring rule → what the rule misses
- [`docs/COLLECTION_PROTOCOL.md`](docs/COLLECTION_PROTOCOL.md) — how the runs were collected
- [`docs/SCORER_CORRECTION.md`](docs/SCORER_CORRECTION.md) — the four-row correction, and why both score files are kept

## Licence

Code (`*.py`, `*.yaml`, `*.sh`): MIT. Data (`data/`): CC BY 4.0. See `LICENSE`.

## Citation

See `CITATION.cff`.

---

## หมายเหตุภาษาไทย

คลังเอกสาร คำสั่ง และค่าอ้างอิงทั้งหมดเป็นภาษาไทย ส่วนโค้ดและเอกสารประกอบเป็นภาษาอังกฤษเพื่อให้คนนอกประเทศทำซ้ำได้ สามเรื่องที่ต้องอ่านก่อนใช้ข้อมูล — เลขเทสในไฟล์ข้อมูลตรงกับบทความแล้ว (`T1`–`T6`) ยกเว้นสองไฟล์ที่ตรึงไว้ตามเดิมโดยตั้งใจ (`docs/TEST_ID_MAPPING.md`) · ต้องใช้ `scores_traps_fixed.csv` ไม่ใช่ `scores_traps.csv` ซึ่งเป็นไฟล์ชั่วคราว · และ `lock_files.py --verify` จะรายงานความต่างเป็นเรื่องปกติ อ่านคำอธิบายทุกข้อได้ที่ `docs/INTEGRITY.md`
