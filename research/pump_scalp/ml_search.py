"""Dernier test : laisser un modele chercher l'edge a ma place.

Mes tranches precedentes sont faites a la main : elles explorent mal l'espace et
leurs t-stats sont biaises par le nombre d'essais. On inverse la charge de la
preuve. Un gradient boosting est entraine sur la PREMIERE moitie de la periode a
predire le rendement forward a partir de toutes les features d'ignition, puis on
regarde ce que valent ses predictions sur la SECONDE moitie, jamais vue.

Si un modele non lineaire, libre de combiner 17 features, ne produit pas un
decile superieur rentable hors echantillon, alors l'edge conditionnel n'existe
pas dans cet espace de features - et ce n'est plus une question d'intuition.
"""
from __future__ import annotations

import sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
pd.set_option("display.width", 200)

FEATS = ["z_burst", "r_burst", "vol_mult", "taker_ratio", "r_btc", "break60",
         "r_60m", "r_240m", "qv_ref_1d", "trades_burst", "sigma_ref",
         "bar_dom", "up_frac", "vol_persist", "break240", "dist_hh1d", "r_1d"]
SPLIT = "2026-03-01"
COST = 0.0019


def run(path, target="fwd_60"):
    ev = pd.read_parquet(path)
    ev["entry_time"] = pd.to_datetime(ev["entry_time"])
    feats = [f for f in FEATS if f in ev.columns]
    d = ev.dropna(subset=feats + [target])
    tr = d[d.entry_time < SPLIT]
    te = d[d.entry_time >= SPLIT]
    print(f"\n{'='*80}\n{path} / {target}  |  IS {len(tr)}  OOS {len(te)}  ({len(feats)} features)")

    m = HistGradientBoostingRegressor(
        max_iter=300, max_depth=4, learning_rate=0.05,
        min_samples_leaf=200, l2_regularization=1.0, random_state=0)
    m.fit(tr[feats].to_numpy(), tr[target].to_numpy())

    for lab, s in (("IS (vu a l'entrainement)", tr), ("OOS (jamais vu)", te)):
        p = m.predict(s[feats].to_numpy())
        q = pd.qcut(p, 10, labels=False, duplicates="drop")
        g = pd.DataFrame({"pred": p, "reel": s[target].to_numpy(), "d": q}).groupby("d")
        t = pd.DataFrame({"n": g.size(),
                          "pred_bps": (g.pred.mean()*1e4).round(1),
                          "reel_bps": (g.reel.mean()*1e4).round(1),
                          "t": (g.reel.mean()/(g.reel.std()/np.sqrt(g.size()))).round(1)})
        print(f"\n-- {lab} : rendement reel par decile de prediction --")
        print(t.to_string())
        top = t.iloc[-1]
        print(f"   decile superieur : {top.reel_bps:.1f} bps brut, "
              f"{top.reel_bps - COST*1e4:.1f} bps net")
        # correlation rang : le modele ordonne-t-il quoi que ce soit ?
        print(f"   correlation de rang pred/reel : "
              f"{pd.Series(p).corr(pd.Series(s[target].to_numpy()), method='spearman'):.4f}")


if __name__ == "__main__":
    for path in ("events_k5_btc.parquet", "events_k30.parquet"):
        for tgt in ("fwd_30", "fwd_60"):
            try:
                run(path, tgt)
            except Exception as e:
                print(f"{path}/{tgt}: {e}")
