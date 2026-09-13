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
| **+ gate médiane sur les LONGS seuls** | **+1,31** | −4,0 % | oui, 15/15 combinaisons, Δ médian +0,175 |
| **+ médiane sous le Kalman (longs)** | **+1,57** | −3,1 % | oui, 9/9 combinaisons, Δ médian +0,226 |
| **+ volume > SMA20 sur la cassure** | **+1,63** | −2,8 % | oui, +1,47 à +1,82 de MA10 à MA50 |

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

## Le stop mèche, retesté après les filtres

Sur la spec d'origine, le stop placé sous la mèche de la bougie de cassure était
le pire des 11 modes testés. **Ce n'est plus vrai une fois les entrées filtrées**
— et ça change la lecture de tout ce qui précède.

| stop | Sharpe | P&L 2 ans | MDD | % stops | stoppés 1re bougie | trades >+3R |
|---|---|---|---|---|---|---|
| ATR ×1,5 | **+1,63** | +12,02 % | −2,8 % | 19,2 % | 6,9 % | 4,34 % |
| mèche nue | +1,37 | +11,07 % | −3,0 % | 28,2 % | 15,1 % | **5,71 %** |
| mèche −0,5 % | +1,33 | — | −2,6 % | 21,6 % | 10,0 % | — |
| mèche −1,5 % | +1,31 | +7,15 % | −2,0 % | 11,8 % | 4,3 % | — |
| plus bas 5 bougies | +1,26 | — | −2,0 % | 8,7 % | 4,3 % | — |
| canal Donchian | +1,24 | — | −1,7 % | 4,1 % | 2,8 % | — |

L'ATR reste devant, mais **l'écart sur l'argent n'est plus significatif** :
+0,94 % de capital sur deux ans, t = +0,52. Le mécanisme d'origine n'a pas
disparu (15,1 % de stops dès la première bougie contre 6,9 %), mais la mèche
garde **plus de gros gagnants** (5,71 % de trades >+3R contre 4,34 %) : le stop
serré donne un levier plus élevé, donc les survivants paient davantage.

Ce qui différencie vraiment les deux, c'est la **régularité**, pas le rendement.
P&L par semestre, en % du capital :

| stop | 24S2 | 25S1 | 25S2 | 26S1 | 26S2 | total |
|---|---|---|---|---|---|---|
| ATR ×1,5 | +2,27 | +3,48 | +3,36 | +1,40 | +1,51 | +12,02 |
| mèche nue | +0,50 | +5,21 | +2,82 | +1,94 | +0,60 | +11,07 |

**Conséquence à retenir : le stop ATR corrigeait surtout un symptôme de mauvaise
sélection d'entrée.** Une fois les entrées filtrées (cassure minimale, médiane
sous le Kalman, volume), le choix du stop pèse beaucoup moins. Le gain annoncé
de +0,66 de Sharpe pour l'ATR était mesuré sur des entrées non filtrées.

Le multiple ATR est bien un plateau et non un pic : ×1,25 → +1,635, ×1,50 →
+1,630, et tout l'intervalle ×1,0 à ×3,0 tient entre +1,47 et +1,64. Le P&L
décroît de façon monotone avec le multiple (+15,97 % à ×0,75, +5,52 % à ×3,0)
pendant que le drawdown décroît aussi : le Sharpe arbitre entre les deux.

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
- **Le résultat 2026 tient encore à deux mois.** P&L net mois par mois, en % du
  capital à 1 % de risque par trade (données au 12 sept. 2026) :

  | config | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | total | sans janv+août |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | origine | +1,58 | −0,07 | −3,38 | −7,06 | +2,33 | −0,81 | −3,89 | +3,69 | +0,46 | −7,15 | −12,42 |
  | + gate longs | +2,04 | +0,86 | −0,79 | −2,63 | +1,06 | −0,21 | −0,65 | +2,16 | −0,24 | +1,60 | −2,60 |
  | + méd<Kal + volume | +1,97 | +1,03 | −0,46 | −2,11 | +0,18 | +0,18 | −0,34 | +2,20 | −0,37 | +2,94 | **−1,23** |

  Chaque filtre réduit la dépendance à janvier et août, aucun ne l'élimine.
- **La performance absolue reste faible** : ~6 %/an à 1 % de risque par trade.
  Le Sharpe monte autant par la baisse de volatilité (9,1 % → 3,5 %/an sur
  juin-sept.) que par la hausse du rendement.
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
ENTRY_MEDIAN_VS_KALMAN = True   # +0,26 : la médiane elle-même sous le Kalman
ENTRY_VOL_MA     = 20       # +0,06 : cassure confirmée par le volume
ENTRY_VOL_MULT   = 1.0      # MA50 x1,2 fait mieux (+1,82) : c'est le max de 12 essais
ENTRY_VOL_SIDES  = "long"
TIME_BELOW_N     = None     # mesuré nuisible
SORTIE_PENTE     = False    # mesuré nuisible
SORTIE_SURCHAUFFE= False    # surajustement
SORTIE_RR        = None     # détruit la queue droite
```
