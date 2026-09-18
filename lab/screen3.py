"""Cloture du cycle 2 : la famille SUIVI de cascade passe au filtre pre-enregistre.

Le balayage fin a montre que le profit factor monte quand le nombre de trades
tombe. On mesure donc cette relation explicitement : si l'essentiel du PF
s'explique par la rarete des trades, il n'y a pas d'edge, seulement de la
variance d'echantillonnage.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from lab import backtest, cascade, protocole2 as P2, screen2
from lab.costs import CoutsHL

STRESS = CoutsHL(taker=0.00045, slippage=P2.SLIPPAGE_STRESS)


def mesurer(px, oi, fr, couts=None, **p):
    sig = cascade.signal_suivi(px, oi, **p)
    sous = px.loc[P2.IS[0]:P2.IS[1]]
    res = backtest.lancer(sous, sig.loc[P2.IS[0]:P2.IS[1]], funding=fr,
                          couts=couts or CoutsHL(), barres_par_an=288 * 365)
    m = dict(res.metriques)
    pf_t = [backtest.profit_factor(b[b != 0])
            for _, b in res.pnl.groupby(pd.Grouper(freq="QE")) if b.abs().sum() > 0]
    m["trimestres_ok"] = sum(1 for x in pf_t if x > 1.0)
    m["trimestres"] = len(pf_t)
    return m


def main():
    px, oi, fr = screen2.charge(P2.ACTIF_CONCEPTION)
    lignes = []
    combos = list(itertools.product((9, 12, 16, 20, 24), (2.5, 3.0, 3.5, 4.0),
                                    (0.003, 0.005, 0.008), (12, 24, 48)))
    for i, (k, z, chute, hor) in enumerate(combos, 1):
        p = dict(k=k, z=z, chute_oi=chute, horizon=hor, sens="short")
        m = mesurer(px, oi, fr, **p)
        s = mesurer(px, oi, fr, couts=STRESS, **p)
        lignes.append({**p, **m, "pf_stress": s["profit_factor"]})
        if i % 45 == 0:
            print(f"  ... {i}/{len(combos)}")
    df = pd.DataFrame(lignes)
    df.to_csv("lab_out/screen_is_cycle2_suivi.csv", index=False)

    print(f"\n{len(df)} configurations testees (famille suivi de cascade).\n")
    fini = df[np.isfinite(df.profit_factor)]
    rho = np.corrcoef(np.log(fini.n_trades), fini.profit_factor)[0, 1]
    print(f"correlation entre log(nombre de trades) et profit factor : {rho:+.2f}")
    print("  (negative = le PF vient de la rarete des trades, pas d'un edge)\n")
    for borne in (50, 100, 150, 200, 300):
        sous = fini[fini.n_trades >= borne]
        if len(sous):
            print(f"  au moins {borne:>3} trades : {len(sous):>3} configs, "
                  f"PF median {sous.profit_factor.median():.2f}, "
                  f"max {sous.profit_factor.max():.2f}")

    ok = df[(df.n_trades >= P2.MIN_TRADES) & (df.profit_factor >= P2.MIN_PF) &
            (df.trimestres_ok >= P2.MIN_TRIMESTRES_OK) &
            (df.pf_stress >= P2.MIN_PF_STRESS)]
    print(f"\n--- {len(ok)} configurations passent TOUS les criteres pre-enregistres ---")
    cols = ["k", "z", "chute_oi", "horizon", "profit_factor", "pf_stress",
            "rendement_net", "sharpe", "n_trades", "trimestres_ok"]
    if len(ok):
        print(ok.sort_values("profit_factor", ascending=False)[cols].to_string(index=False))
    else:
        relache = df[(df.n_trades >= P2.MIN_TRADES) & (df.profit_factor >= P2.MIN_PF)]
        print(f"\n  pour information, en ne gardant que trades >= {P2.MIN_TRADES} et "
              f"PF >= {P2.MIN_PF} ({len(relache)} configs) :")
        if len(relache):
            print(relache.sort_values("profit_factor", ascending=False)[cols]
                  .head(10).to_string(index=False))
    return df


if __name__ == "__main__":
    main()
