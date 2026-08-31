#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_run_log.py — ตรวจ run_log ก่อนวิเคราะห์ (E §7)

รัน: python check_run_log.py [run_log.csv]
ถ้าไม่ผ่านแม้ข้อเดียว ห้ามเริ่มวิเคราะห์
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
if len(sys.argv) > 1:
    path = Path(sys.argv[1])
else:                                   # ในชุดที่เผยแพร่ run_log.csv อยู่ที่รากของ repo
    path = next((c for c in (HERE / "run_log.csv", HERE / "data" / "run_log.csv") if c.exists()),
                HERE / "run_log.csv")

# คอลัมน์ที่ต้องมีค่าเสมอในชุดที่เผยแพร่
REQUIRED = ["ชื่อรุ่นบนหน้าจอ"]
# คอลัมน์ที่โพรโทคอลให้บันทึกไว้ตอนเก็บข้อมูล แต่ว่างในชุดที่เผยแพร่
NOT_PUBLISHED = ["วันเวลาเริ่ม", "วันเวลาจบ", "ค่าตั้งต้นที่หน้าจอแสดง", "ไฟล์แคปหน้าจอ"]
YESNO = ["แชตใหม่", "ปิด memory", "ปิด custom instructions", "ปิด web search และ tools"]
YES = {"ใช่", "yes", "y", "true", "1"}

fails, notes = [], []


def ck(cond, msg):
    if not cond:
        fails.append(msg)


if not path.exists():
    sys.exit(f"ไม่พบไฟล์ {path}\nคัดลอก data/run_log_template.csv มาเป็น run_log.csv "
             f"แล้วกรอกให้ครบก่อน")

df = pd.read_csv(path).fillna("")
print("=" * 60)
print(f"ตรวจ {path.name} — {len(df)} แถว")
print("=" * 60)

EXPECTED = 3 * 6 * 3          # 3 ผลิตภัณฑ์ x 6 เทส x 3 รูปประโยค
ck(len(df) == EXPECTED, f"ต้องมี {EXPECTED} แถว พบ {len(df)}")
ck(df.run_id.is_unique, "run_id ซ้ำ")

x = pd.crosstab(df.model, df.task)
ck((x.values == 3).all(), f"ความสมดุลผิด:\n{x}")

for c in REQUIRED:
    if c not in df.columns:
        fails.append(f"ไม่มีคอลัมน์ {c}")
        continue
    blank = df[df[c].astype(str).str.strip() == ""]
    ck(blank.empty, f"คอลัมน์ '{c}' ว่าง {len(blank)} แถว: "
                    f"{list(blank.run_id)[:6]}")

for c in NOT_PUBLISHED:
    if c in df.columns:
        blank = df[df[c].astype(str).str.strip() == ""]
        if len(blank) == len(df):
            notes.append(f"คอลัมน์ '{c}' ว่างทั้งหมด — ว่างในชุดที่เผยแพร่ (ดู docs/COLLECTION_PROTOCOL.md)")

for c in YESNO:
    if c not in df.columns:
        continue
    bad = df[~df[c].astype(str).str.strip().str.lower().isin(YES)]
    ck(bad.empty, f"'{c}' ไม่ได้ตอบว่าใช่ {len(bad)} แถว: {list(bad.run_id)[:6]}")

# ไฟล์ที่อ้างถึงต้องมีอยู่จริง
for col in ["raw_file"]:
    if col not in df.columns:
        continue
    miss = [r.run_id for r in df.itertuples()
            if str(getattr(r, col.replace(" ", "_"), "") or "").strip()
            and not (HERE / "data" / str(getattr(r, col.replace(" ", "_")))).exists()
            and not (HERE / str(getattr(r, col.replace(" ", "_")))).exists()]
    if miss:
        fails.append(f"ไฟล์ตาม '{col}' ไม่พบ {len(miss)} รายการ: {miss[:6]}")

# เวลาต้องเรียงตามลำดับที่กำหนด
if "วันเวลาเริ่ม" in df.columns:
    t = pd.to_datetime(df.sort_values("order")["วันเวลาเริ่ม"], errors="coerce")
    if t.notna().all():
        ck(t.is_monotonic_increasing,
           "วันเวลาเริ่มไม่เรียงตาม order — รันสลับลำดับจะทำให้เวลาสับสนกับโมเดล")
    else:
        notes.append("แปลงวันเวลาไม่ได้บางแถว ข้ามการตรวจลำดับเวลา")

# รายงานเชิงพรรณนา
if "ใช้คำสั่งขอให้พิมพ์ต่อ" in df.columns:
    v = pd.to_numeric(df["ใช้คำสั่งขอให้พิมพ์ต่อ"], errors="coerce").fillna(0)
    notes.append(f"ใช้คำสั่งขอให้พิมพ์ต่อ {int(v.sum())}/{len(df)} รัน "
                 f"({v.mean():.0%}) — ต้องรายงานในบทความและทำ sensitivity")
if "ผลถูกตัดกลางคัน" in df.columns:
    v = df["ผลถูกตัดกลางคัน"].astype(str).str.strip().str.lower().isin(YES)
    notes.append(f"ผลถูกตัดกลางคัน {int(v.sum())}/{len(df)} รัน")
if "ชื่อรุ่นบนหน้าจอ" in df.columns:
    for m, g in df.groupby("model"):
        vs = sorted(set(g["ชื่อรุ่นบนหน้าจอ"].astype(str).str.strip()) - {""})
        if len(vs) > 1:
            notes.append(f"⚠️ {m} เจอชื่อรุ่นมากกว่าหนึ่งแบบ {vs} "
                         f"— ผู้ให้บริการเปลี่ยนรุ่นระหว่างเก็บข้อมูล ต้องเขียนใน Limitations")

for n in notes:
    print("ℹ️ ", n)
if fails:
    print(f"\n❌ ไม่ผ่าน {len(fails)} ข้อ")
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("\n✅ run_log ผ่าน เริ่มวิเคราะห์ได้")
