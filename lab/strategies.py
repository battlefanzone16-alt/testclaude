"""Catalogue de signaux. Chacun renvoie une position voulue, indexee comme le prix.

Regle commune : un signal de la barre t ne lit que des donnees closes en t.
Tout niveau de reference (plus haut, moyenne, ecart-type) est decale d'une barre
pour qu'il ne contienne jamais la barre qu'il sert a juger.

Chaque famille est un ETAT, pas un evenement : on est long tant que la condition
tient. C'est ce qui evite d'entrer puis de sortir sur la meme ligne recalculee.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _etat(entree_long, sortie_long, entree_short=None, sortie_short=None, index=None):
    """Machine a etats : +1 tant que long, -1 tant que short, 0 sinon.

    Ecrit en boucle explicite parce que l'etat est recursif. Lent mais lisible,
    et on ne triche pas avec un ffill qui masquerait un chevauchement.
    """
    el = entree_long.to_numpy(bool)
    sl = sortie_long.to_numpy(bool)
    es = entree_short.to_numpy(bool) if entree_short is not None else np.zeros(len(el), bool)
    ss = sortie_short.to_numpy(bool) if sortie_short is not None else np.zeros(len(el), bool)
    pos = np.zeros(len(el))
    etat = 0.0
    for i in range(len(el)):
        if etat == 0.0:
            if el[i]:
                etat = 1.0
            elif es[i]:
                etat = -1.0
        elif etat == 1.0:
            if sl[i]:
                etat = -1.0 if es[i] else 0.0
        else:
            if ss[i]:
                etat = 1.0 if el[i] else 0.0
        pos[i] = etat
    return pd.Series(pos, index=index)


def donchian(df, n_entree=48, n_sortie=24, sens="long"):
    """Cassure de canal : long au-dessus du plus haut des n_entree barres precedentes."""
    c = df["close"]
    haut = c.rolling(n_entree).max().shift(1)
    bas = c.rolling(n_sortie).min().shift(1)
    haut_s = c.rolling(n_sortie).max().shift(1)
    bas_e = c.rolling(n_entree).min().shift(1)
    el, sl = c > haut, c < bas
    es, ss = (c < bas_e, c > haut_s) if sens in ("short", "both") else (None, None)
    if sens == "short":
        el = pd.Series(False, index=c.index)
    return _etat(el, sl, es, ss, index=c.index)


def ema_cross(df, rapide=24, lent=120, sens="long"):
    c = df["close"]
    f = c.ewm(span=rapide, adjust=False).mean()
    l = c.ewm(span=lent, adjust=False).mean()
    haussier = f > l
    if sens == "long":
        return haussier.astype(float)
    if sens == "short":
        return -(~haussier).astype(float)
    return haussier.astype(float) - (~haussier).astype(float)


def zscore_mr(df, n=96, entree=2.0, sortie=0.5, sens="both"):
    """Retour a la moyenne sur l'ecart au prix moyen, en unites d'ecart-type."""
    c = df["close"]
    mu = c.rolling(n).mean()
    sd = c.rolling(n).std()
    z = (c - mu) / sd
    el, sl = z < -entree, z > -sortie
    es, ss = z > entree, z < sortie
    if sens == "long":
        es = ss = None
    elif sens == "short":
        el = pd.Series(False, index=c.index)
    return _etat(el, sl, es, ss, index=c.index)


def rsi_mr(df, n=14, entree=25, sortie=55):
    c = df["close"]
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    return _etat(rsi < entree, rsi > sortie, index=c.index)


def heure_du_jour(df, debut=0, fin=8, sens="long"):
    """Saisonnalite intraday : porte une position sur une plage horaire UTC fixe."""
    h = df.index.hour
    dedans = (h >= debut) & (h < fin) if debut < fin else (h >= debut) | (h < fin)
    signe = 1.0 if sens == "long" else -1.0
    return pd.Series(np.where(dedans, signe, 0.0), index=df.index)


def funding_fade(df, funding, seuil_annuel=0.30, sortie_annuel=0.05):
    """Prend le cote paye du funding quand la foule est trop d'un cote.

    Le taux 8 h est annualise (3 prelevements par jour). Funding tres positif =
    longs surcharges : on se met short, on encaisse le funding et la purge.
    """
    f = funding.reindex(df.index.union(funding.index)).ffill().reindex(df.index)
    fa = f * 3 * 365
    return _etat(entree_long=fa < -seuil_annuel, sortie_long=fa > -sortie_annuel,
                 entree_short=fa > seuil_annuel, sortie_short=fa < sortie_annuel,
                 index=df.index)


def tendance_filtre_funding(df, funding, lent=200, seuil_annuel=0.50):
    """Long de tendance, coupe quand le funding devient prohibitif."""
    c = df["close"]
    haussier = c > c.rolling(lent).mean()
    f = funding.reindex(df.index.union(funding.index)).ffill().reindex(df.index)
    supportable = (f * 3 * 365) < seuil_annuel
    return (haussier & supportable).astype(float)


def range_breakout(df, k=0.5, n_atr=24, sens="long"):
    """Cassure de volatilite : k x ATR au-dessus de l'ouverture du jour UTC."""
    c, h, l = df["close"], df["high"], df["low"]
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n_atr).mean().shift(1)
    jour = df.index.floor("D")
    open_jour = df["open"].groupby(jour).transform("first")
    seuil_h = open_jour + k * atr
    seuil_b = open_jour - k * atr
    nouveau_jour = pd.Series(jour, index=df.index).ne(pd.Series(jour, index=df.index).shift(1))
    el, sl = c > seuil_h, nouveau_jour
    es, ss = (c < seuil_b, nouveau_jour) if sens in ("short", "both") else (None, None)
    if sens == "short":
        el = pd.Series(False, index=c.index)
    return _etat(el, sl, es, ss, index=c.index)


def vol_target(df, signal, cible_annuelle=0.40, n_vol=168, levier_max=2.0,
               rythme="D"):
    """Met le signal a l'echelle de la volatilite realisee.

    Une position de taille fixe sur un actif dont la volatilite passe de 30 % a
    120 % n'est pas la meme position. On vise une contribution de risque stable.

    Le facteur n'est reevalue qu'une fois par periode (par defaut chaque jour UTC)
    et arrondi : sinon le levier bouge a chaque barre et le rebalancement mange
    le gain en frais.
    """
    r = df["close"].pct_change()
    vol = r.rolling(n_vol).std() * np.sqrt(24 * 365)
    facteur = (cible_annuelle / vol).clip(upper=levier_max).shift(1)
    facteur = facteur.groupby(df.index.floor(rythme)).transform("first")
    facteur = (facteur * 10).round() / 10          # pas de 0.1 de levier
    return (signal * facteur).fillna(0.0)
