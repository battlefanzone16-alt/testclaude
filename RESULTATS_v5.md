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
| **+ gate médiane sur les LONGS seuls** | **+1,36** | −4,0 % | oui, 15/15 combinaisons, Δ médian +0,175 |

## Ce qui dégrade — testé, écarté

| Option | Effet | Pourquoi |
|---|---|---|
| `TIME_BELOW_N = 1` | Sharpe −0,02 → **−0,21** | coupe les trades qui repassaient la médiane |
| Stratagème A (pente) | +0,87 → +0,64 à +0,75 | ampute la queue droite (>+3R : 5,0 % → 2,0 %) |
| Stratagème B (surchauffe) | IS +1,02 mais **OOS +0,49 → +0,12** | signature de surajustement |
| `SORTIE_RR` = 2R ou 3R | queue droite à **0,0 %** | supprime littéralement les gagnants |
| gate médiane **symétrique** | +1,167 → +1,163 | les deux côtés s'annulent (voir ci-dessous) |
| gate médiane sur les **SHORTS** | +0,82 → **+0,48** | en crypto la baisse est rapide : attendre la médiane, c'est vendre après le mouvement |
| `ENABLE_SHORT = False` (défaut) | Sharpe −0,52 | jette la moitié du signal |

## Le gate médiane est asymétrique

Exiger que la clôture soit du bon côté de la médiane Donchian **en plus** du
Kalman ne sert à rien si on l'applique aux deux sens — c'est pour ça que le
premier test l'avait classé sans intérêt. Séparé par côté :

| | Sharpe longs | Sharpe shorts | global | Calmar |
|---|---|---|---|---|
| sans gate | +0,86 | +0,82 | +1,167 | 1,08 |
| gate symétrique | +1,10 | +0,48 | +1,163 | 1,18 |
| **gate longs seuls** | **+1,10** | +0,82 | **+1,357** | **1,40** |

Robustesse : testé sur 5 seuils de cassure × 3 longueurs Donchian, le gate longs
améliore **les 15 combinaisons** (Δ de +0,086 à +0,212, médiane +0,175), et
améliore **chacun des 5 semestres** mesurés. Lecture économique : en crypto les
baisses sont violentes et rapides, donc attendre la confirmation de la médiane
pour vendre revient à vendre après le mouvement ; les hausses grimpent plus
lentement et laissent le temps de confirmer.

## Réserves

- **~70 configurations testées.** La meilleure est un maximum de 70 essais.
- Le **niveau hors échantillon 2026 dépend entièrement de la coupe** — c'est la
  réserve la plus sérieuse. Sharpe 2026 selon le mois de départ :

  | départ | origine | améliorée | + gate longs |
  |---|---|---|---|
  | janvier | −1,36 | +0,56 | **+0,83** |
  | février | −2,29 | −0,95 | −0,67 |
  | mars | −2,15 | −1,01 | −0,73 |
  | avril | −1,48 | −0,42 | −0,16 |
  | mai | +0,30 | +1,51 | +1,73 |

  Le gate améliore **les cinq coupes** (c'est un effet relatif solide), mais le
  signe absolu tient à la présence de janvier 2026. Autrement dit : les
  améliorations sont établies, la **rentabilité hors échantillon ne l'est pas**.
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
ENTRY_ABOVE_MEDIAN = True   # +0,19 : n'acheter qu'au-dessus de la médiane…
ENTRY_MEDIAN_SIDES = "long" # …mais SURTOUT PAS vendre qu'en dessous (−0,34)
TIME_BELOW_N     = None     # mesuré nuisible
SORTIE_PENTE     = False    # mesuré nuisible
SORTIE_SURCHAUFFE= False    # surajustement
SORTIE_RR        = None     # détruit la queue droite
```
