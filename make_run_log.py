#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_run_log.py — สร้างแบบฟอร์มบันทึกรัน 72 รัน (E1)

ลำดับการรันถูกสุ่มด้วย seed ที่ล็อกไว้ ไม่ใช่เรียงตามโมเดล
เหตุผล: ถ้ารัน ChatGPT ให้ครบก่อนแล้วค่อยรัน Claude ลำดับเวลาจะสับสนกับตัวโมเดล
       ผู้ให้บริการเปลี่ยนรุ่นย่อยระหว่างวันได้ (PR-06 · PR-09)

ผลลัพธ์: data/run_log_template.csv  — เปิดด้วย Excel แล้วกรอกคอลัมน์ที่ว่าง
"""
import random
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "data"
SEED = 20260815                      # ล็อกใน preregistration

MODELS = ["ChatGPT", "Claude", "Gemini"]
TASKS = ["T1", "T2", "T3", "T4", "T5", "T6"]
REPS = [1, 2, 3]

# งานนำร่อง 4 รัน: 1 โมเดล × 4 งาน (rep 1)
PILOT = [(m, t, 1) for m in ["Claude"] for t in ["T1", "T2", "T5", "T6"]]

COLS_FILL = [
    "run_id", "phase", "order", "model", "task", "replicate", "paraphrase",
    "prompt_file", "bundle_file", "raw_file",
]
COLS_BLANK = [
    "วันเวลาเริ่ม", "วันเวลาจบ",
    "ชื่อรุ่นบนหน้าจอ",          # PR-06
    "ค่าตั้งต้นที่หน้าจอแสดง",    # PR-12 แทน PR-07 ที่ทำไม่ได้
    "ไฟล์แคปหน้าจอ",             # E4
    "แชตใหม่",                   # ต้องเป็น ใช่ ทุกแถว
    "ปิด memory", "ปิด custom instructions", "ปิด web search และ tools",
    "ใช้คำสั่งขอให้พิมพ์ต่อ",     # 0 หรือ 1 — ดู §3 ของโพรโทคอล
    "ผลถูกตัดกลางคัน",
    "หมายเหตุเหตุการณ์ผิดปกติ",
]


def _row(rid, phase, n, m, t, r):
    return {"run_id": rid, "phase": phase, "order": n, "model": m, "task": t,
            "replicate": r, "paraphrase": r,
            "prompt_file": f"C_prompts_v1.md § {t}-P{r}",
            "bundle_file": f"data/task_bundle_{t}.md",
            "raw_file": f"raw/{rid}_{m}_{t}_rep{r}.txt",
            **{c: "" for c in COLS_BLANK}}


def build():
    """
    🔴 นำร่องเป็นชุดแยก ไม่ปนกับรันจริง
       เพราะหลังนำร่องเราจะปรับความยากแล้วสร้างข้อมูลใหม่
       ผลจากนำร่องจึงอ้างอิงข้อมูลคนละชุด นำมารวมกันไม่ได้
    """
    rng = random.Random(SEED)

    pilot = [_row(f"P{i+1:03d}", "นำร่อง", i + 1, m, t, r)
             for i, (m, t, r) in enumerate(PILOT)]

    combos = [(t, r) for t in TASKS for r in REPS]
    rng.shuffle(combos)
    main, n = [], 0
    for t, r in combos:
        ms = MODELS[:]
        rng.shuffle(ms)                       # ลำดับโมเดลต่างกันในแต่ละบล็อก
        for m in ms:
            n += 1
            main.append(_row(f"R{n:03d}", "จริง", n, m, t, r))

    OUT.mkdir(exist_ok=True)
    (OUT / "raw").mkdir(exist_ok=True)
    (OUT / "screenshots").mkdir(exist_ok=True)
    dfp = pd.DataFrame(pilot)[COLS_FILL + COLS_BLANK]
    dfm = pd.DataFrame(main)[COLS_FILL + COLS_BLANK]
    dfp.to_csv(OUT / "pilot_log_template.csv", index=False, encoding="utf-8-sig")
    dfm.to_csv(OUT / "run_log_template.csv", index=False, encoding="utf-8-sig")
    return dfp, dfm


if __name__ == "__main__":
    dfp, dfm = build()
    print(f"นำร่อง {len(dfp)} รัน (P001-P{len(dfp):03d}) → data/pilot_log_template.csv")
    print(f"รันจริง {len(dfm)} รัน (R001-R{len(dfm):03d}) → data/run_log_template.csv · seed {SEED}")
    print("\nลำดับ 12 รันแรกของรันจริง:")
    print(dfm.head(12)[["run_id", "model", "task", "replicate"]].to_string(index=False))
    print("\nตรวจความสมดุล (ต้องเป็น 3 ทุกช่อง):")
    print(pd.crosstab(dfm.model, dfm.task).to_string())
    first = dfm.groupby("model").order.min().sort_values()
    print("\nรันแรกของแต่ละโมเดลอยู่ลำดับที่:", dict(first))
