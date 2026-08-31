#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_figures.py — สร้างรูป 3 รูปสำหรับบทความ IEEE

ป้ายกำกับเป็นภาษาอังกฤษ เพราะบทความส่งเป็นภาษาอังกฤษ
และเลี่ยงปัญหาฟอนต์ไทยในไฟล์ vector

รัน: python make_figures.py   →  figs\fig1..fig3 (.png และ .pdf)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
D = HERE / "data"
FIG = HERE / "figs"
FIG.mkdir(exist_ok=True)

plt.rcParams.update({"font.size": 9, "figure.dpi": 300,
                     "savefig.bbox": "tight", "axes.grid": False})

TRAP_EN = {
    "MISSING_VALUE": "Missing value", "DISGUISED_MISSING": "Disguised missing",
    "DUPLICATE_ROW": "Duplicate row", "INCORRECT_UNIT": "Incorrect unit",
    "TEXT_NUMBER_CONFLICT": "Text–number conflict", "STAT_OUTLIER": "Outlier",
    "DELIMITER_SPLIT": "Delimiter split", "NO_EVIDENCE": "No evidence (overclaim)",
    "BAIT_NO_NUMBER": "Bait (unanswerable)",
}
ORDER = ["MISSING_VALUE", "DISGUISED_MISSING", "DUPLICATE_ROW", "INCORRECT_UNIT",
         "STAT_OUTLIER", "DELIMITER_SPLIT", "TEXT_NUMBER_CONFLICT",
         "NO_EVIDENCE", "BAIT_NO_NUMBER"]

tr = pd.read_csv(D / "scores_traps.csv")
ce = pd.read_csv(D / "scores_cells.csv")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return (max(0, c - h), min(1, c + h))


# ---------------------------------------------------------------- Fig 1 · RQ1
sub = ce[ce.present_cell == 1]
g = sub.groupby("model").correct_cell.agg(["sum", "count"])
fig, ax = plt.subplots(figsize=(3.4, 2.4))
xs = np.arange(len(g))
vals = (g["sum"] / g["count"]).values
err = np.array([wilson(r["sum"], r["count"]) for _, r in g.iterrows()]).T
ax.bar(xs, vals, color="#4C72B0", width=0.55)
ax.errorbar(xs, vals, yerr=[vals - err[0], err[1] - vals], fmt="none",
            ecolor="black", capsize=3, lw=0.8)
ax.set_xticks(xs); ax.set_xticklabels(g.index)
ax.set_ylabel("Cell-level accuracy"); ax.set_ylim(0, 1)
for x, v in zip(xs, vals):
    ax.text(x, v + 0.03, f"{v:.2f}", ha="center", fontsize=8)
ax.set_title("Accuracy of reported cells (95% CI)", fontsize=9)
for e in ("top", "right"):
    ax.spines[e].set_visible(False)
fig.savefig(FIG / "fig1_accuracy.png"); fig.savefig(FIG / "fig1_accuracy.pdf")
plt.close(fig)

# ---------------------------------------------------------------- Fig 2 · RQ2
piv = tr.pivot_table(index="trap_type", columns="model",
                     values="trap_hit", aggfunc="mean").reindex(ORDER)
fig, ax = plt.subplots(figsize=(3.6, 3.2))
im = ax.imshow(piv.values, cmap="RdYlGn_r", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(piv.columns))); ax.set_xticklabels(piv.columns)
ax.set_yticks(range(len(piv))); ax.set_yticklabels([TRAP_EN[i] for i in piv.index])
for i in range(piv.shape[0]):
    for j in range(piv.shape[1]):
        v = piv.values[i, j]
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7.5,
                color="white" if (v > 0.62 or v < 0.12) else "black")
ax.set_title("Trap-hit rate by product and trap type", fontsize=9)
fig.colorbar(im, ax=ax, shrink=0.75, label="Failure rate")
fig.savefig(FIG / "fig2_trap_heatmap.png"); fig.savefig(FIG / "fig2_trap_heatmap.pdf")
plt.close(fig)

# ---------------------------------------------------------------- Fig 3 · RQ3
per_run = tr.groupby(["model", "task", "rep"]).trap_hit.mean().reset_index()
within = per_run.groupby(["model", "task"]).trap_hit.std().groupby("model").mean()
between = per_run.groupby(["model", "task"]).trap_hit.mean().groupby("task").std().mean()

fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5),
                         gridspec_kw={"width_ratios": [1.1, 1]})
a = axes[0]
xs = np.arange(len(within))
a.bar(xs, within.values, color="#C44E52", width=0.5, label="Within-product\n(across replicates)")
a.axhline(between, ls="--", lw=1.2, color="black")
a.text(len(within) - 0.5, between + 0.012, f"between-product SD = {between:.3f}",
       ha="right", fontsize=7.5)
a.set_xticks(xs); a.set_xticklabels(within.index)
a.set_ylabel("SD of trap-hit rate")
a.set_title("Run-to-run variation vs. product differences", fontsize=9)
for e in ("top", "right"):
    a.spines[e].set_visible(False)

b = axes[1]
gg = (tr.dropna(subset=["trap_hit"]).groupby(["model", "task", "doc_id"])
        .trap_hit.agg(["mean", "count"]).reset_index())
gg = gg[gg["count"] >= 3]
uns = gg[(gg["mean"] > 0) & (gg["mean"] < 1)].groupby("model").size()
tot = gg.groupby("model").size()
frac = (uns / tot).reindex(within.index).fillna(0)
b.bar(np.arange(len(frac)), frac.values, color="#DD8452", width=0.5)
b.set_xticks(np.arange(len(frac))); b.set_xticklabels(frac.index)
b.set_ylabel("Proportion of trap positions\nwith inconsistent outcome")
b.set_ylim(0, 1)
for x, v in enumerate(frac.values):
    b.text(x, v + 0.03, f"{v:.2f}", ha="center", fontsize=8)
b.set_title("Instability across replicates", fontsize=9)
for e in ("top", "right"):
    b.spines[e].set_visible(False)

fig.savefig(FIG / "fig3_instability.png"); fig.savefig(FIG / "fig3_instability.pdf")
plt.close(fig)

print("สร้างรูปแล้วที่ figs\\")
for f in sorted(FIG.glob("*.png")):
    print("  ", f.name)
print(f"\nSD ภายในผลิตภัณฑ์ (เฉลี่ย) = {within.mean():.3f}")
print(f"SD ระหว่างผลิตภัณฑ์        = {between:.3f}")
print(f"อัตราส่วน                   = {within.mean()/between:.1f} เท่า")
print("\nสัดส่วนตำแหน่งกับดักที่ผลไม่นิ่ง")
print(frac.round(3).to_string())
