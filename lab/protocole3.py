"""Cycle 3 — rotation de value area. Criteres fixes avant le balayage.

Transparence : une configuration a ete mesuree avant d'ecrire ce fichier, la plus
naturelle (H1, profil 10 jours, 2 bougies, stop au retour hors zone) : PF 1.15
cote long, 0.90 cote short. Les criteres ci-dessous n'ont pas ete choisis pour la
faire passer — ils sont plus exigeants qu'elle.
"""
from __future__ import annotations

ACTIF_CONCEPTION = "BTCUSDT"
IS = ("2022-01-01", "2023-06-30")

# Toujours vierges : aucun de ces actifs n'a ete mesure dans ce depot.
ACTIFS_VALIDATION = ("AVAXUSDT", "LINKUSDT", "DOGEUSDT")

MIN_TRADES = 80           # la regle se declenche moins souvent qu'un signal 5 min
MIN_PF = 1.20
MIN_TRIMESTRES_OK = 4     # sur 6 ; assoupli par rapport au cycle 1 car ~100 trades
MIN_PF_PLATEAU = 1.10     # mediane du voisinage de parametres
SLIPPAGE_STRESS = 0.0010
MIN_PF_STRESS = 1.08

PF_OOS_PAR_ACTIF = 1.10
MIN_ACTIFS_OK = 2
PF_OOS_POOLED = 1.10
