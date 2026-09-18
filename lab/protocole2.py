"""Cycle 2 — reversion apres cascade de liquidations. Ecrit avant toute mesure.

Idee. Une chute rapide accompagnee d'une BAISSE d'open interest n'est pas une
vente : c'est une fermeture forcee. Le vendeur n'a pas d'opinion, il subit un
appel de marge. Le prix depasse donc sa valeur le temps que le carnet se
reconstitue. On achete ce depassement, pas la baisse elle-meme.

C'est la chute d'OI qui fait la difference entre ce signal et un simple
"acheter les baisses" : une baisse a OI stable ou croissant est une prise de
position deliberee, et n'a aucune raison de rebondir.

Validation : par GENERALISATION INTER-ACTIFS, choix de l'utilisateur. La regle
est concue sur BTC seul et mesuree sur trois actifs jamais ouverts dans ce depot.
"""
from __future__ import annotations

ACTIF_CONCEPTION = "BTCUSDT"
TIMEFRAME = "5m"

# 18 mois, meme fenetre hostile qu'au cycle 1.
IS = ("2022-01-01", "2023-06-30")

# Jamais mesures dans ce depot, sous aucune forme. C'est le bloc OOS.
ACTIFS_VALIDATION = ("AVAXUSDT", "LINKUSDT", "DOGEUSDT")

# Secondaire, informatif : cette fenetre a deja ete ouverte au cycle 1, elle ne
# compte donc pas comme preuve.
OOS_TEMPS_SECONDAIRE = ("2023-07-01", "2026-08-31")

# Criteres de selection in-sample, fixes d'avance.
MIN_TRADES = 150          # horizon court : sans volume de trades, rien a conclure
MIN_PF = 1.15
MIN_TRIMESTRES_OK = 5     # sur 6
MIN_PF_PLATEAU = 1.08     # mediane du voisinage de parametres

# Le test qui compte vraiment pour ce style. Une cascade, c'est le moment ou le
# carnet est le plus vide : si l'edge ne survit pas a 10 bps de slippage, il
# n'existe que dans le backtest.
SLIPPAGE_STRESS = 0.0010
MIN_PF_STRESS = 1.05

# Seuils de reussite OOS, ecrits avant de les mesurer.
PF_OOS_PAR_ACTIF = 1.10
MIN_ACTIFS_OK = 2         # sur les 3
PF_OOS_POOLED = 1.10      # les trois actifs mis en commun
