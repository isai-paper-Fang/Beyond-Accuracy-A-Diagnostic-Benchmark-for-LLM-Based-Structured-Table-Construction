#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generator.py — สร้างข้อมูลนำเข้าและเฉลยของ iSAI-NLP 2026

อ่านวัตถุดิบจาก A_คลังคำ_v1.yaml เท่านั้น ห้ามมีสตริงเนื้อหาภาษาไทยฝังในไฟล์นี้
(ยกเว้นหัวตารางและคำที่เป็นโครงสร้างเอกสาร)

ผลลัพธ์ที่ data/
    documents/{doc_id}.md      เอกสารรายฉบับ 150 ฉบับ
    task_bundle_{T}.md         รวมเอกสารของแต่ละงาน = สิ่งที่จะวางลง prompt จริง
    documents.json             เอกสารในรูปข้อมูล
    ground_truth_cells.csv     เฉลยระดับเซลล์
    trap_registry.csv          ทะเบียนกับดัก 135 แถว พร้อมค่าคู่ขนาน (B3)
    findings_allowlist.json    claim ที่สาวกลับไปเอกสารได้
    manifest.json              สรุปจำนวนและขนาด prompt (ใช้ตอบ S4)
    ground_truth.xlsx          รวมทุกชีต

รัน:  python generator.py
"""

import os
import re
import json
import random
import hashlib
from pathlib import Path

import yaml
import pandas as pd

HERE = Path(__file__).resolve().parent
BANK = HERE / "A_คลังคำ_v1.yaml"
OUT = HERE / "data"
DOCDIR = OUT / "documents"

COLS = ["รหัสกิจกรรม", "ชื่อกิจกรรม", "หน่วยงานรับผิดชอบ", "งบจัดสรร",
        "เบิกจ่าย", "จำนวนผู้เข้าร่วม", "กลุ่มเป้าหมาย", "สถานะ", "หมายเหตุ"]

# ชนิดฟิลด์ → ใช้เลือก tolerance ตอนให้คะแนน (DV-02)
FIELD_TYPE = {
    "รหัสกิจกรรม": "ข้อความ", "ชื่อกิจกรรม": "ข้อความ",
    "หน่วยงานรับผิดชอบ": "ข้อความ", "งบจัดสรร": "เงินบาท",
    "เบิกจ่าย": "เงินบาท", "จำนวนผู้เข้าร่วม": "จำนวนนับ",
    "กลุ่มเป้าหมาย": "รายการ", "สถานะ": "ข้อความ", "หมายเหตุ": "ข้อความ",
}

# แผนการกระจายตามสเปก §1.2
PLAN = [
    ("T1", ["MISSING_VALUE", "DISGUISED_MISSING"], 3),
    ("T3", ["DUPLICATE_ROW", "INCORRECT_UNIT"], 3),
    ("T4", ["BAIT_NO_NUMBER"], 2),
    ("T5", ["DELIMITER_SPLIT"], 2),
    ("T6", ["STAT_OUTLIER"], 2),
    ("T7", ["NO_EVIDENCE", "TEXT_NUMBER_CONFLICT"], 3),
]
N_PER_TRAP = 15

TH_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")


# ------------------------------------------------------------------ ตัวช่วย
def money(v):
    """จัดรูปเงินแบบมีลูกน้ำ"""
    return f"{v:,}"


def q3_iqr_threshold(vals):
    """เกณฑ์ค่าผิดปกติตามสเปก A4: Q3 + 3*IQR"""
    s = sorted(vals)
    n = len(s)

    def q(p):
        k = (n - 1) * p
        f = int(k)
        c = min(f + 1, n - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    q1, q3 = q(0.25), q(0.75)
    return q3 + 3 * (q3 - q1)


def surface_variant(rng, text, kind):
    """สร้างความต่างเชิงผิวสำหรับ A2 — entity เดิม สตริงต่าง"""
    if kind == "เว้นวรรคเกิน":
        return re.sub(r"\.", ". ", text, count=1)
    if kind == "จุดในตัวย่อ":
        return text.replace(".", "", 1)
    if kind == "เลขไทยกับเลขอารบิก":
        return text.translate(TH_DIGITS)
    return text


class Gen:
    def __init__(self, bank, seed):
        self.b = bank
        self.seed = seed
        self.rng = random.Random(seed)
        self.orgs = bank["หน่วยงาน"]
        self.act = bank["กิจกรรม"]
        self.tg_and = bank["กลุ่มเป้าหมาย"]["มีคำว่าและ"]
        self.tg_plain = bank["กลุ่มเป้าหมาย"]["ไม่มีคำว่าและ"]
        self.txt = bank["ข้อความประกอบ"]
        self.num = bank["ตัวเลข"]
        self.docmeta = bank["เอกสาร"]
        self._used_codes = set()

    # -------------------------------------------------------------- ชิ้นส่วน
    def code(self, year):
        while True:
            c = f"{year}-{self.rng.choice(self.num['รหัสกิจกรรม']['หมวด'])}-{self.rng.randint(1, 999):03d}"
            if c not in self._used_codes:
                self._used_codes.add(c)
                return c

    def activity_name(self, positive):
        a = self.act
        verbs = a["กริยา_ชวนอนุมานผลลัพธ์"] if positive else a["กริยา_เป็นกลาง"]
        return f"{self.rng.choice(a['คำนำหน้า'])}{self.rng.choice(verbs)}{self.rng.choice(a['กรรม'])}"

    def target_groups(self, multi_ok):
        """คืน (สตริงที่แสดงในเซลล์, รายการค่าจริง)"""
        n = self.rng.choice([1, 2, 3, 4]) if multi_ok else 1
        pool = self.tg_and + self.tg_plain
        vals = self.rng.sample(pool, n)
        if n == 1:
            return vals[0], vals
        sep = "; " if self.rng.random() < 0.6 else ";"
        s = sep.join(vals)
        if self.rng.random() < 0.2:
            s += ";"                       # ตัวคั่นปิดท้ายเกินมา
        if self.rng.random() < 0.15:
            s = " " + s + " "              # ช่องว่างหัวท้าย
        return s, vals

    def base_row(self, year, org, positive=False, multi_tg=False):
        alloc_lo, alloc_hi = self.num["งบจัดสรร_บาท"]["ต่ำสุด"], self.num["งบจัดสรร_บาท"]["สูงสุด"]
        step = self.num["งบจัดสรร_บาท"]["ปัดเป็นหลัก"]
        alloc = self.rng.randrange(alloc_lo, alloc_hi, step)
        lo, hi = self.num["อัตราการเบิกจ่าย"]["ปกติ"]
        disb = int(alloc * self.rng.uniform(lo, hi) / step) * step
        p_lo, p_hi = self.num["จำนวนผู้เข้าร่วม"]["ปกติ"]
        cell, vals = self.target_groups(multi_tg)
        return {
            "รหัสกิจกรรม": self.code(year),
            "ชื่อกิจกรรม": self.activity_name(positive),
            "หน่วยงานรับผิดชอบ": org["ย่อ"] if self.rng.random() < 0.5 else org["เต็ม"],
            "_org_full": org["เต็ม"], "_org_short": org["ย่อ"],
            "งบจัดสรร": alloc,
            "เบิกจ่าย": disb,
            "จำนวนผู้เข้าร่วม": self.rng.randint(p_lo, p_hi),
            "กลุ่มเป้าหมาย": cell,
            "_กลุ่มเป้าหมาย_จริง": vals,
            "สถานะ": "ดำเนินการแล้วเสร็จ" if disb > 0 else "ยังไม่ดำเนินการ",
            "หมายเหตุ": "",
            "_หน่วย": "บาท",
        }

    # -------------------------------------------------------------- เอกสาร
    def make(self, doc_id, task, trap):
        rng = self.rng
        year = rng.choice(self.num["ปีงบประมาณ"])
        quarter = rng.choice(self.num["ไตรมาส"])
        org = rng.choice(self.orgs)
        n_rows = rng.randint(*self.docmeta["จำนวนแถว"])
        multi_tg = (trap == "DELIMITER_SPLIT")
        positive = (trap == "NO_EVIDENCE")
        rows = [self.base_row(year, org, positive, multi_tg) for _ in range(n_rows)]

        doc = {
            "doc_id": doc_id, "task": task, "trap_type": trap,
            "year": year, "quarter": quarter,
            "org": org["เต็ม"], "org_short": org["ย่อ"],
            "rows": rows, "footnotes": [], "intro": "", "scope_note": "",
            "gt": {}, "trap": None, "allowlist": [],
        }
        doc["intro"] = self._fill(rng.choice(self.txt["ย่อหน้านำ"]["เป็นกลาง"]), doc)

        if trap:
            getattr(self, "_trap_" + trap.lower())(doc)

        self._add_neutral_footnotes(doc)
        self._finalize(doc)
        return doc

    def _fill(self, tpl, doc, **kw):
        return (tpl.replace("{q}", str(doc["quarter"]))
                   .replace("{ปี}", str(doc["year"]))
                   .replace("{หน่วยงาน}", doc["org"])
                   .replace("{หน่วยงาน2}", kw.get("org2", ""))
                   .replace("{ยอดขัดแย้ง}", kw.get("conflict", ""))
                   .replace("{ยอดจริง}", kw.get("real", ""))
                   .replace("{pct}", kw.get("pct", ""))
                   .replace("{วันที่}", kw.get("date", "")))

    def _add_neutral_footnotes(self, doc):
        want = self.rng.randint(*self.docmeta["จำนวนเชิงอรรถ"])
        while len(doc["footnotes"]) < want:
            t = self._fill(self.rng.choice(self.txt["เชิงอรรถ"]["ตัวลวง"]), doc,
                           date=f"{self.rng.randint(1,28)} ม.ค. {doc['year']}")
            if t not in doc["footnotes"]:
                doc["footnotes"].append(t)

    # ============================================================ กับดัก A
    def _trap_missing_value(self, doc):
        rows = doc["rows"]
        i = self.rng.randint(4, min(8, len(rows) - 2))
        rows[i]["เบิกจ่าย"] = None
        rows[i]["สถานะ"] = "อยู่ระหว่างดำเนินการ"
        # D3 ตัวลวง — ศูนย์จริง ไม่ใช่ค่าหาย
        j = next(k for k in range(len(rows)) if k != i)
        rows[j]["เบิกจ่าย"] = 0
        rows[j]["สถานะ"] = "ยังไม่ดำเนินการ"
        total = sum(r["เบิกจ่าย"] for r in rows if r["เบิกจ่าย"] is not None)
        doc["trap"] = {
            "row_key": rows[i]["รหัสกิจกรรม"], "column": "เบิกจ่าย",
            "distractor_key": rows[j]["รหัสกิจกรรม"],
            "correct": "ค่าที่แสดงการไม่มีข้อมูล", "if_trapped": "ค่าตัวเลขใด ๆ",
            "gt_correct_agg": total, "gt_trapped_agg": total,
            "requires_note": True,
            "note": "sum_excluding เท่ากับ sum_as_zero เชิงเลขคณิต ต้องอาศัยฟิลด์เหตุผล",
        }
        doc["gt"]["ยอดเบิกจ่ายรวม"] = total

    def _trap_disguised_missing(self, doc):
        rows = doc["rows"]
        sent = self.rng.choice(self.num["ค่าเฝ้า"]["ใช้"])
        k = self.rng.choice(self.num["ค่าเฝ้า"]["จำนวนครั้งที่ซ้ำในคอลัมน์"])
        idx = self.rng.sample(range(len(rows)), k)
        for i in idx:
            rows[i]["จำนวนผู้เข้าร่วม"] = sent
        j = next(x for x in range(len(rows)) if x not in idx)
        rows[j]["จำนวนผู้เข้าร่วม"] = self.num["ค่าเฝ้า"]["ตัวลวง"]   # 99 ค่าจริง
        real = [r["จำนวนผู้เข้าร่วม"] for r in rows if r["จำนวนผู้เข้าร่วม"] != sent]
        numeric = isinstance(sent, int)
        with_s = sum(real) + (sent * len(idx) if numeric else 0)
        doc["trap"] = {
            "row_key": ";".join(rows[i]["รหัสกิจกรรม"] for i in sorted(idx)),
            "column": "จำนวนผู้เข้าร่วม",
            "distractor_key": rows[j]["รหัสกิจกรรม"],
            "sentinel": sent, "sentinel_is_numeric": numeric,
            # ค่าเฝ้าที่เป็นข้อความบวกเข้ายอดรวมไม่ได้ ต้องตัดสินจากการปรากฏในผลลัพธ์
            "detection_mode": "aggregate" if numeric else "presence",
            "correct": "ระบุว่าเป็นค่าที่หายไป ไม่นำเข้าการคำนวณ",
            "if_trapped": "นำค่าเฝ้าไปรวมในการคำนวณ" if numeric
                          else "แสดงค่าเฝ้าในผลลัพธ์โดยไม่ทำเครื่องหมาย",
            "gt_correct_agg": sum(real),
            "gt_trapped_agg": with_s if numeric else None,
            "requires_note": True,
        }
        doc["gt"]["ผู้เข้าร่วมรวม"] = sum(real)

    def _trap_duplicate_row(self, doc):
        rows, rng = doc["rows"], self.rng
        i = rng.randint(0, max(0, len(rows) - 8))
        src = rows[i]
        # 🔴 บังคับให้แถวต้นทางใช้ชื่อย่อ ความต่างเชิงผิวจึงทำงานได้เสมอ
        src["หน่วยงานรับผิดชอบ"] = src["_org_short"]
        kind = rng.choice(["ชื่อย่อ", "เว้นวรรคเกิน", "จุดในตัวย่อ", "เลขไทยกับเลขอารบิก"])
        dup = dict(src)
        dup["รหัสกิจกรรม"] = self.code(doc["year"])          # ป้อนซ้ำได้รหัสใหม่
        cand = (src["_org_full"] if kind == "ชื่อย่อ"
                else surface_variant(rng, src["หน่วยงานรับผิดชอบ"], kind))
        if cand == src["หน่วยงานรับผิดชอบ"]:      # แบบที่สุ่มได้ใช้กับชื่อนี้ไม่ได้
            kind, cand = "ชื่อย่อ", src["_org_full"]
        dup["หน่วยงานรับผิดชอบ"] = cand
        j = min(i + rng.randint(6, 8), len(rows))
        rows.insert(j, dup)
        # D3 ตัวลวง — ชื่อเดียวกัน คนละ entity
        a = dict(rows[-1]); a["ชื่อกิจกรรม"] = src["ชื่อกิจกรรม"] + " รุ่นที่ 2"
        a["รหัสกิจกรรม"] = self.code(doc["year"])
        a["งบจัดสรร"] = int(a["งบจัดสรร"] * 0.7 // 500) * 500
        a["เบิกจ่าย"] = int(a["เบิกจ่าย"] * 0.7 // 500) * 500
        rows.append(a)
        raw = sum(r["เบิกจ่าย"] for r in rows if isinstance(r["เบิกจ่าย"], int))
        doc["trap"] = {
            "row_key": dup["รหัสกิจกรรม"], "column": "แถวทั้งแถว",
            "duplicate_of": src["รหัสกิจกรรม"], "variant_kind": kind,
            "distractor_key": a["รหัสกิจกรรม"],
            "correct": "ยุบซ้ำก่อนรวมยอด", "if_trapped": "นับสองครั้ง",
            "gt_correct_agg": raw - dup["เบิกจ่าย"], "gt_trapped_agg": raw,
            "gt_correct_rowcount": len(rows) - 1, "gt_trapped_rowcount": len(rows),
            "requires_note": False,
        }
        doc["gt"]["ยอดเบิกจ่ายรวม"] = raw - dup["เบิกจ่าย"]

    def _trap_incorrect_unit(self, doc):
        rows, rng = doc["rows"], self.rng
        org2 = rng.choice([o for o in self.orgs if o["เต็ม"] != doc["org"]])
        mult = self.num["หน่วยเงิน"]["ตัวคูณ"]
        cut = len(rows) // 2
        for r in rows[cut:]:
            r["หน่วยงานรับผิดชอบ"] = org2["ย่อ"]
            r["_หน่วย"] = "พันบาท"
            r["งบจัดสรร"] = max(1, round(r["งบจัดสรร"] / mult))
            r["เบิกจ่าย"] = max(0, round(r["เบิกจ่าย"] / mult))
        doc["footnotes"].append(
            self._fill(rng.choice(self.txt["เชิงอรรถ"]["ระบุหน่วย"]), doc, org2=org2["ย่อ"]))
        conv = sum(r["เบิกจ่าย"] * (mult if r["_หน่วย"] == "พันบาท" else 1) for r in rows)
        unconv = sum(r["เบิกจ่าย"] for r in rows)
        s2c = sum(r["เบิกจ่าย"] * mult for r in rows[cut:])
        s2u = sum(r["เบิกจ่าย"] for r in rows[cut:])
        doc["trap"] = {
            "row_key": ";".join(r["รหัสกิจกรรม"] for r in rows[cut:]),
            "column": "งบจัดสรร;เบิกจ่าย", "unit_org": org2["ย่อ"],
            "correct": "แปลงเป็นบาทก่อนคำนวณ", "if_trapped": "บวกตรงโดยไม่แปลง",
            "gt_correct_agg": conv, "gt_trapped_agg": unconv,
            "gt_correct_share": round(100 * s2c / conv, 2),
            "gt_trapped_share": round(100 * s2u / unconv, 2),
            "requires_note": False,
        }
        doc["gt"]["ยอดเบิกจ่ายรวม"] = conv

    def _trap_text_number_conflict(self, doc):
        rows, rng = doc["rows"], self.rng
        real = sum(r["เบิกจ่าย"] for r in rows if isinstance(r["เบิกจ่าย"], int))
        lo, hi = self.num["ขนาดความขัดแย้ง"]["ช่วง"]
        d = rng.uniform(lo, hi) * (1 if rng.random() < 0.5 else -1)
        stated = int(real * (1 + d) // 100) * 100
        alloc = sum(r["งบจัดสรร"] for r in rows)
        doc["intro"] = self._fill(rng.choice(self.txt["ย่อหน้านำ"]["ระบุยอดที่ขัดแย้ง"]),
                                  doc, conflict=money(stated),
                                  pct=str(round(100 * stated / alloc, 1)))
        # D3 ตัวลวง — เชิงอรรถที่ระบุยอดตรงกับตารางเป๊ะ
        doc["footnotes"].append(
            self._fill(self.txt["เชิงอรรถ"]["ยอดที่ตรงกัน"][0], doc, real=money(alloc)))
        doc["trap"] = {
            "row_key": "-", "column": "ย่อหน้านำ",
            "correct": "รายงานว่ามีความขัดแย้ง",
            "if_trapped": "รายงานตัวเลขเดียวโดยไม่ระบุความไม่ตรงกัน",
            "gt_correct_agg": real, "gt_trapped_agg": stated,
            "gt_delta_pct": round(100 * abs(d), 2), "requires_note": True,
        }
        doc["gt"]["ยอดเบิกจ่ายรวม"] = real

    def _trap_stat_outlier(self, doc):
        rows, rng = doc["rows"], self.rng
        i, j = rng.sample(range(len(rows)), 2)
        rows[i]["จำนวนผู้เข้าร่วม"] = rng.randint(*self.num["จำนวนผู้เข้าร่วม"]["ค่าผิดปกติ"])
        # 🔴 ตัวลวงต้อง "สูงจนสะดุดตา แต่ไม่เกินเกณฑ์" — คำนวณจากการแจกแจงจริง
        #    ตั้งค่าคงที่ไว้ล่วงหน้าไม่ได้ เพราะ IQR ของแต่ละเอกสารไม่เท่ากัน
        hint_lo, hint_hi = self.num["จำนวนผู้เข้าร่วม"]["ตัวลวงสูงแต่ไม่เกินเกณฑ์"]
        cand = rng.randint(hint_lo, hint_hi)
        for _ in range(40):
            rows[j]["จำนวนผู้เข้าร่วม"] = cand
            thr = q3_iqr_threshold([r["จำนวนผู้เข้าร่วม"] for r in rows])
            if rows[i]["จำนวนผู้เข้าร่วม"] > thr >= cand:
                break
            cand = int(cand * 0.9)
        else:                       # เผื่อกรณีสุดโต่ง — ถอยไปใช้ค่าสูงสุดของแถวปกติ
            others = [r["จำนวนผู้เข้าร่วม"] for k, r in enumerate(rows) if k not in (i, j)]
            cand = max(others)
            rows[j]["จำนวนผู้เข้าร่วม"] = cand
        vals = [r["จำนวนผู้เข้าร่วม"] for r in rows]
        thr = q3_iqr_threshold(vals)
        doc["trap"] = {
            "row_key": rows[i]["รหัสกิจกรรม"], "column": "จำนวนผู้เข้าร่วม",
            "distractor_key": rows[j]["รหัสกิจกรรม"],
            "outlier_value": rows[i]["จำนวนผู้เข้าร่วม"],
            "distractor_value": rows[j]["จำนวนผู้เข้าร่วม"],
            "threshold": round(thr, 1),
            "correct": "ทำเครื่องหมายว่าควรตรวจสอบเพิ่มเติม",
            "if_trapped": "ไม่ทำเครื่องหมายใด ๆ",
            "gt_correct_agg": None, "gt_trapped_agg": None,
            "requires_note": True,
            "_valid": rows[i]["จำนวนผู้เข้าร่วม"] > thr >= rows[j]["จำนวนผู้เข้าร่วม"],
        }

    def _trap_delimiter_split(self, doc):
        rows = doc["rows"]
        # บังคับให้มีค่าเดี่ยวที่มีคำว่า "และ" อยู่ในชื่อ = ตัวลวงหลัก
        i = self.rng.randrange(len(rows))
        bait = self.rng.choice(self.tg_and)
        rows[i]["กลุ่มเป้าหมาย"] = bait
        rows[i]["_กลุ่มเป้าหมาย_จริง"] = [bait]
        # 🔴 ต้องมีเซลล์หลายค่าอย่างน้อย 3 เซลล์ ไม่งั้นกับดักแทบไม่มีอะไรให้แยก
        multi = [k for k, r in enumerate(rows) if len(r["_กลุ่มเป้าหมาย_จริง"]) > 1]
        pool = [k for k in range(len(rows)) if k != i and k not in multi]
        while len(multi) < 3 and pool:
            k = pool.pop(self.rng.randrange(len(pool)))
            n = self.rng.choice([2, 3, 4])
            vals = self.rng.sample(self.tg_and + self.tg_plain, n)
            sep = "; " if self.rng.random() < 0.6 else ";"
            rows[k]["กลุ่มเป้าหมาย"] = sep.join(vals)
            rows[k]["_กลุ่มเป้าหมาย_จริง"] = vals
            multi.append(k)
        correct = sum(len(r["_กลุ่มเป้าหมาย_จริง"]) for r in rows)
        naive = len(rows)                       # ไม่แยกเลย = นับเซลล์ละหนึ่ง
        doc["trap"] = {
            "row_key": ";".join(r["รหัสกิจกรรม"] for r in rows
                                if len(r["_กลุ่มเป้าหมาย_จริง"]) > 1),
            "column": "กลุ่มเป้าหมาย", "distractor_key": rows[i]["รหัสกิจกรรม"],
            "distractor_value": bait,
            "correct": "แยกที่ ; เท่านั้น ห้ามแยกที่คำว่า และ",
            "if_trapped": "ไม่แยกเซลล์หลายค่า",
            "gt_correct_agg": correct, "gt_trapped_agg": naive,
            "requires_note": False,
        }
        doc["gt"]["จำนวนกลุ่มเป้าหมายรวม"] = correct

    # ============================================================ กับดัก B
    def _trap_no_evidence(self, doc):
        for r in doc["rows"]:
            r["สถานะ"] = "ดำเนินการแล้วเสร็จ"
            r["จำนวนผู้เข้าร่วม"] = self.rng.randint(150, 250)
        doc["trap"] = {
            "row_key": "-", "column": "ทั้งเอกสาร",
            "correct": "รายงานเฉพาะกิจกรรมและปริมาณ ระบุว่าไม่มีข้อมูลผลลัพธ์",
            "if_trapped": "อ้างว่าโครงการได้ผล/สำเร็จ/มีประสิทธิภาพ",
            "gt_correct_agg": None, "gt_trapped_agg": None, "requires_note": True,
        }

    def _trap_bait_no_number(self, doc):
        doc["scope_note"] = self.txt["ขอบเขตข้อมูล"]["ระบุ"]
        rows = doc["rows"]
        alloc = sum(r["งบจัดสรร"] for r in rows)
        disb = sum(r["เบิกจ่าย"] for r in rows)
        # D3 ตัวลวง — ตัวเลขที่ลบกันแล้วดูเหมือนคำตอบได้
        doc["footnotes"].append(
            f"หมายเหตุ: ยอดคงเหลือสะสมถึงไตรมาสที่ 3 เท่ากับ {money(alloc - disb)} บาท")
        doc["footnotes"].append(
            f"หมายเหตุ: งบประมาณที่ได้รับจัดสรรทั้งปีเท่ากับ {money(alloc * 4 // 3)} บาท")
        doc["trap"] = {
            "row_key": "-", "column": "ยอดคงเหลือไตรมาสที่ 4",
            "distractor_value": alloc - disb,
            "correct": "ระบุว่าเอกสารไม่มีข้อมูลไตรมาสที่ 4",
            "if_trapped": "ผลิตค่าตัวเลขใด ๆ",
            "gt_correct_agg": None, "gt_trapped_agg": None, "requires_note": True,
        }

    # -------------------------------------------------------------- ปิดท้าย
    def _finalize(self, doc):
        rows = doc["rows"]
        doc["gt"].setdefault("จำนวนแถว", len(rows))
        # findings_allowlist — claim เชิงข้อเท็จจริงที่สาวกลับไปเอกสารได้
        al = [f"กิจกรรม {r['รหัสกิจกรรม']} มีสถานะ {r['สถานะ']}" for r in rows]
        al += [f"กิจกรรม {r['รหัสกิจกรรม']} มีผู้เข้าร่วม {r['จำนวนผู้เข้าร่วม']} คน"
               for r in rows if isinstance(r["จำนวนผู้เข้าร่วม"], int)]
        doc["allowlist"] = al

    # -------------------------------------------------------------- เรนเดอร์
    def render(self, doc):
        L = [f"# รายงานผลการดำเนินงาน {doc['org']}",
             f"ไตรมาสที่ {doc['quarter']} ปีงบประมาณ พ.ศ. {doc['year']}",
             f"รหัสเอกสาร: {doc['doc_id']}", ""]
        if doc["scope_note"]:
            L += [doc["scope_note"], ""]
        L += [doc["intro"], "",
              "| " + " | ".join(COLS) + " |",
              "|" + "---|" * len(COLS)]
        for r in doc["rows"]:
            cells = []
            for c in COLS:
                v = r[c]
                if v is None:
                    cells.append("-")
                elif c in ("งบจัดสรร", "เบิกจ่าย") and isinstance(v, int):
                    cells.append(money(v))
                else:
                    cells.append(str(v))
            L.append("| " + " | ".join(cells) + " |")
        if doc["footnotes"]:
            L += [""] + doc["footnotes"]
        return "\n".join(L) + "\n"


# ------------------------------------------------------------------ ประกอบ
def build(seed=None):
    bank = yaml.safe_load(BANK.read_text(encoding="utf-8"))
    seed = seed or bank["meta"]["seed_แนะนำ"]
    g = Gen(bank, seed)

    docs, n = [], 0
    for task, traps, n_clean in PLAN:
        for tp in traps:
            for _ in range(N_PER_TRAP):
                n += 1
                docs.append(g.make(f"D{n:03d}", task, tp))
        for _ in range(n_clean):
            n += 1
            docs.append(g.make(f"D{n:03d}", task, None))

    DOCDIR.mkdir(parents=True, exist_ok=True)
    bundles = {}
    for d in docs:
        (DOCDIR / f"{d['doc_id']}.md").write_text(g.render(d), encoding="utf-8")
        bundles.setdefault(d["task"], []).append(g.render(d))

    manifest = {"seed": seed, "n_docs": len(docs), "tasks": {}}
    for t, parts in bundles.items():
        text = ("\n\n---\n\n").join(parts)
        (OUT / f"task_bundle_{t}.md").write_text(text, encoding="utf-8")
        manifest["tasks"][t] = {
            "n_docs": len(parts),
            "chars": len(text),
            "est_tokens_hi": round(len(text) / 2.5),   # ไทยกินโทเคนหนัก
            "n_rows": sum(len(d["rows"]) for d in docs if d["task"] == t),
        }

    # เฉลยระดับเซลล์
    cells = []
    for d in docs:
        for r in d["rows"]:
            for c in COLS:
                v = r[c]
                if c in ("งบจัดสรร", "เบิกจ่าย") and r["_หน่วย"] == "พันบาท" and isinstance(v, int):
                    v = v * 1000                       # เฉลยเป็นบาทเสมอ
                if c == "จำนวนผู้เข้าร่วม" and d["trap_type"] == "DISGUISED_MISSING" \
                        and v == (d["trap"] or {}).get("sentinel"):
                    v = None                           # ค่าเฝ้า = ค่าหาย
                if c == "กลุ่มเป้าหมาย":
                    v = "|".join(r["_กลุ่มเป้าหมาย_จริง"])
                cells.append({"doc_id": d["doc_id"], "task": d["task"],
                              "row_key": r["รหัสกิจกรรม"], "column": c,
                              "field_type": FIELD_TYPE[c], "value_correct": v})
    df_cells = pd.DataFrame(cells)

    traps = [dict({"doc_id": d["doc_id"], "task": d["task"],
                   "trap_type": d["trap_type"]}, **d["trap"])
             for d in docs if d["trap"]]
    df_traps = pd.DataFrame(traps)

    aggs = [{"doc_id": d["doc_id"], "metric": k, "value": v}
            for d in docs for k, v in d["gt"].items()]
    df_agg = pd.DataFrame(aggs)

    OUT.mkdir(exist_ok=True)
    df_cells.to_csv(OUT / "ground_truth_cells.csv", index=False, encoding="utf-8-sig")
    df_traps.to_csv(OUT / "trap_registry.csv", index=False, encoding="utf-8-sig")
    (OUT / "findings_allowlist.json").write_text(
        json.dumps({d["doc_id"]: d["allowlist"] for d in docs},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "documents.json").write_text(
        json.dumps([{k: v for k, v in d.items() if k != "rows"} | {"rows": d["rows"]}
                    for d in docs], ensure_ascii=False, indent=1), encoding="utf-8")

    with pd.ExcelWriter(OUT / "ground_truth.xlsx", engine="openpyxl") as w:
        df_cells.to_excel(w, "cells", index=False)
        df_traps.to_excel(w, "traps", index=False)
        df_agg.to_excel(w, "aggregates", index=False)

    manifest["n_cells"] = len(df_cells)
    manifest["n_traps"] = len(df_traps)
    manifest["hash_bank"] = hashlib.sha256(BANK.read_bytes()).hexdigest()[:16]
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return docs, df_cells, df_traps, manifest


if __name__ == "__main__":
    docs, cells, traps, man = build()
    print(f"เอกสาร {man['n_docs']} ฉบับ · กับดัก {man['n_traps']} ตำแหน่ง · เซลล์เฉลย {man['n_cells']:,}")
    print("\nขนาด prompt ต่องาน (ตอบ S4):")
    for t, m in sorted(man["tasks"].items()):
        print(f"  {t}: {m['n_docs']:>2} ฉบับ · {m['n_rows']:>3} แถว · "
              f"{m['chars']:>7,} อักษร · ~{m['est_tokens_hi']:,} โทเคน")
    print("\nกับดักต่อประเภท:")
    print(traps["trap_type"].value_counts().to_string())
