# Kalman v5 — ce qui a été mesuré, et ce qui a été écarté

Protocole : 58 alts Binance les plus liquides hors BTC, H4, **sept. 2024 → août 2026**.
Coûts = 0,086 % aller-retour + spread **mesuré sur les archives de carnet** × 3.
Choix faits sur sept. 2024 → déc. 2025 ; **2026 gardé hors échantillon**.
Moteur : `quantlab/core/engine_v5.py` (entrée à l'ouverture suivante, sortie deux
phases, stop intrabar prioritaire).

Métrique : Sharpe du capital agrégé, chaque trade engageant 1/58 du capital.

## Le diagnostic qui change tout

| Motif de sortie | Trades | Total | Part des pertes |
|---|---|---|---|
| **SL_dur** | 5 665 | −14 092 % | **97 %** |
| clot_kalman | 296 | −457 % | 3 % |
| clot_mediane | 6 653 | +14 586 % | — |

Le stop dur coûte **31×** plus que la population `clot<Kalman`. Et son 0 % de win
rate est une tautologie : on entre au-dessus du Kalman, on sort en dessous.

33 % des stops tombent **dès la première bougie** — le stop est posé sur la mèche
de la bougie de cassure, un niveau que le prix vient de visiter, alors que
l'entrée a lieu à l'ouverture suivante. Mais il ne coupe pas du bruit pour
autant : six bougies après un stop, le trade serait encore à −0,92R en médiane.

## Ce qui améliore

| Levier | Sharpe | MDD | Plateau ? |
|---|---|---|---|
| référence (spec d'origine) | −0,02 | −16,4 % | — |
| **stop ATR ×1,25 à ×1,5** | **+0,64 à +0,70** | −10 % | oui, +0,51 à +0,70 de ×1,0 à ×3,0 |
| **+ cassure ≥ 0,75 % du Kalman** | **+0,87** | −4,7 % | oui, WR monotone 25,6 % → 33,3 % |
| **+ break-even à +2,5 %** | **+1,17** | −4,4 % | oui, +0,90 à +1,17 de 1,5 % à 7 % |
| activer le short | +0,50 vs long seul | — | — |

## Ce qui dégrade — testé, écarté

| Option | Effet | Pourquoi |
|---|---|---|
| `TIME_BELOW_N = 1` | Sharpe −0,02 → **−0,21** | coupe les trades qui repassaient la médiane |
| Stratagème A (pente) | +0,87 → +0,64 à +0,75 | ampute la queue droite (>+3R : 5,0 % → 2,0 %) |
| Stratagème B (surchauffe) | IS +1,02 mais **OOS +0,49 → +0,12** | signature de surajustement |
| `SORTIE_RR` = 2R ou 3R | queue droite à **0,0 %** | supprime littéralement les gagnants |
| gate médiane à l'entrée | +0,02 seulement | l'essentiel du problème n'est pas là |
| `ENABLE_SHORT = False` (défaut) | Sharpe −0,52 | jette la moitié du signal |

## Réserves

- **~55 configurations testées.** La meilleure est un maximum de 55 essais.
- Le **premier semestre 2026**, seul segment vraiment hors échantillon, reste
  négatif : −2,11 pour la spec d'origine, −0,55 avec ATR + cassure.
- La preuve hors échantillon du **break-even dépend de la coupe** : janv.-sept.
  2026 le favorise (+0,61 contre +0,49), mars-sept. 2026 le défavorise (−0,86
  contre −0,55). Prometteur, pas établi.
- Mesuré ailleurs dans ce dépôt sur 138 perps et 4,7 ans : le suivi de tendance
  crypto casse à partir de 2025. Le S1-26 négatif n'est pas propre à v5.

## Config retenue

```python
SL_MODE          = "atr"    # le gain principal : +0,66 de Sharpe
SL_ATR_MULT      = 1.5
MIN_DIST_KALMAN  = 0.0075   # exiger une vraie cassure : +0,23
ENABLE_SHORT     = True
BE_ACTIVATION_PCT= 2.5      # prometteur, à confirmer
TIME_BELOW_N     = None     # mesuré nuisible
SORTIE_PENTE     = False    # mesuré nuisible
SORTIE_SURCHAUFFE= False    # surajustement
SORTIE_RR        = None     # détruit la queue droite
```
