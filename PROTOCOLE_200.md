# Protocole de recherche — 200 essais

Fixé **avant** toute recherche. Aucune règle ci-dessous ne sera modifiée après
avoir vu les résultats.

## Découpage
- **IS (recherche)** : 2022-01-01 → 2024-08-31 — 2,7 ans. Seule période regardée
  pour classer les 200 essais.
- **OOS (validation)** : 2024-09-01 → 2026-09-12 — 2,0 ans. Ouvert **une seule
  fois**, à la fin, sur les candidats déjà sélectionnés.

## Univers
Point-in-time : les 40 plus gros volumes en dollars sur 30 jours glissants,
reclassés chaque mois, tirés des 130 perps listés en 2022. Aucun biais du
survivant, aucun futur dans le classement.

## Coûts
Frais 0,086 % aller-retour + spread mesuré ×3, appliqués à la **rotation**
(|Δposition|). Identiques pour tous les essais.

## Contrainte « swing »
Signal quotidien, durée de détention médiane ≥ 2 jours. Pas de scalping.

## Règle de décision — fixée d'avance
Un essai n'est retenu que si **les trois** conditions sont réunies :
1. Sharpe IS > 0,50
2. Sharpe OOS > 0,50
3. Sharpe déflaté (Bailey & López de Prado, **N = 200**) > 0,50

Le seuil de bruit à battre : le maximum attendu de 200 essais de pur bruit sur
4,7 ans vaut environ **1,6 de Sharpe**. Tout candidat en dessous est ininterprétable.

## Ce que ce protocole ne corrige pas
J'ai déjà vu les deux périodes au cours des travaux précédents. Le découpage
IS/OOS limite le surajustement **de cette recherche-ci**, il n'efface pas mon
exposition antérieure aux données. À garder en tête dans la lecture finale.
