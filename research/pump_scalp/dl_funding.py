import sys, pandas as pd, bv_extra
from bvision import months
syms = sorted({s.strip() for s in open("universe_union.txt") if s.strip()})
jobs = [(s, y, m) for s in syms for y, m in months("2024-09-01", "2026-08-31")]
print(f"{len(jobs)} fichiers funding", file=sys.stderr)
bv_extra.run(jobs, bv_extra.fetch_funding_month, 16, "funding")
