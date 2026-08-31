#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
instability_examples.py — หาตัวอย่างที่ "โมเดลเดิม เอกสารเดิม แต่ตอบไม่เหมือนกัน"

เป็นหลักฐานรูปธรรมของ RQ3 · เขียนออกมาเป็น ตัวอย่างความไม่คงที่.md

รัน: python instability_examples.py
"""
import json
from pathlib import Path

import pandas as pd

from scorer import RunOutput, get

HERE = Path(__file__).resolve().parent
D = HERE / "data"
N_SHOW = 8

tr = pd.read_csv(D / "scores_traps.csv")
ce = pd.read_csv(D / "scores_cells.csv")
docs = json.loads((D / "documents.json").read_text(encoding="utf-8"))
doc_order, doc_meta = {}, {}
for d in docs:
    doc_order.setdefault(d["task"], []).append(d["doc_id"])
    doc_meta[d["doc_id"]] = d

# ---------------------------------------------------------------- หา trap ที่ไม่นิ่ง
g = (tr.dropna(subset=["trap_hit"])
       .groupby(["model", "task", "doc_id", "trap_type"])
       .trap_hit.agg(["mean", "count"]).reset_index())
unstable = g[(g["count"] >= 3) & (g["mean"] > 0) & (g["mean"] < 1)]
unstable = unstable.sort_values("mean", key=lambda s: (s - 0.5).abs())

# ---------------------------------------------------------------- หาเซลล์ที่ไม่นิ่ง
cg = (ce.groupby(["model", "task", "doc_id", "row_key", "column"])
        .correct_cell.agg(["mean", "count"]).reset_index())
cell_unstable = cg[(cg["count"] >= 3) & (cg["mean"] > 0) & (cg["mean"] < 1)]

cache = {}


def load(model, task, rep):
    k = (model, task, rep)
    if k not in cache:
        hits = list((D / "raw").glob(f"*_{model}_{task}_rep{rep}.txt"))
        cache[k] = (RunOutput(hits[0].read_text(encoding="utf-8", errors="replace"),
                              doc_ids=doc_order.get(task)) if hits else None)
    return cache[k]


def brief(rec, keys=6):
    """ย่อรายการให้อ่านง่าย ตัดฟิลด์ที่ยาวเกิน"""
    out = {}
    for k, v in list(rec.items())[:keys]:
        s = str(v)
        out[k] = s if len(s) <= 90 else s[:87] + "…"
    return json.dumps(out, ensure_ascii=False)


L = ["# ตัวอย่างความไม่คงที่ระหว่างการรันซ้ำ",
     "**หลักฐานรูปธรรมของ RQ3 · สร้างอัตโนมัติจาก `instability_examples.py`**", "",
     "> ทุกตัวอย่างในนี้คือ **โมเดลเดียวกัน เอกสารเดียวกัน คำสั่งความหมายเดียวกัน**",
     "> ต่างกันแค่ paraphrase ของ prompt เท่านั้น แต่คำตอบออกมาคนละอย่าง", "",
     f"พบตำแหน่งกับดักที่ผลไม่นิ่ง **{len(unstable)} ตำแหน่ง** "
     f"และเซลล์ที่ผลไม่นิ่ง **{len(cell_unstable):,} เซลล์**", "", "---", ""]

def all_reps_present(r):
    """เลือกเฉพาะตัวอย่างที่ทุก rep มีรายการของเอกสารนั้นจริง จะได้เทียบกันเห็นชัด"""
    sub = tr[(tr.model == r.model) & (tr.task == r.task) & (tr.doc_id == r.doc_id)]
    for _, row in sub.iterrows():
        o = load(r.model, r.task, str(row["rep"])[-1])
        if not o or not (o.by_doc.get(r.doc_id) or o.doc_rows.get(r.doc_id)):
            return False
    return True


picked, seen = [], set()
for r in unstable.itertuples():
    if len(picked) >= N_SHOW:
        break
    if (r.model, r.trap_type) in seen:      # กระจายให้เห็นหลายโมเดล หลายกับดัก
        continue
    if all_reps_present(r):
        picked.append(r)
        seen.add((r.model, r.trap_type))
if len(picked) < N_SHOW:
    for r in unstable.itertuples():
        if len(picked) >= N_SHOW:
            break
        if r not in picked and all_reps_present(r):
            picked.append(r)

for i, r in enumerate(picked, 1):
    dm = doc_meta[r.doc_id]
    L += [f"## ตัวอย่างที่ {i} · {r.model} · {r.trap_type}",
          f"เอกสาร `{r.doc_id}` · งาน {r.task} · "
          f"ตกกับดัก {int(r.mean * r.count)} จาก {int(r.count)} ครั้ง", ""]
    sub = tr[(tr.model == r.model) & (tr.task == r.task) & (tr.doc_id == r.doc_id)]
    for _, row in sub.sort_values("rep").iterrows():
        out = load(r.model, r.task, str(row["rep"])[-1])
        recs = (out.by_doc.get(r.doc_id, []) + out.doc_rows.get(r.doc_id, [])) if out else []
        verdict = "🔴 ตก" if row["trap_hit"] == 1 else "✅ ไม่ตก"
        L.append(f"**rep {str(row['rep'])[-1]}** — {verdict}")
        L.append("```json")
        L.append(brief(recs[0]) if recs else "ไม่พบรายการของเอกสารนี้ในผลลัพธ์")
        L.append("```")
    L += ["", "---", ""]

# ---------------------------------------------------------------- สรุปเชิงตัวเลข
L += ["## สรุปเชิงตัวเลข", "",
      "### ตำแหน่งกับดักที่ผลไม่นิ่ง แยกตามโมเดล", ""]
t1 = unstable.groupby("model").size().rename("จำนวนตำแหน่ง").to_frame()
tot = g.groupby("model").size().rename("ตำแหน่งทั้งหมด")
t1 = t1.join(tot)
t1["สัดส่วน"] = (t1["จำนวนตำแหน่ง"] / t1["ตำแหน่งทั้งหมด"]).round(3)
L += [t1.to_markdown(), "",
      "### ตำแหน่งกับดักที่ผลไม่นิ่ง แยกตามประเภทกับดัก", ""]
t2 = unstable.groupby("trap_type").size().rename("จำนวนตำแหน่งที่ไม่นิ่ง").to_frame()
L += [t2.sort_values("จำนวนตำแหน่งที่ไม่นิ่ง", ascending=False).to_markdown(), "",
      "### เซลล์ที่ตอบไม่เหมือนกันระหว่างรัน แยกตามโมเดล", ""]
t3 = (cell_unstable.groupby("model").size().rename("เซลล์ที่ไม่นิ่ง").to_frame()
      .join(cg.groupby("model").size().rename("เซลล์ทั้งหมด")))
t3["สัดส่วน"] = (t3["เซลล์ที่ไม่นิ่ง"] / t3["เซลล์ทั้งหมด"]).round(3)
L += [t3.to_markdown(), "",
      "> **วิธีอ่าน** สัดส่วนนี้คือโอกาสที่ถ้าคุณถามคำถามเดิมซ้ำ จะได้คำตอบต่างออกไป",
      "> ยิ่งสูง ยิ่งแปลว่าผลจากการทดสอบครั้งเดียวเชื่อไม่ได้"]

out_path = HERE / "ตัวอย่างความไม่คงที่.md"
out_path.write_text("\n".join(L), encoding="utf-8")
print(f"เขียน {out_path.name} แล้ว")
print(f"  ตำแหน่งกับดักที่ไม่นิ่ง {len(unstable)} · เซลล์ที่ไม่นิ่ง {len(cell_unstable):,}")
print("\n" + t1.to_string())
print("\n" + t3.to_string())
