"""Ensemble de rotations de value area : on n'elit aucun parametre.

Le balayage montre que le profit factor d'une configuration depend du nombre de
bins du profil — un choix d'affichage, pas une propriete du marche. Une regle
dont le resultat change quand on redessine le meme graphique n'a pas d'edge :
elle a de la variance.

On integre donc les parametres de nuisance au lieu d'en elire un. Chaque variante
vote pour sa position, et la position finale est la moyenne des votes. Ce qui
survit a cette moyenne ne peut plus etre un accident de grille : si la moitie des
variantes gagne et l'autre perd, l'ensemble vaut zero, ce qui est la reponse
honnete.

Effet secondaire utile : la taille de position devient graduelle. On est
pleinement engage quand toutes les lectures du profil s'accordent, marginalement
quand elles se contredisent.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from lab import strategie_va as va, volume_profile as vp

LOOKBACKS = (6, 8, 10, 12, 14, 16, 20, 25, 30)
BINS = (40, 60, 80, 100)
STOPS = ("val", "extreme")
MAX_BARRES = (24, 72, 240)
N_BOUGIES = 2                      # la regle enoncee : deux bougies hors de la zone


def variantes():
    return list(itertools.product(LOOKBACKS, BINS, STOPS, MAX_BARRES))


def signal(barres: pd.DataFrame, fin: pd.DataFrame, *, sens: str = "long",
           mult_tf: int = 1, cache: dict | None = None) -> pd.Series:
    """Moyenne des positions de toutes les variantes. Aucun parametre n'est choisi."""
    cache = {} if cache is None else cache
    votes = np.zeros(len(barres))
    n = 0
    for lb, nb, stop, maxb in variantes():
        cle = (lb, nb)
        if cle not in cache:
            cache[cle] = vp.niveaux(barres.index, fin,
                                    lookback=pd.Timedelta(days=lb), n_bins=nb)
        pos = va.signal(barres, cache[cle], n_bougies=N_BOUGIES, sens=sens,
                        stop=stop, max_barres=max(2, maxb // mult_tf))
        votes += pos.to_numpy()
        n += 1
    return pd.Series(votes / n, index=barres.index)
