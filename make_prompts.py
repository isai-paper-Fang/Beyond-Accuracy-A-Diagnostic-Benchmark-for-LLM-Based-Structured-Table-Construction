#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_prompts.py — ประกอบข้อความที่จะวางจริง หนึ่งไฟล์ต่อหนึ่งรัน

เหตุผล: การให้คนคัดลอกสามชิ้นมาต่อกันเอง 80 ครั้ง คือจุดที่จะเกิดความผิดพลาด
        เช่น ลืมสัญญา output หรือหยิบ paraphrase ผิด — ประกอบไว้ล่วงหน้าให้หมด

ผลลัพธ์: data/prompts/{run_id}_{model}_{task}_rep{r}.txt
         เปิดไฟล์ กด Ctrl+A Ctrl+C วางในแชตใหม่ ส่งครั้งเดียว จบ

รัน: python make_prompts.py
"""
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SRC = HERE / "C_prompts_v1.md"
OUT = HERE / "data" / "prompts"


def load_blocks():
    txt = SRC.read_text(encoding="utf-8")
    # สัญญา output = บล็อกแรกที่มีคำว่า "รูปแบบคำตอบ"
    contract = None
    for b in re.findall(r"```\n(.*?)```", txt, re.S):
        if "รูปแบบคำตอบ" in b:
            contract = b.strip()
            break
    if contract is None:
        raise SystemExit("หาสัญญา output ไม่เจอใน C_prompts_v1.md")

    prompts = {}
    for m in re.finditer(r"####\s*(T\d)-P(\d)\s*\n+```\n(.*?)```", txt, re.S):
        prompts[(m.group(1), int(m.group(2)))] = m.group(3).strip()
    return contract, prompts


def build():
    contract, prompts = load_blocks()
    if len(prompts) != 18:
        raise SystemExit(f"ต้องมี 18 prompt พบ {len(prompts)}")

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in ("pilot_log_template.csv", "run_log_template.csv"):
        df = pd.read_csv(HERE / "data" / name)
        for r in df.itertuples():
            key = (r.task, int(r.paraphrase))
            bundle = (HERE / "data" / f"task_bundle_{r.task}.md").read_text(encoding="utf-8")
            text = (
                f"{prompts[key]}\n\n"
                f"{contract}\n\n"
                f"----------------- เอกสาร -----------------\n\n"
                f"{bundle}"
            )
            fn = f"{r.run_id}_{r.model}_{r.task}_rep{r.replicate}.txt"
            (OUT / fn).write_text(text, encoding="utf-8")
            rows.append({"run_id": r.run_id, "model": r.model, "task": r.task,
                         "rep": r.replicate, "paraphrase": r.paraphrase,
                         "file": fn, "chars": len(text)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build()
    print(f"สร้างไฟล์พร้อมวาง {len(df)} ไฟล์ ที่ data/prompts/")
    print("\nขนาดต่อรัน (อักษร):")
    print(df.groupby("task").chars.agg(["min", "max"]).to_string())
    print(f"\nเล็กสุด {df.chars.min():,} · ใหญ่สุด {df.chars.max():,} อักษร")
    # ตรวจว่า paraphrase ตรงกับ replicate ทุกไฟล์
    bad = df[df.rep != df.paraphrase]
    print("ตรวจ paraphrase = replicate:", "ผ่าน" if bad.empty else f"ผิด {len(bad)} แถว")
