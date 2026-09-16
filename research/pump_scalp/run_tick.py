"""Backtest tick sur un echantillon ALEATOIRE de jours-symboles.

Le tirage aleatoire est essentiel. Si on ne fait tourner le detecteur que sur
les journees ou l'on sait qu'un pump a eu lieu, on mesure sa performance
conditionnellement a la reussite - les faux positifs des journees calmes
disparaissent et le P&L est un mirage. Ici le detecteur voit des journees
ordinaires dans la meme proportion qu'en live.
"""
import sys, time, itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
import flow_features as ff, tick_engine as te

N_JOURS = 2500
TAILLE = 10_000
LATENCES = [0.2, 2.0, 10.0, 60.0]
SEED = 7

uni = sorted({s.strip() for s in open("universe_union.txt") if s.strip()})
rng = np.random.default_rng(SEED)
jours = pd.date_range("2024-09-01", "2026-08-30", freq="D")
pairs = list({(uni[i], jours[j]) for i, j in
              zip(rng.integers(0, len(uni), N_JOURS * 2),
                  rng.integers(0, len(jours), N_JOURS * 2))})[:N_JOURS]
print(f"{len(pairs)} jours-symboles tires au hasard", file=sys.stderr)


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
        base = {"symbol": sym, "jour": str(jour.date()),
                "ts": float(t[i]), "px_sig": float(px[i]),
                "vol_jour": float(qv.sum())}
        j = np.searchsorted(t, t[i] - 30.0)
        base["r_30s"] = float(px[i] / px[j] - 1.0) if j < i else np.nan
        for lat in LATENCES:
            p_in = te.sweep_buy(t, px, qv, sell, t[i] + lat, TAILLE)
            base[f"px_in_{lat}"] = p_in
            if np.isfinite(p_in):
                for hz in (60, 300, 900, 3600):
                    k = min(np.searchsorted(t, t[i] + lat + hz), len(px) - 1)
                    base[f"fwd_{lat}_{hz}"] = float(px[k] / p_in - 1.0)
                # trade complet avec sortie en temps-tick
                r = te.run_trade(t, px, qv, sell, i, lat * 1000, TAILLE,
                                 stop_pct=0.015, trail_pct=0.02, max_hold_s=3600)
                if r:
                    base[f"pnl_{lat}"], base[f"duree_{lat}"], base[f"why_{lat}"] = r
        out.append(base)
    return out


rows, t0, n = [], time.time(), 0
LOT = 60
for k in range(0, len(pairs), LOT):
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fu in as_completed([ex.submit(work, p) for p in pairs[k:k + LOT]]):
            n += 1
            rows.extend(fu.result())
    if k % (LOT * 5) == 0:
        print(f"  {n}/{len(pairs)} jours, {len(rows)} declenchements "
              f"({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

d = pd.DataFrame(rows)
d.to_parquet("tick_events.parquet", compression="zstd")
print(f"\n{len(d)} declenchements sur {n} jours ({len(d)/max(n,1):.2f}/jour) "
      f"en {time.time()-t0:.0f}s", file=sys.stderr)
