# Collection protocol

The runs in `data/raw/` were collected through the systems' **web interfaces**, not their APIs. This document records exactly what was done, so the same procedure can be repeated on other systems.

## What was fixed before collection

- The corpus, the reference pairs, and the scoring rules were generated and hashed (`data/lockfile.json`) **before** any model saw a document.
- The analysis plan was fixed before collection. Two deviations occurred and are recorded in `analysis.py`.

## Per-run procedure

For every one of the 72 runs:

1. Open a **new chat**.
2. Turn **memory** off.
3. Turn **custom instructions** off.
4. Turn **web search and tools** off.
5. Paste the prompt for that (test, sentence form) pair, followed by the task bundle for that test.
6. Save the response verbatim to `data/raw/R###_<Model>_<Task>_rep<N>.txt`, including any free-text reasoning before the JSON block.
7. Record in `run_log.csv`: the model name shown on screen, whether a "continue" prompt was needed, whether the output was truncated, and any anomaly.

Run order was randomised across systems and tests rather than grouped by system.

## What was recorded and why it matters

The `ชื่อรุ่นบนหน้าจอ` column exists because a web interface does not expose a model version to the client. What it displayed was:

| System | Name shown on screen | Runs |
|---|---|---|
| ChatGPT | `GPT-5.6` | 18 |
| Claude | `sonnet 5` | 18 |
| Gemini | `Gemini 3.5 Flash-Lite` | 18 |

🔴 **The three services are not matched in tier.** Flash-Lite is a lightweight variant. Part of any difference observed between Gemini and the other two may follow from tier rather than from model family. Anyone repeating this protocol should either match tiers or record the mismatch as we have.

## What could not be controlled

System prompts, inference settings (temperature, top-p, max tokens), and model updates are not exposed by a web interface. The results therefore describe **these services during August 2026**, not the underlying base models. This is why the paper calls them deployed services rather than models.

## The excluded fourth system

A fourth system, a Thai-tuned model, was reached through a developer playground rather than a web interface. Its maximum-completion-token setting truncated responses at low values, and its runs became unstable at higher values, so no setting produced comparable data. It was dropped before any analysis, and the decision is recorded in `preregistration.md` §12. Its runs are not part of this release: the released data covers only the three systems the paper reports.

## Adding new systems

Follow the same seven steps. Name new files `R###_<Model>_<Task>_rep<N>.txt` using the test IDs `T1`–`T6`, add a row to `run_log.csv`, and re-run `reproduce.sh`. The scorer discovers runs from the filenames, so nothing else needs changing.

## What `run_log.csv` in this release does and does not contain

Every run has its `run_id`, model, test, sentence form, the prompt and bundle it used, the raw-output file it produced, the model name the interface displayed, and the four hygiene flags (new chat, memory off, custom instructions off, tools off), plus whether a continuation was requested and whether the output was truncated.

Four columns the protocol calls for are **empty in every row of this release**: `วันเวลาเริ่ม`, `วันเวลาจบ`, `ค่าตั้งต้นที่หน้าจอแสดง` and `ไฟล์แคปหน้าจอ`. The screenshots themselves are not published. Anyone repeating the protocol should fill them; do not read this release as evidence that per-run timings were captured.

## Known limitations of this protocol

- Web interfaces may apply server-side changes between runs that leave no trace in the log.
- Three runs returned truncated output (4%, 31%, 32% of expected records). They were retained with their completed portions, and the sensitivity analysis reports what happens when they are removed.
- The prompts for tests `T3` and `T6` did not ask for a document identifier, so outputs from those two tests were matched to documents by order, and only when the returned record count matched the document count exactly.
