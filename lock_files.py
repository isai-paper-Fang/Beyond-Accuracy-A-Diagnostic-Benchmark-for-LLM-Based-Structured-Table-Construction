#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lock_files.py — คำนวณลายนิ้วมือของไฟล์ที่ล็อก (F2)

ใช้พิสูจน์ว่าไฟล์ที่ใช้ตอนเก็บข้อมูลคือไฟล์เดียวกับที่ประกาศไว้ใน preregistration
รันสองครั้ง: ตอนล็อก และตอนส่งบทความ ถ้า hash ต่างแปลว่ามีการแก้ระหว่างทาง

รัน: python lock_files.py [--verify]
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK = HERE / "data" / "lockfile.json"
TZ = timezone(timedelta(hours=7))       # Asia/Bangkok

TARGETS = [
    "A_คลังคำ_v1.yaml",
    "trap_spec.md",
    "trap_rules.yaml",
    "C_prompts_v1.md",
    "E_โพรโทคอลเก็บข้อมูล.md",
    "preregistration.md",
    "generator.py",
    "tie_out.py",
    "scorer.py",
    "test_scorer.py",
    "make_run_log.py",
    "check_run_log.py",
    "data/ground_truth_cells.csv",
    "data/trap_registry.csv",
    "data/findings_allowlist.json",
    "data/documents.json",
    "data/run_log_template.csv",
    "data/pilot_log_template.csv",
]


def sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def timestamp_proof():
    """
    หลักฐานเวลาที่ไม่ได้อ้างนาฬิกาเครื่องตัวเองอย่างเดียว
    ถ้าอยู่ใน git ให้ผูกกับ commit ด้วย
    """
    out = {"local_time": datetime.now(TZ).isoformat()}
    try:
        h = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE,
                           capture_output=True, text=True, timeout=5)
        if h.returncode == 0:
            out["git_commit"] = h.stdout.strip()
    except Exception:
        pass
    return out


def build():
    entries = {}
    missing = []
    for t in TARGETS:
        p = HERE / t
        if p.exists():
            entries[t] = {"sha256": sha(p), "bytes": p.stat().st_size}
        else:
            missing.append(t)
    doc = HERE / "data" / "documents"
    if doc.exists():
        h = hashlib.sha256()
        for f in sorted(doc.glob("*.md")):
            h.update(f.read_bytes())
        entries["data/documents/* (รวม)"] = {
            "sha256": h.hexdigest(), "n_files": len(list(doc.glob('*.md')))}
    return {"stamped": timestamp_proof(), "files": entries, "missing": missing}


def main():
    verify = "--verify" in sys.argv
    now = build()
    if verify:
        if not LOCK.exists():
            sys.exit("ยังไม่มี lockfile.json — รันโดยไม่ใส่ --verify ก่อน")
        old = json.loads(LOCK.read_text(encoding="utf-8"))
        diff = [k for k, v in now["files"].items()
                if k in old["files"] and old["files"][k]["sha256"] != v["sha256"]]
        added = [k for k in now["files"] if k not in old["files"]]
        gone = [k for k in old["files"] if k not in now["files"]]
        print(f"ล็อกเมื่อ {old['stamped']['local_time']}")
        if not (diff or added or gone):
            print("✅ ไฟล์ทุกไฟล์ตรงกับตอนล็อก")
            return 0
        print("⚠️  มีการเปลี่ยนแปลงหลังล็อก — ต้องบันทึกใน §12 ของ preregistration")
        for k in diff:
            print("   แก้ไข :", k)
        for k in added:
            print("   เพิ่ม  :", k)
        for k in gone:
            print("   หายไป :", k)
        return 1

    LOCK.parent.mkdir(exist_ok=True)
    LOCK.write_text(json.dumps(now, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ล็อก {len(now['files'])} รายการ เมื่อ {now['stamped']['local_time']}")
    if now["missing"]:
        print("⚠️  ยังไม่มีไฟล์:", ", ".join(now["missing"]))
    for k, v in now["files"].items():
        print(f"  {v['sha256'][:16]}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
