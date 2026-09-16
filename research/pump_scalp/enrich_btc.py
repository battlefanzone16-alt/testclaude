"""Ajoute les rendements forward de BTC et le residu alt - beta*BTC.

Question a trancher : le "pump de token" a-t-il une continuation PROPRE, ou
n'est-on qu'en train de capter la direction du marche avec un levier ? Si le
residu est nul, le signal est un timing BTC deguise - et il se joue alors sur
BTC, moins cher et plus liquide.

Le beta est estime par symbole sur les rendements 5-min de TOUTE la periode.
C'est un diagnostic, pas un signal : un leger look-ahead sur le beta est
acceptable ici et va meme CONTRE nous (il maximise la part expliquee par BTC).
"""
import numpy as np, pandas as pd, bvision

HZ = [5, 15, 30, 60, 120, 240]
START, END = "2025-09-01", "2026-09-01"

ev = pd.read_parquet("events_k5.parquet")
ev["entry_time"] = pd.to_datetime(ev["entry_time"])

btc = bvision.fetch("BTCUSDT", "1m", START, END)
bo = btc["open"].to_numpy("float64")
bfwd = pd.DataFrame(index=btc.index)
for h in HZ:
    nxt = np.concatenate([bo[h:], np.full(h, np.nan)])
    bfwd[f"btc_{h}"] = nxt / bo - 1.0
ev = ev.merge(bfwd, left_on="entry_time", right_index=True, how="left")

# beta par symbole, sur rendements 5-min
br5 = btc["close"].astype("float64").pct_change(5)
betas = {}
for sym in ev.symbol.unique():
    df = bvision.fetch(sym, "1m", START, END)
    if len(df) < 5000:
        betas[sym] = 1.0; continue
    a = df["close"].astype("float64").pct_change(5)
    j = a.index.intersection(br5.index)
    x, y = br5.loc[j].to_numpy(), a.loc[j].to_numpy()
    m = np.isfinite(x) & np.isfinite(y)
    betas[sym] = float(np.dot(x[m], y[m]) / np.dot(x[m], x[m])) if m.sum() > 1000 else 1.0
ev["beta"] = ev.symbol.map(betas)
print("beta : median %.2f, p10 %.2f, p90 %.2f" % (
    ev.beta.median(), ev.beta.quantile(.1), ev.beta.quantile(.9)))

for h in HZ:
    ev[f"res_{h}"] = ev[f"fwd_{h}"] - ev["beta"] * ev[f"btc_{h}"]
ev.to_parquet("events_k5_btc.parquet", compression="zstd")
print(f"-> events_k5_btc.parquet ({len(ev)} lignes)")
