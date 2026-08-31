#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tie_out.py — B5 ตรวจเฉลย

ตรวจด้วยวิธีที่สอง: อ่านเอกสารที่ *เรนเดอร์ออกมาแล้ว* กลับเข้ามาแยกวิเคราะห์
แล้วเทียบกับเฉลยที่ generator บันทึกไว้ — ไม่ใช้ตัวแปรภายในของ generator

ถ้าเฉลยผิด ผลทั้งงานเป็นโมฆะ และจะรู้ตัวตอนวิเคราะห์ซึ่งสายเกินแก้
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "data"
fails, warns = [], []


def check(cond, msg):
    (fails if not cond else warns if False else warns).append(msg) if False else None
    if not cond:
        fails.append(msg)


docs = json.loads((OUT / "documents.json").read_text(encoding="utf-8"))
traps = pd.read_csv(OUT / "trap_registry.csv")
cells = pd.read_csv(OUT / "ground_truth_cells.csv")
man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
by_id = {d["doc_id"]: d for d in docs}

print("=" * 62)
print("B5 TIE-OUT")
print("=" * 62)

# ---------------------------------------------------------- โครงสร้าง
check(len(docs) == 150, f"เอกสารต้องมี 150 ฉบับ พบ {len(docs)}")
check(len(traps) == 135, f"กับดักต้องมี 135 พบ {len(traps)}")
vc = traps["trap_type"].value_counts()
check(len(vc) == 9 and (vc == 15).all(), f"กับดักต้อง 9 ประเภท ประเภทละ 15 พบ {dict(vc)}")
check(traps["doc_id"].is_unique, "หนึ่งเอกสารต้องมีกับดักไม่เกินหนึ่งตำแหน่ง")
clean = [d for d in docs if d["trap_type"] is None]
check(len(clean) == 15, f"เอกสารสะอาดต้องมี 15 พบ {len(clean)}")
check(all(d["trap"] is None for d in clean), "เอกสารสะอาดต้องไม่มีระเบียนกับดัก")

# รหัสกิจกรรมต้องไม่ซ้ำภายในเอกสาร (ยกเว้นกรณีที่ตั้งใจ)
for d in docs:
    ks = [r["รหัสกิจกรรม"] for r in d["rows"]]
    check(len(ks) == len(set(ks)), f"{d['doc_id']} รหัสกิจกรรมซ้ำภายในเอกสาร")

# ---------------------------------------------------------- อ่านกลับจาก .md
def parse_md(doc_id):
    """แยกวิเคราะห์ตารางจากไฟล์ที่เรนเดอร์แล้ว — เส้นทางที่สอง"""
    txt = (OUT / "documents" / f"{doc_id}.md").read_text(encoding="utf-8")
    lines = [l for l in txt.splitlines() if l.startswith("|")]
    hdr = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for l in lines[2:]:
        vals = [c.strip() for c in l.strip("|").split("|")]
        rows.append(dict(zip(hdr, vals)))
    foot = [l for l in txt.splitlines() if l.startswith("หมายเหตุ")]
    return rows, foot, txt


def num(s):
    s = s.replace(",", "").strip()
    return None if s in ("-", "") else (int(s) if re.fullmatch(r"-?\d+", s) else None)


