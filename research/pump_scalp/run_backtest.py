"""Backtest complet : regles de sortie x contrainte de portefeuille x couts.

On materialise ce que donnent reellement les regles de scalp les plus
defendables. L'event study dit que la derive conditionnelle est nulle ; le
theoreme d'arret optionnel dit qu'alors aucune regle de sortie ne peut creer
d'esperance. Ce script verifie que le moteur le confirme, et chiffre le seuil
de cout auquel la strategie basculerait - c'est-a-dire la taille reelle du
gisement brut.
"""
from __future__ import annotations

import itertools
import numpy as np, pandas as pd
from dataclasses import replace

from simulate import ExitRules, portfolio
from simulate_vec import simulate_batch, net, RAISONS

pd.set_option("display.width", 230)

ev = pd.read_parquet("events_tail.parquet")
ev["entry_time"] = pd.to_datetime(ev["entry_time"])
z = np.load("paths_tail.npz")
O, H, L, ok = z["o"].astype("float64"), z["h"].astype("float64"), z["l"].astype("float64"), z["ok"]
print(f"{len(ev)} evenements, chemins {O.shape}")


def risk_of(ev, mode, mult):
    if mode == "sigma":
        u = ev["sigma_ref"].to_numpy() * np.sqrt(5.0)
    elif mode == "burst":
        u = ev["r_burst"].to_numpy()
    else:
        u = np.ones(len(ev))
    return np.clip(u * mult, 0.003, 0.15)


def evaluate(rules, risk, mask=None, max_concurrent=3, label=""):
    m = ok if mask is None else (ok & mask)
    idx = np.flatnonzero(m)
    ret, ebar, why = simulate_batch(O[idx], H[idx], L[idx], risk[idx], rules)
    t = pd.DataFrame({
        "symbol": ev["symbol"].to_numpy()[idx],
        "entry_time": ev["entry_time"].to_numpy()[idx],
        "hold": ebar, "brut": ret, "net": net(ret, rules),
        "raison": [RAISONS.get(w, "?") for w in why],
        "z": ev["z_burst"].to_numpy()[idx],
    }).dropna(subset=["brut"])
    t["exit_time"] = t["entry_time"] + pd.to_timedelta(t["hold"], unit="m")
    t = t.sort_values(["entry_time", "z"], ascending=[True, False]).reset_index(drop=True)
    t = t[portfolio(t, max_concurrent=max_concurrent)]

    r = t["net"].to_numpy()
    if len(r) < 50:
        return None
    mois = t.groupby(t.entry_time.dt.to_period("M"))["net"].mean() * 1e4
    eq = np.cumprod(1 + r * 0.25)          # 25% du capital par trade
    peak = np.maximum.accumulate(eq)
    return {
        "variante": label, "n": len(r), "n/j": round(len(r)/365, 1),
        "brut_bps": round(t.brut.mean()*1e4, 1),
        "net_bps": round(r.mean()*1e4, 1),
        "t": round(r.mean()/(r.std(ddof=1)/np.sqrt(len(r))), 1),
        "win%": round((r > 0).mean()*100, 1),
        "hold_med": int(t.hold.median()),
        "mois_pos": f"{int((mois>0).sum())}/{len(mois)}",
        "equity": round(float(eq[-1]), 3),
        "maxDD%": round(float(-(eq/peak - 1).min())*100, 1),
        "sortie_dominante": t.raison.value_counts().idxmax(),
    }


print("\n### Grille de regles de sortie (long, r_burst>3%, 3 positions max)")
rows = []
for mode, mult in [("sigma", 4.0), ("sigma", 8.0), ("burst", 0.5), ("burst", 1.0)]:
    risk = risk_of(ev, mode, mult)
    for hold, trail, arm in itertools.product([30, 60, 120, 240], [1.0, 2.0], [0.5, 1.5]):
        r = evaluate(ExitRules(max_hold=hold, stop_k=1.0, trail_k=trail, arm_at=arm),
                     risk, label=f"{mode}x{mult} hold{hold} trail{trail} arm{arm}")
        if r: rows.append(r)
d = pd.DataFrame(rows).sort_values("net_bps", ascending=False)
print(d.head(12).to_string(index=False))
print(f"\n  -> sur {len(d)} combinaisons : {(d.net_bps > 0).sum()} positives en net, "
      f"mediane {d.net_bps.median():.1f} bps, meilleure {d.net_bps.max():.1f} bps")
print(f"  -> en BRUT (cout zero) : {(d.brut_bps > 0).sum()}/{len(d)} positives, "
      f"mediane {d.brut_bps.median():.1f} bps")
d.to_csv("grille_sorties.csv", index=False)
