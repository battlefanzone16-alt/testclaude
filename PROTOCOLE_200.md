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

---

# RÉSULTAT — 266 essais, aucun retenu

266 essais lancés (133 signaux × 2 constructions), 256 valides après la
contrainte de durée ≥ 2 jours.

## Le seuil de bruit, calculé avant d'ouvrir l'OOS

| | |
|---|---|
| meilleur Sharpe IS obtenu | **+0,877** |
| erreur-type d'un Sharpe sur 2,67 ans | 0,720 |
| **maximum attendu de 266 essais de PUR BRUIT** | **+2,058** |
| Sharpe déflaté du meilleur essai | **0,051** |

Le meilleur des 266 est **très en dessous** de ce que produirait le hasard.
Médiane des 256 essais : −0,53. Positifs : 52/256.

## La validation OOS, ouverte une seule fois

| corrélation de rang IS → OOS sur les 20 meilleurs | **+0,024** |
|---|---|
| essais avec Sharpe IS > 0,50 **et** OOS > 0,50 | **0 / 20** |

Le classement IS n'a aucun pouvoir prédictif sur l'OOS. C'est le même constat
que pour le classement par token : on classe du bruit.

## Verdict

**Aucun essai ne remplit la règle fixée d'avance.** Les trois conditions
échouent, et la première échoue si largement que les autres sont superflues.

## Ce que la recherche apprend quand même

Familles systématiquement perdantes (Sharpe IS médian) : volume en pic −2,21 ·
nombre de transactions −2,20 · efficience −1,27 · divergence flux/prix −0,92 ·
**momentum −0,78** · proximité au plus haut −0,69 · flux taker −0,49.

Le momentum et les signaux de flux, très populaires, sont parmi les pires.

Seule famille au Sharpe IS médian positif : la **faible volatilité** (+0,25), et
elle est positive des deux côtés sur ses sept variantes :

| signal | IS | OOS |
|---|---|---|
| vol_basse_90 | +0,43 | +0,90 |
| vol_basse_60 | +0,37 | +0,87 |
| max_neg_20 | +0,45 | +0,60 |
| skew_neg_60 | +0,64 | +0,40 |

C'est l'anomalie de faible risque, bien documentée hors crypto. Mais elle ne
passe pas non plus : le composite des trois donne un Sharpe total de **+0,35**,
donc **moins bon que ses composants** — signature d'un effet qui n'est pas
partagé — avec un alpha à t = +0,78 et des années en dents de scie
(+1,40 · −1,08 · −0,56 · +1,11 · +0,67).

## La leçon, et elle vaut plus que les 266 essais

La recherche aveugle à grande échelle n'a rien produit, alors que le travail sur
la Kalman a produit un effet qui **généralise** (−0,10 → +0,93 sur 2,7 ans jamais
regardés). La différence n'est pas la chance : c'est que les améliorations de la
Kalman corrigeaient des **défauts identifiés par un mécanisme** — un stop posé
sur un niveau qu'on vient de visiter, une cassure d'une seule mèche, un sens de
trade jeté — et non le maximum d'un balayage.

Chercher le maximum de 266 essais, c'est chercher le bruit. Corriger une erreur
qu'on sait nommer, c'est autre chose.
