"""La configuration retenue au terme de l'etude. Seule candidate survivante.

    Profil de volume ancre du DERNIER EXTREME de la semaine ecoulee jusqu'a la
    cloture du dimanche, applique toute la semaine suivante.
    Deux clotures hors de la value area, puis retour dedans : on pose un ordre
    LIMITE au bord franchi. Objectif le bord oppose, invalidation a l'extreme de
    l'excursion, duree maximale 240 heures.

Pourquoi cet ancrage. Le profil de la semaine entiere melange le mouvement et ce
qui l'entoure ; le profil de la jambe entre les deux extremes, lui, coupe trop —
il fait tomber l'edge brut de 0.066 a 0.012 R. Depuis le dernier extreme jusqu'a
la cloture, on garde le mouvement en cours et rien d'autre, et la value area est
deux fois plus etroite (3.5 % du prix contre 8.6 %).

Pourquoi l'ordre limite. L'entree est un NIVEAU connu une semaine a l'avance,
pas un evenement a poursuivre : c'est le seul cas de cette etude ou le passif se
defend. En taker, l'esperance est negative.

Tout est causal : le dernier extreme d'une semaine close est connu le dimanche a
23h59, et ne sert qu'a partir du lundi.
"""
from __future__ import annotations

PARAMS = {
    "profil": "hebdomadaire, ancre du dernier extreme a la cloture du dimanche",
    "n_bins": 60,
    "part_value_area": 0.70,
    "n_bougies_dehors": 2,
    "entree": "ordre limite au bord franchi",
    "attente_remplissage": 12,      # barres H1 avant annulation de l'ordre
    "objectif": "bord oppose de la value area",
    "invalidation": "extreme de l'excursion",
    "max_barres": 240,
}

MESURES = {
    "trades": 3861,
    "actifs": 10,
    "periode": "2022-01 -> 2026-08",
    "profit_factor": 1.131,
    "ic90_bootstrap_grappes": (1.050, 1.213),
    "part_tirages_au_dessus_de_1": 0.996,
    "actifs_au_dessus_de_1": "8/10",
    "taux_remplissage": 0.75,
    "pire_cas_taker_et_traversee_5bps": 1.058,
    "portefeuille_10_actifs": {
        "risque_par_trade": 0.005,
        "rendement_annuel": 0.013,
        "drawdown_max": -0.031,
        "trimestres_positifs": "12/19",
    },
}

RESERVES = (
    "Cette variante a emerge apres plusieurs centaines de configurations testees "
    "dans la session. L'intervalle de confiance ne corrige PAS cette recherche.",
    "Les dix actifs ont desormais servi : il ne reste aucun bloc vierge pour "
    "valider un reglage supplementaire. Tout ajustement ulterieur exige des "
    "actifs neufs ou du temps neuf.",
    "Le rendement est mince : 1.3 %/an a 0.5 % de risque par trade. A 2 % de "
    "risque, environ 5 %/an pour 12 % de drawdown.",
    "Les shorts portent l'essentiel du resultat : PF 1.21 contre 1.06 pour les "
    "longs. Une asymetrie non expliquee est une fragilite.",
)
