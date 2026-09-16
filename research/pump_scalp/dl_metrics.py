import sys, pandas as pd, bv_extra
syms = [s.strip() for s in open("universe.txt") if s.strip()]
days = pd.date_range("2025-09-01", "2026-08-31", freq="D")
jobs = [(s, d) for s in syms for d in days]
print(f"{len(jobs)} fichiers metrics ({len(syms)} symboles x {len(days)} jours)", file=sys.stderr)
bv_extra.run(jobs, bv_extra.fetch_metrics_day, 40, "metrics")
