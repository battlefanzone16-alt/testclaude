"""Features d'ignition de momentum, strictement causales.

Convention temporelle, respectee partout :
  - une feature indexee a la barre t n'utilise QUE des barres <= t (barres closes) ;
  - un signal calcule a la cloture de t est execute a l'OUVERTURE de t+1.
C'est la seule convention qui correspond a un scanner tournant en live sur la
cloture de la minute.

Normalisation : tout est mesure par rapport au *regime propre du token avant la
bougie d'ignition*. Les references (vol, volume) sont decalees de K minutes pour
que la rafale elle-meme ne serve pas a se normaliser — sinon un pump vertical
gonfle son propre denominateur et le z-score s'effondre juste quand il devrait
exploser.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_PER_DAY = 1440


def add_features(df: pd.DataFrame, k: int = 5, w_ref: int = MIN_PER_DAY,
                 btc_close: pd.Series | None = None) -> pd.DataFrame:
    """Ajoute les features d'ignition. `df` : OHLCV 1m d'un seul symbole.

    k     : fenetre de rafale, en minutes (le mouvement qu'on veut detecter)
    w_ref : fenetre de reference pour le regime normal (defaut 1 jour)
    """
    out = pd.DataFrame(index=df.index)
    c = df["close"].astype("float64")
    qv = df["quote_volume"].astype("float64")

    ret1 = c.pct_change()

    # --- 1. Amplitude de la rafale, en unites de vol pre-rafale ---------------
    r_burst = c / c.shift(k) - 1.0
    # ecart-type des rendements 1m mesure AVANT la rafale (shift k)
    sigma_ref = ret1.rolling(w_ref, min_periods=w_ref // 4).std().shift(k)
    sigma_ref = sigma_ref.replace(0.0, np.nan)
    out["r_burst"] = r_burst
    out["sigma_ref"] = sigma_ref
    out["z_burst"] = r_burst / (sigma_ref * np.sqrt(k))

    # --- 2. Expansion de volume ----------------------------------------------
    qv_burst = qv.rolling(k).sum()
    qv_ref = qv.rolling(w_ref, min_periods=w_ref // 4).median().shift(k) * k
    out["qv_burst"] = qv_burst
    out["vol_mult"] = qv_burst / qv_ref.replace(0.0, np.nan)

    # --- 3. Pression acheteuse (part du flux agressif a l'achat) -------------
    tq_burst = df["taker_quote"].astype("float64").rolling(k).sum()
    out["taker_ratio"] = tq_burst / qv_burst.replace(0.0, np.nan)

    # --- 4. Idiosyncrasie : ce qui reste une fois le marche retire ------------
    if btc_close is not None:
        b = btc_close.reindex(df.index).ffill().astype("float64")
        out["r_btc"] = b / b.shift(k) - 1.0
        out["r_resid"] = out["r_burst"] - out["r_btc"]
    else:
        out["r_btc"] = np.nan
        out["r_resid"] = out["r_burst"]

    # --- 5. Contexte : sommes-nous deja tard dans le mouvement ? --------------
    # cassure du plus-haut des 60 dernieres minutes (hors barre courante)
    out["hh60"] = df["high"].rolling(60).max().shift(1)
    out["break60"] = c / out["hh60"] - 1.0
    out["r_60m"] = c / c.shift(60) - 1.0
    out["r_240m"] = c / c.shift(240) - 1.0

    # --- 6. Forme de la rafale : regime ou meche ? ---------------------------
    # Une meche de liquidation, c'est UNE barre. Un pump sur news, c'est une
    # sequence d'achats. Le meme r_burst recouvre les deux ; ces trois features
    # les separent.
    absr = ret1.abs()
    out["bar_dom"] = absr.rolling(k).max() / r_burst.abs().replace(0.0, np.nan)
    out["up_frac"] = (ret1 > 0).rolling(k).mean()
    # persistance du volume : le flux est-il encore eleve, ou etait-ce un a-coup ?
    qv_med = qv.rolling(w_ref, min_periods=w_ref // 4).median().shift(k)
    out["vol_persist"] = (qv.rolling(30).mean() / qv_med.replace(0.0, np.nan))
    # position dans la structure plus large
    out["hh240"] = df["high"].rolling(240).max().shift(1)
    out["break240"] = c / out["hh240"] - 1.0
    out["dist_hh1d"] = c / df["high"].rolling(MIN_PER_DAY).max().shift(1) - 1.0
    # amplitude deja parcourue sur la journee : proxy d'epuisement
    out["r_1d"] = c / c.shift(MIN_PER_DAY) - 1.0

    # liquidite instantanee : de quoi filtrer les tokens intradables
    out["qv_ref_1d"] = qv.rolling(w_ref, min_periods=w_ref // 4).median().shift(k)
    out["trades_burst"] = df["trades"].astype("float64").rolling(k).sum()
    return out


def forward_paths(df: pd.DataFrame, entry_idx: np.ndarray, horizons) -> dict:
    """Rendements forward et MFE/MAE depuis l'ouverture de la barre d'entree.

    entry_idx : positions entieres de la barre d'ENTREE (deja t+1, pas t).
    Vectorise : les extremes forward sont precalcules par un rolling inverse
    plutot que par une boucle sur les evenements.
    """
    o = df["open"].to_numpy(dtype="float64")
    h = pd.Series(df["high"].to_numpy(dtype="float64"))
    l = pd.Series(df["low"].to_numpy(dtype="float64"))
    n = len(df)
    entry_px = o[entry_idx]
    last = np.minimum(entry_idx, n - 1)
    res = {}
    for hz in horizons:
        res[f"fwd_{hz}"] = o[np.minimum(entry_idx + hz, n - 1)] / entry_px - 1.0
        # max/min sur la fenetre [i, i+hz-1] : rolling(hz) puis decalage arriere
        fmax = h.rolling(hz, min_periods=1).max().shift(-(hz - 1)).to_numpy()
        fmin = l.rolling(hz, min_periods=1).min().shift(-(hz - 1)).to_numpy()
        res[f"mfe_{hz}"] = fmax[last] / entry_px - 1.0
        res[f"mae_{hz}"] = fmin[last] / entry_px - 1.0
    return res
