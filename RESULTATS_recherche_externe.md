# Recherche externe — ce qui a été trouvé

Sources consultées : recherche web (littérature et blogs quant), GitHub. Le proxy
de l'environnement bloque les sites académiques (NBER, arXiv, SSRN, ScienceDirect,
Semantic Scholar) et les blogs (Substack, Medium) ; seuls les hébergeurs de code
sont joignables. Les spécifications ont donc été extraites des résumés de
recherche, puis réimplémentées et testées ici.

## Pistes testées

| piste | source | verdict |
|---|---|---|
| Momentum transversal alts, rebalance hebdo | littérature crypto | **échec** — Sharpe négatif IS et OOS |
| Porte de régime BTC sur facteurs alts | stratégie primée SMU | **échec sur 2022-2026** ; leur 3,72× vient de 2020-21 |
| Momentum géré par le risque (2 sem., vol-scalé) | Finance Research Letters | inclus dans les 266 essais — échec |
| **Filtre de tendance BTC (SMA50)** | le plus ancien du domaine | **RETENU** — voir ci-dessous |

## Le seul résultat qui passe : filtre de tendance sur BTC

Long BTC quand la clôture est au-dessus de sa moyenne 50 jours, cash sinon.
**9 ans d'historique** (BTC spot 2017-08 → 2026-08), coûts 0,20 % par bascule.

| | multiple | rendt/an | vol | Sharpe | t | MDD | Calmar |
|---|---|---|---|---|---|---|---|
| acheter et garder | 18,3× | 37,9 % | 67,0 % | 0,82 | 2,13 | −83,2 % | 0,46 |
| **> SMA50** | **64,6×** | **58,5 %** | 45,9 % | **1,23** | **2,79** | −64,8 % | **0,90** |
| panier BTC+ETH filtré | 76,7× | 61,6 % | 46,5 % | **1,26** | 2,83 | **−56,8 %** | 1,08 |

Environ **10 bascules par an** → durée de détention moyenne ~5 semaines. C'est
bien du swing.

### Ce qui rend ce résultat crédible

1. **Alpha significatif** : régression sur BTC → beta 0,47, alpha +33,5 %/an,
   **t = 3,02**. C'est la seule statistique vraiment significative produite de
   toute la session.
2. **Stable sur les trois sous-périodes**, et bat acheter-garder dans chacune :

   | | 2017-2019 | 2020-2022 | 2023-2026 |
   |---|---|---|---|
   | SMA50 | **+1,19** | **+1,31** | **+1,47** |
   | acheter-garder | +0,68 | +0,76 | +1,14 |

3. **Robuste aux coûts et au retard** : à 0,50 % de coût et 2 jours de retard
   d'exécution, Sharpe encore +0,95 et 20,3× de multiple.
4. **Marche aussi sur ETH seul** : Sharpe 1,07 (t = 2,56) contre 0,71 en
   acheter-garder.
5. Ce n'est **pas une découverte** — c'est la règle la plus testée de l'histoire
   du trading. C'est précisément pour ça qu'elle n'est pas surajustée par moi.

### Ce qui limite ce résultat, et il faut le lire aussi

1. **Le test apparié sur le rendement TOTAL n'est pas significatif** (t = +0,27).
   Le filtre ne bat pas acheter-garder en rendement absolu de façon prouvée ; il
   gagne en **rendement par unité de risque**. C'est une différence réelle.
2. **Le drawdown reste de −65 %.** Ce n'est pas une stratégie confortable.
   Lever ×2 le porte à −90 % : **ne pas lever**.
3. **Les dernières années sont faibles** : 2025 −2,3 %, 2026 +13,2 %. Le résultat
   est porté par 2017, 2020 et 2023.
4. **SMA50 est le meilleur de six longueurs testées** ; SMA200 fait moins bien
   qu'acheter-garder. Il y a donc de la sélection, atténuée par la stabilité sur
   les trois sous-périodes.

### Ce qui NE généralise PAS : les alts

Le même filtre appliqué aux 129 tokens du panel (2022-2026) :

| | résultat |
|---|---|
| améliore le Sharpe | 77/129 = 60 % (Wilcoxon p = 0,033 ; t = +1,59, p = 0,12) |
| **réduit le drawdown** | **121/129 tokens** (médiane −97,3 % → −80,8 %) |
| portefeuille équipondéré, alpha | **−0,7 %/an, t = −0,06** |

**Sur les alts, le filtre coupe le drawdown mais n'apporte aucun alpha.**
L'alpha de +33,5 % est spécifique à BTC et ETH.

À noter au passage : le panier alt équipondéré fait **0,11×** sur 2022-2026, soit
−89 %. C'est la réalité sans biais du survivant de la détention d'alts.

## Conclusion

Ce que la recherche externe a produit de solide, c'est la règle la plus banale du
domaine, appliquée aux deux seuls actifs crypto où elle a de l'alpha. Elle est
exécutable sur un perp DEX (BTC perp, long seul, aucun spot requis), donc
compatible avec la contrainte d'accès.

Et elle s'accorde avec tout le reste de la session : l'edge crypto vit dans la
**tendance de BTC** et dans les **primes structurelles** (funding), pas dans la
sélection d'alts.
