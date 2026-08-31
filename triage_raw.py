#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
triage_raw.py — ตรวจสุขภาพไฟล์ดิบทั้ง 72 รัน ก่อนให้คะแนน

ตรวจสามอย่าง
  1. ไฟล์นั้นเป็น "สำเนาของ prompt" หรือเปล่า (คัดลอกผิดช่อง)
  2. แยกวิเคราะห์บล็อก json ได้ไหม
  3. ได้รายการมากี่รายการ เทียบกับที่ควรได้

รัน: python triage_raw.py
"""
import hashlib
import json
from pathlib import Path

import pandas as pd

from scorer import RunOutput

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
PROMPTS = HERE / "data" / "prompts"

# จำนวนแถวอินพุตต่องาน ใช้ประเมินว่าผลลัพธ์ครบไหม
docs = json.loads((HERE / "data" / "documents.json").read_text(encoding="utf-8"))
rows_per_task, docs_per_task = {}, {}
for d in docs:
    rows_per_task[d["task"]] = rows_per_task.get(d["task"], 0) + len(d["rows"])
    docs_per_task[d["task"]] = docs_per_task.get(d["task"], 0) + 1


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


prompt_hashes = {sha(p) for p in PROMPTS.glob("*.txt")}

doc_order = {}
for d in docs:
    doc_order.setdefault(d["task"], []).append(d["doc_id"])

rows = []
for f in sorted(RAW.glob("*.txt")):
    rid, model, task, rep = f.stem.split("_")
    raw = f.read_text(encoding="utf-8", errors="replace")
    is_prompt = sha(f) in prompt_hashes
    out = None if is_prompt else RunOutput(raw, doc_ids=doc_order.get(task))
    rows.append({
        "run_id": rid, "model": model, "task": task, "rep": rep,
        "bytes": f.stat().st_size,
        "เป็นสำเนา prompt": is_prompt,
        "parse": "—" if is_prompt else out.status,
        "แถวกิจกรรม": 0 if is_prompt else len(out.by_row),
        "รายการเอกสาร": 0 if is_prompt else len(out.by_doc),
        "แถวที่ควรได้": rows_per_task[task],
        "เอกสารที่ควรได้": docs_per_task[task],
    })

df = pd.DataFrame(rows)
df["ใช้ได้"] = (~df["เป็นสำเนา prompt"]) & (df["parse"] == "ok")

# 🔴 หน่วยของผลลัพธ์ไม่เท่ากันทุกงาน — วัดความครบด้วยหน่วยที่ถูกต้องของงานนั้น
#    T1 T2 T4 T5 = รายกิจกรรม · T3 T6 = รายเอกสาร
DOC_LEVEL = {"T3", "T6"}
df["ความครบ%"] = df.apply(
    lambda r: round(100 * (r["รายการเอกสาร"] / r["เอกสารที่ควรได้"]
                           if r["task"] in DOC_LEVEL
                           else r["แถวกิจกรรม"] / r["แถวที่ควรได้"]))
    if not r["เป็นสำเนา prompt"] else 0, axis=1)

print("=" * 74)
print(f"ตรวจไฟล์ดิบ {len(df)} รัน")
print("=" * 74)

bad_copy = df[df["เป็นสำเนา prompt"]]
if len(bad_copy):
    print(f"\n🔴 เป็นสำเนาของ prompt ไม่ใช่คำตอบ — {len(bad_copy)} รัน ต้องรันใหม่")
    for m, g in bad_copy.groupby("model"):
        print(f"   {m:<9} {len(g):>2} รัน : {', '.join(g.run_id)}")

bad_parse = df[(~df["เป็นสำเนา prompt"]) & (df["parse"] != "ok")]
if len(bad_parse):
    print(f"\n⚠️  แยกวิเคราะห์บล็อก json ไม่ผ่าน — {len(bad_parse)} รัน")
    for r in bad_parse.itertuples():
        print(f"   {r.run_id} {r.model:<9} {r.task}  ({r.parse})")

ok = df[df["ใช้ได้"]]
print(f"\n✅ ใช้ให้คะแนนได้ {len(ok)}/{len(df)} รัน")

print("\n--- ความครบของผลลัพธ์ (% ของแถวที่ควรได้) ---")
piv = ok.pivot_table(index="model", columns="task", values="ความครบ%", aggfunc="mean")
print(piv.round(0).to_string())

print("\n--- จำนวนรันที่ใช้ได้ ต่อ โมเดล × งาน ---")
print(pd.crosstab(ok.model, ok.task).to_string())

trunc = ok[ok["ความครบ%"] < 80]
if len(trunc):
    print(f"\n⚠️  ผลลัพธ์ไม่ครบ 80% — {len(trunc)} รัน (อาจถูกตัดกลางคัน)")
    for _, r in trunc.sort_values("ความครบ%").iterrows():
        unit = "เอกสาร" if r["task"] in DOC_LEVEL else "แถว"
        got = r["รายการเอกสาร"] if r["task"] in DOC_LEVEL else r["แถวกิจกรรม"]
        want = r["เอกสารที่ควรได้"] if r["task"] in DOC_LEVEL else r["แถวที่ควรได้"]
        print(f"   {r['run_id']} {r['model']:<9} {r['task']} ได้ {got}/{want} {unit} "
              f"({r['ความครบ%']:.0f}%)")

df.to_csv(HERE / "data" / "triage_raw.csv", index=False, encoding="utf-8-sig")
print(f"\nบันทึกตารางเต็มที่ data/triage_raw.csv")
