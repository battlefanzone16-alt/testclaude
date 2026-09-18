"""Verdict sur la rotation de value area, sur quatre actifs et deux periodes.

L'ensemble n'ayant aucun parametre libre, il n'y a rien a geler et rien a
consommer : chaque mesure est un test d'hypothese, pas une selection. On peut
donc regarder partout sans biaiser quoi que ce soit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lab import backtest, data, ensemble_va as E
from lab.costs import CoutsHL

ACTIFS = ("BTCUSDT", "AVAXUSDT", "LINKUSDT", "DOGEUSDT")
PERIODES = {"bear 2022 - mi 2023": ("2022-01-01", "2023-06-30"),
            "mi 2023 - aout 2026": ("2023-07-01", "2026-08-31")}
STRESS = CoutsHL(taker=0.00045, slippage=0.0010)


def mesure(barres, sig, fr, fen, couts=None, ban=24 * 365):
    sous = barres.loc[fen[0]:fen[1]]
    if len(sous) < 500:
        return None
    res = backtest.lancer(sous, sig.loc[fen[0]:fen[1]], funding=fr,
                          couts=couts or CoutsHL(), barres_par_an=ban)
    return res


def ligne(nom, res, sig_fen):
    m = res.metriques
    return (f"  {nom:<22} PF {m['profit_factor']:>5.2f}  net {m['rendement_net']*100:>+7.1f}%  "
            f"Sharpe {m['sharpe']:>5.2f}  DD {m['max_dd']*100:>4.0f}%  "
            f"expo {sig_fen.abs().mean()*100:>4.1f}%")


if __name__ == "__main__":
    total = {}
    for sym in ACTIFS:
        print(f"\n########## {sym} ##########")
        h1 = data.load(sym, "1h", "2021-10", "2026-08")
        m5 = data.load(sym, "5m", "2021-10", "2026-08")
        fr = data.load_funding(sym, "2021-10", "2026-08")
        cache = {}
        sl = E.signal(h1, m5, sens="long", cache=cache)
        ss = E.signal(h1, m5, sens="short", cache=cache)
        for nom, fen in PERIODES.items():
            print(f"\n  --- {nom} ---")
            for etiq, sig in (("long", sl), ("short", ss), ("long + short", sl + ss)):
                res = mesure(h1, sig, fr, fen)
                if res is None:
                    print(f"  {etiq:<22} donnee insuffisante")
                    continue
                print(ligne(etiq, res, sig.loc[fen[0]:fen[1]]))
                total.setdefault((nom, etiq), []).append(res.metriques["profit_factor"])
            res_s = mesure(h1, sl + ss, fr, fen, couts=STRESS)
            if res_s is not None:
                print(f"  {'(slippage 10 bps)':<22} PF {res_s.metriques['profit_factor']:>5.2f}")

    print("\n\n########## SYNTHESE : profit factor median sur les 4 actifs ##########")
    for (nom, etiq), pfs in sorted(total.items()):
        pfs = [p for p in pfs if np.isfinite(p)]
        print(f"  {nom:<22} {etiq:<14} median {np.median(pfs):.2f}   "
              f"({', '.join(f'{p:.2f}' for p in pfs)})")
