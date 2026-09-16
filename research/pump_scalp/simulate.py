"""Simulateur de trade barre-a-barre + contrainte de portefeuille.

Deux passes, volontairement separees :

  Passe 1 (par symbole) : chaque evenement est simule isolement. Les regles de
  sortie ne dependent que du chemin de prix du token, donc le resultat d'un
  trade ne depend pas de savoir si le portefeuille l'aurait pris. On peut donc
  tout precalculer une fois.

  Passe 2 (portefeuille) : on rejoue les evenements dans l'ordre chronologique
  et on n'admet un trade que si un slot est libre. C'est la ou vivent les
  contraintes realistes (N positions max, une seule par symbole).

Convention intra-barre : quand le stop et la cible sont tous deux dans le range
d'une barre, on suppose que le STOP est touche en premier. L'OHLC 1m ne donne
pas l'ordre des ticks ; supposer l'inverse serait s'offrir gratuitement le
meilleur des deux mondes sur toutes les barres volatiles - exactement les
barres ou vit cette strategie.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class ExitRules:
    max_hold: int = 120           # time stop, en minutes
    stop_k: float = 1.0           # stop initial = stop_k * unite de risque
    trail_k: float = 1.5          # rappel depuis le plus-haut, en unites de risque
    arm_at: float = 1.0           # le trailing ne s'arme qu'apres MFE >= arm_at * risque
    tp_k: float = 0.0             # 0 = pas de take-profit dur
    fee_bps: float = 4.5          # taker Binance USDT-M, par cote
    slip_bps: float = 5.0         # slippage suppose, par cote


def simulate_one(o, h, l, entry_i, risk, rules: ExitRules):
    """Simule un trade long ouvert a l'ouverture de `entry_i`.

    risk : distance de risque en FRACTION du prix d'entree (ex. 0.02 = 2%).
    Renvoie (exit_i, ret_brut, raison).
    """
    n = len(o)
    px_in = o[entry_i]
    stop_d = rules.stop_k * risk
    trail_d = rules.trail_k * risk
    arm_d = rules.arm_at * risk
    tp_d = rules.tp_k * risk

    stop_px = px_in * (1.0 - stop_d)
    tp_px = px_in * (1.0 + tp_d) if tp_d > 0 else np.inf
    peak = px_in
    armed = False
    last = min(entry_i + rules.max_hold, n - 1)

    for i in range(entry_i, last + 1):
        lo, hi = l[i], h[i]
        # 1) le stop courant est teste en premier (convention conservatrice)
        if lo <= stop_px:
            return i, stop_px / px_in - 1.0, "stop" if not armed else "trail"
        # 2) puis la cible dure, si elle existe
        if hi >= tp_px:
            return i, tp_px / px_in - 1.0, "tp"
        # 3) mise a jour du trailing avec le plus-haut de CETTE barre, applicable
        #    seulement a partir de la barre suivante
        if hi > peak:
            peak = hi
            if not armed and peak >= px_in * (1.0 + arm_d):
                armed = True
            if armed:
                stop_px = max(stop_px, peak * (1.0 - trail_d))
    return last, o[min(last + 1, n - 1)] / px_in - 1.0, "time"


def net_return(ret_brut: float, rules: ExitRules) -> float:
    """Cout aller-retour : frais taker + slippage, sur les deux cotes."""
    c = (rules.fee_bps + rules.slip_bps) / 1e4
    return (1.0 + ret_brut) * (1.0 - c) / (1.0 + c) - 1.0


def portfolio(trades, max_concurrent: int = 3, rank_col: str = "z_burst"):
    """Passe 2 : filtre chronologique a N slots.

    `trades` doit etre trie par entry_time et contenir entry_time / exit_time /
    symbol. Renvoie le masque booleen des trades reellement pris.
    """
    import pandas as pd
    t = trades.reset_index(drop=True)
    open_until = []                      # (exit_time, symbol)
    taken = np.zeros(len(t), dtype=bool)
    ent = t["entry_time"].to_numpy()
    ext = t["exit_time"].to_numpy()
    sym = t["symbol"].to_numpy()

    for i in range(len(t)):
        now = ent[i]
        open_until = [x for x in open_until if x[0] > now]
        if len(open_until) >= max_concurrent:
            continue
        if any(s == sym[i] for _, s in open_until):
            continue
        taken[i] = True
        open_until.append((ext[i], sym[i]))
    return taken
