# Carry de funding perp — chiffrage

Mesuré sur les archives Binance : funding de 117 perps (2021-10 → 2026-08) et
klines spot des 30 perps les plus liquides (2022-01 → 2026-08), téléchargées
pour ce test.

## Le funding brut, d'abord

| | |
|---|---|
| funding annualisé médian, 117 tokens | **+4,63 %/an** |
| tokens à funding moyen positif | 84 / 117 = **72 %** |
| part du temps à funding positif (token médian) | **82 %** |

Attention au piège d'annualisation : **6 tokens sur 117 versent toutes les 4 h**
et non toutes les 8 h. L'intervalle est détecté par token.

**Mais ce n'est pas structurel — c'est cyclique :**

| année | funding médian annualisé | tokens positifs |
|---|---|---|
| 2022 | **−0,53 %** | 48 % |
| 2023 | +8,29 % | 85 % |
| 2024 | **+13,73 %** | 96 % |
| 2025 | +4,09 % | 72 % |
| 2026 | −0,08 % | 50 % |

Le funding est la prime payée par les longs à levier. Elle s'évapore exactement
quand ils se déleveragent.

## La stratégie chiffrée

Short perp + long spot (delta-neutre). Chaque lundi : classement par funding
moyen des 30 jours précédents (décalé d'un jour, aucun futur), on garde les N
plus élevés à funding positif, on conserve ce qui reste sélectionné.

P&L = funding encaissé **+ variation de la base perp/spot** − coûts de rotation.
La base est réellement valorisée sur les deux jambes ; elle coûte **−0,26 pt/an**
(base moyenne −3,9 bps, écart-type 6,8 bps — faible sur des perps liquides).

| N | net/an | vol | Sharpe | MDD | semaines + |
|---|---|---|---|---|---|
| 5 | +6,53 % | 2,67 % | 2,45 | −3,46 % | 85 % |
| **10** | **+7,11 %** | 1,76 % | **4,05** | −1,24 % | 89 % |
| 20 | +7,05 % | 1,74 % | 4,06 | −1,70 % | 89 % |
| 30 | +6,67 % | 1,66 % | 4,01 | −1,69 % | 87 % |

Rotation ≈ 16 %/semaine sur le top 10.

### Résistance aux coûts (top 10)

| hypothèse | net/an | Sharpe |
|---|---|---|
| maker/maker (Hyperliquid) | +8,10 % | 4,63 |
| taker Binance, spread mesuré | +7,11 % | 4,05 |
| **taker, spread ×3 (prudent)** | **+5,72 %** | **3,14** |
| taker ×2, spread ×3 | +4,23 % | 2,28 |
| frais ×4 et spread ×5 | −0,13 % | −0,06 |

Le point mort est autour de frais ×4 / spread ×5. Marge confortable.

### Année par année (top 10, coûts prudents)

| 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|
| **+0,03 %** | +6,27 % | **+13,81 %** | +3,32 % | +2,98 % |

*jusqu'à fin août. Aucune année négative, mais **2022 est plat** : en régime de
déleveragement la prime disparaît.

## Combinaison avec la Kalman

Corrélation hebdomadaire des deux : **−0,185**.

| | rendt/an | vol | Sharpe | MDD |
|---|---|---|---|---|
| Kalman seule | +2,37 % | 2,85 % | 0,83 | −4,60 % |
| carry seul | +5,72 % | 1,82 % | 3,14 | −1,53 % |
| 50 / 50 | +4,04 % | 1,54 % | 2,62 | **−0,75 %** |
| **80 % carry / 20 % Kalman** | **+5,05 %** | 1,46 % | **3,45** | −1,02 % |

Le mélange bat les deux composants en Sharpe. Année par année : +0,99 %,
+5,28 %, +11,07 %, +3,40 %, +2,57 % — cinq années positives.

## Ce qui n'est PAS dans ces chiffres

1. **Le risque de marge.** C'est le vrai risque du cash-and-carry : il n'est pas
   dans le P&L, il est dans l'appel de marge. Si le token s'envole, la jambe
   short perd et il faut reposter, même si le spot gagne en face. Sans marge
   croisée ou portefeuille, on peut être liquidé sur une position pourtant
   neutre. C'est ainsi que meurent les books de base, pas par le P&L.
2. **Le capital réellement immobilisé.** Le rendement est par unité de notionnel.
   Il faut 1× pour le spot plus la marge du perp : à 1,2× de capital déployé,
   les +5,72 % deviennent ~+4,8 % sur capital.
3. **La capacité.** Le funding encaissé dépend de la taille par rapport à
   l'open interest. À taille, on écrase la prime qu'on vient chercher.
4. **L'univers** (30 plus liquides) est choisi sur la liquidité de tout
   l'échantillon. Biais léger — la liquidité est très persistante — mais réel.
5. **C'est un trade encombré.** La quasi-totalité des fonds « market neutral »
   crypto font ça. Les ~5-7 % nets mesurés ici correspondent d'ailleurs à ce que
   ces fonds affichent, ce qui est plutôt un gage de réalisme du chiffrage.
