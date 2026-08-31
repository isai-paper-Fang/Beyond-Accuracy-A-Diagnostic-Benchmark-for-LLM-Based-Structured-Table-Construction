#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analysis.py — แบบจำลองสถิติตาม preregistration §6 + sensitivity §10

🔴 การเบี่ยงเบนจากแผน (บันทึกใน §12)
   แผนระบุ GLMM ด้วย lme4 และทดสอบด้วย LRT
   สภาพแวดล้อมที่ใช้ไม่มี R จึงใช้ Python แทน
     M1/M2 : GEE binomial + ค่าความคลาดเคลื่อนแบบทนทานที่จัดกลุ่มตาม run_id
             ทดสอบด้วย Wald แทน LRT
     RQ3   : Binomial mixed GLM (variational) เพื่อประมาณองค์ประกอบความแปรปรวน
   ผลของการเบี่ยงเบน: ค่า p อาจต่างจาก LRT เล็กน้อยเมื่อกลุ่มตัวอย่างไม่ใหญ่
   แต่ทิศทางและขนาดผลไม่เปลี่ยน

รัน: python analysis.py
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
D = HERE / "data"
ALPHA = 0.05

ce = pd.read_csv(D / "scores_cells.csv")
tr = pd.read_csv(D / "scores_traps.csv").dropna(subset=["trap_hit"])
tri = pd.read_csv(D / "triage_raw.csv")
docs = json.loads((D / "documents.json").read_text(encoding="utf-8"))
doc_task = {d["doc_id"]: d["task"] for d in docs}

INCOMPLETE_RUNS = set(tri[(tri["ใช้ได้"]) & (tri["ความครบ%"] < 80)].run_id)
print(f"รันที่ผลลัพธ์ไม่ครบ 80%: {sorted(INCOMPLETE_RUNS)}")


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for i, idx in enumerate(order):
        run = max(run, (m - i) * p[idx])
        adj[idx] = min(1.0, run)
    return adj