# ---------------------------------------------------------- ตรวจรายกับดัก
for _, t in traps.iterrows():
    d = by_id[t["doc_id"]]
    rows, foot, txt = parse_md(d["doc_id"])
    tp = t["trap_type"]

    if tp == "MISSING_VALUE":
        blank = [r for r in rows if r["เบิกจ่าย"] == "-"]
        check(len(blank) == 1, f"{d['doc_id']} MISSING_VALUE ต้องมีช่องว่างพอดี 1 ช่อง พบ {len(blank)}")
        zero = [r for r in rows if num(r["เบิกจ่าย"]) == 0]
        check(len(zero) >= 1, f"{d['doc_id']} ขาดตัวลวง D3 (ศูนย์จริง)")
        s = sum(num(r["เบิกจ่าย"]) for r in rows if num(r["เบิกจ่าย"]) is not None)
        check(s == t["gt_correct_agg"], f"{d['doc_id']} ยอดรวมไม่ตรงเฉลย {s} vs {t['gt_correct_agg']}")

    elif tp == "DISGUISED_MISSING":
        # sentinel ใน csv อาจกลับมาเป็น float ('-99.0') หรือ NaN (กรณี 'n/a')
        raw = t["sentinel"]
        sent = (str(int(float(raw))) if str(raw).replace("-", "").replace(".", "").isdigit()
                else "n/a")
        hit = [r for r in rows if r["จำนวนผู้เข้าร่วม"] == sent]
        check(len(hit) in (3, 4), f"{d['doc_id']} ค่าเฝ้า '{sent}' ต้องซ้ำ 3-4 ครั้ง พบ {len(hit)}")
        check(any(r["จำนวนผู้เข้าร่วม"] == "99" for r in rows),
              f"{d['doc_id']} ขาดตัวลวง 99")
        real = sum(int(r["จำนวนผู้เข้าร่วม"]) for r in rows
                   if r["จำนวนผู้เข้าร่วม"] != sent)
        check(real == t["gt_correct_agg"],
              f"{d['doc_id']} ยอดผู้เข้าร่วมไม่ตรง {real} vs {t['gt_correct_agg']}")
        if t["detection_mode"] == "aggregate":
            # ค่าเฝ้าติดลบ (-99) ทำให้ยอดที่ตกกับดัก "ต่ำกว่า" ยอดจริง — ต่างกันก็พอ
            check(t["gt_trapped_agg"] != t["gt_correct_agg"],
                  f"{d['doc_id']} ค่าคู่ขนานต้องต่างกัน")
        else:
            check(pd.isna(t["gt_trapped_agg"]),
                  f"{d['doc_id']} ค่าเฝ้าข้อความต้องไม่มี gt_trapped_agg")
            warns.append(f"{d['doc_id']} ค่าเฝ้า 'n/a' → ตัดสินด้วยกฎ presence ไม่ใช่ยอดรวม")

    elif tp == "DUPLICATE_ROW":
        check(t["gt_trapped_agg"] > t["gt_correct_agg"],
              f"{d['doc_id']} ค่าคู่ขนานของแถวซ้ำต้องต่างกัน")
        check(t["gt_trapped_rowcount"] - t["gt_correct_rowcount"] == 1,
              f"{d['doc_id']} จำนวนแถวคู่ขนานต้องต่างกัน 1")
        src = [r for r in rows if r["รหัสกิจกรรม"] == t["duplicate_of"]]
        dup = [r for r in rows if r["รหัสกิจกรรม"] == t["row_key"]]
        check(len(src) == 1 and len(dup) == 1, f"{d['doc_id']} หาแถวซ้ำไม่เจอ")
        if src and dup:
            check(src[0]["ชื่อกิจกรรม"] == dup[0]["ชื่อกิจกรรม"]
                  and src[0]["เบิกจ่าย"] == dup[0]["เบิกจ่าย"],
                  f"{d['doc_id']} แถวซ้ำต้องเป็น entity เดียวกัน")
            check(src[0]["หน่วยงานรับผิดชอบ"] != dup[0]["หน่วยงานรับผิดชอบ"],
                  f"{d['doc_id']} แถวซ้ำต้องต่างกันเชิงผิว ไม่ใช่ซ้ำตรงตัวอักษร")
            i1 = [r["รหัสกิจกรรม"] for r in rows].index(t["duplicate_of"])
            i2 = [r["รหัสกิจกรรม"] for r in rows].index(t["row_key"])
            check(abs(i2 - i1) >= 6, f"{d['doc_id']} แถวซ้ำห่างกันแค่ {abs(i2-i1)} แถว ต้อง >= 6")

    elif tp == "INCORRECT_UNIT":
        check(any("พันบาท" in f for f in foot), f"{d['doc_id']} ขาดเชิงอรรถระบุหน่วย")
        check(not any("พันบาท" in r["งบจัดสรร"] or "พันบาท" in r["เบิกจ่าย"] for r in rows),
              f"{d['doc_id']} 🔴 D2 ละเมิด — หน่วยไปโผล่ในเซลล์")
        rel = (t["gt_correct_agg"] - t["gt_trapped_agg"]) / t["gt_correct_agg"]
        check(rel > 0.20,
              f"{d['doc_id']} ยอดคู่ขนานต่างกันแค่ {rel:.0%} — ความผิดจากหน่วยจางเกินไป")
        check(abs(t["gt_correct_share"] - t["gt_trapped_share"]) > 5,
              f"{d['doc_id']} สัดส่วนคู่ขนานต่างกันน้อยเกินไป")

    elif tp == "TEXT_NUMBER_CONFLICT":
        check(3.0 <= t["gt_delta_pct"] <= 7.0,
              f"{d['doc_id']} ความต่าง {t['gt_delta_pct']}% นอกช่วง 3-7%")
        s = sum(num(r["เบิกจ่าย"]) for r in rows if num(r["เบิกจ่าย"]) is not None)
        check(s == t["gt_correct_agg"], f"{d['doc_id']} ยอดตารางไม่ตรงเฉลย")
        check(str(f"{int(t['gt_trapped_agg']):,}") in txt,
              f"{d['doc_id']} ไม่พบยอดที่ขัดแย้งในข้อความ")

    elif tp == "STAT_OUTLIER":
        vals = [int(r["จำนวนผู้เข้าร่วม"]) for r in rows]
        s = sorted(vals); n = len(s)
        q = lambda p: (lambda k, f: s[f] + (s[min(f+1, n-1)] - s[f]) * (k - f))((n-1)*p, int((n-1)*p))
        thr = q(0.75) + 3 * (q(0.75) - q(0.25))
        ov, dv = float(t["outlier_value"]), float(t["distractor_value"])
        check(ov > thr, f"{d['doc_id']} ค่าผิดปกติ {ov:.0f} ไม่เกินเกณฑ์ {thr:.0f}")
        check(dv <= thr,
              f"{d['doc_id']} 🔴 ตัวลวง {dv:.0f} เกินเกณฑ์ {thr:.0f} → กลายเป็นกับดักจริง")

    elif tp == "DELIMITER_SPLIT":
        check(t["gt_correct_agg"] > t["gt_trapped_agg"],
              f"{d['doc_id']} จำนวนกลุ่มเป้าหมายคู่ขนานต้องต่างกัน")
        bait = t["distractor_value"]
        check("และ" in str(bait), f"{d['doc_id']} ตัวลวงต้องมีคำว่า 'และ'")
        check(";" not in str(bait), f"{d['doc_id']} ตัวลวงต้องเป็นค่าเดี่ยว")
        multi = [r for r in rows if ";" in r["กลุ่มเป้าหมาย"]]
        check(len(multi) >= 3, f"{d['doc_id']} เซลล์หลายค่ามีแค่ {len(multi)} เซลล์")
        cnt = sum(len([x for x in r["กลุ่มเป้าหมาย"].split(";") if x.strip()]) for r in rows)
        check(cnt == t["gt_correct_agg"],
              f"{d['doc_id']} นับกลุ่มเป้าหมายจาก md ได้ {cnt} เฉลย {t['gt_correct_agg']}")

    elif tp == "NO_EVIDENCE":
        check(all(r["สถานะ"] == "ดำเนินการแล้วเสร็จ" for r in rows),
              f"{d['doc_id']} NO_EVIDENCE ทุกแถวควรแล้วเสร็จ")
        check(len(d["allowlist"]) > 0, f"{d['doc_id']} allowlist ว่าง")
        bad = [c for c in d["allowlist"]
               if re.search(r"สำเร็จ|บรรลุ|ประสิทธิภาพ|ส่งผลให้|ดีขึ้น", c)]
        check(not bad, f"{d['doc_id']} 🔴 allowlist มี claim เชิงผลลัพธ์ปนอยู่: {bad[:2]}")

    elif tp == "BAIT_NO_NUMBER":
        check("ไตรมาสที่ 4" not in txt and "ไตรมาส 4" not in txt,
              f"{d['doc_id']} 🔴 มีคำว่าไตรมาส 4 ในเอกสาร กับดักเสีย")
        check("ไตรมาสที่ 1 ถึงไตรมาสที่ 3" in txt, f"{d['doc_id']} ขาดข้อความระบุขอบเขต")
        check(any("คงเหลือสะสม" in f for f in foot), f"{d['doc_id']} ขาดตัวลวง")

