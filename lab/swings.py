"""Detection de points de retournement, utilisable en direct.

Le piege de l'ancrage "a l'oeil" : sur un graphique termine, un plus haut se voit
immediatement. En direct, il n'existe qu'une fois que le prix en est redescendu
d'un certain pourcentage. Entre les deux, il y a un decalage de plusieurs
bougies, et c'est exactement dans ce decalage que loge le biais de retrospection.

Ce module ne renvoie donc jamais un swing a la date ou il s'est produit, mais a
la date ou il est devenu CONNAISSABLE. Un swing haut forme en t et confirme en
t+9 n'est disponible qu'a partir de t+9.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def zigzag(df: pd.DataFrame, seuil: float = 0.05) -> pd.DataFrame:
    """Swings confirmes par un retracement de `seuil` (fraction du prix).

    Renvoie, pour chaque barre : le prix et la date du dernier swing haut confirme
    et du dernier swing bas confirme, tels qu'ils etaient connaissables A CETTE
    BARRE. Les colonnes sont donc utilisables telles quelles dans un signal.
    """
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    n = len(df)

    px_haut = np.full(n, np.nan)      # prix du dernier swing haut confirme
    i_haut = np.full(n, -1)           # sa position
    px_bas = np.full(n, np.nan)
    i_bas = np.full(n, -1)

    sens = 0                          # +1 on cherche un haut, -1 on cherche un bas
    ext_px, ext_i = high[0], 0
    dernier_haut_px, dernier_haut_i = np.nan, -1
    dernier_bas_px, dernier_bas_i = np.nan, -1

    for t in range(n):
        if sens >= 0:
            if high[t] > ext_px:
                ext_px, ext_i = high[t], t
            # le sommet devient un swing confirme quand le prix en retrace `seuil`
            if sens == 1 and low[t] <= ext_px * (1 - seuil):
                dernier_haut_px, dernier_haut_i = ext_px, ext_i
                sens, ext_px, ext_i = -1, low[t], t
            elif sens == 0 and low[t] <= ext_px * (1 - seuil):
                dernier_haut_px, dernier_haut_i = ext_px, ext_i
                sens, ext_px, ext_i = -1, low[t], t
            elif sens == 0:
                sens = 1
        else:
            if low[t] < ext_px:
                ext_px, ext_i = low[t], t
            if high[t] >= ext_px * (1 + seuil):
                dernier_bas_px, dernier_bas_i = ext_px, ext_i
                sens, ext_px, ext_i = 1, high[t], t

        px_haut[t], i_haut[t] = dernier_haut_px, dernier_haut_i
        px_bas[t], i_bas[t] = dernier_bas_px, dernier_bas_i

    return pd.DataFrame({"px_haut": px_haut, "i_haut": i_haut,
                         "px_bas": px_bas, "i_bas": i_bas}, index=df.index)


def retard_de_confirmation(df: pd.DataFrame, seuil: float = 0.05) -> pd.Series:
    """Combien de barres separent la formation d'un swing de sa confirmation.

    C'est la mesure directe de ce que l'oeil s'offre gratuitement.
    """
    z = zigzag(df, seuil)
    retards = []
    vu = set()
    for t, (ih, ib) in enumerate(zip(z["i_haut"], z["i_bas"])):
        for i in (ih, ib):
            if i >= 0 and i not in vu:
                vu.add(i)
                retards.append(t - i)
    return pd.Series(retards, name="retard_barres")


def zigzag_retrospectif(df: pd.DataFrame, seuil: float = 0.05) -> pd.DataFrame:
    """La MEME detection, mais les swings sont disponibles des leur formation.

    C'est la version de l'oeil qui lit un graphique termine : le sommet est la,
    evident, des la bougie ou il se forme. Impossible a trader en direct.
    On la mesure quand meme, car l'ecart avec la version causale chiffre
    exactement ce que le coup d'oeil doit a la retrospection.
    """
    z = zigzag(df, seuil)
    n = len(df)
    px_haut = np.full(n, np.nan); i_haut = np.full(n, -1)
    px_bas = np.full(n, np.nan); i_bas = np.full(n, -1)

    pivots_h = sorted(set(int(i) for i in z["i_haut"] if i >= 0))
    pivots_b = sorted(set(int(i) for i in z["i_bas"] if i >= 0))
    high = df["high"].to_numpy(); low = df["low"].to_numpy()

    ph = pb = 0
    dh_px = dh_i = db_px = db_i = None
    for t in range(n):
        while ph < len(pivots_h) and pivots_h[ph] <= t:
            dh_i = pivots_h[ph]; dh_px = high[dh_i]; ph += 1
        while pb < len(pivots_b) and pivots_b[pb] <= t:
            db_i = pivots_b[pb]; db_px = low[db_i]; pb += 1
        if dh_i is not None:
            px_haut[t], i_haut[t] = dh_px, dh_i
        if db_i is not None:
            px_bas[t], i_bas[t] = db_px, db_i
    return pd.DataFrame({"px_haut": px_haut, "i_haut": i_haut,
                         "px_bas": px_bas, "i_bas": i_bas}, index=df.index)
