# The nine diagnostic conditions

For each condition: where it lives, what the document does, what a correct answer looks like, which rule decides, and — most importantly — **what the rule does not catch**.

Test IDs below are **data-file IDs**. See [`TEST_ID_MAPPING.md`](TEST_ID_MAPPING.md).

Every condition appears in 15 documents. Each system meets each condition 45 times (15 documents × 3 sentence forms).

---

## Family A — defects present in the source document

### `MISSING_VALUE` · host test `T1`

- **In the document** — one activity's disbursement cell is empty, marked with a dash.
- **Correct behaviour** — report that cell as unavailable, and do not label the row complete.
- **Reference pair** — `gt_correct_agg` equals `gt_trapped_agg`. They are *arithmetically identical*, because a total that excludes an absent value equals a total that counts it as zero.
- **Rules** (disjunctive) — `numeric_at_trap_cell` on column `เบิกจ่าย`; `missing_keyword` at document scope against the `INCOMPLETE` word set.
- **Does not catch** — a system that omits the row entirely *and* says so. The condition is about substituting a number for an absence, not about coverage.
- **Note** — this condition is the reason the output contract requires a justification field: no numeric comparison can separate the two behaviours.

### `DISGUISED_MISSING` · host test `T1`

- **In the document** — a sentinel value (e.g. an implausible placeholder) appears where a real number should be, and looks like a valid number.
- **Correct behaviour** — treat the sentinel as missing, not as data.
- **Rules** — `agg_equals_trapped_and_undetected` (tolerance: `จำนวนนับ`); secondary flags `sentinel_present`, `agg_equals_trapped_but_detected`.
- **Does not catch** — a system that detects the sentinel, says so, **and still includes it**. That case is recorded as the secondary flag `detected_but_included`, not as a failure. Claude did this on 30 of its 45 positions while scoring 0.00 on the condition itself.

### `DUPLICATE_ROW` · host test `T3`

- **In the document** — one agency appears under several written forms (an extra space, an abbreviation, a spelled-out name).
- **Correct behaviour** — merge the forms before aggregating.
- **Rules** — `agg_equals_trapped` (tolerance: `เงินบาท`, ±1); `rowcount_equals_trapped`; secondary flag `rowcount_below_correct` (over-merging).
- **Does not catch** — a total that is wrong for some *other* reason. The rule fires only when the reported total or row count equals the value that counting the duplicate twice would give.
- **Note** — the only condition on which all three systems failed the majority of the time.

### `INCORRECT_UNIT` · host test `T3`

- **In the document** — some rows are stated in a different unit, declared in a footnote.
- **Correct behaviour** — convert before aggregating.
- **Rules** — `agg_equals_trapped` (tolerance: `เงินบาท`) only.
- **Does not catch** — 🔴 **anything except plain addition without conversion.** In our runs the rule fired zero times, yet only 62 of 135 observations reported a correct document total: 28 reported a value matching neither reference, and 45 reported no per-document total at all. A rate of 0.00 for this condition is the clearest example in the benchmark of *no failure detected* not meaning *correct*.

### `DELIMITER_SPLIT` · host test `T5`

- **In the document** — one field holds several values separated by a delimiter.
- **Correct behaviour** — emit one record per value.
- **Rules** — `agg_equals_trapped` (tolerance: `จำนวนนับ`); secondary flag `split_at_distractor` (over-splitting a field that should stay whole).
- **Does not catch** — a partial split, or a split that also drops a value, unless the resulting count happens to equal the un-split count.

### `STAT_OUTLIER` · host test `T6`

- **In the document** — one participation count exceeds 3 × IQR of its own document.
- **Correct behaviour** — flag the row for review. **Do not correct the value** — this follows the data-error / error-indicator distinction of Bhadauria et al.
- **Rules** — `no_flag_at_trap_row` on column `ควรตรวจสอบเพิ่มเติม`; secondary flags `keyword_at_trap_row` (over-judging: declaring the value wrong rather than flagging it) and `flag_at_distractor_row` (false alarm on a legitimate value).
- **Does not catch** — a system that flags the right row for the wrong reason.
- **Note** — read the failure rate together with `overjudge`. Claude failed 15/45 *and* over-judged 30/45; a low failure rate here is not the same as cautious behaviour.

---

## Family B — the document is clean, but invites an unsupported output

### `BAIT_NO_NUMBER` · host test `T4`

- **In the document** — the prompt asks for a fourth-quarter balance; the document does not report one. A previous-quarter figure sits in a footnote as a plausible substitute (`distractor_value`).
- **Correct behaviour** — state that the requested period is not reported.
- **Rules** — `numeric_where_refusal_expected` on the column `ยอดคงเหลือไตรมาสที่ 4`, against the `REFUSAL` word set.
- **Does not catch** — abstaining for the wrong reason, or abstaining on a period that *is* reported.

### `TEXT_NUMBER_CONFLICT` · host test `T7`

- **In the document** — a total stated in prose disagrees with the total computable from the table.
- **Correct behaviour** — report the conflict.
- **Rules** — `missing_keyword` against the `CONFLICT` word set.
- **Does not catch** — a system that notices the conflict and describes it in words the `CONFLICT` set does not contain. The rule is lexical.

### `NO_EVIDENCE` · host test `T7`

- **In the document** — no outcome measure is reported anywhere.
- **Correct behaviour** — do not claim an outcome.
- **Rules** — `claim_outside_allowlist`, checked against `findings_allowlist.json` and the `OUTCOME` word set.
- **Does not catch** — an unsupported claim phrased outside the `OUTCOME` word set, or a claim about something other than an outcome.
- **Note** — 🔴 the four rows corrected in `scores_traps_fixed.csv` are all in this condition. See [`SCORER_CORRECTION.md`](SCORER_CORRECTION.md).

---

## Word sets and tolerances

Defined once in `trap_rules.yaml` and shared across rules.

| Set | Used by |
|---|---|
| `REFUSAL` | `BAIT_NO_NUMBER` |
| `CONFLICT` | `TEXT_NUMBER_CONFLICT` |
| `OUTCOME` | `NO_EVIDENCE` |
| `JUDGMENT` | `STAT_OUTLIER` (over-judging flag) |
| `DETECT` | `DISGUISED_MISSING` |
| `INCOMPLETE` | `MISSING_VALUE` |

| Tolerance | Value |
|---|---|
| `เงินบาท` (money) | ±1 baht |
| `จำนวนนับ` (count) | exact |
| `ร้อยละ` (percentage) | ±0.5 pp |

## Rules are disjunctive

A condition fires if **any** of its `hit_rules` matches. The `rules_fired` column of `scores_traps_fixed.csv` records which one did, so a failure can always be traced to a specific rule.

## Reading a zero

A zero in the failure-rate table means: *the specific error this condition defines was not observed.* It does not mean the output was correct. Each entry above lists what its rule does not catch; `INCORRECT_UNIT` is the worked example.
