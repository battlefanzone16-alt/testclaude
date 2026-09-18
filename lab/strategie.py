"""La configuration candidate, gelee avant tout regard sur l'out-of-sample.

Choix : Donchian bidirectionnel a levier inverse a la volatilite.

Pourquoi ces valeurs. Le screen in-sample (230 configurations, fenetre
2022-01 -> 2023-06) fait apparaitre une ILE de parametres, pas un pic : toutes
les combinaisons de canal entre 192 et 336 heures sortent entre 1.27 et 1.76 de
profit factor, entourees de ~1.00 en dessous (24-96 h) comme au-dessus (504 h).
On prend donc le CENTRE de cette ile (240 h d'entree, 24 h de sortie), pas son
maximum (288/96, PF 1.84) : le maximum d'une grille est l'endroit ou le bruit
s'ajoute au signal.

Le levier inverse a la volatilite ameliore les 20 cellules de l'ile, pas une
seule — c'est ce qui le distingue d'un parametre ajuste.

Ce fichier ne doit plus bouger. Toute modification posterieure a la mesure OOS
invalide la mesure OOS.
"""
from __future__ import annotations

import pandas as pd

from lab import strategies as S

PARAMS = {
    "n_entree": 240,        # canal d'entree : 10 jours
    "n_sortie": 24,         # canal de sortie : 1 jour
    "sens": "both",
    "cible_vol": 0.40,      # volatilite annualisee visee
    "n_vol": 168,           # fenetre d'estimation de la vol : 7 jours
    "levier_max": 2.0,
    "rythme_levier": "D",   # le levier ne bouge qu'une fois par jour
}


def signal(df: pd.DataFrame, funding: pd.Series | None = None) -> pd.Series:
    """Position voulue, de -2 a +2, connue a la cloture de chaque barre."""
    brut = S.donchian(df, n_entree=PARAMS["n_entree"],
                      n_sortie=PARAMS["n_sortie"], sens=PARAMS["sens"])
    return S.vol_target(df, brut,
                        cible_annuelle=PARAMS["cible_vol"],
                        n_vol=PARAMS["n_vol"],
                        levier_max=PARAMS["levier_max"],
                        rythme=PARAMS["rythme_levier"])
