"""Indicateurs de la littérature, tous strictement causaux.

Convention : toute valeur à l'indice i n'utilise que l'information <= barre i.
Aucune fonction n'utilise center=True, shift(-n) ou un fill arrière.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def sma(s, n):  return s.rolling(n, min_periods=n).mean()
def ema(s, n):  return s.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(s, n):
    """Lissage de Wilder (RMA) — base de RSI, ATR, ADX."""
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def true_range(h, l, c):
    pc = c.shift(1)
    return pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def atr(h, l, c, n=14):
    return wilder(true_range(h, l, c), n)


def rsi(c, n=14):
    d = c.diff()
    return 100 - 100 / (1 + wilder(d.clip(lower=0), n) / wilder((-d).clip(lower=0), n))


def macd(c, f=12, s=26, sig=9):
    line = ema(c, f) - ema(c, s)
    signal = line.ewm(span=sig, adjust=False, min_periods=sig).mean()
    return line, signal, line - signal


def hma(s, n):
    """Hull MA — WMA(2*WMA(n/2) - WMA(n), sqrt(n))."""
    def wma(x, k):
        w = np.arange(1, k + 1, dtype=float)
        return x.rolling(k, min_periods=k).apply(lambda v: np.dot(v, w) / w.sum(), raw=True)
    return wma(2 * wma(s, n // 2) - wma(s, n), int(np.sqrt(n)))


def kama(s, n=10, fast=2, slow=30):
    """Kaufman Adaptive MA — boucle explicite, récurrence causale."""
    x = s.to_numpy(float)
    chg = np.abs(x - np.roll(x, n)); chg[:n] = np.nan
    vol = pd.Series(np.abs(np.diff(x, prepend=x[0]))).rolling(n).sum().to_numpy()
    er = np.divide(chg, vol, out=np.zeros_like(chg), where=vol > 0)
    sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
    out = np.full_like(x, np.nan)
    start = n
    out[start] = x[start]
    for i in range(start + 1, len(x)):
        out[i] = out[i - 1] + (sc[i] if np.isfinite(sc[i]) else 0.0) * (x[i] - out[i - 1])
    return pd.Series(out, index=s.index)


def dema(s, n):
    e = ema(s, n); return 2 * e - ema(e, n)


def tema(s, n):
    e1 = ema(s, n); e2 = ema(e1, n); e3 = ema(e2, n)
    return 3 * e1 - 3 * e2 + e3


def alma(s, n=21, offset=0.85, sigma=6.0):
    m = offset * (n - 1); sd = n / sigma
    w = np.exp(-((np.arange(n) - m) ** 2) / (2 * sd * sd)); w /= w.sum()
    return s.rolling(n, min_periods=n).apply(lambda v: np.dot(v, w), raw=True)


def adx_dmi(h, l, c, n=14):
    up, dn = h.diff(), -l.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=h.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=h.index)
    tr = wilder(true_range(h, l, c), n)
    pdi = 100 * wilder(plus, n) / tr
    mdi = 100 * wilder(minus, n) / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return wilder(dx, n), pdi, mdi


def vortex(h, l, c, n=14):
    tr = true_range(h, l, c).rolling(n, min_periods=n).sum()
    vp = (h - l.shift(1)).abs().rolling(n, min_periods=n).sum()
    vm = (l - h.shift(1)).abs().rolling(n, min_periods=n).sum()
    return vp / tr, vm / tr


def aroon(h, l, n=25):
    up = h.rolling(n + 1, min_periods=n + 1).apply(lambda v: v.argmax() / n * 100, raw=True)
    dn = l.rolling(n + 1, min_periods=n + 1).apply(lambda v: v.argmin() / n * 100, raw=True)
    return up, dn


def supertrend(h, l, c, n=10, mult=3.0):
    """SuperTrend — récurrence causale (la bande dépend de son état précédent)."""
    a = atr(h, l, c, n); mid = (h + l) / 2
    ub, lb = (mid + mult * a).to_numpy(), (mid - mult * a).to_numpy()
    cl = c.to_numpy(float)
    fu, fl = ub.copy(), lb.copy()
    dirn = np.ones(len(cl))
    started = False
    for i in range(1, len(cl)):
        if not np.isfinite(ub[i]):
            dirn[i] = dirn[i - 1]; continue
        if not started:                      # amorçage au premier ATR valide :
            started = True                   # sans ça fu/fl restent NaN à vie
            fu[i], fl[i] = ub[i], lb[i]
            dirn[i] = 1 if cl[i] > fu[i] else -1
            continue
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or cl[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or cl[i - 1] < fl[i - 1]) else fl[i - 1]
        if cl[i] > fu[i]:   dirn[i] = 1
        elif cl[i] < fl[i]: dirn[i] = -1
        else:               dirn[i] = dirn[i - 1]
    return pd.Series(dirn, index=c.index)


def psar(h, l, af0=0.02, step=0.02, af_max=0.2):
    """Parabolic SAR de Wilder."""
    hi, lo = h.to_numpy(float), l.to_numpy(float)
    n = len(hi); out = np.full(n, np.nan); dirn = np.ones(n)
    sar, ep, af, up = lo[0], hi[0], af0, True
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if up:
            sar = min(sar, lo[i - 1], lo[max(i - 2, 0)])
            if lo[i] < sar:
                up, sar, ep, af = False, ep, lo[i], af0
            elif hi[i] > ep:
                ep, af = hi[i], min(af + step, af_max)
        else:
            sar = max(sar, hi[i - 1], hi[max(i - 2, 0)])
            if hi[i] > sar:
                up, sar, ep, af = True, ep, hi[i], af0
            elif lo[i] < ep:
                ep, af = lo[i], min(af + step, af_max)
        out[i], dirn[i] = sar, (1 if up else -1)
    return pd.Series(dirn, index=h.index)


def linreg_slope(s, n):
    x = np.arange(n, dtype=float); xc = x - x.mean(); den = (xc ** 2).sum()
    return s.rolling(n, min_periods=n).apply(lambda v: np.dot(xc, v - v.mean()) / den, raw=True)


def choppiness(h, l, c, n=14):
    tr = true_range(h, l, c).rolling(n, min_periods=n).sum()
    rng = h.rolling(n, min_periods=n).max() - l.rolling(n, min_periods=n).min()
    return 100 * np.log10(tr / rng) / np.log10(n)


def kalman_bq(c, pn=0.01, mn=3.0):
    """Kalman BackQuant du dépôt (gain stationnaire ≡ EMA)."""
    x = c.to_numpy(float); out = np.empty_like(x); p = 1.0
    out[0] = x[0]
    for i in range(1, len(x)):
        p += pn
        k = p / (p + mn)
        out[i] = out[i - 1] + k * (x[i] - out[i - 1])
        p *= (1 - k)
    return pd.Series(out, index=c.index)
