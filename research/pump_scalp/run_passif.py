"""Entree PASSIVE apres l'ignition : le mecanisme jamais teste.

Tous mes backtests traversent le spread et paient le taker des deux cotes, soit
9 bps de frais plus le slippage mesure. Un bot professionnel ne fait pas cela.
Avec un maker a 2 bps (voire un rabais aux paliers eleves) et zero slippage a
l'entree, le peage tombe de ~23 bps a ~7 - alors que le gisement mesure a 5
minutes vaut 8 a 10 bps.

Le taux de remplissage est compte comme un resultat, pas comme un filtre : un
ordre non execute est une occasion manquee.
"""
import sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
import flow_features as ff, tick_engine as te

N_JOURS, SEED, LAT, TAILLE = 2500, 7, 2.0, 10_000
DECOTES = [0, 5, 10, 20, 40]          # bps sous le prix de declenchement
FENETRES = [30, 120, 300]             # secondes de validite de l'ordre
SORTIES = [("300s", 300, 0.015, 0.010), ("900s", 900, 0.020, 0.015)]

uni = sorted({s.strip() for s in open("universe_union.txt") if s.strip()})
rng = np.random.default_rng(SEED)
jours = pd.date_range("2024-09-01", "2026-08-30", freq="D")
pairs = list({(uni[i], jours[j]) for i, j in
              zip(rng.integers(0, len(uni), N_JOURS*2), rng.integers(0, len(jours), N_JOURS*2))})[:N_JOURS]

def work(pj):
    sym, jour = pj
    try: d = ff.load_day(sym, jour)
    except Exception: return []
    if d is None or len(d["t"]) < 5000: return []
    t, px, q, sell = d["t"], d["px"], d["q"], d["sell"]; qv = px*q
    try:
        grid, sig, vps, tps = te.baseline(t, px, qv)
        sigs = te.detect(t, px, qv, sell, W=30.0, z_min=6.0, vol_mult=8.0,
                         cooldown=900.0, grid=grid, sig=sig, vps=vps, tps=tps)
    except Exception: return []
    out=[]
    for i in sigs:
        base = {"symbol": sym, "ts": float(t[i])}
        for dec in DECOTES:
            for fen in FENETRES:
                for lab, hold, stop, trail in SORTIES:
                    r = te.trade_passif(t, px, qv, sell, i, LAT*1000, TAILLE,
                                        dec, fen, hold, trail, stop)
                    k = f"{dec}_{fen}_{lab}"
                    base[f"rempli_{k}"] = r is not None
                    if r: base[f"pnl_{k}"] = r[0]
        out.append(base)
    return out

rows, t0, n = [], time.time(), 0
LOT=60
for k in range(0, len(pairs), LOT):
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fu in as_completed([ex.submit(work,p) for p in pairs[k:k+LOT]]):
            n+=1; rows.extend(fu.result())
    if k % (LOT*6)==0:
        print(f"  {n}/{len(pairs)} jours, {len(rows)} declenchements ({time.time()-t0:.0f}s)",
              file=sys.stderr, flush=True)
pd.DataFrame(rows).to_parquet("tick_passif.parquet", compression="zstd")
print(f"\n{len(rows)} declenchements en {time.time()-t0:.0f}s", file=sys.stderr)
