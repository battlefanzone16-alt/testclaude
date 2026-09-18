"""Le protocole, ecrit une fois pour toutes, avant d'avoir vu le moindre resultat.

Si une regle de selection doit changer apres coup, elle change ICI, dans un commit
date, avec sa raison. C'est la seule protection serieuse contre le sur-ajustement :
rendre le deplacement des poteaux visible dans l'historique git.
"""
from __future__ import annotations

SYMBOLE = "BTCUSDT"
TIMEFRAME = "1h"

# Conception. Regime mixte et hostile : krach de 2022 puis rebond de 2023.
# Choisi expres : sur une fenetre haussiere, n'importe quel biais long affiche un
# profit factor flatteur, et le buy & hold gagne sans strategie.
IS = ("2022-01-01", "2023-06-30")

# Validation. Jamais regardes avant le gel de la configuration.
OOS_FORWARD = ("2023-07-01", "2026-08-31")
OOS_BACKWARD = ("2020-01-01", "2021-12-31")

# Criteres de selection, fixes d'avance.
MIN_TRADES = 25           # en dessous, le profit factor est du bruit
MIN_PF = 1.20             # marge au-dessus de 1 : les couts sont deja dedans
MIN_TRIMESTRES_OK = 5     # sur les 6 trimestres de l'IS
MAX_DD = -0.35
MIN_PF_PLATEAU = 1.10     # mediane du voisinage de parametres
MIN_PF_LATENCE = 1.10     # avec une barre de retard a l'execution

# Un seuil de reussite en OOS, ecrit avant de le mesurer.
PF_OOS_ACCEPTABLE = 1.10