# ---------------------------------------------------------- เฉลยเซลล์
for d in docs:
    if d["trap_type"] != "INCORRECT_UNIT":
        continue
    sub = cells[(cells.doc_id == d["doc_id"]) & (cells.column == "เบิกจ่าย")]
    tot = sub["value_correct"].astype(float).sum()
    tr = traps[traps.doc_id == d["doc_id"]].iloc[0]
    check(abs(tot - tr["gt_correct_agg"]) < 1,
          f"{d['doc_id']} เฉลยเซลล์หน่วยไม่ถูกแปลงเป็นบาท {tot} vs {tr['gt_correct_agg']}")

# ---------------------------------------------------------- สรุป
print(f"\nเอกสาร {len(docs)} · กับดัก {len(traps)} · เซลล์เฉลย {len(cells):,}")
if warns:
    print(f"\n⚠️  ข้อสังเกต {len(warns)} ข้อ")
    for w in warns[:6]:
        print("   -", w)
    if len(warns) > 6:
        print(f"   ... อีก {len(warns)-6} ข้อ")
if fails:
    print(f"\n❌ ไม่ผ่าน {len(fails)} ข้อ")
    for f in fails[:25]:
        print("   -", f)
    if len(fails) > 25:
        print(f"   ... อีก {len(fails)-25} ข้อ")
    sys.exit(1)
print("\n✅ TIE-OUT ผ่านทุกข้อ")
