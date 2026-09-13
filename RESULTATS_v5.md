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

## Les pentes : l'effet est réel, le sens est inversé

Hypothèse testée : une cassure sur une médiane Donchian fortement pentue serait
plus fiable qu'une cassure sur une médiane plate. Pente mesurée sur 20 bougies,
normalisée par l'ATR, à la bougie de signal. **Longs, sans aucun filtre médiane**
(donc l'effet n'est pas un artefact des filtres déjà en place) :

| pente de la médiane | trades | win | R moyen | P&L |
|---|---|---|---|---|
| très négative | 764 | 21,5 % | **+0,411** | +5,42 % |
| négative | 764 | 20,3 % | +0,211 | +2,78 % |
| plate | 763 | 16,1 % | +0,008 | +0,11 % |
| positive | 764 | 17,8 % | −0,068 | −0,90 % |
| très positive | 764 | 17,1 % | **−0,142** | −1,87 % |

Monotone sur les cinq quintiles, et **à l'envers de l'hypothèse**. La moitié de
l'observation est exacte — une médiane plate ou légèrement montante est bien la
zone des faux signaux — mais le bon côté est celui des médianes qui *tombent*.
Lecture : la partie rentable de ce système de suivi de tendance est en fait sa
composante contrariante — on achète le retournement, pas la confirmation.

Appliqué comme filtre (longs seuls, config complète) :

| filtre | Sharpe | P&L 2 ans | MDD | 24S2 | 25S1 | 25S2 | 26S1 | 26S2 |
|---|---|---|---|---|---|---|---|---|
| aucun | +1,63 | **+12,02 %** | −2,8 % | 2,00 | 1,62 | 1,10 | 1,09 | 2,02 |
| pente ≥ 0 (hypothèse) | +0,69 | +3,80 % | −2,7 % | −0,56 | 1,54 | 0,82 | −0,53 | 0,12 |
| pente ≤ −0,02 (inverse) | +1,73 | +11,81 % | −2,2 % | 2,29 | 2,10 | 1,12 | 1,72 | **−1,46** |

L'hypothèse telle quelle coûte les deux tiers du P&L. L'inverse monte le Sharpe
sans rapporter un centime de plus, et fait passer juil.-sept. 2026 de +1,51 % à
−0,49 % : il bloque 63 des 152 longs gagnants du dernier segment.

Autres pentes mesurées au même endroit : la borne haute du canal et le Kalman ne
donnent rien de monotone. **La largeur du canal, si** — et dans le sens de
l'intuition cette fois (canal qui s'écarte = expansion de volatilité = vraie
cassure) : R moyen +0,494 dans le quintile le plus expansif contre −0,072 dans
le plus resserré. Comme filtre : Sharpe +1,81, Calmar 2,86, MDD −2,0 %, mais
P&L +11,33 % contre +12,02 %.

## Le point où les filtres cessent d'apporter de l'argent

| étape | trades | P&L 2 ans | Sharpe |
|---|---|---|---|
| 1. spec d'origine | 12 874 | −0,22 % | −0,01 |
| 2. + ATR / cassure / BE | 7 688 | +9,33 % | +1,13 |
| 3. + gate longs | 7 159 | +10,76 % | +1,31 |
| 4. + méd<Kal + volume | 5 852 | **+12,02 %** | +1,63 |
| 5a. + pente inverse | 5 155 | +11,81 % | +1,73 |
| 5b. + canal qui s'écarte | 5 015 | +11,33 % | **+1,81** |

Les étapes 2 à 4 ajoutent du Sharpe **et** de l'argent. L'étape 5, dans ses deux
variantes, ajoute du Sharpe **en retirant** de l'argent : elle coupe des trades
et de la variance, pas des pertes. C'est le signe que le filtrage a donné ce
qu'il avait à donner. Les deux filtres de pente sont donc livrés en option,
désactivés par défaut.

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

## Sorties en RR : on est sauvé par les runners, et uniquement par eux

Qui fait le résultat ? Trades triés par R décroissant, part du P&L total cumulée :

| top X % des trades | nombre | part du P&L |
|---|---|---|
| 0,5 % | 29 | **50,5 %** |
| 1 % | 59 | **80,9 %** |
| 2 % | 119 | 128,4 % |
| 5 % | 298 | 222,3 % |
| 20 % | 1 192 | 374,0 % |

