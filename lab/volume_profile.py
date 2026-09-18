"""Profil de volume : volume echange a chaque niveau de prix, et sa value area.

Le profil est construit a partir des bougies 5 minutes, pas des bougies de
signal. Un profil calcule sur des H1 en posant tout le volume de l'heure au prix
typique est une caricature : 12 points de mesure par heure valent mieux qu'un.

Definitions, methode Market Profile standard :
  POC  le niveau de prix ou le volume echange est le plus grand
  VA   la zone qui contient 70 % du volume, etendue de proche en proche depuis
       le POC en prenant a chaque pas le voisin le plus charge
  VAH  le haut de cette zone      VAL  le bas de cette zone
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def value_area(bins_prix: np.ndarray, volumes: np.ndarray,
               part: float = 0.70) -> tuple[float, float, float]:
    """(POC, VAL, VAH) a partir d'un histogramme volume-par-prix deja construit."""
    total = volumes.sum()
    if total <= 0:
        return np.nan, np.nan, np.nan
    i_poc = int(np.argmax(volumes))
    cible = total * part
    cumul = volumes[i_poc]
    bas = haut = i_poc
    while cumul < cible and (bas > 0 or haut < len(volumes) - 1):
        v_bas = volumes[bas - 1] if bas > 0 else -1.0
        v_haut = volumes[haut + 1] if haut < len(volumes) - 1 else -1.0
        if v_haut >= v_bas:
            haut += 1
            cumul += v_haut
        else:
            bas -= 1
            cumul += v_bas
    return float(bins_prix[i_poc]), float(bins_prix[bas]), float(bins_prix[haut])


def niveaux(signal_index: pd.DatetimeIndex, fin: pd.DataFrame, *,
            lookback: pd.Timedelta, n_bins: int = 60,
            part: float = 0.70) -> pd.DataFrame:
    """POC / VAL / VAH glissants, calcules sur la donnee fine.

    Le profil attache a une barre de signal n'utilise QUE des bougies 5 minutes
    deja closes a ce moment-la : la borne haute de la fenetre est l'horodatage de
    la barre, exclue.
    """
    prix = ((fin["high"] + fin["low"] + fin["close"]) / 3).to_numpy()
    vol = fin["volume"].to_numpy()
    ts = fin.index.to_numpy()

    debuts = (signal_index - lookback).to_numpy()
    i_deb = np.searchsorted(ts, debuts, side="left")
    i_fin = np.searchsorted(ts, signal_index.to_numpy(), side="left")

    out = np.full((len(signal_index), 3), np.nan)
    for i, (a, b) in enumerate(zip(i_deb, i_fin)):
        if b - a < 12:                     # moins d'une heure de donnee : inutile
            continue
        p, v = prix[a:b], vol[a:b]
        lo, hi = p.min(), p.max()
        if not np.isfinite(lo) or hi <= lo:
            continue
        bords = np.linspace(lo, hi, n_bins + 1)
        h, _ = np.histogram(p, bins=bords, weights=v)
        centres = (bords[:-1] + bords[1:]) / 2
        out[i] = value_area(centres, h, part)

    return pd.DataFrame(out, index=signal_index, columns=["poc", "val", "vah"])
