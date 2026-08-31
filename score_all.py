#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_all.py — ให้คะแนนทุกรันที่ใช้ได้ แล้วออกตารางผลครบชุด

รัน:  python score_all.py

ผลลัพธ์
  data\scores_traps.csv   Y4 trap_hit รายตำแหน่ง + ธงรอง  (ผลรันซ้ำ · เขียนทับได้)
  data\scores_cells.csv   Y1 Y2 รายเซลล์
  data\summary_rq1.csv    ความถูกต้องรายผลิตภัณฑ์
  data\summary_rq2.csv    ตาราง ผลิตภัณฑ์ x กับดัก  ← รูปหลักของบทความ
  data\summary_rq3.csv    ความแกว่งระหว่าง replicate

หมายเหตุ: ระบบที่สี่ถูกตัดออกก่อนวิเคราะห์ และไม่ได้เผยแพร่ในชุดนี้ (ดู preregistration §12)
"""
import json
from pathlib import Path

import pandas as pd

from scorer import RunOutput, score_trap, score_cells

HERE = Path(__file__).resolve().parent
D = HERE / "data"
EXCLUDE_MODELS = set()                # ระบบที่ถูกตัดออกไม่ได้อยู่ในชุดข้อมูลที่เผยแพร่แล้ว

traps_all = pd.read_csv(D / "trap_registry.csv")
cells_all = pd.read_csv(D / "ground_truth_cells.csv")
allow = json.loads((D / "findings_allowlist.json").read_text(encoding="utf-8"))
docs = json.loads((D / "documents.json").read_text(encoding="utf-8"))
doc_order = {}
for d in docs:
    doc_order.setdefault(d["task"], []).append(d["doc_id"])
clean_docs = {d["doc_id"] for d in docs if d["trap_type"] is None}

tri = pd.read_csv(D / "triage_raw.csv")
valid = tri[(~tri["เป็นสำเนา prompt"]) & (tri["parse"] == "ok")
            & (~tri.model.isin(EXCLUDE_MODELS))]
print(f"ให้คะแนน {len(valid)} รัน (ตัด {', '.join(EXCLUDE_MODELS)} และไฟล์ที่ใช้ไม่ได้)")

trap_rows, cell_rows, fallback_runs = [], [], []
for r in valid.itertuples():
    f = D / "raw" / f"{r.run_id}_{r.model}_{r.task}_{r.rep}.txt"
    out = RunOutput(f.read_text(encoding="utf-8", errors="replace"),
                    doc_ids=doc_order.get(r.task))
    if out.positional_fallback:
        fallback_runs.append(r.run_id)
    meta = {"run_id": r.run_id, "model": r.model, "task": r.task, "rep": r.rep}

    for t in traps_all[traps_all.task == r.task].to_dict("records"):
        t["_allowlist"] = allow.get(t["doc_id"], [])
        trap_rows.append({**meta, **score_trap(out, t)})

    gt = cells_all[cells_all.task == r.task].to_dict("records")
    for c in score_cells(out, gt):
        cell_rows.append({**meta, **c})

tr = pd.DataFrame(trap_rows)
ce = pd.DataFrame(cell_rows)
tr.to_csv(D / "scores_traps.csv", index=False, encoding="utf-8-sig")
ce.to_csv(D / "scores_cells.csv", index=False, encoding="utf-8-sig")
if fallback_runs:
    print(f"⚠️  ใช้การจับคู่ตามลำดับ {len(fallback_runs)} รัน (T3/T6) — บันทึกใน §12 แล้ว")

# ---------------------------------------------------------------- RQ1
print("\n" + "=" * 66)
print("RQ1 · ความถูกต้องระดับเซลล์")
print("=" * 66)
rq1 = ce.groupby("model").agg(
    เซลล์ทั้งหมด=("correct_cell", "size"),
    Y2_ปรากฏ=("present_cell", "mean"),
    Y1_ถูก=("correct_cell", "mean"),
).round(3)
rq1["Y1_เฉพาะที่ปรากฏ"] = (ce[ce.present_cell == 1].groupby("model")
                            .correct_cell.mean().round(3))
print(rq1.to_string())
rq1.to_csv(D / "summary_rq1.csv", encoding="utf-8-sig")

print("\nY1 รายงาน (เฉพาะเซลล์ที่ปรากฏ)")
print(ce[ce.present_cell == 1].pivot_table(index="model", columns="task",
                                           values="correct_cell").round(2).to_string())

# ---------------------------------------------------------------- RQ2
print("\n" + "=" * 66)
print("RQ2 · อัตราตกกับดัก  ผลิตภัณฑ์ x กับดัก   ← รูปหลักของบทความ")
print("=" * 66)
rq2 = tr.pivot_table(index="trap_type", columns="model",
                     values="trap_hit", aggfunc="mean").round(2)
rq2["เฉลี่ย"] = rq2.mean(axis=1).round(2)
print(rq2.to_string())
rq2.to_csv(D / "summary_rq2.csv", encoding="utf-8-sig")

band = tr.groupby("trap_type").trap_hit.mean()
out_band = band[(band < 0.15) | (band > 0.85)]
if len(out_band):
    print(f"\n🔴 กับดักที่อยู่นอกช่วง 0.15-0.85 — ไม่ให้ข้อมูลเชิงจำแนก {len(out_band)}/9")
    for k, v in out_band.items():
        print(f"   {k:<22} {v:.2f}  ({'ง่ายเกินไป' if v < 0.15 else 'ยากเกินไป'})")

flags = [c for c in ("overjudge", "false_alarm", "overmerge", "oversplit") if c in tr]
if flags:
    print("\n--- ธงรอง (เชิงพรรณนา ไม่เข้าโมเดล) ---")
    print(tr.groupby("model")[flags].mean().round(3).to_string())

# ---------------------------------------------------------------- RQ3
print("\n" + "=" * 66)
print("RQ3 · ความแกว่งระหว่างการรันซ้ำ")
print("=" * 66)
per_run = tr.groupby(["model", "task", "rep"]).trap_hit.mean().reset_index()

# 🔴 ต้องเทียบ "ภายในงานเดียวกัน" เท่านั้น
#    ถ้าเอาทุกงานมารวมกันก่อนคิด SD ความต่างระหว่างงานจะถูกนับเป็นความแกว่งของการรันซ้ำ
#    ทำให้ตัวเลขพองเกินจริง — ผิดพลาดนี้เคยเกิดขึ้นแล้วในการคำนวณรอบแรก
within = per_run.groupby(["model", "task"]).trap_hit.std().groupby("model").mean()
between = per_run.groupby(["model", "task"]).trap_hit.mean().groupby("task").std().mean()

rq3 = pd.DataFrame({
    "อัตราตกกับดักเฉลี่ย": per_run.groupby("model").trap_hit.mean().round(3),
    "SD ระหว่าง replicate (ภายในงาน)": within.round(3),
})
print(rq3.to_string())
print(f"\nSD ระหว่าง replicate ภายในงาน (เฉลี่ย) = {within.mean():.3f}")
print(f"SD ระหว่างผลิตภัณฑ์ ภายในงาน          = {between:.3f}")
print(f"อัตราส่วน = {within.mean()/between:.2f} เท่า")
if within.mean() >= between * 0.9:
    print("→ ความแกว่งจากการรันซ้ำใหญ่พอ ๆ กับความต่างระหว่างผลิตภัณฑ์")
    print("  การจัดอันดับจากการรันครั้งเดียวจึงเชื่อไม่ได้")

gg = (tr.dropna(subset=["trap_hit"]).groupby(["model", "task", "doc_id"])
        .trap_hit.agg(["mean", "count"]).reset_index())
gg = gg[gg["count"] >= 3]
uns = gg[(gg["mean"] > 0) & (gg["mean"] < 1)].groupby("model").size()
rq3["สัดส่วนตำแหน่งที่ผลไม่นิ่ง"] = (uns / gg.groupby("model").size()).round(3)
print("\nสัดส่วนตำแหน่งกับดักที่รัน 3 ครั้งได้ผลไม่ตรงกัน")
print(rq3["สัดส่วนตำแหน่งที่ผลไม่นิ่ง"].to_string())
rq3.to_csv(D / "summary_rq3.csv", encoding="utf-8-sig")

# ---------------------------------------------------------------- เอกสารสะอาด
print("\n--- อัตราการรายงานผิดในเอกสารสะอาด 15 ฉบับ ---")
cl = ce[ce.doc_id.isin(clean_docs) & (ce.present_cell == 1)]
if len(cl):
    print(cl.groupby("model").correct_cell.mean().round(3).rename("ความถูกต้อง").to_string())

print("\nบันทึกไฟล์สรุปทั้งหมดที่ data\\summary_*.csv แล้ว")