**59 trades sur 5 963 font 81 % de l'argent.** Au-delà du top 2 % le cumul
dépasse 100 % : tout le reste de la distribution est net négatif. Le seuil du
top 1 % est à +7,35R, et seulement 5,25 % des trades dépassent +3R.

TP fixe, P&L sur deux ans (référence sortie souple : **+14,15 %**) :

| TP | P&L | Sharpe | win | Calmar | 26S2 |
|---|---|---|---|---|---|
| 1R | +3,52 % | 0,837 | 42,6 % | 0,83 | −1,57 |
| 2R | +7,75 % | 1,311 | 25,9 % | 1,50 | −1,38 |
| 3R | +10,33 % | 1,520 | 22,7 % | 1,68 | −1,77 |
| 4R | +11,53 % | 1,568 | 22,1 % | 1,80 | −0,99 |
| 6R | +13,45 % | 1,590 | 22,0 % | 2,13 | +0,05 |
| **aucun** | **+14,15 %** | **1,635** | 21,9 % | **2,40** | **+1,50** |

Monotone : plus le TP est haut, moins il coûte, et aucun ne rapporte. Un TP à 1R
divise le P&L par quatre. Tous les TP fixes rendent aussi 26S2 négatif.

**Prise partielle** (on solde une fraction à X×R, le reste court) :

| variante | Sharpe | P&L | win | MDD | Calmar |
|---|---|---|---|---|---|
| référence | 1,635 | **14,15 %** | 21,9 % | −3,0 % | **2,40** |
| 30 % à 3R | **1,662** | 13,00 % | 22,7 % | −2,9 % | 2,33 |
| 50 % à 3R | 1,664 | 12,24 % | 22,7 % | −2,9 % | 2,17 |
| 30 % à 2R | 1,645 | 12,20 % | 25,9 % | −2,6 % | 2,35 |
| **30 % à 1R** | 1,594 | 10,90 % | **41,9 %** | −2,5 % | 2,26 |

Encore le même motif : le Sharpe monte à peine, le P&L descend, et le Calmar
baisse. Le seul intérêt réel de la prise partielle n'est pas financier : à 1R
elle fait passer le **win rate de 21,9 % à 41,9 %**, soit quatre trades gagnants
sur dix au lieu de deux, pour 3,25 points de P&L sur deux ans. Ça ne fait pas
gagner davantage, ça rend la courbe psychologiquement tenable.

## Une seule position, tout le capital, stop fixe à 1,5 %

Construction de la spec d'origine : un signal à la fois, tout le capital engagé,
stop à 1,5 % du prix d'entrée. Testée avec `sl_mode="pct"` et `fixed_lev=1.0`.

D'abord un fait mécanique : **le stop à 1,5 % est touché 56 à 66 % du temps** en
H4 crypto, et 35 % des trades sortent dans leur propre bougie d'entrée.

Avec un seul slot on ne prend que ~670 des 6 272 signaux : **il faut choisir**,
et le choix domine tout. Sur 40 tirages aléatoires du token :

| | 1 position (tout le capital) |
|---|---|
| P&L 2 ans, médiane | **−6,1 %** |
| écart-type entre tirages | **± 54,6 points** |
| minimum / maximum | −72,9 % / +138,6 % |
| tirages gagnants | **19/40** (pile ou face) |
| MDD médian / pire | −66,8 % / −84,1 % |
| volatilité annuelle | ~77 % |

Les meilleures règles de sélection testées (cassure la plus faible +57,2 %,
pente médiane la plus basse +64,6 %) sont à **+1,08 et +1,21 écart-type** du
hasard : indiscernables de la chance. Aucune règle de sélection n'a été trouvée.

## Combien de positions simultanées faut-il ?

Même config, dimensionnement par le risque (1 % par position), choix du token
aléatoire quand il y a plus de signaux que de slots, 20 tirages par ligne.

