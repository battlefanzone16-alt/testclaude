"""Moteur de backtest vectorise, une seule convention d'execution.

Convention, unique et non negociable :
    - le signal de la barre t n'utilise que l'information disponible a cloture(t) ;
    - il est execute a l'ouverture de la barre t+1 ;
    - le P&L de l'intervalle [open(t+1), open(t+2)] revient a ce signal.

Autrement dit : rendements open-to-open, position decalee de deux barres par
rapport au signal brut. Aucune autre convention n'est admise dans ce depot :
c'est ce decalage qui separe un backtest d'une tautologie.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from lab.costs import HL, CoutsHL

HEURES_AN = 24 * 365


@dataclass
class Resultat:
    equity: pd.Series          # courbe de capital, base 1
    pnl: pd.Series             # P&L net par barre, en fraction du capital
    position: pd.Series        # position effectivement portee sur chaque barre
    trades: pd.DataFrame       # un trade = un segment de position non nulle
    metriques: dict

    def __repr__(self) -> str:
        m = self.metriques
        return (f"PF={m['profit_factor']:.2f} net={m['rendement_net']*100:+.1f}% "
                f"Sharpe={m['sharpe']:.2f} DD={m['max_dd']*100:.1f}% "
                f"trades={m['n_trades']} expo={m['exposition']*100:.0f}%")


def funding_horaire(index: pd.DatetimeIndex, taux_8h: pd.Series,
                    couts: CoutsHL = HL) -> pd.Series:
    """Taux 8 h -> cout horaire aligne sur l'index des barres.

    Le dernier taux publie vaut jusqu'au suivant ; Hyperliquid preleve 1/8 par
    heure. Un long paie quand le funding est positif.
    """
    f = taux_8h.reindex(index.union(taux_8h.index)).ffill().reindex(index)
    return f.fillna(0.0) / couts.funding_par_heure


def lancer(df: pd.DataFrame, signal: pd.Series, *,
           funding: pd.Series | None = None,
           couts: CoutsHL = HL,
           latence: int = 0,
           barres_par_an: int = HEURES_AN) -> Resultat:
    """Applique un signal a une serie OHLCV et renvoie P&L net et metriques.

    signal  : position voulue, en fraction du capital, indexee comme df,
              calculee avec la seule information de cloture de la barre.
    latence : barres d'attente supplementaires avant execution. 0 = on entre a
              la premiere ouverture qui suit la cloture du signal. Passer a 1
              est le test de robustesse : une strategie qui meurt avec une barre
              de retard vit d'un artefact de synchronisation, pas d'un edge.
    """
    if not signal.index.equals(df.index):
        raise ValueError("signal et prix doivent partager exactement le meme index")

    open_ = df["open"].astype(float)
    # rendement de l'intervalle qui commence a open(t) et finit a open(t+1)
    r = open_.shift(-1) / open_ - 1.0

    # signal(t) connu a cloture(t) ~= open(t+1) -> porte sur [open(t+1), open(t+2)]
    pos = signal.shift(1 + latence).fillna(0.0)

    # le changement de position a lieu a l'ouverture du segment que pos couvre
    trade = (pos - pos.shift(1).fillna(0.0)).abs()
    cout_txn = trade * couts.par_cote

    if funding is not None:
        fh = funding_horaire(df.index, funding, couts)
        # duree d'une barre en heures : le funding est proportionnel au temps porte
        heures = df.index.to_series().diff().dt.total_seconds().div(3600).fillna(1.0)
        cout_fund = pos * fh * heures          # un long paie si fh > 0
    else:
        cout_fund = pd.Series(0.0, index=df.index)

    brut = (pos * r).fillna(0.0)
    pnl = (brut - cout_txn - cout_fund).fillna(0.0)
    equity = (1.0 + pnl).cumprod()

    trades = _ledger(pos, pnl, df.index)
    m = _metriques(pnl, equity, pos, trades, cout_txn, cout_fund, barres_par_an)
    return Resultat(equity=equity, pnl=pnl, position=pos, trades=trades, metriques=m)


def _ledger(pos: pd.Series, pnl: pd.Series, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Decoupe le P&L en trades : segments contigus de position de meme signe."""
    sign = np.sign(pos.to_numpy())
    changed = np.r_[True, sign[1:] != sign[:-1]]
    seg_id = changed.cumsum()
    g = pd.DataFrame({"seg": seg_id, "sign": sign, "pnl": pnl.to_numpy()}, index=index)
    g = g[g["sign"] != 0]
    if g.empty:
        return pd.DataFrame(columns=["debut", "fin", "sens", "barres", "pnl"])
    agg = g.groupby("seg").agg(debut=("pnl", lambda s: s.index[0]),
                               fin=("pnl", lambda s: s.index[-1]),
                               sens=("sign", "first"),
                               barres=("pnl", "size"),
                               pnl=("pnl", "sum"))
    return agg.reset_index(drop=True)


def profit_factor(pnl_trades: pd.Series) -> float:
    gains = pnl_trades[pnl_trades > 0].sum()
    pertes = -pnl_trades[pnl_trades < 0].sum()
    if pertes == 0:
        return float("inf") if gains > 0 else float("nan")
    return float(gains / pertes)


def _metriques(pnl, equity, pos, trades, cout_txn, cout_fund, bpa) -> dict:
    n = len(pnl)
    sigma = pnl.std()
    dd = equity / equity.cummax() - 1.0
    tpnl = trades["pnl"] if len(trades) else pd.Series(dtype=float)
    ans = n / bpa
    return {
        "profit_factor": profit_factor(tpnl) if len(tpnl) else float("nan"),
        "pf_barres": profit_factor(pnl[pnl != 0]),
        "rendement_net": float(equity.iloc[-1] - 1.0),
        "cagr": float(equity.iloc[-1] ** (1 / ans) - 1.0) if ans > 0 and equity.iloc[-1] > 0 else float("nan"),
        "sharpe": float(pnl.mean() / sigma * np.sqrt(bpa)) if sigma > 0 else 0.0,
        "max_dd": float(dd.min()),
        "n_trades": int(len(trades)),
        "win_rate": float((tpnl > 0).mean()) if len(tpnl) else float("nan"),
        "pnl_moyen_trade": float(tpnl.mean()) if len(tpnl) else float("nan"),
        "exposition": float((pos != 0).mean()),
        "cout_txn_total": float(cout_txn.sum()),
        "cout_funding_total": float(cout_fund.sum()),
        "barres": n,
    }


def buy_and_hold(df: pd.DataFrame, funding: pd.Series | None = None,
                 couts: CoutsHL = HL) -> Resultat:
    return lancer(df, pd.Series(1.0, index=df.index), funding=funding, couts=couts)
