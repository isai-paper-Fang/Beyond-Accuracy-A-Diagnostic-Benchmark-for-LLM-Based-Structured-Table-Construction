#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_human_sample.py — สุ่มตัวอย่าง 100 รายการให้คนตรวจ แล้วคำนวณ κ

ขั้นที่ 1  python make_human_sample.py
           → data\human_rater_A.csv และ human_rater_B.csv (ช่องคำตัดสินว่างไว้)
           → data\human_key.csv (คำตัดสินของโปรแกรม เก็บแยก ห้ามให้ผู้ตรวจเห็น)

ขั้นที่ 2  ผู้ตรวจสองคนกรอกคอลัมน์ 'คำตัดสินของคุณ' เป็น 1 (ตกกับดัก) หรือ 0 (ไม่ตก)
           โดยดูจากไฟล์เอกสารและไฟล์คำตอบดิบที่ระบุไว้ **ห้ามดูคำตัดสินของโปรแกรม**

ขั้นที่ 3  python make_human_sample.py --kappa
           → คำนวณ Cohen's κ ระหว่างคนกับโปรแกรม และระหว่างคนสองคน
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
D = HERE / "data"
SEED = 20260815
N = 100


def cohen_kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    po = (a == b).mean()
    pe = sum((a == v).mean() * (b == v).mean() for v in (0, 1))
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def build():
    tr = pd.read_csv(D / "scores_traps.csv").dropna(subset=["trap_hit"])
    rng = np.random.RandomState(SEED)
    # สุ่มแบบแบ่งชั้นตาม trap_type · NO_EVIDENCE ได้โควตาสูงกว่า
    # เพราะเป็นกับดักที่การให้คะแนนด้วยรายการคำอ่อนที่สุด (preregistration §9)
    weights = {t: (2.0 if t == "NO_EVIDENCE" else 1.0)
               for t in tr.trap_type.unique()}
    tot = sum(weights.values())
    picks = []
    for t, w in weights.items():
        k = max(4, int(round(N * w / tot)))
        g = tr[tr.trap_type == t]
        picks.append(g.sample(min(k, len(g)), random_state=rng))
    s = pd.concat(picks).sample(frac=1, random_state=rng).head(N).reset_index(drop=True)

    s["ไฟล์เอกสาร"] = "data/documents/" + s.doc_id + ".md"
    s["ไฟล์คำตอบ"] = ("data/raw/" + s.run_id + "_" + s.model + "_"
                      + s.task + "_" + s.rep.astype(str) + ".txt")
    s["item_id"] = ["H%03d" % (i + 1) for i in range(len(s))]

    key = s[["item_id", "run_id", "model", "task", "doc_id", "trap_type", "trap_hit"]]
    key.to_csv(D / "human_key.csv", index=False, encoding="utf-8-sig")

    sheet = s[["item_id", "trap_type", "doc_id", "ไฟล์เอกสาร", "ไฟล์คำตอบ"]].copy()
    sheet["คำตัดสินของคุณ (1=ตกกับดัก, 0=ไม่ตก)"] = ""
    sheet["หมายเหตุ"] = ""
    for r in ("A", "B"):
        sheet.to_csv(D / f"human_rater_{r}.csv", index=False, encoding="utf-8-sig")

    print(f"สร้างตัวอย่าง {len(sheet)} รายการ")
    print(sheet.trap_type.value_counts().to_string())
    print("\nไฟล์ให้ผู้ตรวจ: data\\human_rater_A.csv · human_rater_B.csv")
    print("เฉลยของโปรแกรม: data\\human_key.csv  🔴 ห้ามให้ผู้ตรวจเห็น")


def kappa():
    key = pd.read_csv(D / "human_key.csv")
    col = "คำตัดสินของคุณ (1=ตกกับดัก, 0=ไม่ตก)"
    got = {}
    for r in ("A", "B"):
        p = D / f"human_rater_{r}.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p)
        d = d[d[col].notna() & (d[col].astype(str).str.strip() != "")]
        if len(d):
            got[r] = d.set_index("item_id")[col].astype(float).astype(int)
    if not got:
        sys.exit("ยังไม่มีใครกรอกคำตัดสิน")
    k = key.set_index("item_id").trap_hit.astype(int)
    print(f"{'ผู้ตรวจ':<10}{'จำนวนที่กรอก':>14}{'κ กับโปรแกรม':>16}{'สอดคล้อง %':>14}")
    for r, v in got.items():
        idx = v.index.intersection(k.index)
        kk = cohen_kappa(v[idx], k[idx])
        print(f"{r:<10}{len(idx):>14}{kk:>16.3f}{(v[idx] == k[idx]).mean()*100:>13.1f}%")
    if len(got) == 2:
        idx = got["A"].index.intersection(got["B"].index)
        print(f"\nκ ระหว่างผู้ตรวจ A กับ B = {cohen_kappa(got['A'][idx], got['B'][idx]):.3f}")
    print("\nเกณฑ์ที่ตั้งไว้ใน preregistration §9: κ ≥ 0.80")
    print("ถ้าไม่ถึงเกณฑ์ ให้รายงานค่าที่ได้ตรง ๆ 🔴 ห้ามแก้ scorer แล้ววัดใหม่")


if __name__ == "__main__":
    kappa() if "--kappa" in sys.argv else build()
