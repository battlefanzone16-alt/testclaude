"""Mesure out-of-sample de la configuration gelee. A executer une fois.

Rien ici ne doit servir a ajuster quoi que ce soit : si le resultat deplait, la
reponse n'est pas de retoucher lab/strategie.py, c'est de recommencer un cycle
complet sur une autre idee, avec un nouveau bloc OOS jamais ouvert.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lab import backtest, data, protocole as P, strategie
from lab.costs import CoutsHL


def fenetre(sym, debut, fin, marge_mois=14):
    """Charge avec de la marge a gauche : les indicateurs ont besoin de chauffer."""
    d0 = (pd.Timestamp(debut) - pd.DateOffset(months=marge_mois)).strftime("%Y-%m")
    px = data.load(sym, P.TIMEFRAME, d0, pd.Timestamp(fin).strftime("%Y-%m"))
    fr = data.load_funding(sym, d0, pd.Timestamp(fin).strftime("%Y-%m"))
    return px, fr


def evaluer(sym, debut, fin, **kw):
    """Signal calcule sur l'historique complet, P&L mesure sur la seule fenetre."""
    px, fr = fenetre(sym, debut, fin)
    sig = strategie.signal(px, fr)
    sous = px.loc[debut:fin]
    return backtest.lancer(sous, sig.loc[debut:fin], funding=fr, **kw)


def ic_profit_factor(trades, n=5000, seed=0):
    """Intervalle de confiance du PF par bootstrap sur les trades."""
    pnl = trades["pnl"].to_numpy()
    if len(pnl) < 5:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    tirages = rng.choice(pnl, size=(n, len(pnl)), replace=True)
    gains = np.where(tirages > 0, tirages, 0).sum(axis=1)
    pertes = -np.where(tirages < 0, tirages, 0).sum(axis=1)
    pf = np.divide(gains, pertes, out=np.full(n, np.nan), where=pertes > 0)
    return float(np.nanpercentile(pf, 5)), float(np.nanpercentile(pf, 95))


def bloc(titre, sym, debut, fin):
    print(f"\n=== {titre} : {sym} {debut} -> {fin} ===")
    res = evaluer(sym, debut, fin)
    px, fr = fenetre(sym, debut, fin)
    bh = backtest.buy_and_hold(px.loc[debut:fin], fr)
    m, mb = res.metriques, bh.metriques
    lo, hi = ic_profit_factor(res.trades)
    print(f"  strategie   : {res}")
    print(f"  buy & hold  : net {mb['rendement_net']*100:+.1f}%  Sharpe {mb['sharpe']:.2f}  "
          f"DD {mb['max_dd']*100:.0f}%")
    print(f"  PF {m['profit_factor']:.2f}  [IC 90 % bootstrap : {lo:.2f} - {hi:.2f}]  "
          f"win rate {m['win_rate']*100:.0f}%  PnL/trade {m['pnl_moyen_trade']*100:+.2f}%")
    print(f"  couts       : txn {m['cout_txn_total']*100:.1f}%  "
          f"funding {m['cout_funding_total']*100:+.1f}%")
    print("  par annee   :")
    for an, b in res.pnl.groupby(res.pnl.index.year):
        if b.abs().sum() == 0:
            continue
        pf = backtest.profit_factor(b[b != 0])
        print(f"      {an}  PF {pf:>5.2f}   net {b.sum()*100:>+7.1f}%")
    return res


if __name__ == "__main__":
    print("CONFIGURATION GELEE :", strategie.PARAMS)
    av = bloc("OOS FORWARD", P.SYMBOLE, *P.OOS_FORWARD)
    ar = bloc("OOS BACKWARD", P.SYMBOLE, *P.OOS_BACKWARD)

    print("\n=== resistance, sur l'OOS forward ===")
    print(f"  1 barre de retard : {evaluer(P.SYMBOLE, *P.OOS_FORWARD, latence=1)}")
    print(f"  couts x2          : {evaluer(P.SYMBOLE, *P.OOS_FORWARD, couts=CoutsHL(taker=0.0009, slippage=0.0004))}")
    print(f"  couts x4          : {evaluer(P.SYMBOLE, *P.OOS_FORWARD, couts=CoutsHL(taker=0.0018, slippage=0.0008))}")

    print("\n=== memes parametres, autres actifs, OOS forward ===")
    for sym in ("ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"):
        try:
            print(f"  {sym:>8} : {evaluer(sym, *P.OOS_FORWARD)}")
        except Exception as e:
            print(f"  {sym:>8} : indisponible ({type(e).__name__})")

    print(f"\n=== verdict contre le seuil ecrit d'avance (PF >= {P.PF_OOS_ACCEPTABLE}) ===")
    for nom, r in (("forward", av), ("backward", ar)):
        pf = r.metriques["profit_factor"]
        print(f"  {nom:>8} : PF {pf:.2f}  ->  {'PASSE' if pf >= P.PF_OOS_ACCEPTABLE else 'ECHOUE'}")
