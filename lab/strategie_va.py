"""Rotation de value area : sortie puis retour dans la zone de valeur.

La regle, telle qu'enoncee :
  le prix cloture SOUS la VAL pendant n bougies, puis cloture a nouveau AU-DESSUS
  de la VAL -> on est long, objectif la VAH. Symetrique au-dessus de la VAH.

Le raisonnement : hors de la value area, le prix est a un niveau que le marche a
peu echange. S'il n'y reste pas, c'est que la sortie n'a pas ete acceptee, et la
zone dense qu'il vient de quitter le rappelle — jusqu'a son autre bord.

L'objectif et l'invalidation sont tous deux definis par le profil, pas par un
niveau ajustable : c'est ce qui rend la regle testable sans parametre cache.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def signal(df: pd.DataFrame, niveaux: pd.DataFrame, *, n_bougies: int = 2,
           sens: str = "long", stop: str = "val", max_barres: int = 120) -> pd.Series:
    """Position voulue, connue a la cloture de chaque barre.

    stop : "val"     on sort si le prix re-cloture du mauvais cote du bord franchi
           "extreme" on sort si le prix repasse sous le plus bas de l'excursion
    """
    c = df["close"].to_numpy()
    low = df["low"].to_numpy()
    high = df["high"].to_numpy()
    val = niveaux["val"].to_numpy()
    vah = niveaux["vah"].to_numpy()

    n = len(c)
    pos = np.zeros(n)
    compte = 0          # bougies consecutives hors de la value area
    extreme = np.nan    # plus bas (ou plus haut) atteint pendant l'excursion
    etat = 0            # 0 hors marche, 1 en position
    age = 0

    for i in range(n):
        if not np.isfinite(val[i]) or not np.isfinite(vah[i]):
            pos[i] = 0.0
            continue

        if etat == 1:
            age += 1
            if sens == "long":
                touche = c[i] >= vah[i]
                casse = (c[i] < val[i]) if stop == "val" else (low[i] < extreme)
            else:
                touche = c[i] <= val[i]
                casse = (c[i] > vah[i]) if stop == "val" else (high[i] > extreme)
            if touche or casse or age >= max_barres:
                etat, compte, age = 0, 0, 0
                extreme = np.nan
            else:
                pos[i] = 1.0 if sens == "long" else -1.0
                continue

        dehors = c[i] < val[i] if sens == "long" else c[i] > vah[i]
        if dehors:
            compte += 1
            extreme = low[i] if compte == 1 else (min(extreme, low[i]) if sens == "long"
                                                  else max(extreme, high[i]))
            if sens == "short":
                extreme = high[i] if compte == 1 else max(extreme, high[i])
        else:
            if compte >= n_bougies:          # retour dans la zone apres n bougies dehors
                etat, age = 1, 0
                pos[i] = 1.0 if sens == "long" else -1.0
            compte = 0

    return pd.Series(pos, index=df.index)
