"""Liste des couples (symbole, jour) d'open interest a telecharger pour un jeu d'evenements."""
import sys, pandas as pd
ev = pd.read_parquet(sys.argv[1]); ev["signal_time"] = pd.to_datetime(ev["signal_time"])
e = ev[ev.r_burst > 0.03]
pairs = set()
for s, d in zip(e.symbol, e.signal_time.dt.normalize()):
    pairs.add((s, d)); pairs.add((s, d - pd.Timedelta(days=1)))
pd.DataFrame(sorted(pairs), columns=["symbol", "day"]).to_parquet(sys.argv[2])
print(f"{len(e)} evenements -> {len(pairs)} couples -> {sys.argv[2]}")
