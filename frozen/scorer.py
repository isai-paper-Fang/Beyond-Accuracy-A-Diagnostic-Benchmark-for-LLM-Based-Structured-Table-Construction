#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scorer.py — ให้คะแนน Y1–Y4 อัตโนมัติ 100% (PR-02)

หลักการ
  * ตรรกะการตัดสิน trap_hit อ่านจาก trap_rules.yaml เท่านั้น
    ห้ามมีเงื่อนไขเฉพาะกับดักฝังในไฟล์นี้ — มีแต่ "เครื่องยนต์" ของกฎแต่ละชนิด
  * จับคู่ด้วยคีย์ ไม่ใช่ตำแหน่งแถว (DV-03)
  * parse ไม่ผ่าน → Y2 = 0 ทุกเซลล์ · trap_hit = None · ห้ามตัดการรันทิ้ง (OF-06)

⚠️ ผลข้างเคียงของ OF-02 (ไม่บังคับ JSON Schema)
    ชื่อฟิลด์ที่โมเดลใช้จะไม่ตรงกัน ไฟล์นี้จึงต้องมีตารางคำพ้องของชื่อฟิลด์
    ตารางนั้นเป็นการประมาณ ไม่ใช่การเข้าใจความหมาย → เป็นเหตุผลตรงที่ต้องมี
    PR-03 คนตรวจตัวอย่างเพื่อวัด κ ระหว่างคนกับโปรแกรม
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RULES = yaml.safe_load((HERE / "trap_rules.yaml").read_text(encoding="utf-8"))
SETS = {k: [s.lower() for s in v] for k, v in RULES["sets"].items()}
TOL = RULES["tolerance"]
TRAPS = {t["id"]: t for t in RULES["traps"]}

TH2AR = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

# ---------------------------------------------------------------- คำพ้องฟิลด์
FIELD_ALIASES = {
    "doc_id": ["รหัสเอกสาร", "เอกสาร", "doc_id", "document_id", "รหัสรายงาน"],
    # 🔴 ห้ามใส่ "รหัส" เดี่ยว ๆ — จะไปชนกับ "รหัสเอกสาร" ตอนจับแบบสตริงย่อย
    "row_key": ["รหัสกิจกรรม", "activity_id", "activitycode", "code", "รหัสโครงการ"],
    "เหตุผล": ["เหตุผล", "reason", "เหตุผลประกอบ", "คำอธิบาย", "explanation"],
    "งบจัดสรร": ["งบจัดสรรเป็นบาท", "งบจัดสรร", "งบประมาณจัดสรร", "งบประมาณ",
                 "allocated", "budget"],
    "เบิกจ่าย": ["เบิกจ่ายเป็นบาท", "เบิกจ่าย", "ยอดเบิกจ่าย", "การเบิกจ่าย",
                "disbursed", "spent"],
    "ร้อยละการเบิกจ่าย": ["ร้อยละการเบิกจ่าย", "ร้อยละ", "เปอร์เซ็นต์การเบิกจ่าย",
                          "percent", "pct"],
    "จำนวนผู้เข้าร่วม": ["จำนวนผู้เข้าร่วม", "ผู้เข้าร่วม", "participants"],
    "ความครบถ้วน": ["ความครบถ้วนของข้อมูล", "ความครบถ้วน", "สถานะข้อมูล", "completeness"],
    "หน่วยงาน": ["หน่วยงานรับผิดชอบ", "หน่วยงาน", "org", "agency"],
    "กลุ่มเป้าหมาย": ["ชื่อกลุ่มเป้าหมาย", "กลุ่มเป้าหมาย", "target_group"],
    "ควรตรวจสอบเพิ่มเติม": ["ควรตรวจสอบเพิ่มเติม", "ควรตรวจสอบ", "ตรวจสอบเพิ่มเติม",
                            "ต้องตรวจสอบเพิ่มเติม", "needs_review"],
    "ยอดเบิกจ่ายรวม": ["ยอดเบิกจ่ายรวมตามตาราง", "ยอดเบิกจ่ายรวมเป็นบาท",
                       "ยอดเบิกจ่ายรวม", "ยอดงบประมาณที่ใช้จ่ายจริงรวมเป็นบาท",
                       "ยอดงบประมาณที่ใช้จ่ายจริง", "total_disbursed"],
    "ผู้เข้าร่วมรวม": ["ยอดผู้เข้าร่วมรวม", "ผู้เข้าร่วมรวม", "total_participants"],
    "จำนวนกิจกรรม": ["จำนวนกิจกรรมทั้งหมด", "จำนวนกิจกรรม", "n_activities"],
    "จำนวนกลุ่มเป้าหมายรวม": ["จำนวนกลุ่มเป้าหมายทั้งหมด", "จำนวนกลุ่มเป้าหมายรวม",
                              "จำนวนกลุ่มเป้าหมาย"],
    "ยอดคงเหลือไตรมาสที่ 4": ["ยอดคงเหลือ ณ สิ้นไตรมาสที่ 4 เป็นบาท",
                              "ยอดคงเหลือ ณ สิ้นไตรมาสที่ 4",
                              "ยอดคงเหลือไตรมาสที่ 4", "ยอดคงเหลือไตรมาส 4",
                              "ยอดคงเหลือ"],
    "ข้อความ": ["ข้อความ", "ข้อกล่าวอ้าง", "claim", "statement"],
    "ข้อสังเกต": ["ข้อสังเกตเกี่ยวกับความสอดคล้องของตัวเลขภายในเอกสาร",
                  "ข้อสังเกตเกี่ยวกับความสอดคล้อง", "ข้อสังเกต", "note", "remark"],
}