| slots | trades | Sharpe médian | écart-type | vol/an | MDD |
|---|---|---|---|---|---|
| 1 | 471 | 0,61 | **± 0,52** | 23,8 % | −25,9 % |
| 2 | 903 | 0,85 | ± 0,30 | 38,0 % | −27,7 % |
| 3 | 1 330 | 0,98 | ± 0,24 | 49,2 % | −34,7 % |
| 5 | 1 984 | 1,00 | ± 0,18 | 64,6 % | −45,9 % |
| 8 | 2 938 | 1,03 | ± 0,13 | 92,0 % | −57,0 % |
| 12 | 3 933 | 1,31 | ± 0,09 | 129,2 % | −68,2 % |
| **20** | 5 138 | **1,64** | ± 0,04 | 188,0 % | −80,4 % |
| 30 | 5 730 | 1,67 | ± 0,03 | 233,5 % | −84,7 % |
| 58 | 5 963 | 1,63 | ± 0,00 | 246,9 % | −86,3 % |

(Les volatilités et drawdowns de ce tableau sont à 1 % de risque par position
*sans* division par le nombre de tokens : c'est le Sharpe et l'écart-type qui
sont à lire, la taille se règle ensuite.)

**Le Sharpe monte de façon monotone avec le nombre de slots et l'incertitude
s'effondre.** À 20 slots on retrouve le 1,63 du portefeuille complet avec 88 %
des signaux. À 3 slots on plafonne à 0,98 ± 0,24. À 1 slot, 0,61 ± 0,52 :
l'écart-type dépasse presque le résultat.

**Conclusion : la diversification entre tokens n'est pas un raffinement de ce
système, c'en est le moteur principal.** Le signal par token est faible ; ce qui
produit un Sharpe de 1,6 c'est d'en empiler 20 à 30 en parallèle.

## Comment le portefeuille est construit

Point important, souvent mal compris : **il n'y a aucune sélection entre tokens.**
Les 58 perps tournent en parallèle, chacun indépendamment, une position à la fois
par token. Trois signaux le même jour sur trois tokens = les trois sont pris. Le
P&L agrégé divise par 58, ce qui revient à allouer 1/58 du capital à chaque token.

| | valeur |
|---|---|
| positions ouvertes simultanément (médiane) | 10 |
| p90 / p99 / maximum | 24 / 37 / 47 |
| part du temps à zéro position | 2,3 % |
| exposition brute (médiane / max) | 0,055× / 0,26× du capital |

L'exposition brute reste très basse : la marge n'est jamais le facteur limitant,
et il reste énormément de place pour monter en taille. C'est aussi pourquoi la
volatilité n'est que de 3-4 %/an.

## Restreindre l'univers (classement point-in-time par volume)

Classement recalculé chaque début de mois sur le volume en dollars des 30 jours
précédents, décalé d'un jour — aucune information future.

| univers | Sharpe | P&L 2 ans | MDD | Calmar | coût A/R moyen |
|---|---|---|---|---|---|
| top 10 | 0,811 | 8,86 % | −4,34 % | 0,98 | 0,1237 % |
| top 20 | 1,588 | 16,23 % | −3,06 % | 2,51 | 0,1344 % |
| **top 30** | **1,661** | **16,42 %** | **−2,78 %** | **2,78** | 0,1474 % |
| top 40 | 1,560 | 14,83 % | −3,16 % | 2,23 | 0,1570 % |
| 58 (référence) | 1,633 | 14,98 % | −3,01 % | 2,36 | 0,1687 % |

Le top 30 améliore la variante sans filtre de canal sur les quatre colonnes, et
le coût moyen baisse de 0,169 % à 0,147 % (le volume et le spread sont très
corrélés, donc trier par volume trie déjà par spread). Le top 10 est trop
concentré. **Mais les deux effets ne se cumulent pas** : sur la variante AVEC
filtre de canal, le top 30 dégrade (1,804 → 1,723, MDD −2,02 % → −2,45 %).

## Config retenue et pourquoi (arbitrage Sharpe / P&L)

Pour comparer un Sharpe à un P&L il faut les rendre commensurables : on ramène
chaque variante à **10 % de volatilité annuelle**, le rendement devient alors
proportionnel au Sharpe.

