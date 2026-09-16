"""Walk-forward sur la PROCEDURE, pas sur une regle choisie apres coup.

Le probleme a resoudre. J'ai teste beaucoup de filtres, et j'ai fini par en
trouver un qui a un OOS positif. Mais quand on essaie 400 regles, la meilleure
a un bon OOS par construction - c'est le meme piege que le Deflated Sharpe
traite pour les Sharpe.

La seule reponse honnete : simuler ce qu'on aurait REELLEMENT fait. Chaque mois,
on choisit la meilleure regle sur les 6 mois precedents seulement, et on la
joue le mois suivant sans la changer. Le resultat agrege de ces mois est la
performance de la methode, selection comprise. Si elle est nulle, c'est que
mes belles regles etaient des artefacts de recherche.
"""
from __future__ import annotations

import itertools, sys
import numpy as np, pandas as pd
from evaluate2 import episodes

COST = 0.0019
TRAIN_M = 6
MIN_EP_TRAIN = 40


def build_library(ev):
    """Bibliotheque de regles, definie une fois, sans regarder les resultats."""
    lib = {}
    sess = {"tout": slice(None), "asie": (0, 7), "euro": (7, 13), "us": (13, 21)}
    for rb, br, zt, ext, (sn, sv) in itertools.product(
            [0.03, 0.05], [1.0, 0.02, 0.01], [3, 4, 6], [1.0, 0.03], sess.items()):
        m = (ev.r_burst > rb) & (ev.breadth_z2 < br) & (ev.z_burst > zt) & (ev.r_60m < ext)
        if sv != slice(None):
            m &= ev.entry_time.dt.hour.between(*sv)
        lib[f"rb{rb}_br{br}_z{zt}_ext{ext}_{sn}"] = m.to_numpy()
    return lib


def ep_mean(ev, mask, col, months_mask):
    d = ev[mask & months_mask]
    d = d.dropna(subset=[col])
    if len(d) < 5:
        return np.nan, 0
    e = d.assign(_ep=episodes(d.entry_time)).groupby("_ep")[col].mean()
    return float(e.mean()), len(e)


def main():
    ev = pd.read_parquet("events_breadth.parquet")
    ev["entry_time"] = pd.to_datetime(ev["entry_time"])
    ev["mois"] = ev.entry_time.dt.to_period("M")
    lib = build_library(ev)
    print(f"{len(lib)} regles dans la bibliotheque x 3 horizons = "
          f"{len(lib)*3} candidats evalues chaque mois", file=sys.stderr)

    mois = sorted(ev.mois.unique())
    horizons = ["fwd_60", "fwd_120", "fwd_240"]
    res = []
    for i in range(TRAIN_M, len(mois)):
        test_m = mois[i]
        train = ev.mois.isin(mois[i - TRAIN_M:i]).to_numpy()
        test = (ev.mois == test_m).to_numpy()

        best, best_score = None, -np.inf
        for name, m in lib.items():
            for h in horizons:
                s, n = ep_mean(ev, m, h, train)
                if n >= MIN_EP_TRAIN and np.isfinite(s) and s > best_score:
                    best, best_score = (name, h), s
        if best is None:
            continue
        name, h = best
        oos, n_oos = ep_mean(ev, lib[name], h, test)
        res.append({"mois": str(test_m), "regle_choisie": name, "horizon": h,
                    "IS_train_bps": round(best_score*1e4, 1),
                    "n_ep_test": n_oos,
                    "OOS_bps": round(oos*1e4, 1) if np.isfinite(oos) else np.nan,
                    "OOS_net_bps": round((oos-COST)*1e4, 1) if np.isfinite(oos) else np.nan})
    d = pd.DataFrame(res)
    print("\n=== Ce que la methode aurait reellement rapporte, mois par mois ===")
    print(d.to_string(index=False))
    v = d.OOS_net_bps.dropna()
    print(f"\nmoyenne OOS nette : {v.mean():+.1f} bps par episode")
    print(f"mois positifs : {(v>0).sum()}/{len(v)}")
    print(f"mediane : {v.median():+.1f} bps")
    print(f"\nA comparer avec l'IS moyen selectionne : {d.IS_train_bps.mean():+.1f} bps.")
    print("L'ecart entre les deux EST la prime de surapprentissage de la recherche.")
    d.to_csv("walkforward.csv", index=False)


if __name__ == "__main__":
    main()
