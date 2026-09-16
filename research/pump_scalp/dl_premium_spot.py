import sys, pandas as pd, bv_extra
from bvision import months
syms = [s.strip() for s in open("universe.txt") if s.strip()]
ms = list(months("2025-09-01", "2026-08-31"))
jobs = [(s, y, m) for s in syms for y, m in ms]
print(f"{len(jobs)} fichiers x2 (premium + spot)", file=sys.stderr)
bv_extra.run(jobs, bv_extra.fetch_premium_month, 12, "premium")
bv_extra.run(jobs, bv_extra.fetch_spot_month, 12, "spot")
