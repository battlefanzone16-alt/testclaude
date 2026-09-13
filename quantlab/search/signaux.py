"""Bibliothèque de signaux pour la recherche. Tous causaux : un signal daté t
n'utilise que des données <= t."""
import numpy as np
import pandas as pd


def z(x, n):
    m = x.rolling(n, min_periods=max(5, n // 2)).mean()
    s = x.rolling(n, min_periods=max(5, n // 2)).std()
    return (x - m) / s.replace(0, np.nan)


def construire(d):
    P, H, L, V, D, TK, TR, F = (d[k] for k in ("P", "H", "L", "V", "D", "TK", "TR", "F"))
    R = P.pct_change(fill_method=None)
    LR = np.log(P).diff()
    sig = {}

    # --- prix : tendance et retournement -------------------------------------
    for n in (3, 5, 10, 20, 30, 60, 90, 180, 360):
        sig[f"mom_{n}"] = P.pct_change(n, fill_method=None)
        sig[f"rev_{n}"] = -P.pct_change(n, fill_method=None)
    for n in (30, 60, 90, 180, 360):
        sig[f"mom_{n}_skip7"] = P.shift(7).pct_change(n - 7, fill_method=None)
    # --- position dans la fourchette ----------------------------------------
    for n in (20, 30, 60, 90, 180, 360):
        hh = H.rolling(n, min_periods=int(n * .6)).max()
        ll = L.rolling(n, min_periods=int(n * .6)).min()
        sig[f"prox_haut_{n}"] = P / hh
        sig[f"prox_bas_{n}"] = P / ll
        sig[f"pos_canal_{n}"] = (P - ll) / (hh - ll).replace(0, np.nan)
    # --- volatilité ----------------------------------------------------------
    for n in (10, 20, 30, 60, 90):
        v = LR.rolling(n, min_periods=max(5, n // 2)).std()
        sig[f"vol_{n}"] = v
        sig[f"vol_basse_{n}"] = -v
    for n in (20, 60):
        v = LR.rolling(n, min_periods=n // 2).std()
        sig[f"vol_expansion_{n}"] = v / v.rolling(4 * n, min_periods=2 * n).mean()
        sig[f"vol_contraction_{n}"] = -v / v.rolling(4 * n, min_periods=2 * n).mean()
    # --- forme de la distribution -------------------------------------------
    for n in (30, 60, 90):
        sig[f"skew_{n}"] = LR.rolling(n, min_periods=n // 2).skew()
        sig[f"skew_neg_{n}"] = -LR.rolling(n, min_periods=n // 2).skew()
        sig[f"kurt_{n}"] = LR.rolling(n, min_periods=n // 2).kurt()
    for n in (20, 60):
        sig[f"max_{n}"] = R.rolling(n, min_periods=n // 2).max()          # effet loterie
        sig[f"max_neg_{n}"] = -R.rolling(n, min_periods=n // 2).max()
    # --- efficience et forme de bougie ---------------------------------------
    for n in (10, 20, 60):
        chem = LR.abs().rolling(n, min_periods=n // 2).sum()
        sig[f"efficience_{n}"] = (np.log(P) - np.log(P.shift(n))).abs() / chem.replace(0, np.nan)
        sig[f"inefficience_{n}"] = -sig[f"efficience_{n}"]
    # --- liquidité -----------------------------------------------------------
    for n in (20, 60):
        sig[f"amihud_{n}"] = (R.abs() / D.replace(0, np.nan)).rolling(n, min_periods=n // 2).mean()
        sig[f"amihud_neg_{n}"] = -sig[f"amihud_{n}"]
        sig[f"dollars_{n}"] = D.rolling(n, min_periods=n // 2).mean()
    for n in (5, 20, 60):
        sig[f"vol_surge_{n}"] = z(D, n)
        sig[f"vol_calme_{n}"] = -z(D, n)
    # --- funding -------------------------------------------------------------
    for n in (1, 3, 7, 30, 90):
        f = F.rolling(n, min_periods=1).mean()
        sig[f"fund_{n}"] = f
        sig[f"fund_neg_{n}"] = -f
    for n in (30, 90):
        sig[f"fund_z_{n}"] = z(F.rolling(7, min_periods=3).mean(), n)
        sig[f"fund_z_neg_{n}"] = -sig[f"fund_z_{n}"]
    for n in (7, 30):
        sig[f"fund_chg_{n}"] = F.rolling(n, min_periods=n // 2).mean() - F.rolling(4 * n, min_periods=2 * n).mean()
        sig[f"fund_chg_neg_{n}"] = -sig[f"fund_chg_{n}"]
    # --- flux taker ----------------------------------------------------------
    for n in (1, 3, 7, 20, 60):
        t = TK.rolling(n, min_periods=1).mean()
        sig[f"flux_{n}"] = t
        sig[f"flux_neg_{n}"] = -t
    for n in (20, 60, 90):
        sig[f"flux_z_{n}"] = z(TK.rolling(5, min_periods=2).mean(), n)
        sig[f"flux_z_neg_{n}"] = -sig[f"flux_z_{n}"]
    for n in (20, 60):
        # divergence : le flux monte mais pas le prix (et l'inverse)
        sig[f"diverg_{n}"] = z(TK.rolling(5, min_periods=2).mean(), n) - z(P.pct_change(5, fill_method=None), n)
        sig[f"diverg_neg_{n}"] = -sig[f"diverg_{n}"]
    for n in (20, 60):
        sig[f"taille_trade_{n}"] = (D / TR.replace(0, np.nan)).rolling(n, min_periods=n // 2).mean()
        sig[f"nb_trades_z_{n}"] = z(TR, n)
    # --- croisements de familles --------------------------------------------
    v30 = LR.rolling(30, min_periods=15).std()
    sig["mom60_sur_vol"] = P.pct_change(60, fill_method=None) / v30.replace(0, np.nan)
    sig["rev5_sur_vol"] = -P.pct_change(5, fill_method=None) / v30.replace(0, np.nan)
    sig["fund_moins_mom"] = z(F.rolling(7, min_periods=3).mean(), 90) - z(P.pct_change(30, fill_method=None), 90)
    sig["fund_plus_mom"] = z(F.rolling(7, min_periods=3).mean(), 90) + z(P.pct_change(30, fill_method=None), 90)
    sig["flux_moins_fund"] = z(TK.rolling(5, min_periods=2).mean(), 60) - z(F.rolling(7, min_periods=3).mean(), 60)
    return sig
