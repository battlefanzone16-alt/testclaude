"""Profil de volume hebdomadaire fixe : lundi 00h00 -> dimanche 23h59 UTC.

Aucune borne a deviner, aucun swing a confirmer. Le profil d'une semaine est
complet le dimanche a minuit, et sert de reference pour TOUTE la semaine
suivante. L'information est donc disponible a la seconde ou on s'en sert :
il n'y a structurellement aucune fuite possible.

C'est la version stricte de la regle. Si la rotation de value area a un contenu,
elle doit apparaitre ici — ou nulle part.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lab.volume_profile import value_area


def profils_hebdo(fin: pd.DataFrame, n_bins: int = 60,
                  part: float = 0.70) -> pd.DataFrame:
    """Un POC/VAL/VAH par semaine calendaire, calcule sur la donnee 5 minutes."""
    prix = (fin["high"] + fin["low"] + fin["close"]) / 3
    sem = fin.index.to_period("W-SUN")
    lignes = {}
    for periode, idx in prix.groupby(sem).groups.items():
        p = prix.loc[idx].to_numpy()
        v = fin["volume"].loc[idx].to_numpy()
        if len(p) < 288 or not np.isfinite(p).all():
            continue
        lo, hi = p.min(), p.max()
        if hi <= lo:
            continue
        bords = np.linspace(lo, hi, n_bins + 1)
        h, _ = np.histogram(p, bins=bords, weights=v)
        centres = (bords[:-1] + bords[1:]) / 2
        poc, val, vah = value_area(centres, h, part)
        lignes[periode] = {"poc": poc, "val": val, "vah": vah,
                           "haut": hi, "bas": lo, "volume": v.sum()}
    return pd.DataFrame(lignes).T.sort_index()


def niveaux(barres_index: pd.DatetimeIndex, hebdo: pd.DataFrame) -> pd.DataFrame:
    """Niveaux de la semaine PRECEDENTE, portes sur chaque barre de la semaine."""
    sem = barres_index.to_period("W-SUN")
    prec = sem - 1
    out = hebdo.reindex(prec)
    out.index = barres_index
    return out[["poc", "val", "vah"]]


def statistique_rotation(barres: pd.DataFrame, niv: pd.DataFrame, *,
                         n_bougies: int = 2, max_barres: int = 240) -> pd.DataFrame:
    """Probabilite brute d'atteindre la VAH apres etre repasse au-dessus de la VAL.

    Aucun cout, aucune taille de position : on mesure uniquement si la logique
    enoncee se verifie. Pour chaque declenchement on note lequel, de l'objectif
    ou de l'invalidation, arrive le premier.
    """
    c = barres["close"].to_numpy()
    h = barres["high"].to_numpy()
    b = barres["low"].to_numpy()
    val = niv["val"].to_numpy(float)
    vah = niv["vah"].to_numpy(float)
    n = len(c)
    evts = []

    for sens in (1, -1):
        compte = 0
        extreme = np.nan
        for i in range(n):
            if not np.isfinite(val[i]) or not np.isfinite(vah[i]):
                compte = 0
                continue
            dehors = c[i] < val[i] if sens == 1 else c[i] > vah[i]
            if dehors:
                compte += 1
                pire = b[i] if sens == 1 else h[i]
                extreme = pire if compte == 1 else (min(extreme, pire) if sens == 1
                                                    else max(extreme, pire))
                continue
            if compte >= n_bougies:
                entree = c[i]
                objectif = vah[i] if sens == 1 else val[i]
                invalid = extreme
                gagne = None
                for j in range(i + 1, min(i + 1 + max_barres, n)):
                    if sens == 1:
                        if b[j] <= invalid:
                            gagne = False; break
                        if h[j] >= objectif:
                            gagne = True; break
                    else:
                        if h[j] >= invalid:
                            gagne = False; break
                        if b[j] <= objectif:
                            gagne = True; break
                evts.append({"date": barres.index[i], "sens": sens, "entree": entree,
                             "objectif": objectif, "invalidation": invalid,
                             "gagne": gagne,
                             "gain_pct": abs(objectif - entree) / entree,
                             "perte_pct": abs(entree - invalid) / entree,
                             "barres_dehors": compte})
            compte = 0
    return pd.DataFrame(evts)
