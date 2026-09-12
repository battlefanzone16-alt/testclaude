"""Signaux TRANSVERSAUX sur le top 40 : on classe les tokens entre eux.

Le diagnostic préalable (ratio de variance de Lo-MacKinlay sur 2022-2026)
justifie ce changement d'angle :
    - le marché lui-même est une marche aléatoire (VR 1,00 à 1,04) ;
    - la composante transversale revient à la moyenne, de plus en plus loin
      qu'on regarde (VR 0,98 à 8 h, 0,93 à 2 j, 0,87 à 30 j).
Chercher un edge directionnel était donc chercher au mauvais endroit.

Chaque signal renvoie un SCORE par token et par barre (plus haut = plus acheté),
strictement causal. `to_weights` en fait un portefeuille neutre en dollars.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def to_weights(score: pd.DataFrame, mask: pd.DataFrame, mode="rank",
               decile=0.2) -> pd.DataFrame:
    """Score -> poids neutres en dollars, brut normalisé à 1.

    mode="rank"   : pondération par le rang centré (utilise toute la section)
    mode="decile" : long le décile haut, short le décile bas (Jegadeesh-Titman)
    """
    s = score.where(mask)
    if mode == "decile":
        q = s.rank(axis=1, pct=True)
        w = pd.DataFrame(0.0, index=s.index, columns=s.columns)
        w = w.mask(q >= 1 - decile, 1.0).mask(q <= decile, -1.0).where(s.notna(), 0.0)
    else:
        q = s.rank(axis=1, pct=True)
        w = (q - 0.5).where(s.notna(), 0.0)
    w = w.sub(w.mean(axis=1).where(w.abs().sum(axis=1) > 0, 0.0), axis=0).where(s.notna(), 0.0)
    g = w.abs().sum(axis=1)
    return w.div(g.replace(0.0, np.nan), axis=0).fillna(0.0)


# ───────────────────────── retour à la moyenne / momentum ─────────────────────
def rev(px, n):      return -np.log(px).diff(n)                 # contrarian
def mom(px, n):      return np.log(px).diff(n)                  # momentum
def mom_skip(px, n, skip):                                       # JT : on saute le récent
    lp = np.log(px); return lp.shift(skip) - lp.shift(n)
def vol_adj_mom(px, n, w=90):
    v = np.log(px).diff().rolling(w, min_periods=w // 2).std()
    return np.log(px).diff(n) / v.replace(0.0, np.nan)


# ───────────────────────── volatilité / risque ────────────────────────────────
def lowvol(px, w=90):
    return -np.log(px).diff().rolling(w, min_periods=w // 2).std()

def idio_vol(px, mkt, w=90):
    """Volatilité résiduelle après retrait du marché (Ang et al.)."""
    r = np.log(px).diff()
    x = r.sub(mkt, axis=0)
    return -x.rolling(w, min_periods=w // 2).std()

def beta_mkt(px, mkt, w=90):
    r = np.log(px).diff()
    cov = r.rolling(w, min_periods=w // 2).cov(mkt)
    return cov.div(mkt.rolling(w, min_periods=w // 2).var(), axis=0)

def bab(px, mkt, w=90):                                          # Frazzini-Pedersen
    return -beta_mkt(px, mkt, w)

def maxret(px, w=30):                                            # effet loterie, Bali et al.
    return -np.log(px).diff().rolling(w, min_periods=w // 2).max()

def idio_skew(px, mkt, w=180):
    x = np.log(px).diff().sub(mkt, axis=0)
    return -x.rolling(w, min_periods=w // 2).skew()

def vol_of_vol(px, w=90, s=30):
    v = np.log(px).diff().rolling(s, min_periods=s // 2).std()
    return -v.rolling(w, min_periods=w // 2).std()


# ───────────────────────── liquidité / taille ─────────────────────────────────
def size(px, vol, w=90):
    return -(px * vol).rolling(w, min_periods=w // 2).median()

def amihud(px, vol, w=90):                                       # illiquidité
    il = np.log(px).diff().abs() / (px * vol).replace(0.0, np.nan)
    return il.rolling(w, min_periods=w // 2).median()

def volume_shock(px, vol, s=6, w=180):
    dv = (px * vol)
    return -(dv.rolling(s, min_periods=s).mean() /
             dv.rolling(w, min_periods=w // 2).median().replace(0.0, np.nan))


# ───────────────────────── position dans la fourchette ────────────────────────
def range_pos(px, hi, lo, w=180):                                # 52-week high, George-Hwang
    h = hi.rolling(w, min_periods=w // 2).max()
    l = lo.rolling(w, min_periods=w // 2).min()
    return (px - l) / (h - l).replace(0.0, np.nan)

def dist_high(px, hi, w=180):
    return px / hi.rolling(w, min_periods=w // 2).max().replace(0.0, np.nan)


# ───────────────────────── flux / financement (perps) ─────────────────────────
def taker_imb(taker_quote, quote_volume, w=6):
    """Déséquilibre acheteur/vendeur des ordres au marché, lissé."""
    r = (2.0 * taker_quote / quote_volume.replace(0.0, np.nan) - 1.0)
    return r.rolling(w, min_periods=1).mean()

def funding_carry(fund, w=21):
    """Portage : on encaisse le financement en étant du côté qui le reçoit."""
    return -fund.rolling(w, min_periods=max(3, w // 3)).mean()

def avg_trade(quote_volume, trades, w=30):
    return -(quote_volume / trades.replace(0.0, np.nan)).rolling(w, min_periods=w // 3).median()


# ───────────────────────── moteur de backtest transversal ─────────────────────
def run_xs(close: pd.DataFrame, w: pd.DataFrame, tf="4h", cost=None,
           vol_target=0.20, vol_win=90, max_lev=3.0):
    """Portefeuille neutre en dollars : w décidé en i capte le rendement i+1."""
    from .portfolio import BARS_PER_YEAR
    ann = BARS_PER_YEAR[tf]
    ret = close.pct_change()
    fwd = ret.shift(-1).fillna(0.0)
    raw = (w * fwd).sum(axis=1)
    pv = raw.shift(1).rolling(vol_win, min_periods=vol_win // 3).std() * np.sqrt(ann)
    k = (vol_target / pv).clip(upper=max_lev).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    u = w.mul(k, axis=0)
    pnl = (u * fwd).sum(axis=1)
    du = u.diff(); du.iloc[0] = u.iloc[0]; du = du.abs()
    if cost is None:            fric = 0.0
    elif isinstance(cost, pd.DataFrame):
        fric = (du * cost.reindex_like(du).ffill()).sum(axis=1)
    else:                       fric = du.sum(axis=1) * cost
    return (pnl - fric).iloc[:-1]


def sharpe(x, tf="4h"):
    from .portfolio import BARS_PER_YEAR
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(BARS_PER_YEAR[tf])) if s > 0 else 0.0