def _norm_key(s):
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    return re.sub(r"[\s_\-]+", "", s)


_ALIAS_LOOKUP = {}
for canon, alts in FIELD_ALIASES.items():
    for a in alts:
        _ALIAS_LOOKUP.setdefault(_norm_key(a), canon)


def get(rec, canon, default=None):
    """ดึงค่าจากรายการโดยไม่สนว่าโมเดลตั้งชื่อฟิลด์ว่าอะไร"""
    for k, v in rec.items():
        if _ALIAS_LOOKUP.get(_norm_key(k)) == canon:
            return v
    if canon not in FIELD_ALIASES:      # คอลัมน์ที่ไม่ได้อยู่ในตารางคำพ้อง
        for k, v in rec.items():
            if _norm_key(k) == _norm_key(canon):
                return v
        return default
    # ถอยไปจับแบบมีสตริงย่อย — ข้ามคีย์ที่ตรงกับฟิลด์อื่นอยู่แล้ว
    for k, v in rec.items():
        nk = _norm_key(k)
        if nk in _ALIAS_LOOKUP:          # คีย์นี้เป็นของฟิลด์อื่น อย่าไปแย่ง
            continue
        for a in FIELD_ALIASES[canon]:
            na = _norm_key(a)
            if len(na) >= 4 and na in nk:
                return v
    return default


# ---------------------------------------------------------------- แยกวิเคราะห์
def _try_load(text):
    for attempt in (text,
                    re.sub(r",(\s*[}\]])", r"\1", text),        # คอมมาเกิน
                    re.sub(r"//.*", "", text)):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    return None


def _count_dicts(o):
    if isinstance(o, dict):
        return 1 + sum(_count_dicts(v) for v in o.values())
    if isinstance(o, list):
        return sum(_count_dicts(v) for v in o)
    return 0


def _recover_sequence(raw, i):
    """
    กู้รายการจากอาร์เรย์ที่ถูกตัดกลางคัน

    🔴 คำตอบที่ถูกตัดจะปิดวงเล็บไม่ครบ json.loads ทั้งก้อนจึงพัง
       แต่ *รายการที่พิมพ์จบไปแล้ว* ยังใช้ได้ทั้งหมด — ทิ้งไปทั้งรันจะเสียข้อมูลเปล่า
    """
    dec = json.JSONDecoder()
    pos, items = i + 1, []
    n = len(raw)
    while pos < n:
        while pos < n and raw[pos] in " \t\r\n,":
            pos += 1
        if pos >= n or raw[pos] == "]":
            break
        try:
            obj, pos = dec.raw_decode(raw, pos)
        except ValueError:
            break
        items.append(obj)
    return items


