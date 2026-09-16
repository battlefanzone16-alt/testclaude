"""Le slippage reel a l'entree, mesure sur les trades, pas suppose.

Toute l'etude compare un edge brut a un peage suppose de 19 bps aller-retour,
dont 5 bps de slippage par cote. Ce 5 bps etait une hypothese de travail, jamais
verifiee - et c'est le chiffre qui decide de tout.

Mesure directe : au moment du signal, on rejoue un ordre au marche de X dollars
en consommant les trades agressifs a l'achat dans l'ordre chronologique, et on
compare le prix moyen obtenu au dernier prix affiche avant l'ordre. C'est
exactement ce que paierait un preneur de liquidite, mesure sur le flux reel de
la bougie d'ignition.

C'est une borne INFERIEURE du cout reel : on consomme le flux qui s'est
effectivement produit, sans compter que notre propre ordre aurait deplace le
carnet et attire des reactions.
"""
import sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
import flow_features as ff

TAILLES = [1_000, 5_000, 10_000, 25_000, 50_000, 100_000]

ev = pd.read_parquet("events_tail24.parquet")
ev["signal_time"] = pd.to_datetime(ev["signal_time"])
sel = ev[ev.r_burst > 0.08].copy()          # les vraies ignitions
sel["jour"] = sel.signal_time.dt.normalize()
groups = list(sel.groupby(["symbol", "jour"], sort=False))
print(f"{len(sel)} ignitions >8%, {len(groups)} jours-symboles", file=sys.stderr)


def sweep(d, s_epoch, taille):
    """Prix moyen paye par un ordre au marche de `taille` dollars lance a s."""
    t, px, q, sell = d["t"], d["px"], d["q"], d["sell"]
    m = (t >= s_epoch) & (t < s_epoch + 120) & (~sell)      # achats agressifs
    if m.sum() < 3:
        return np.nan
    p, qq = px[m], q[m] * px[m]
    ref = px[t < s_epoch][-1] if (t < s_epoch).any() else p[0]
    cum = np.cumsum(qq)
    k = np.searchsorted(cum, taille)
    if k >= len(cum):
        return np.nan                                        # flux insuffisant
    w = qq[:k + 1].copy()
    w[-1] -= (cum[k] - taille)
    vwap = float(np.dot(p[:k + 1], w) / w.sum())
    return (vwap / ref - 1.0) * 1e4                          # bps


def work(item):
    (sym, jour), g = item
    try:
        d = ff.load_day(sym, jour)
    except Exception:
        return []
    if d is None or len(d["t"]) < 500:
        return []
    out = []
    for st, rb, qvr in zip(g.signal_time, g.r_burst, g.qv_ref_1d):
        s = st.timestamp()
        row = {"r_burst": rb, "qv_ref_1d": qvr}
        for T in TAILLES:
            row[T] = sweep(d, s, T)
        out.append(row)
    return out

rows, t0, n = [], time.time(), 0
LOT = 60
for k in range(0, len(groups), LOT):
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fu in as_completed([ex.submit(work, it) for it in groups[k:k+LOT]]):
            n += 1; rows.extend(fu.result())
    if k % (LOT*4) == 0:
        print(f"  {n}/{len(groups)} ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

d = pd.DataFrame(rows)
d.to_parquet("slippage.parquet", compression="zstd")
print(f"\n{len(d)} ignitions mesurees\n")
print("Slippage a l'entree, en bps, selon la taille de l'ordre")
print("(ordre au marche lance a la cloture de la bougie de signal)")
out = []
for T in TAILLES:
    v = d[T].dropna()
    if len(v) < 50: continue
    out.append({"taille_$": f"{T:,}", "n": len(v),
                "median_bps": round(float(v.median()), 1),
                "moyen_bps": round(float(v.mean()), 1),
                "p75_bps": round(float(v.quantile(.75)), 1),
                "p90_bps": round(float(v.quantile(.90)), 1),
                "remplissage_%": round(d[T].notna().mean()*100)})
print(pd.DataFrame(out).to_string(index=False))

print("\nPar liquidite du token (ordre de 10 000 $) :")
d["_l"] = pd.cut(d.qv_ref_1d, [0, 5e3, 2e4, 1e5, 1e9],
                 labels=["<5k$/min", "5-20k", "20-100k", ">100k"])
g2 = d.groupby("_l", observed=True)[10_000]
print(pd.DataFrame({"n": g2.size(), "median_bps": g2.median().round(1),
                    "p90_bps": g2.quantile(.9).round(1)}).to_string())
