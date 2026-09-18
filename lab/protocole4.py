"""Cycle 10 — l'hypothese de derive. Ecrit et COMMITE avant toute mesure.

Ce fichier existe parce que le cycle 6 a echoue pour une raison precise : j'y ai
choisi un ancrage parmi trois en regardant les dix actifs sur lesquels j'allais
ensuite annoncer le resultat. Le diagnostic du cycle 9 l'a prouve — les deux
ancrages rejetes donnent le meme chiffre sur un echantillon neuf (1.005 -> 1.039
et 0.981 -> 0.978) tandis que celui que j'avais retenu s'effondre (1.103 -> 1.006).
Le gain de selection reste colle a l'option choisie.

Ici, tout est fixe d'avance : l'hypothese, le filtre, l'ancrage, les actifs, et
le seuil de reussite. Aucune de ces lignes ne bougera apres la mesure.

HYPOTHESE
    La rotation de value area ne fonctionne que dans le sens de la derive de
    l'actif. Sur un actif en declin durable, le setup long rachete un couteau qui
    tombe ; seul le short paie. Symetriquement sur un actif qui monte.

    Fondement : au cycle 9, la correlation de rang entre derive annuelle et
    profit factor vaut +0.51 (p = 0.020), et la degradation frappe le cote long
    (1.049 -> 0.933 entre les deux echantillons) beaucoup plus que le short
    (1.196 -> 1.119).

FILTRE, causal par construction
    A chaque semaine, on mesure la derive des 26 semaines precedentes.
    Derive > 0 : seuls les setups LONG sont autorises.
    Derive < 0 : seuls les setups SHORT sont autorises.
    Aucune autre valeur de fenetre ne sera testee avant la mesure primaire.

ANCRAGE
    Profil de la semaine entiere. C'est le plus simple, et c'est le seul des
    trois qui n'ait pas ete choisi en regardant un resultat. Les deux autres
    seront reportes en secondaire, a titre de robustesse, JAMAIS comme candidats.
"""
from __future__ import annotations

# Dix actifs jamais touches dans ce depot, sous aucune forme.
ACTIFS = ("UNIUSDT", "XLMUSDT", "ALGOUSDT", "ICPUSDT", "EOSUSDT",
          "SANDUSDT", "MANAUSDT", "GALAUSDT", "CHZUSDT", "RUNEUSDT")

FENETRE = ("2022-01-01", "2026-08-31")
DERIVE_SEMAINES = 26           # six mois, valeur unique, pas de grille
ANCRAGE = "semaine"
N_BOUGIES = 2
ATTENTE = 12
MAX_BARRES = 240
SLIPPAGE_STOP = 0.0010

# Criteres de reussite, ecrits avant de mesurer.
PF_MINIMUM = 1.10              # sur les dix actifs mis en commun
IC_BAS_MINIMUM = 1.00          # borne basse du bootstrap en grappes d'actifs
DOIT_BATTRE_LE_NON_FILTRE = True   # le filtre doit ameliorer, sinon il ne sert a rien

# Ce qui sera conclu, selon le resultat, sans renegociation possible :
#   - les trois criteres passent  -> l'hypothese de derive survit a un vrai test
#     hors echantillon, et merite un dernier lot de dix actifs pour confirmation.
#   - le filtre n'ameliore pas    -> l'hypothese est fausse, l'etude s'arrete.
#   - PF entre 1.00 et 1.10       -> effet reel mais trop faible pour etre trade,
#     meme conclusion pratique qu'un echec.
