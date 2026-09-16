"""Sorties COURTES et tailles variables.

Ce que corrige ce passage. Le premier backtest tick sortait au bout d'une heure
en mediane, alors que la mesure forward dit que l'edge vit entre 1 et 15 minutes
et devient negatif a une heure. Je tenais la position precisement jusqu'a ce que
le gain se soit dissipe. Erreur de conception, pas resultat.

On balaie donc la duree de detention ET la taille de position - la seconde parce
que le slippage mesure va de 1,6 bps a 1 000 $ a 6,8 bps a 10 000 $ : a ce
niveau d'edge, la taille n'est pas un detail d'exploitation, c'est un parametre
de premier ordre.
"""
import sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
import flow_features as ff, tick_engine as te

N_JOURS, SEED, LAT = 2500, 7, 2.0
TAILLES = [1_000, 5_000, 10_000, 25_000]
SORTIES = [("60s",   60,  0.010, 0.005),
           ("180s", 180,  0.012, 0.008),
           ("300s", 300,  0.015, 0.010),
           ("600s", 600,  0.018, 0.012),
           ("900s", 900,  0.020, 0.015)]

uni = sorted({s.strip() for s in open("universe_union.txt") if s.strip()})
rng = np.random.default_rng(SEED)
jours = pd.date_range("2024-09-01", "2026-08-30", freq="D")
pairs = list({(uni[i], jours[j]) for i, j in
              zip(rng.integers(0, len(uni), N_JOURS*2), rng.integers(0, len(jours), N_JOURS*2))})[:N_JOURS]
print(f"{len(pairs)} jours-symboles (meme tirage que le premier passage)", file=sys.stderr)


def work(pj):
    sym, jour = pj
    try:
        d = ff.load_day(sym, jour)
    except Exception:
        return []
    if d is None or len(d["t"]) < 5000:
        return []
    t, px, q, sell = d["t"], d["px"], d["q"], d["sell"]
    qv = px * q
    try:
        grid, sig, vps, tps = te.baseline(t, px, qv)
        sigs = te.detect(t, px, qv, sell, W=30.0, z_min=6.0, vol_mult=8.0,
                         cooldown=900.0, grid=grid, sig=sig, vps=vps, tps=tps)
    except Exception:
        return []
    out = []
    for i in sigs:
        base = {"symbol": sym, "ts": float(t[i])}
        j = np.searchsorted(t, t[i] - 30.0)
        base["r_30s"] = float(px[i]/px[j] - 1.0) if j < i else np.nan
        for T in TAILLES:
            for lab, hold, stop, trail in SORTIES:
                r = te.run_trade(t, px, qv, sell, i, LAT*1000, T,
                                 stop_pct=stop, trail_pct=trail, max_hold_s=hold)
                if r:
                    base[f"pnl_{T}_{lab}"] = r[0]
                    base[f"dur_{T}_{lab}"] = r[1]
        out.append(base)
    return out


rows, t0, n = [], time.time(), 0
LOT = 60
for k in range(0, len(pairs), LOT):
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fu in as_completed([ex.submit(work, p) for p in pairs[k:k+LOT]]):
            n += 1; rows.extend(fu.result())
    if k % (LOT*6) == 0:
        print(f"  {n}/{len(pairs)} jours, {len(rows)} declenchements "
              f"({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

pd.DataFrame(rows).to_parquet("tick_events2.parquet", compression="zstd")
print(f"\n{len(rows)} declenchements en {time.time()-t0:.0f}s", file=sys.stderr)
