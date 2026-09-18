"""Screen in-sample du cycle 2, sur l'actif de conception uniquement."""
from __future__ import annotations

import itertools

import pandas as pd

from lab import backtest, cascade, data, protocole2 as P2
from lab.costs import CoutsHL

BARRES_AN = 288 * 365
STRESS = CoutsHL(taker=0.00045, slippage=P2.SLIPPAGE_STRESS)


def charge(sym, debut_marge="2021-11", fin="2023-06"):
    px = data.load(sym, P2.TIMEFRAME, debut_marge, fin)
    oi = data.load_metrics(sym, debut_marge, fin)["sum_open_interest"]
    fr = data.load_funding(sym, debut_marge, fin)
    return px, oi, fr


def mesurer(px, oi, fr, fenetre, couts=None, **params) -> dict:
    sig = cascade.signal(px, oi, **params)
    sous = px.loc[fenetre[0]:fenetre[1]]
    res = backtest.lancer(sous, sig.loc[fenetre[0]:fenetre[1]], funding=fr,
                          couts=couts or CoutsHL(), barres_par_an=BARRES_AN)
    m = dict(res.metriques)
    pf_trim = []
    for _, bloc in res.pnl.groupby(pd.Grouper(freq="QE")):
        if bloc.abs().sum() == 0:
            continue
        pf_trim.append(backtest.profit_factor(bloc[bloc != 0]))
    m["trimestres"] = len(pf_trim)
    m["trimestres_ok"] = sum(1 for x in pf_trim if x > 1.0)
    m["_res"] = res
    return m


def grille():
    for k, z, chute, horizon, sens in itertools.product(
            (6, 12, 24), (2.5, 3.5, 4.5), (0.0, 0.003, 0.008), (12, 24, 48),
            ("long", "short")):
        yield {"k": k, "z": z, "chute_oi": chute, "horizon": horizon, "sens": sens}


if __name__ == "__main__":
    px, oi, fr = charge(P2.ACTIF_CONCEPTION)
    bh = backtest.lancer(px.loc[P2.IS[0]:P2.IS[1]],
                         pd.Series(1.0, index=px.loc[P2.IS[0]:P2.IS[1]].index),
                         funding=fr, barres_par_an=BARRES_AN)
    print(f"IS {P2.IS[0]} -> {P2.IS[1]} sur {P2.ACTIF_CONCEPTION} {P2.TIMEFRAME} | "
          f"{len(px.loc[P2.IS[0]:P2.IS[1]])} barres | "
          f"buy & hold {bh.metriques['rendement_net']*100:+.1f}%\n")

    lignes = []
    configs = list(grille())
    for i, p in enumerate(configs, 1):
        m = mesurer(px, oi, fr, P2.IS, **p)
        m.pop("_res")
        lignes.append({**p, **m})
        if i % 40 == 0:
            print(f"  ... {i}/{len(configs)}")
    df = pd.DataFrame(lignes)
    df.to_csv("lab_out/screen_is_cycle2.csv", index=False)
    print(f"\n{len(df)} configurations testees.\n")

    pd.set_option("display.width", 220)
    cols = ["k", "z", "chute_oi", "horizon", "sens", "profit_factor", "rendement_net",
            "sharpe", "max_dd", "n_trades", "exposition", "trimestres_ok"]
    ok = df[(df.n_trades >= P2.MIN_TRADES) & (df.profit_factor >= P2.MIN_PF) &
            (df.trimestres_ok >= P2.MIN_TRIMESTRES_OK)]
    print(f"--- {len(ok)} configurations passent les criteres pre-enregistres ---")
    print(ok.sort_values("profit_factor", ascending=False)[cols].head(20).to_string(index=False))

    print("\n--- effet du filtre open interest, a autres parametres egaux (sens=long) ---")
    lo = df[df.sens == "long"]
    print(lo.pivot_table(index=["k", "horizon"], columns="chute_oi",
                         values="profit_factor").round(3).to_string())
    print("\n--- idem, sens=short ---")
    sh = df[df.sens == "short"]
    print(sh.pivot_table(index=["k", "horizon"], columns="chute_oi",
                         values="profit_factor").round(3).to_string())
