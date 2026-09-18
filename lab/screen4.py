"""Balayage de la rotation de value area sur l'actif de conception."""
from __future__ import annotations

import itertools

import pandas as pd

from lab import backtest, data, protocole3 as P3, strategie_va as va, volume_profile as vp
from lab.costs import CoutsHL

STRESS = CoutsHL(taker=0.00045, slippage=P3.SLIPPAGE_STRESS)
MARGE = "2021-10"


def charge(sym, fin="2023-06"):
    h1 = data.load(sym, "1h", MARGE, fin)
    m5 = data.load(sym, "5m", MARGE, fin)
    fr = data.load_funding(sym, MARGE, fin)
    return h1, m5, fr


def profils(h1, m5, tf, lookback_jours, n_bins=60):
    """Niveaux calcules une fois par (timeframe, lookback) : c'est le seul cout lourd."""
    barres = h1 if tf == "1h" else h1.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    niv = vp.niveaux(barres.index, m5, lookback=pd.Timedelta(days=lookback_jours),
                     n_bins=n_bins)
    return barres, niv


def mesurer(barres, niv, fr, fenetre, couts=None, barres_an=24 * 365, **p):
    sig = va.signal(barres, niv, **p)
    sous = barres.loc[fenetre[0]:fenetre[1]]
    res = backtest.lancer(sous, sig.loc[fenetre[0]:fenetre[1]], funding=fr,
                          couts=couts or CoutsHL(), barres_par_an=barres_an)
    m = dict(res.metriques)
    pf_t = [backtest.profit_factor(b[b != 0])
            for _, b in res.pnl.groupby(pd.Grouper(freq="QE")) if b.abs().sum() > 0]
    m["trimestres_ok"] = sum(1 for x in pf_t if x > 1.0)
    return m


if __name__ == "__main__":
    h1, m5, fr = charge(P3.ACTIF_CONCEPTION)
    lignes = []
    for tf, lb in itertools.product(("1h", "4h"), (3, 5, 10, 20, 30)):
        barres, niv = profils(h1, m5, tf, lb)
        ban = 24 * 365 if tf == "1h" else 6 * 365
        mult = 1 if tf == "1h" else 4
        for n_b, stop, maxb, sens in itertools.product(
                (1, 2, 3), ("val", "extreme"), (24, 72, 240), ("long", "short")):
            p = dict(n_bougies=n_b, stop=stop, max_barres=max(2, maxb // mult), sens=sens)
            m = mesurer(barres, niv, fr, P3.IS, barres_an=ban, **p)
            s = mesurer(barres, niv, fr, P3.IS, couts=STRESS, barres_an=ban, **p)
            lignes.append({"tf": tf, "lookback": lb, **p, **m,
                           "pf_stress": s["profit_factor"]})
        print(f"  ... {tf} lookback {lb}j fait")
    df = pd.DataFrame(lignes)
    df.to_csv("lab_out/screen_is_cycle3.csv", index=False)
    print(f"\n{len(df)} configurations testees.\n")

    pd.set_option("display.width", 240)
    cols = ["tf", "lookback", "n_bougies", "stop", "max_barres", "sens",
            "profit_factor", "pf_stress", "rendement_net", "sharpe", "max_dd",
            "n_trades", "trimestres_ok"]
    print("--- PF median par (sens, timeframe, lookback) ---")
    print(df.pivot_table(index=["sens", "tf"], columns="lookback",
                         values="profit_factor", aggfunc="median").round(2).to_string())
    ok = df[(df.n_trades >= P3.MIN_TRADES) & (df.profit_factor >= P3.MIN_PF) &
            (df.trimestres_ok >= P3.MIN_TRIMESTRES_OK) & (df.pf_stress >= P3.MIN_PF_STRESS)]
    print(f"\n--- {len(ok)} configurations passent tous les criteres pre-enregistres ---")
    if len(ok):
        print(ok.sort_values("profit_factor", ascending=False)[cols].head(25).to_string(index=False))
