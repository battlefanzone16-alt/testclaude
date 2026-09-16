import sys, pandas as pd, bvision
syms = [s.strip() for s in open("universe.txt") if s.strip()]
if "BTCUSDT" not in syms: syms.append("BTCUSDT")
print(f"{len(syms)} symboles x 12 mois", file=sys.stderr)
bvision.fetch_many(syms, "1m", "2025-09-01", "2026-09-01", workers=24)
print("termine", file=sys.stderr)
