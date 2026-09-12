"""Zoo de stratégies de SUIVI / CONTINUATION DE TENDANCE de la littérature.

Chaque fonction renvoie une série de position cible dans {-1, 0, +1}, valant
la position DÉTENUE À PARTIR DE LA CLÔTURE de la barre i. Le backtest applique
donc position[i] au rendement de la barre i+1 : aucune information future.

Paramètres = valeurs canoniques publiées. AUCUNE optimisation : c'est la seule
façon de rendre un test sur 8 mois interprétable.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from . import indicators as I


def _sr(sig_long, sig_short, index):
    """Stop-and-reverse : reste dans le dernier état signalé."""
    p = pd.Series(np.nan, index=index)
    p[sig_long.fillna(False).to_numpy()] = 1.0
    p[sig_short.fillna(False).to_numpy()] = -1.0
    return p.ffill().fillna(0.0)


def _state(entry_l, exit_l, entry_s, exit_s, index):
    """Entrées/sorties distinctes, avec état plat possible (type Turtle)."""
    el, xl = entry_l.fillna(False).to_numpy(), exit_l.fillna(False).to_numpy()
    es, xs = entry_s.fillna(False).to_numpy(), exit_s.fillna(False).to_numpy()
    out = np.zeros(len(index)); pos = 0.0
    for i in range(len(index)):
        if pos == 0.0:
            if el[i]:   pos = 1.0
            elif es[i]: pos = -1.0
        elif pos > 0 and xl[i]: pos = -1.0 if es[i] else 0.0
        elif pos < 0 and xs[i]: pos = 1.0 if el[i] else 0.0
        out[i] = pos
    return pd.Series(out, index=index)


# ─────────────────────── moyennes mobiles ───────────────────────
def sma_cross_50_200(d):
    f, s = I.sma(d.close, 50), I.sma(d.close, 200)
    return _sr(f > s, f < s, d.index)

def ema_cross_12_26(d):
    f, s = I.ema(d.close, 12), I.ema(d.close, 26)
    return _sr(f > s, f < s, d.index)

def ema_cross_20_50(d):
    f, s = I.ema(d.close, 20), I.ema(d.close, 50)
    return _sr(f > s, f < s, d.index)

def triple_ema_4_9_18(d):
    a, b, c = I.ema(d.close, 4), I.ema(d.close, 9), I.ema(d.close, 18)
    return _sr((a > b) & (b > c), (a < b) & (b < c), d.index)

def price_vs_sma200(d):
    m = I.sma(d.close, 200)
    return _sr(d.close > m, d.close < m, d.index)

def macd_signal_cross(d):
    line, sig, _ = I.macd(d.close)
    return _sr(line > sig, line < sig, d.index)

def macd_zero_cross(d):
    line, _, _ = I.macd(d.close)
    return _sr(line > 0, line < 0, d.index)

def hull_ma_20(d):
    h = I.hma(d.close, 20)
    return _sr(h > h.shift(1), h < h.shift(1), d.index)

def kama_10(d):
    k = I.kama(d.close)
    return _sr(k > k.shift(1), k < k.shift(1), d.index)

def tema_20_slope(d):
    t = I.tema(d.close, 20)
    return _sr(t > t.shift(1), t < t.shift(1), d.index)

def dema_cross_10_30(d):
    f, s = I.dema(d.close, 10), I.dema(d.close, 30)
    return _sr(f > s, f < s, d.index)

def alma_21_slope(d):
    a = I.alma(d.close, 21)
    return _sr(a > a.shift(1), a < a.shift(1), d.index)

def guppy_ribbon(d):
    sh = sum(I.ema(d.close, n) for n in (3, 5, 8, 10, 12, 15)) / 6
    ln = sum(I.ema(d.close, n) for n in (30, 35, 40, 45, 50, 60)) / 6
    return _sr(sh > ln, sh < ln, d.index)

def ichimoku_tk_cross(d):
    conv = (d.high.rolling(9, min_periods=9).max() + d.low.rolling(9, min_periods=9).min()) / 2
    base = (d.high.rolling(26, min_periods=26).max() + d.low.rolling(26, min_periods=26).min()) / 2
    return _sr(conv > base, conv < base, d.index)

def ichimoku_kumo(d):
    conv = (d.high.rolling(9, min_periods=9).max() + d.low.rolling(9, min_periods=9).min()) / 2
    base = (d.high.rolling(26, min_periods=26).max() + d.low.rolling(26, min_periods=26).min()) / 2
    # nuage projeté 26 en avant => à la barre i on lit le span calculé il y a 26 barres
    a = ((conv + base) / 2).shift(26)
    b = ((d.high.rolling(52, min_periods=52).max() + d.low.rolling(52, min_periods=52).min()) / 2).shift(26)
    return _sr(d.close > a.combine(b, max), d.close < a.combine(b, min), d.index)


# ─────────────────────── cassures / canaux ───────────────────────
def donchian_20(d):
    u = d.high.rolling(20, min_periods=20).max().shift(1)
    l = d.low.rolling(20, min_periods=20).min().shift(1)
    return _sr(d.close > u, d.close < l, d.index)

def donchian_55(d):
    u = d.high.rolling(55, min_periods=55).max().shift(1)
    l = d.low.rolling(55, min_periods=55).min().shift(1)
    return _sr(d.close > u, d.close < l, d.index)

def turtle_s1_20_10(d):
    """Turtle System 1 : entrée cassure 20, sortie cassure inverse 10."""
    u20 = d.high.rolling(20, min_periods=20).max().shift(1)
    l20 = d.low.rolling(20, min_periods=20).min().shift(1)
    u10 = d.high.rolling(10, min_periods=10).max().shift(1)
    l10 = d.low.rolling(10, min_periods=10).min().shift(1)
    return _state(d.close > u20, d.close < l10, d.close < l20, d.close > u10, d.index)

def turtle_s2_55_20(d):
    u55 = d.high.rolling(55, min_periods=55).max().shift(1)
    l55 = d.low.rolling(55, min_periods=55).min().shift(1)
    u20 = d.high.rolling(20, min_periods=20).max().shift(1)
    l20 = d.low.rolling(20, min_periods=20).min().shift(1)
    return _state(d.close > u55, d.close < l20, d.close < l55, d.close > u20, d.index)

def bollinger_breakout(d):
    m = I.sma(d.close, 20); s = d.close.rolling(20, min_periods=20).std(ddof=0)
    return _sr(d.close > m + 2 * s, d.close < m - 2 * s, d.index)

def keltner_breakout(d):
    m = I.ema(d.close, 20); a = I.atr(d.high, d.low, d.close, 20)
    return _sr(d.close > m + 2 * a, d.close < m - 2 * a, d.index)

def volatility_breakout_lw(d):
    """Larry Williams : cassure de clôture + k * range précédent."""
    rng = (d.high - d.low).shift(1)
    return _sr(d.close > d.close.shift(1) + 0.5 * rng,
               d.close < d.close.shift(1) - 0.5 * rng, d.index)

def nbar_high_low_50(d):
    u = d.close.rolling(50, min_periods=50).max().shift(1)
    l = d.close.rolling(50, min_periods=50).min().shift(1)
    return _sr(d.close >= u, d.close <= l, d.index)


# ─────────────────────── momentum ───────────────────────
def tsmom_90(d):
    """Time-series momentum (Moskowitz-Ooi-Pedersen) : signe du rendement passé."""
    r = d.close / d.close.shift(90) - 1
    return _sr(r > 0, r < 0, d.index)

def tsmom_180(d):
    r = d.close / d.close.shift(180) - 1
    return _sr(r > 0, r < 0, d.index)

def roc_14(d):
    r = d.close.pct_change(14)
    return _sr(r > 0, r < 0, d.index)

def rsi_50_regime(d):
    r = I.rsi(d.close, 14)
    return _sr(r > 50, r < 50, d.index)

def cci_100(d):
    tp = (d.high + d.low + d.close) / 3
    m = tp.rolling(20, min_periods=20).mean()
    md = (tp - m).abs().rolling(20, min_periods=20).mean()
    c = (tp - m) / (0.015 * md)
    return _sr(c > 100, c < -100, d.index)

def tsi_25_13(d):
    m = d.close.diff()
    dbl = I.ema(I.ema(m, 25), 13); dba = I.ema(I.ema(m.abs(), 25), 13)
    t = 100 * dbl / dba
    return _sr(t > 0, t < 0, d.index)

def awesome_oscillator(d):
    mp = (d.high + d.low) / 2
    ao = I.sma(mp, 5) - I.sma(mp, 34)
    return _sr(ao > 0, ao < 0, d.index)

def elder_impulse(d):
    e = I.ema(d.close, 13); _, _, hist = I.macd(d.close)
    up = (e > e.shift(1)) & (hist > hist.shift(1))
    dn = (e < e.shift(1)) & (hist < hist.shift(1))
    return _sr(up, dn, d.index)


# ─────────────────────── force de tendance ───────────────────────
def adx_dmi_cross(d):
    adx, pdi, mdi = I.adx_dmi(d.high, d.low, d.close, 14)
    return _sr((pdi > mdi) & (adx > 25), (mdi > pdi) & (adx > 25), d.index)

def vortex_14(d):
    vp, vm = I.vortex(d.high, d.low, d.close, 14)
    return _sr(vp > vm, vp < vm, d.index)

def aroon_25(d):
    up, dn = I.aroon(d.high, d.low, 25)
    return _sr(up > dn, up < dn, d.index)

def supertrend_10_3(d):
    return I.supertrend(d.high, d.low, d.close, 10, 3.0)

def psar_002(d):
    return I.psar(d.high, d.low)

def chandelier_22_3(d):
    a = I.atr(d.high, d.low, d.close, 22)
    long_stop = d.high.rolling(22, min_periods=22).max() - 3 * a
    short_stop = d.low.rolling(22, min_periods=22).min() + 3 * a
    return _sr(d.close > short_stop, d.close < long_stop, d.index)

def atr_trailing_14_3(d):
    a = I.atr(d.high, d.low, d.close, 14)
    c = d.close.to_numpy(float); av = (3 * a).to_numpy()
    n = len(c); stop = np.full(n, np.nan); dirn = np.ones(n)
    for i in range(1, n):
        if not np.isfinite(av[i]): continue
        if not np.isfinite(stop[i - 1]):
            stop[i], dirn[i] = c[i] - av[i], 1; continue
        if dirn[i - 1] > 0:
            stop[i] = max(stop[i - 1], c[i] - av[i])
            dirn[i] = -1 if c[i] < stop[i] else 1
            if dirn[i] < 0: stop[i] = c[i] + av[i]
        else:
            stop[i] = min(stop[i - 1], c[i] + av[i])
            dirn[i] = 1 if c[i] > stop[i] else -1
            if dirn[i] > 0: stop[i] = c[i] - av[i]
    return pd.Series(dirn, index=d.index)


# ─────────────────────── statistique / filtres ───────────────────────
def linreg_slope_50(d):
    s = I.linreg_slope(d.close, 50)
    return _sr(s > 0, s < 0, d.index)

def kalman_bq_trend(d):
    k = I.kalman_bq(d.close)
    return _sr(d.close > k, d.close < k, d.index)

def zscore_50_regime(d):
    m = I.sma(d.close, 50); s = d.close.rolling(50, min_periods=50).std(ddof=0)
    z = (d.close - m) / s
    return _sr(z > 0.5, z < -0.5, d.index)

def ema50_chop_filtered(d):
    """EMA-50 filtrée par l'indice de choppiness (< 50 = marché directionnel)."""
    e = I.ema(d.close, 50); ch = I.choppiness(d.high, d.low, d.close, 14)
    raw = _sr(d.close > e, d.close < e, d.index)
    return raw.where(ch < 50, 0.0)


ZOO = {name: fn for name, fn in sorted(globals().items())
       if callable(fn) and not name.startswith("_")
       and getattr(fn, "__module__", None) == __name__
       and name not in ("np", "pd", "I")}