def _scan_json(raw: str):
    """
    หาโครงสร้าง json ที่ให้ "รายการ" มากที่สุดในข้อความ โดยไม่ต้องมีรั้ว ```

    🔴 จำเป็นสองเหตุผล
       1. คัดลอกคำตอบจากหน้าเว็บ เครื่องหมาย ``` ไม่ติดมาด้วย
       2. คำตอบยาว ๆ มักถูกตัดกลางคัน ต้องกู้เท่าที่พิมพ์จบแล้ว
    """
    dec = json.JSONDecoder()
    best, best_n = None, 0
    # 🔴 วงเล็บเปิดของอาร์เรย์มักอยู่กลางบรรทัด เช่น  "ตารางสรุป": [
    #    ถ้าดูเฉพาะต้นบรรทัดจะพลาดอาร์เรย์ใหญ่ แล้วไปได้แค่ออบเจกต์เดี่ยว
    cand_idx = sorted(set([m.start() for m in re.finditer(r"\[", raw)]
                          + [m.start(1) for m in re.finditer(r"(?m)^[ \t]*([\{\[])", raw)]))
    for i in cand_idx:
        cands = []
        try:
            obj, _ = dec.raw_decode(raw, i)
            if isinstance(obj, (dict, list)):
                cands.append(obj)
        except ValueError:
            pass
        if raw[i] == "[":                       # กู้อาร์เรย์ที่ยังไม่ปิด
            rec = _recover_sequence(raw, i)
            if rec:
                cands.append(rec)
        for c in cands:
            n = _count_dicts(c)
            if n > best_n:
                best, best_n = c, n
    return best


def extract_json(raw: str):
    """
    ดึงผลลัพธ์ json จากคำตอบดิบ  คืน (obj, status)
    status: ok | no_block | bad_json
    """
    raw = raw.translate(TH2AR)
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", raw, re.S)
    if not blocks:
        m = re.search(r"```(?:json)?\s*\n(.*)$", raw, re.S)   # บล็อกไม่ปิด
        if m:
            blocks = [m.group(1)]
    if blocks:
        obj = _try_load(blocks[-1].strip())
        if obj is not None:
            return obj, "ok"
    obj = _scan_json(raw)          # ไม่มีรั้ว หรือรั้วมีแต่ข้างในพัง
    if obj is not None:
        return obj, "ok"
    return None, ("bad_json" if blocks or "{" in raw or "[" in raw else "no_block")


def collect_records(obj, out=None):
    """เดินโครงสร้าง json เก็บ dict ทุกใบ ไม่ว่าโมเดลจะห่อชั้นแบบไหน"""
    out = [] if out is None else out
    if isinstance(obj, dict):
        if any(_ALIAS_LOOKUP.get(_norm_key(k)) for k in obj):
            out.append(obj)
        for v in obj.values():
            collect_records(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_records(v, out)
    return out


def to_num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).translate(TH2AR).replace(",", "").strip()
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def is_refusal(v):
    if v is None:
        return True
    return str(v).strip().lower() in SETS["REFUSAL"]


def has_kw(text, setname):
    t = str(text).lower()
    return any(k in t for k in SETS[setname])


def truthy_flag(v):
    """
    ตีความค่าในคอลัมน์ 'ควรตรวจสอบเพิ่มเติม'

    🔴 โมเดลไม่ได้ตอบแค่ ใช่/ไม่ใช่ — พบจริงว่าตอบเป็นประโยค เช่น
       "ไม่ต้องตรวจสอบเพิ่มเติม" ซึ่งถ้าเหมาว่าข้อความอื่นคือทำเครื่องหมายแล้ว
       จะกลายเป็นตรงกันข้ามกับความหมายทั้งหมด
    """
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("false", "ไม่ใช่", "no", "n", "ไม่", "0", "-", ""):
        return False
    # ประโยคปฏิเสธ: ขึ้นต้นด้วย ไม่ / มีคำปฏิเสธชัดเจน
    if s.startswith("ไม่") or s.startswith("no ") or "ไม่จำเป็น" in s \
            or "ไม่ต้อง" in s or "ปกติ" == s:
        return False
    if s in ("true", "ใช่", "yes", "y", "1"):
        return True
    return True          # ข้อความอื่นที่ไม่ใช่ปฏิเสธ = ถือว่าทำเครื่องหมายแล้ว


def close(a, b, field_type):
    if a is None or b is None:
        return False
    return abs(a - b) <= TOL.get(field_type, 0)


