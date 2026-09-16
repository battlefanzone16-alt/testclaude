import sys, bvision
syms = [s.strip() for s in open("universe_hist.txt") if s.strip()]
if "BTCUSDT" not in syms: syms.append("BTCUSDT")
print(f"{len(syms)} symboles x 12 mois (2024-09 -> 2025-09)", file=sys.stderr)
bvision.fetch_many(syms, "1m", "2024-09-01", "2025-09-01", workers=24, collect=False)
print("termine", file=sys.stderr)
