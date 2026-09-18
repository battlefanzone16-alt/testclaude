"""Tests du moteur. Ils protegent contre les trois facons de se mentir :
anticipation, couts oublies, P&L qui ne se referme pas sur la courbe de capital.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lab import backtest
from lab.costs import CoutsHL

SANS_COUT = CoutsHL(taker=0.0, slippage=0.0)


def _px(n=200, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame({"open": close, "high": close * 1.002,
                         "low": close * 0.998, "close": close,
                         "volume": 1.0}, index=idx)


def test_pas_anticipation():
    """Un signal qui connait le futur ne doit PAS etre rentable une fois decale.

    On construit le signal parfait sur la barre courante : s'il restait aligne,
    le moteur afficherait un P&L delirant. Decale d'une barre, il ne doit plus
    battre le hasard de facon suspecte.
    """
    df = _px()
    r_futur = df["open"].shift(-1) / df["open"] - 1
    oracle = pd.Series(np.sign(r_futur).fillna(0.0), index=df.index)
    res = backtest.lancer(df, oracle, couts=SANS_COUT)
    aligne = (oracle * r_futur).sum()   # ce que verrait un moteur qui n'attend pas
    assert aligne > 0.5, "test mal construit : l'oracle devrait exploser"
    assert res.pnl.sum() < 0.05 * aligne, "le moteur laisse fuir de l'information"


def test_execution_ouverture_suivante():
    """Position portee sur [open(t+1), open(t+2)] quand le signal nait en t."""
    df = _px(10)
    sig = pd.Series(0.0, index=df.index)
    sig.iloc[3] = 1.0
    res = backtest.lancer(df, sig, couts=SANS_COUT)
    assert res.position.iloc[4] == 1.0 and res.position.iloc[3] == 0.0
    attendu = df["open"].iloc[5] / df["open"].iloc[4] - 1
    assert abs(res.pnl.iloc[4] - attendu) < 1e-12


def test_couts_factures_aux_deux_bouts():
    df = _px(50)
    sig = pd.Series(0.0, index=df.index)
    sig.iloc[10:20] = 1.0
    couts = CoutsHL(taker=0.0004, slippage=0.0001)
    res = backtest.lancer(df, sig, couts=couts)
    assert abs(res.metriques["cout_txn_total"] - couts.aller_retour) < 1e-12


def test_funding_paye_par_le_long():
    df = _px(30)
    taux = pd.Series(0.0008, index=df.index[::8])      # 0.08 % par 8 h
    long_ = backtest.lancer(df, pd.Series(1.0, index=df.index),
                            funding=taux, couts=SANS_COUT)
    short = backtest.lancer(df, pd.Series(-1.0, index=df.index),
                            funding=taux, couts=SANS_COUT)
    assert long_.metriques["cout_funding_total"] > 0
    assert short.metriques["cout_funding_total"] < 0
    heures = long_.metriques["exposition"] * len(df)
    assert abs(long_.metriques["cout_funding_total"] - 0.0008 / 8 * heures) < 1e-9


def test_equity_coherente_avec_pnl():
    df = _px(120)
    sig = pd.Series(np.where(np.arange(120) % 7 < 3, 1.0, -1.0), index=df.index)
    res = backtest.lancer(df, sig)
    assert abs(res.equity.iloc[-1] - (1 + res.pnl).prod()) < 1e-12


def test_profit_factor():
    pnl = pd.Series([0.03, -0.01, 0.02, -0.04])
    assert abs(backtest.profit_factor(pnl) - 1.0) < 1e-12


if __name__ == "__main__":
    for nom, fn in sorted(globals().items()):
        if nom.startswith("test_"):
            fn()
            print(f"ok  {nom}")
