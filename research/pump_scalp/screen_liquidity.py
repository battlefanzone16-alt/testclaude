"""Screen 1d sur tout l'univers : liquidite mediane + anciennete de listing."""
import sys
import numpy as np, pandas as pd
import bvision

START, END = "2025-09-01", "2026-09-01"

syms = [s.strip() for s in open("symbols_all.txt") if s.strip()]
syms = [s for s in syms if s.isascii()]          # quelques tickers non-ASCII exotiques
print(f"{len(syms)} symboles ASCII", file=sys.stderr)

uni = bvision.fetch_many(syms, "1d", START, END, workers=24)
print(f"{len(uni)} symboles avec donnees", file=sys.stderr)

rows = []
for s, df in uni.items():
    if len(df) < 30:
        continue
    rows.append({
        "symbol": s,
        "n_days": len(df),
        "first": df.index[0].date(),
        "last": df.index[-1].date(),
        "qv_median_musd": float(df["quote_volume"].median()) / 1e6,
        "qv_p25_musd": float(df["quote_volume"].quantile(.25)) / 1e6,
        "px_last": float(df["close"].iloc[-1]),
        # amplitude journaliere mediane : proxy de "ca bouge"
        "range_median_pct": float(((df["high"] - df["low"]) / df["close"]).median() * 100),
    })
out = pd.DataFrame(rows).sort_values("qv_median_musd", ascending=False)
out.to_csv("liquidity_screen.csv", index=False)
print(out.head(25).to_string(index=False), file=sys.stderr)