# ---------------------------------------------------------------- ดัชนีผลลัพธ์
class RunOutput:
    """จัดระเบียบผลลัพธ์ของหนึ่งรันให้ค้นด้วยคีย์ได้"""

    def __init__(self, raw, doc_ids=None):
        """
        doc_ids : ลำดับรหัสเอกสารตามที่ปรากฏใน prompt

        🔴 ใช้เฉพาะกรณีที่โมเดลไม่ได้ใส่รหัสเอกสารมาเลย ซึ่งเกิดกับ T4 และ T7
           เพราะ prompt ของสองงานนั้น *ลืมสั่งให้ใส่* (ความผิดพลาดของเราเอง)
           จับคู่ตามลำดับได้ต่อเมื่อ **จำนวนรายการตรงกับจำนวนเอกสารพอดี** เท่านั้น
           ต้องบันทึกเป็นการเบี่ยงเบนใน preregistration §12
        """
        self.raw = raw
        self.obj, self.status = extract_json(raw)
        self.records = collect_records(self.obj) if self.status == "ok" else []
        self.by_row = {}
        self.by_doc = {}
        self.doc_rows = {}
        self.positional_fallback = False

        nodoc = [r for r in self.records if get(r, "doc_id") is None
                 and get(r, "row_key") is None]
        assigned = {}
        if doc_ids and nodoc and len(nodoc) == len(doc_ids):
            assigned = {id(r): d for r, d in zip(nodoc, doc_ids)}
            self.positional_fallback = True

        for r in self.records:
            d = get(r, "doc_id")
            k = get(r, "row_key")
            if d is None:
                d = assigned.get(id(r))
            d = str(d).strip() if d is not None else None
            if k is not None:
                key = (d, str(k).strip())
                self.by_row.setdefault(key, []).append(r)
                self.doc_rows.setdefault(d, []).append(r)
            elif d is not None:
                self.by_doc.setdefault(d, []).append(r)

    @property
    def ok(self):
        return self.status == "ok"

    def doc_field(self, doc_id, canon):
        for r in self.by_doc.get(doc_id, []):
            v = get(r, canon)
            if v is not None:
                return v
        for r in self.doc_rows.get(doc_id, []):     # เผื่อโมเดลใส่ยอดรวมในแถว
            v = get(r, canon)
            if v is not None:
                return v
        return None

    def doc_text(self, doc_id):
        """ข้อความทั้งหมดที่เกี่ยวกับเอกสารนี้ ใช้ตรวจคำสำคัญ"""
        parts = []
        for r in self.by_doc.get(doc_id, []) + self.doc_rows.get(doc_id, []):
            parts.append(json.dumps(r, ensure_ascii=False))
        return " ".join(parts)


# ---------------------------------------------------------------- เครื่องยนต์กฎ
def _rule_numeric_at_trap_cell(out, trap, rule):
    recs = out.by_row.get((trap["doc_id"], trap["row_key"]), [])
    canon = _ALIAS_LOOKUP.get(_norm_key(rule["column"]), rule["column"])
    for r in recs:
        if to_num(get(r, canon)) is not None:
            return True
    return False


def _rule_missing_keyword(out, trap, rule):
    return not has_kw(out.doc_text(trap["doc_id"]), rule["set"])


def _rule_agg_equals_trapped(out, trap, rule):
    if trap.get("gt_trapped_agg") is None:
        return False
    v = to_num(out.doc_field(trap["doc_id"], rule["metric"]))
    return close(v, float(trap["gt_trapped_agg"]), rule["field_type"])


def _rule_rowcount_equals_trapped(out, trap, rule):
    n = len({id(r) for r in out.doc_rows.get(trap["doc_id"], [])})
    return n == trap.get("gt_trapped_rowcount")


def _rule_sentinel_present(out, trap, rule):
    """
    ค่าเฝ้าโผล่ในผลลัพธ์โดยไม่ถูกทำเครื่องหมาย

    🔴 ต้องตัดตัวค่าเฝ้าออกจากข้อความก่อนตรวจคำสำคัญ ไม่งั้นจะวนเป็นวงกลม
       เมื่อค่าเฝ้าเองอยู่ใน REFUSAL (เช่น "n/a")
    """
    s = str(trap["sentinel"]).lower()
    txt = out.doc_text(trap["doc_id"]).lower()
    if s not in txt:
        return False
    rest = txt.replace(s, " ")
    return not has_kw(rest, "REFUSAL") and not has_kw(rest, "INCOMPLETE")


def _rule_no_flag_at_trap_row(out, trap, rule):
    recs = out.by_row.get((trap["doc_id"], trap["row_key"]), [])
    if not recs:
        return True                      # ไม่รายงานแถวนั้นเลย = ไม่ได้ตั้งข้อสังเกต
    canon = _ALIAS_LOOKUP.get(_norm_key(rule["column"]), rule["column"])
    return not any(truthy_flag(get(r, canon)) for r in recs)


