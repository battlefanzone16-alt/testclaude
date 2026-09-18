"""Signal du cycle 2 : reversion apres fermeture forcee.

Trois conditions doivent tomber ensemble sur la meme fenetre de k barres :
  1. un choc de prix, mesure en ecarts-types locaux et non en pourcentage fixe ;
  2. une BAISSE d'open interest — la marque d'une position fermee, pas ouverte ;
  3. un volume superieur a son regime habituel.

La deuxieme condition est le coeur du signal. Une chute a open interest stable
est une prise de position deliberee : le vendeur a une opinion, et rien ne dit
qu'elle est fausse. Une chute a open interest en baisse est une sortie subie :
le vendeur n'a pas choisi son prix, donc ce prix ne veut rien dire.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BARRES_PAR_JOUR = 288        # en 5 minutes


def aligner_oi(index: pd.DatetimeIndex, oi: pd.Series) -> pd.Series:
    """Open interest sur l'index des barres, sans jamais lire le futur."""
    s = oi.reindex(index.union(oi.index)).ffill().reindex(index)
    return s


def signal(df: pd.DataFrame, oi: pd.Series, *, k: int = 12, z: float = 3.0,
           chute_oi: float = 0.005, vol_mult: float = 1.0, horizon: int = 24,
           sens: str = "long", n_ref: int = BARRES_PAR_JOUR) -> pd.Series:
    """Position voulue. Sortie par le temps : on tient horizon barres, pas plus.

    Sortir par le temps plutot que par un niveau evite la tautologie du cycle 1 :
    aucune regle de sortie ne peut etre ajustee pour flatter l'entree.
    """
    c = df["close"]
    r1 = c.pct_change()
    sigma_k = r1.rolling(n_ref).std() * np.sqrt(k)
    choc = (c / c.shift(k) - 1.0) / sigma_k

    o = aligner_oi(df.index, oi)
    d_oi = o / o.shift(k) - 1.0

    vol_k = df["volume"].rolling(k).sum()
    vol_rel = vol_k / vol_k.rolling(n_ref).median()

    forcee = (d_oi <= -chute_oi) & (vol_rel >= vol_mult)
    if sens == "long":
        entree = (choc <= -z) & forcee
        signe = 1.0
    else:
        entree = (choc >= z) & forcee
        signe = -1.0

    entree = entree.fillna(False)
    # en position si une entree est tombee dans les horizon dernieres barres
    porte = entree.rolling(horizon, min_periods=1).max().fillna(0.0)
    return pd.Series(signe * porte.to_numpy(), index=df.index)


def signal_suivi(df: pd.DataFrame, oi: pd.Series, **kw) -> pd.Series:
    """Le miroir : on SUIT la cascade au lieu de la fader.

    Le screen du cycle 2 montre qu'acheter apres une liquidation baissiere perd
    sur les 27 cellules testees. Une perte aussi uniforme n'est pas du bruit :
    elle dit que le mouvement continue. Une liquidation en appelle une autre,
    parce que la baisse de prix declenche le palier de marge suivant.
    """
    sens = kw.pop("sens", "long")
    inverse = "short" if sens == "long" else "long"
    return -signal(df, oi, sens=inverse, **kw)
