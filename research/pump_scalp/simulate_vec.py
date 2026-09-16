"""Simulateur vectorise : meme regles que simulate.py, mais en boucle sur le
TEMPS plutot que sur les trades.

L'astuce : le trailing stop est path-dependant, donc non vectorisable sur le
temps ; mais il est parfaitement vectorisable sur les evenements. On boucle donc
sur les 480 barres d'horizon en mettant a jour des vecteurs de taille n. Cout :
480 iterations numpy au lieu de n*480 iterations Python.

Convention intra-barre identique : STOP teste avant la cible. Quand les deux
sont dans le range de la meme barre, on suppose le pire. Sur une strategie qui
ne vit que dans les barres violentes, l'hypothese inverse fabriquerait de la
performance a partir de rien.
"""
from __future__ import annotations

import numpy as np
from simulate import ExitRules


def simulate_batch(O, Hi, Lo, risk, rules: ExitRules):
    """O/Hi/Lo : (n, H) chemins RELATIFS au prix d'entree (donc O[:,0] == 1).

    Renvoie (ret_brut, exit_bar, raison) — raison codee 0=stop 1=trail 2=tp 3=time.
    """
    n, H = O.shape
    last = min(rules.max_hold, H - 2)

    stop = np.full(n, 1.0 - rules.stop_k * risk)
    tp = (np.full(n, 1.0 + rules.tp_k * risk) if rules.tp_k > 0
          else np.full(n, np.inf))
    arm = 1.0 + rules.arm_at * risk
    trail_d = rules.trail_k * risk

    peak = np.ones(n)
    armed = np.zeros(n, dtype=bool)
    alive = np.isfinite(O[:, 0])
    ret = np.full(n, np.nan)
    ebar = np.full(n, -1, dtype=np.int32)
    why = np.full(n, -1, dtype=np.int8)
    last_o = np.where(alive, 1.0, np.nan)      # dernier prix connu, pour fin de donnees

    for i in range(0, last + 1):
        if not alive.any():
            break
        lo, hi, op = Lo[:, i], Hi[:, i], O[:, i]
        have = alive & np.isfinite(lo) & np.isfinite(hi)

        # fin d'historique alors qu'on est encore en position : on sort au dernier prix
        dead = alive & ~have
        if dead.any():
            ret[dead] = last_o[dead] - 1.0
            ebar[dead] = i - 1
            why[dead] = 3
            alive = alive & ~dead

        if not have.any():
            continue
        last_o = np.where(have & np.isfinite(op), op, last_o)

        hit_stop = have & (lo <= stop)
        if hit_stop.any():
            ret[hit_stop] = stop[hit_stop] - 1.0
            ebar[hit_stop] = i
            why[hit_stop] = np.where(armed[hit_stop], 1, 0)
            alive = alive & ~hit_stop
            have = have & ~hit_stop

        hit_tp = have & (hi >= tp)
        if hit_tp.any():
            ret[hit_tp] = tp[hit_tp] - 1.0
            ebar[hit_tp] = i
            why[hit_tp] = 2
            alive = alive & ~hit_tp
            have = have & ~hit_tp

        if not have.any():
            continue
        newpeak = have & (hi > peak)
        peak = np.where(newpeak, hi, peak)
        armed = armed | (have & (peak >= arm))
        upd = have & armed
        stop = np.where(upd, np.maximum(stop, peak - trail_d), stop)

    # time stop : sortie a l'ouverture de la barre suivante
    if alive.any():
        nxt = O[:, min(last + 1, H - 1)]
        fallback = np.where(np.isfinite(nxt), nxt, last_o)
        ret[alive] = fallback[alive] - 1.0
        ebar[alive] = last + 1
        why[alive] = 3
    return ret, ebar, why


RAISONS = {0: "stop", 1: "trail", 2: "tp", 3: "time"}


def net(ret, rules: ExitRules):
    c = (rules.fee_bps + rules.slip_bps) / 1e4
    return (1.0 + ret) * (1.0 - c) / (1.0 + c) - 1.0