| config | Sharpe | P&L 2 ans | vol | MDD | Calmar | rendt à 10 % de vol |
|---|---|---|---|---|---|---|
| #4 ATR ×1,00 | 1,474 | 16,06 % | 5,05 % | −3,53 % | 2,15 | 14,74 % |
| **#4 ATR ×1,25** | **1,633** | **14,98 %** | 4,26 % | −3,01 % | **2,36** | 16,33 % |
| #4 ATR ×1,50 | 1,628 | 12,63 % | 3,63 % | −2,78 % | 2,16 | 16,28 % |
| #4 ATR ×1,75 | 1,522 | 10,10 % | 3,14 % | −2,50 % | 1,94 | 15,22 % |
| #5b canal ×1,50 | **1,804** | 11,88 % | 3,08 % | −2,02 % | 2,81 | **18,04 %** |
| #5a pente ×1,25 | 1,754 | 14,95 % | 3,95 % | −2,47 % | 2,87 | 17,54 % |

**Correction d'une comparaison biaisée.** Le tableau ci-dessus compare des
configurations de volatilités différentes, ce qui fausse la lecture du drawdown.
À volatilité égale :

| | vol | rendt/an | MDD | Calmar |
|---|---|---|---|---|
| #4 ×1,25 tel quel | 4,26 % | 7,10 % | −3,01 % | 2,36 |
| #4 ×1,25 desserré ×0,72 | 3,08 % | 5,12 % | −2,19 % | 2,34 |
| **#5b canal ×1,50** | 3,08 % | **5,67 %** | **−2,02 %** | **2,81** |

À risque égal, le filtre de canal gagne sur **les deux** axes. Son coût n'est
donc pas « 3 points de P&L » — c'est uniquement la régularité : 25S2 tombe à
0,77 et 26S1 à 0,88.

**Défaut livré : ATR ×1,50 + filtre de canal** (le plus défensif, MDD −2,02 %).
**Variante P&L maximum : ATR ×1,25, canal décoché** (P&L 14,98 %, MDD −3,01 %),
à faire tourner de préférence sur le top 30. Motifs du choix des paramètres :

- ×1,25 **domine** ×1,50 sur les deux axes (Sharpe 1,633 vs 1,628, P&L 14,98 %
  vs 12,63 %) et se trouve au centre d'un plateau ×1,0–×1,75.
- Le Sharpe maximum (#5b, 1,804) rend 18,0 %/an à volatilité égale contre 16,3 %
  — un écart dans le bruit — mais fait tomber 25S2 de 1,05 à 0,77 et 26S1 de
  1,31 à 0,88, et coûte 3,1 points de P&L. Régularité contre un gain non établi.
- #5a a le meilleur 26S1 (1,85) mais un 26S2 à **−2,80** : le segment le plus
  récent, donc le plus informatif, est celui qu'il casse.

Sharpe par semestre de la config retenue : **1,84 · 1,82 · 1,05 · 1,31 · 1,50**
— les cinq positifs. Douze derniers mois glissants : Sharpe +1,63, P&L +6,59 %.

## Le chiffre qui décide : Sharpe déflaté

Sharpe 1,633 sur deux ans. **Erreur-type 1,070** → IC95 [−0,47 ; 3,73], t = 1,53.
Pas significatif à 95 %, avant toute correction pour essais multiples.

Et il y a eu ~115 configurations testées. Le maximum attendu de 115 essais de
**pur bruit** sur un échantillon de cette longueur vaut **2,76**, soit davantage
que le 1,633 obtenu. Sharpe déflaté (Bailey & López de Prado) : **0,146**.

Nuances dans les deux sens, à ne pas escamoter :
- Les 115 essais ne sont pas indépendants (beaucoup de variantes imbriquées),
  donc le nombre effectif d'essais est bien inférieur et le test est sévère.
- En face, plusieurs améliorations ont passé des contrôles que le Sharpe déflaté
  ne voit pas : 15/15 et 9/9 combinaisons de paramètres améliorées, gradients
  monotones sur cinq quintiles, cinq semestres positifs.
- Mais aucune de ces nuances ne renverse le constat : deux ans ne suffisent pas.

Ce qu'il faudrait pour trancher : **~9 ans d'historique**, ou **~18 mois de
forward test** à ce Sharpe (t = Sharpe × √T, donc T = (2/1,633)² ≈ 1,5 an).
Le forward test est la seule voie qui échappe au biais de sélection, puisqu'il
porte sur des données qui n'existent pas encore.

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