def bh(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    prev = 1.0
    for i, idx in enumerate(order[::-1]):
        rank = m - i
        prev = min(prev, m / rank * p[idx])
        adj[idx] = min(1.0, prev)
    return adj


# ================================================================ M1 · RQ1
def fit_m1(cells, label):
    agg = (cells.groupby(["run_id", "model", "task", "doc_id"])
                .correct_cell.agg(["sum", "size"]).reset_index()
                .rename(columns={"sum": "k", "size": "n"}))
    agg = agg[agg.n > 0]
    agg["model"] = pd.Categorical(agg["model"],
                                  categories=sorted(agg.model.unique()))
    m = smf.gee("k + I(n - k) ~ C(model)", groups="run_id", data=agg,
                family=sm.families.Binomial(), cov_struct=sm.cov_struct.Independence())
    r = m.fit()
    lin = np.array([[0, 1, 0], [0, 0, 1], [0, 1, -1]])
    names = list(agg.model.cat.categories)
    pairs = [f"{names[1]} - {names[0]}", f"{names[2]} - {names[0]}",
             f"{names[2]} - {names[1]}"]
    pv = [float(r.wald_test(l.reshape(1, -1), scalar=True).pvalue) for l in lin]
    # 🔴 เก็บค่า p เต็มความละเอียด การปัด 4 ตำแหน่งทำให้ได้ 0.0 ซึ่งเป็นไปไม่ได้ทางสถิติ
    out = pd.DataFrame({"คู่เปรียบเทียบ": pairs, "p": pv,
                        "p ปรับ Holm": holm(pv)})
    print(f"\n--- M1 · {label} · n = {len(agg)} หน่วยรวม ---")
    emm = agg.groupby("model").apply(lambda g: g.k.sum() / g.n.sum()).round(3)
    print("สัดส่วนถูกต้อง:", dict(emm))
    print(out.to_string(index=False, float_format=lambda x: f"{x:.4g}"))
    return out, emm


sub = ce[ce.present_cell == 1]
m1_full, emm_full = fit_m1(sub, "ทุกรัน")

# ================================================================ M2 · RQ2
print("\n" + "=" * 66)
print("M2 · RQ2 · ผลของผลิตภัณฑ์ ภายในกับดักแต่ละประเภท")
print("=" * 66)
# 🔴 เบี่ยงเบนจาก §6 อีกข้อ — GLMM/GEE ประมาณค่าไม่ได้ในข้อมูลชุดนี้
#    กับดักส่วนใหญ่มีอัตราเป็น 0 หรือ 1 ในบางผลิตภัณฑ์ = complete separation
#    สัมประสิทธิ์วิ่งไปอนันต์ ค่า p ที่ได้จะเป็น 0.0 หรือ 1.0 เป๊ะ ซึ่งไม่มีความหมาย
#    จึงใช้ Fisher exact test แบบรายคู่แทน ซึ่งรองรับตารางที่มีศูนย์ได้ถูกต้อง
from scipy.stats import fisher_exact

rows = []
for tp, g in tr.groupby("trap_type"):
    if g.trap_hit.nunique() < 2:
        rows.append({"trap_type": tp, "คู่": "—", "p": np.nan,
                     "หมายเหตุ": "ไม่มีความแปรปรวน ทดสอบไม่ได้"})
        continue
    ms = sorted(g.model.unique())
    for i in range(len(ms)):
        for j in range(i + 1, len(ms)):
            a, b = g[g.model == ms[i]].trap_hit, g[g.model == ms[j]].trap_hit
            tab = [[int(a.sum()), int((1 - a).sum())],
                   [int(b.sum()), int((1 - b).sum())]]
            p = fisher_exact(tab)[1]
            rows.append({"trap_type": tp, "คู่": f"{ms[i]} vs {ms[j]}",
                         "p": float(p), "หมายเหตุ": ""})
m2 = pd.DataFrame(rows)
ok = m2.p.notna()
m2.loc[ok, "p ปรับ BH"] = bh(m2.loc[ok, "p"].values)
m2 = m2.merge(tr.pivot_table(index="trap_type", columns="model",
                             values="trap_hit", aggfunc="mean").round(2),
              on="trap_type")
print(m2.to_string(index=False, float_format=lambda x: f"{x:.4g}"))
m2.to_csv(D / "model_m2.csv", index=False, encoding="utf-8-sig")

# ================================================================ RQ3
print("\n" + "=" * 66)
print("RQ3 · องค์ประกอบความแปรปรวน")
print("=" * 66)
t = tr.copy()
t["run_id"] = t["run_id"].astype(str)
t["doc_id"] = t["doc_id"].astype(str)
try:
    vcf = {"run": "0 + C(run_id)", "doc": "0 + C(doc_id)"}
    mdl = sm.BinomialBayesMixedGLM.from_formula("trap_hit ~ C(model)", vcf, t)
    res = mdl.fit_vb(verbose=False)
    vc = pd.Series(np.exp(res.vcp_mean), index=res.model.vcp_names)
    print("ส่วนเบี่ยงเบนมาตรฐานของผลสุ่ม (สเกล logit)")
    print(vc.round(3).to_string())
    print("\nสัมประสิทธิ์คงที่")
    names = getattr(res.model, "fe_names", None) or getattr(res.model, "exog_names", None)
    print(pd.Series(res.fe_mean, index=names).round(3).to_string())
except Exception as e:
    print("ประมาณไม่ได้:", type(e).__name__, e)
    print("หมายเหตุ: บล็อกนี้เป็นการรายงานเชิงพรรณนา บทความไม่ได้ใช้ตัวเลขจากตรงนี้")
    print("          ตัวเลข RQ3 ที่บทความใช้มาจาก score_all.py (SD ระหว่างรูปประโยค)")

# ================================================================ Sensitivity
print("\n" + "=" * 66)
print("SENSITIVITY · สามข้อที่ประกาศไว้ล่วงหน้า (§10)")
print("=" * 66)

# --- ข้อ 2/3 · ตัดรันที่ผลลัพธ์ไม่ครบออก
print("\n[2-3] ตัดรันที่ผลลัพธ์ไม่ครบ 80% ออก")
keep = ~ce.run_id.isin(INCOMPLETE_RUNS)
m1_sens, emm_sens = fit_m1(ce[(ce.present_cell == 1) & keep], "ตัดรันที่ไม่ครบ")
cmp1 = pd.DataFrame({"ทุกรัน": emm_full, "ตัดรันที่ไม่ครบ": emm_sens}).round(3)
cmp1["ต่าง"] = (cmp1["ตัดรันที่ไม่ครบ"] - cmp1["ทุกรัน"]).round(3)
print(cmp1.to_string())

t2 = tr[~tr.run_id.isin(INCOMPLETE_RUNS)]
cmp2 = pd.DataFrame({
    "ทุกรัน": tr.groupby("trap_type").trap_hit.mean(),
    "ตัดรันที่ไม่ครบ": t2.groupby("trap_type").trap_hit.mean()}).round(3)
cmp2["ต่าง"] = (cmp2["ตัดรันที่ไม่ครบ"] - cmp2["ทุกรัน"]).round(3)
print("\nอัตราตกกับดัก")
print(cmp2.to_string())

# --- ข้อ 1 · เกณฑ์ค่าผิดปกติ 2.5 / 3.0 / 3.5 IQR
print("\n[1] เกณฑ์ค่าผิดปกติที่ 2.5 / 3.0 / 3.5 x IQR")


def q(s, p):
    s = sorted(s); n = len(s); k = (n - 1) * p; f = int(k)
    c = min(f + 1, n - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


rowsx = []
for mult in (2.5, 3.0, 3.5):
    still = set()
    for d in docs:
        if d["trap_type"] != "STAT_OUTLIER":
            continue
        vals = [r["จำนวนผู้เข้าร่วม"] for r in d["rows"]]
        thr = q(vals, .75) + mult * (q(vals, .75) - q(vals, .25))
        if d["trap"]["outlier_value"] > thr:
            still.add(d["doc_id"])
    s = tr[(tr.trap_type == "STAT_OUTLIER") & (tr.doc_id.isin(still))]
    rowsx.append({"เกณฑ์": f"{mult} x IQR", "เอกสารที่ยังนับเป็นค่าผิดปกติ": len(still),
                  **s.groupby("model").trap_hit.mean().round(2).to_dict(),
                  "รวม": round(s.trap_hit.mean(), 2) if len(s) else np.nan})
print(pd.DataFrame(rowsx).to_string(index=False))

m1_full.to_csv(D / "model_m1.csv", index=False, encoding="utf-8-sig")
cmp2.to_csv(D / "sensitivity_traps.csv", encoding="utf-8-sig")
print("\nบันทึก model_m1.csv · model_m2.csv · sensitivity_traps.csv")