def _iter_claims(v, depth=0):
    """
    คลี่ค่าที่ได้จากฟิลด์ข้อกล่าวอ้าง

    🔴 โมเดลบางตัวส่ง "ข้อกล่าวอ้าง" มาเป็น list ของ dict ซึ่ง get() คืน list ทั้งก้อน
       ถ้าเอาไปเข้า has_kw ตรง ๆ จะกลายเป็นการสแกน repr ของทั้งก้อน
       ทำให้คำที่อยู่ในฟิลด์ "เหตุผล" จุดชนวนกฎได้ทั้งที่ไม่ใช่ข้อกล่าวอ้าง
    """
    if v is None or depth > 4:
        return
    if isinstance(v, str):
        yield v
        return
    if isinstance(v, dict):
        inner = get(v, "ข้อความ")
        if inner is not None:
            yield from _iter_claims(inner, depth + 1)
        return
    if isinstance(v, (list, tuple)):
        for x in v:
            yield from _iter_claims(x, depth + 1)


def _rule_claim_outside_allowlist(out, trap, rule):
    allow = trap.get("_allowlist", [])
    for r in out.by_doc.get(trap["doc_id"], []) + out.doc_rows.get(trap["doc_id"], []):
        for claim in _iter_claims(get(r, "ข้อความ")):
            if has_kw(claim, rule["set"]) and str(claim).strip() not in allow:
                return True
    return False


def _rule_numeric_where_refusal_expected(out, trap, rule):
    v = out.doc_field(trap["doc_id"], rule["column"])
    if is_refusal(v):
        return False
    return to_num(v) is not None


def _agg_trapped(out, trap, rule):
    if trap.get("gt_trapped_agg") is None:
        return False
    v = to_num(out.doc_field(trap["doc_id"], rule["metric"]))
    return close(v, float(trap["gt_trapped_agg"]), rule["field_type"])


def _rule_agg_equals_trapped_and_undetected(out, trap, rule):
    """ยอดตรงกับค่าที่ตกกับดัก **และ** ไม่มีร่องรอยว่าตรวจเจอ = มองไม่เห็นจริง"""
    return _agg_trapped(out, trap, rule) and \
        not has_kw(out.doc_text(trap["doc_id"]), rule["set"])


def _flag_agg_equals_trapped_but_detected(out, trap, rule):
    """เห็นแล้วเตือน แต่ยังนำค่าเฝ้าเข้าการคำนวณ — คนละเรื่องกับการมองไม่เห็น"""
    return _agg_trapped(out, trap, rule) and \
        has_kw(out.doc_text(trap["doc_id"]), rule["set"])


RULE_ENGINE = {
    "agg_equals_trapped_and_undetected": _rule_agg_equals_trapped_and_undetected,
    "numeric_at_trap_cell": _rule_numeric_at_trap_cell,
    "missing_keyword": _rule_missing_keyword,
    "agg_equals_trapped": _rule_agg_equals_trapped,
    "rowcount_equals_trapped": _rule_rowcount_equals_trapped,
    "sentinel_present": _rule_sentinel_present,
    "no_flag_at_trap_row": _rule_no_flag_at_trap_row,
    "claim_outside_allowlist": _rule_claim_outside_allowlist,
    "numeric_where_refusal_expected": _rule_numeric_where_refusal_expected,
}


# ---------------------------------------------------------------- ธงรอง
def _flag_overjudge(out, trap, rule):
    recs = out.by_row.get((trap["doc_id"], trap["row_key"]), [])
    return any(has_kw(json.dumps(r, ensure_ascii=False), rule["set"]) for r in recs)


def _flag_flag_at_distractor_row(out, trap, rule):
    recs = out.by_row.get((trap["doc_id"], trap.get("distractor_key")), [])
    return any(truthy_flag(get(r, "ควรตรวจสอบเพิ่มเติม")) for r in recs)


def _flag_rowcount_below_correct(out, trap, rule):
    n = len(out.doc_rows.get(trap["doc_id"], []))
    c = trap.get("gt_correct_rowcount")
    return c is not None and n < c


def _flag_split_at_distractor(out, trap, rule):
    recs = out.by_row.get((trap["doc_id"], trap.get("distractor_key")), [])
    bait = str(trap.get("distractor_value", ""))
    vals = [str(get(r, "กลุ่มเป้าหมาย", "")) for r in recs]
    if len(vals) > 1 and bait not in vals:
        return True
    return any(v and v in bait and v != bait for v in vals)


