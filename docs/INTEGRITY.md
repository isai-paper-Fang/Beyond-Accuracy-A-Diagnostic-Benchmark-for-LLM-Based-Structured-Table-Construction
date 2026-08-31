# What `data/lockfile.json` proves, and what it does not

`preregistration.md` was written on 11 August 2026, before any data was collected. `lock_files.py` then recorded a SHA-256 of every file the plan depended on, and `data/lockfile.json` is that record. Running `python lock_files.py --verify` compares the files as they stand now against those hashes.

**It will report differences, and that is expected.** This page lists every one of them and why it exists, so the report can be read rather than guessed at.

## Run the check

```bash
python lock_files.py --verify
```

## Every difference, and why

### Three files are reported missing

`E_โพรโทคอลเก็บข้อมูล.md`, `data/run_log_template.csv`, `data/pilot_log_template.csv` were part of the working directory but are not part of this release. The collection protocol is published here as `docs/COLLECTION_PROTOCOL.md` instead, and the run log as `run_log.csv`.

### Two files changed because the scorer was corrected

| File | Why |
|---|---|
| `scorer.py` | a bug mislabelled four `NO_EVIDENCE` observations. `docs/SCORER_CORRECTION.md` documents the fix and its effect on the results. |
| `trap_rules.yaml` | changed with it. |

This deviation is recorded in `preregistration.md` §12.

### Two files changed for reasons recorded in the preregistration

`preregistration.md` itself and `test_scorer.py` were edited during the study, in both cases before analysis. `preregistration.md` §12 is the log.

### Eight files changed because the test IDs were renumbered for release

The six tests carried non-contiguous IDs while the experiment ran; they were renumbered to `T1`–`T6` for this release. See [`TEST_ID_MAPPING.md`](TEST_ID_MAPPING.md). Renumbering rewrites bytes, so the hashes of these files no longer match:

`C_prompts_v1.md` · `trap_rules.yaml` · `generator.py` · `scorer.py` · `make_run_log.py` · `data/ground_truth_cells.csv` · `data/trap_registry.csv` · `data/documents.json`

**The pre-renumbering bytes of all eight are kept in `frozen/`.** Six of them hash-match `lockfile.json` exactly, which is what makes the 11 August lock verifiable for those six:

| `frozen/` file | matches `lockfile.json`? |
|---|---|
| `C_prompts_v1.md` | yes |
| `generator.py` | yes |
| `make_run_log.py` | yes |
| `data/documents.json` | yes |
| `data/ground_truth_cells.csv` | yes |
| `data/trap_registry.csv` | yes |
| `scorer.py` | no — this is the post-fix version, not the locked one |
| `trap_rules.yaml` | no — this is the post-fix version, not the locked one |

To check the six for yourself:

```python
import json, hashlib, pathlib
lock = json.load(open("data/lockfile.json", encoding="utf-8"))["files"]
for rel in ["C_prompts_v1.md", "generator.py", "make_run_log.py",
            "data/documents.json", "data/ground_truth_cells.csv", "data/trap_registry.csv"]:
    h = hashlib.sha256(pathlib.Path("frozen", rel).read_bytes()).hexdigest()
    print(rel, h == lock[rel]["sha256"])
```

The two that do not match cannot be verified against the 11 August lock from this repository, because the pre-fix versions of the scorer were superseded during the study. `docs/SCORER_CORRECTION.md` states exactly what the fix changed, and `data/scores_traps_uncorrected.csv` is the output of the pre-fix scorer, so the effect of the change is auditable even though the code is not.

## What this adds up to

The lock establishes that the corpus, the reference values, the prompts and the generator were fixed before data collection. It does not establish that the scorer was never touched — it was, once, and that change is documented in three places. It also does not establish the *time* independently: the timestamp in `lockfile.json` comes from the authoring machine's own clock, which proves nothing on its own. Nothing in the paper is described as preregistered; the analysis plan is described as prespecified and hash-locked, which is what this record supports.

## Files that were deliberately not renumbered

`preregistration.md` and `trap_spec.md` are dated records of decisions taken before the data existed. Rewriting their test IDs would falsify that record, so both keep the original IDs. [`TEST_ID_MAPPING.md`](TEST_ID_MAPPING.md) maps between the two schemes.
