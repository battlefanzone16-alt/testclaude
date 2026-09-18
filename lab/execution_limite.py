"""Simulateur evenementiel avec ordres limites, et le prix a payer pour les poser.

Pourquoi un moteur a part. Le moteur vectoriel suppose qu'on obtient toujours
son execution : on decide une position, elle est prise. Avec un ordre limite,
c'est faux — l'ordre n'est rempli que si le prix vient le chercher. Simuler du
maker sans modeliser les non-executions, c'est s'offrir les frais bas ET tous
les trades, ce qui n'existe pas.

Microstructure respectee :
  - un achat limite POSE AU-DESSUS du prix courant est marketable : il traverse
    le spread et paie le taker. On ne pose donc l'ordre qu'une fois le prix
    repasse au-dessus de la VAL, ou un achat a la VAL devient passif ;
  - l'objectif (VAH) est une vente limite posee sous... au-dessus du prix : elle
    est passive, donc maker ;
  - le stop, lui, est une sortie subie : taker, plus le slippage.

Un setup dont l'ordre n'est jamais rempli ne compte pas comme un trade, mais il
est compte dans le taux de remplissage : c'est la mesure du cout de la patience.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lab.costs import HL, CoutsHL


@dataclass
class Resultat:
    trades: pd.DataFrame
    setups: int
    remplis: int
    equity: pd.Series
    metriques: dict = field(default_factory=dict)

    def __repr__(self):
        m = self.metriques
        return (f"PF={m['profit_factor']:.2f} net={m['rendement_net']*100:+.1f}% "
                f"trades={len(self.trades)} fill={self.remplis}/{self.setups} "
                f"({m['taux_remplissage']*100:.0f}%)")


def simuler(barres: pd.DataFrame, niv: pd.DataFrame, funding: pd.Series | None = None, *,
            n_bougies: int = 2, attente: int = 12, profondeur_min: float = 0.0,
            max_barres: int = 240, couts: CoutsHL = HL,
            risque_par_trade: float = 0.01, entree: str = "limite",
            cible_mode: str = "bord", marge_fill: float = 0.0) -> Resultat:
    """Rejoue la regle barre par barre, avec ou sans ordre limite a l'entree.

    cible_mode "bord" : objectif au bord oppose de la zone (la VAH pour un long),
                        soit toute la largeur de la value area ;
    cible_mode "poc"  : objectif au POC, l'aimant classique du Market Profile,
                        plus proche donc plus souvent atteint.

    entree "limite" : on pose un achat a la VAL une fois le prix repasse dessus,
                      et il faut que le prix y revienne dans `attente` barres ;
    entree "marche" : on entre a l'ouverture suivante, en taker, toujours rempli.

    profondeur_min : excursion minimale hors de la value area, en fraction du
                     prix, pour que le setup soit retenu. C'est le filtre qui
                     evite les stops colles a l'entree.
    """
    o = barres["open"].to_numpy(); h = barres["high"].to_numpy()
    b = barres["low"].to_numpy(); c = barres["close"].to_numpy()
    val = niv["val"].to_numpy(float); vah = niv["vah"].to_numpy(float)
    poc = niv["poc"].to_numpy(float)
    idx = barres.index
    n = len(c)

    if funding is not None:
        f = funding.reindex(idx.union(funding.index)).ffill().reindex(idx).fillna(0.0)
        fh = (f / couts.funding_par_heure).to_numpy()
        heures = idx.to_series().diff().dt.total_seconds().div(3600).fillna(1.0).to_numpy()
    else:
        fh = np.zeros(n); heures = np.ones(n)

    trades = []
    setups = remplis = 0

    for sens in (1, -1):
        compte = 0
        extreme = np.nan
        etat = "attente"          # attente -> ordre_pose -> en_position
        prix_ordre = stop = cible = np.nan
        t_ordre = t_entree = -1
        prix_entree = np.nan

        for i in range(n):
            if not np.isfinite(val[i]) or not np.isfinite(vah[i]):
                continue

            if etat == "en_position":
                age = i - t_entree
                touche_stop = (b[i] <= stop) if sens == 1 else (h[i] >= stop)
                touche_cible = (h[i] >= cible) if sens == 1 else (b[i] <= cible)
                sortie = None
                if touche_stop:                       # on verifie le stop d'abord
                    sortie, prix_sortie, maker = "stop", stop, False
                elif touche_cible:
                    sortie, prix_sortie, maker = "cible", cible, True
                elif age >= max_barres:
                    sortie, prix_sortie, maker = "temps", c[i], False
                if sortie:
                    frais_sortie = couts.maker if maker else couts.taker + couts.slippage
                    brut = sens * (prix_sortie - prix_entree) / prix_entree
                    cout_f = sum(fh[j] * heures[j] for j in range(t_entree, i + 1)) * sens
                    trades.append({"date": idx[t_entree], "sortie": idx[i], "sens": sens,
                                   "motif": sortie, "barres": age,
                                   "brut": brut, "frais": frais_entree + frais_sortie,
                                   "funding": cout_f,
                                   "net": brut - frais_entree - frais_sortie - cout_f,
                                   "risque": abs(prix_entree - stop) / prix_entree})
                    etat, compte = "attente", 0
                    continue

            if etat == "ordre_pose":
                if i - t_ordre > attente:             # l'ordre expire non rempli
                    etat, compte = "attente", 0
                else:
                    # marge_fill : il ne suffit pas de toucher le niveau, il faut le
                    # traverser de cette marge. C'est la file d'attente : si le prix
                    # effleure et repart, l'ordre devant le notre a pris le flux.
                    seuil_fill = (prix_ordre * (1 - marge_fill) if sens == 1
                                  else prix_ordre * (1 + marge_fill))
                    touche = (b[i] <= seuil_fill) if sens == 1 else (h[i] >= seuil_fill)
                    if touche:
                        remplis += 1
                        prix_entree = prix_ordre
                        frais_entree = couts.maker    # passif : le prix vient a nous
                        t_entree = i
                        cible = (poc[i] if cible_mode == "poc"
                                 else (vah[i] if sens == 1 else val[i]))
                        etat = "en_position"
                    continue

            dehors = c[i] < val[i] if sens == 1 else c[i] > vah[i]
            if dehors:
                compte += 1
                pire = b[i] if sens == 1 else h[i]
                extreme = pire if compte == 1 else (min(extreme, pire) if sens == 1
                                                    else max(extreme, pire))
                continue

            if compte >= n_bougies and etat == "attente":
                bord = val[i] if sens == 1 else vah[i]
                profondeur = abs(bord - extreme) / bord
                if profondeur >= profondeur_min:
                    setups += 1
                    stop = extreme
                    if entree == "limite":
                        prix_ordre, t_ordre = bord, i
                        etat = "ordre_pose"
                    else:
                        if i + 1 < n:
                            remplis += 1
                            prix_entree = o[i + 1]
                            frais_entree = couts.taker + couts.slippage
                            t_entree = i + 1
                            cible = (poc[i] if cible_mode == "poc"
                                     else (vah[i] if sens == 1 else val[i]))
                            etat = "en_position"
            compte = 0

    tr = pd.DataFrame(trades)
    if tr.empty:
        return Resultat(tr, setups, remplis, pd.Series(dtype=float),
                        {"profit_factor": np.nan, "rendement_net": 0.0,
                         "taux_remplissage": 0.0})

    tr = tr.sort_values("date").reset_index(drop=True)
    # taille de position : risque fixe par trade, plafonnee a 3x le capital
    tr["taille"] = (risque_par_trade / tr["risque"].clip(lower=0.002)).clip(upper=3.0)
    tr["pnl"] = tr["net"] * tr["taille"]
    equity = (1 + tr["pnl"]).cumprod()
    gains = tr.loc[tr.pnl > 0, "pnl"].sum()
    pertes = -tr.loc[tr.pnl < 0, "pnl"].sum()
    m = {
        "profit_factor": float(gains / pertes) if pertes > 0 else np.nan,
        "pf_sans_taille": float(tr.loc[tr.net > 0, "net"].sum() /
                                max(-tr.loc[tr.net < 0, "net"].sum(), 1e-12)),
        "pf_brut": float(tr.loc[tr.brut > 0, "brut"].sum() /
                         max(-tr.loc[tr.brut < 0, "brut"].sum(), 1e-12)),
        "rendement_net": float(equity.iloc[-1] - 1.0),
        "win_rate": float((tr.pnl > 0).mean()),
        "taux_remplissage": remplis / setups if setups else 0.0,
        "frais_totaux": float((tr.frais * tr.taille).sum()),
        "n_trades": len(tr),
    }
    return Resultat(tr, setups, remplis, equity, m)