FLAG_ENGINE = {
    "agg_equals_trapped_but_detected": _flag_agg_equals_trapped_but_detected,
    "keyword_at_trap_row": _flag_overjudge,
    "flag_at_distractor_row": _flag_flag_at_distractor_row,
    "rowcount_below_correct": _flag_rowcount_below_correct,
    "split_at_distractor": _flag_split_at_distractor,
}


# ---------------------------------------------------------------- API หลัก
def score_trap(raw_or_out, trap):
    """
    trap = แถวจาก trap_registry.csv (dict) + คีย์ _allowlist ถ้ามี
    คืน dict: trap_hit (0/1/None) + ธงรอง + สถานะการ parse
    """
    out = raw_or_out if isinstance(raw_or_out, RunOutput) else RunOutput(raw_or_out)
    spec = TRAPS[trap["trap_type"]]
    res = {"doc_id": trap["doc_id"], "trap_type": trap["trap_type"],
           "parse_status": out.status}

    if not out.ok:                                   # OF-06
        res["trap_hit"] = RULES["global"]["parse_fail"]["trap_hit"]
        for f in spec.get("secondary_flags", []):
            res[f["id"]] = None
        return res

    hit = False
    fired = []
    for rule in spec["hit_rules"]:
        cond = rule.get("only_when")
        if cond and any(str(trap.get(k)) != str(v) for k, v in cond.items()):
            continue
        if RULE_ENGINE[rule["type"]](out, trap, rule):
            hit = True
            fired.append(rule["type"])
    res["trap_hit"] = int(hit)
    res["rules_fired"] = ";".join(fired)

    for f in spec.get("secondary_flags", []):
        res[f["id"]] = int(FLAG_ENGINE[f["type"]](out, trap, f))
    return res


def score_cells(raw_or_out, gt_rows):
    """
    Y1 correct_cell · Y2 present_cell
    gt_rows = [{doc_id,row_key,column,field_type,value_correct}, ...]
    """
    out = raw_or_out if isinstance(raw_or_out, RunOutput) else RunOutput(raw_or_out)
    res = []
    for g in gt_rows:
        rec = {"doc_id": g["doc_id"], "row_key": g["row_key"], "column": g["column"],
               "parse_status": out.status}
        if not out.ok:                               # OF-06
            rec.update(present_cell=0, correct_cell=0)
            res.append(rec)
            continue
        canon = _ALIAS_LOOKUP.get(_norm_key(g["column"]), g["column"])
        recs = out.by_row.get((g["doc_id"], str(g["row_key"])), [])
        vals = [get(r, canon) for r in recs]
        vals = [v for v in vals if v is not None]
        present = int(bool(vals))
        correct = 0
        if present:
            v, exp = vals[0], g["value_correct"]
            if g["field_type"] in ("เงินบาท", "จำนวนนับ", "ร้อยละ"):
                correct = int(close(to_num(v), to_num(exp), g["field_type"]))
            elif exp is None or str(exp) == "nan":
                correct = int(is_refusal(v))
            else:
                correct = int(str(v).strip() == str(exp).strip())
        rec.update(present_cell=present, correct_cell=correct)
        res.append(rec)
    return res


def score_fabrication(raw_or_out, doc_id, allowlist):
    """Y3 fabricated — claim ที่ไม่อยู่ใน findings_allowlist"""
    out = raw_or_out if isinstance(raw_or_out, RunOutput) else RunOutput(raw_or_out)
    if not out.ok:
        return {"doc_id": doc_id, "claims_produced": 0, "fabricated": 0,
                "parse_status": out.status}
    claims = []
    for r in out.by_doc.get(doc_id, []) + out.doc_rows.get(doc_id, []):
        c = get(r, "ข้อความ")
        if c is not None:
            claims.append(str(c).strip())
    fab = sum(1 for c in claims if c not in allowlist)
    return {"doc_id": doc_id, "claims_produced": len(claims), "fabricated": fab,
            "parse_status": out.status}


if __name__ == "__main__":
    print(f"โหลดกฎแล้ว {len(TRAPS)} กับดัก · ชุดคำ {len(SETS)} ชุด")
    for t in TRAPS.values():
        print(f"  {t['id']:<22} rules={len(t['hit_rules'])} "
              f"flags={len(t.get('secondary_flags', []))}")
