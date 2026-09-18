"""Ensemble de rotations de value area ancrees sur les swings, version causale.

Meme principe qu'ensemble_va : aucun parametre n'est elu, toutes les variantes
votent. Seule change la facon d'ancrer le profil — non plus les N derniers jours,
mais l'espace entre le dernier plus bas et le dernier plus haut CONFIRMES.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from lab import strategie_va as va, swings, volume_profile as vp

SEUILS = (0.03, 0.05, 0.08, 0.12)
BINS = (40, 60, 80)
STOPS = ("val", "extreme")
MAX_BARRES = (24, 72, 240)
N_BOUGIES = 2


def variantes():
    return list(itertools.product(SEUILS, BINS, STOPS, MAX_BARRES))


def signal(barres, fin, *, sens="long", retrospectif=False, cache=None):
    cache = {} if cache is None else cache
    votes = np.zeros(len(barres))
    n = 0
    for seuil, nb, stop, maxb in variantes():
        cle = (seuil, nb, retrospectif)
        if cle not in cache:
            z = (swings.zigzag_retrospectif if retrospectif else swings.zigzag)(barres, seuil)
            cache[cle] = vp.niveaux_ancres(barres, fin, z, mode="jambe", n_bins=nb)
        votes += va.signal(barres, cache[cle], n_bougies=N_BOUGIES, sens=sens,
                           stop=stop, max_barres=maxb).to_numpy()
        n += 1
    return pd.Series(votes / n, index=barres.index)
