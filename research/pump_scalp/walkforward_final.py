"""Walk-forward sur 24 mois, avec et sans open interest.

C'est le test qui tranche. Deux periodes independamment constituees (univers
screene sur chaque periode separement, pas d'univers 2026 applique a 2024), un
walk-forward glissant, et la comparaison de la MEME procedure avec et sans les
features d'open interest.

Le chiffre qui compte n'est pas la performance de la meilleure regle : c'est
celle de la procedure, selection comprise. Et la comparaison avec/sans OI
isole l'apport propre de l'information nouvelle.
"""
from __future__ import annotations

import itertools, sys
import numpy as np, pandas as pd
from evaluate2 import episodes

COST = 0.0019
HZ = ["fwd_60", "fwd_120", "fwd_240"]


def load():
    a = pd.read_parquet("events_micro.parquet")
    b = pd.read_parquet("events_micro_hist.parquet")
    for d in (a, b):
        d["entry_time"] = pd.to_datetime(d["entry_time"])
    ev = pd.concat([b, a], ignore_index=True).sort_values("entry_time")
    ev["mois"] = ev.entry_time.dt.to_period("M")
    return ev.reset_index(drop=True)


def library(ev, avec_oi: bool):
    """Bibliotheque de regles. Seuils ronds, jamais optimises."""
    lib = {}
    sess = {"tout": None, "euro": (7, 13), "us": (13, 21)}
    ois = [-9.0, 0.005, 0.01, 0.02] if avec_oi else [-9.0]
    for rb, br, zt, oi, (sn, sv) in itertools.product(
            [0.03, 0.05], [1.0, 0.01], [3, 4], ois, sess.items()):
        m = (ev.r_burst > rb) & (ev.breadth_z2 < br) & (ev.z_burst > zt)
        if oi > -9:
            m &= ev.oi_chg_5m > oi
        if sv:
            m &= ev.entry_time.dt.hour.between(*sv)
        lib[f"rb{rb}_br{br}_z{zt}_oi{oi}_{sn}"] = m.to_numpy()
    return lib


def ep_series(ev, mask, col, mmask):
    d = ev[mask & mmask].dropna(subset=[col])
    if len(d) < 5:
        return np.array([])
    return d.assign(_ep=episodes(d.entry_time)).groupby("_ep")[col].mean().to_numpy()


def walk(ev, lib, train_m, min_ep, critere):
    mois = sorted(ev.mois.unique())
    out = []
    for i in range(train_m, len(mois)):
        tm = mois[i]
        tr = ev.mois.isin(mois[i - train_m:i]).to_numpy()
        te = (ev.mois == tm).to_numpy()
        best, score, bm = None, -np.inf, np.nan
        for name, m in lib.items():
            for h in HZ:
                r = ep_series(ev, m, h, tr)
                if len(r) < min_ep:
                    continue
                se = r.std(ddof=1) / np.sqrt(len(r))
                s = (r.mean() if critere == "moyenne"
                     else r.mean() / se if critere == "t"
                     else r.mean() - 1.5 * se)
                if s > score:
                    best, score, bm = (name, h), s, r.mean()
        if best is None:
            continue
        r = ep_series(ev, lib[best[0]], best[1], te)
        out.append({"mois": str(tm), "regle": f"{best[0]} {best[1]}",
                    "IS_bps": round(bm * 1e4, 1), "n_ep": len(r),
                    "OOS_net_bps": round((r.mean() - COST) * 1e4, 1) if len(r) else np.nan})
    return pd.DataFrame(out)


def main():
    ev = load()
    print(f"{len(ev)} evenements, {ev.entry_time.min():%Y-%m} -> {ev.entry_time.max():%Y-%m} "
          f"({ev.mois.nunique()} mois)", file=sys.stderr)
    print(f"couverture open interest : {ev.oi_chg_5m.notna().mean()*100:.0f} % "
          f"(sur r_burst>3% : {ev.loc[ev.r_burst>0.03,'oi_chg_5m'].notna().mean()*100:.0f} %)",
          file=sys.stderr)

    rows, det = [], {}
    for avec in (False, True):
        lib = library(ev, avec)
        for tm, me, cr in [(6, 100, "t"), (6, 150, "t"), (6, 150, "prudent"),
                           (6, 300, "prudent"), (9, 150, "t")]:
            d = walk(ev, lib, tm, me, cr)
            v = d.OOS_net_bps.dropna()
            lab = f"{'AVEC OI ' if avec else 'sans OI '}| {cr}, {me} ep, train {tm}m"
            rows.append({"procedure": lab, "mois_testes": len(v),
                         "OOS_moy_bps": round(v.mean(), 1),
                         "OOS_med_bps": round(v.median(), 1),
                         "mois_pos": f"{int((v>0).sum())}/{len(v)}",
                         "IS_moy_bps": round(d.IS_bps.mean(), 1),
                         "ecart_IS_OOS": round(d.IS_bps.mean() - v.mean(), 1)})
            det[lab] = d
    r = pd.DataFrame(rows)
    print("\n=== WALK-FORWARD SUR 24 MOIS : la procedure, selection comprise ===")
    print(r.to_string(index=False))
    a = r[r.procedure.str.startswith("AVEC")].OOS_moy_bps
    s = r[r.procedure.str.startswith("sans")].OOS_moy_bps
    print(f"\nmoyenne des procedures AVEC open interest : {a.mean():+.1f} bps "
          f"({(a>0).sum()}/{len(a)} positives)")
    print(f"moyenne des procedures SANS open interest : {s.mean():+.1f} bps "
          f"({(s>0).sum()}/{len(s)} positives)")
    best = r.loc[r.OOS_moy_bps.idxmax(), "procedure"]
    print(f"\n--- detail : {best} ---")
    print(det[best].to_string(index=False))
    r.to_csv("walkforward_final.csv", index=False)
    for k, d in det.items():
        d.to_csv(f"wf_{k.split('|')[0].strip().replace(' ','_')}_{abs(hash(k))%1000}.csv", index=False)


if __name__ == "__main__":
    main()
