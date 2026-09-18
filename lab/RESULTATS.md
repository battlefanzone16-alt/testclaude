# Cycle 1 — Donchian bidirectionnel a levier de volatilite, BTCUSDT 1 h

Statut : **rejete.** Le profit factor est positif en out-of-sample, et pourtant la
strategie n'est pas exploitable. Ce document explique pourquoi, pour que le cycle
suivant ne recommence pas la meme erreur.

## Protocole

| | fenetre | buy & hold |
|---|---|---|
| Conception (IS) | 2022-01-01 -> 2023-06-30 (18 mois) | **-39.6 %**, DD -68 % |
| Validation forward | 2023-07-01 -> 2026-08-31 (38 mois) | +104.6 %, DD -54 % |
| Validation backward | 2020-01-01 -> 2021-12-31 (24 mois) | +299.5 %, DD -62 % |

Fenetre IS choisie hostile expres : sur une fenetre haussiere, un profit factor
positif ne demontre rien, le buy & hold en fait autant sans strategie.

Couts : bareme Hyperliquid tier de base, taker 4.5 bps + 2 bps de slippage par
cote, funding horaire sur le notionnel porte. Execution a l'ouverture qui suit la
cloture du signal.

## Selection

230 configurations, huit familles. Distribution des PF majoritairement perdante
(mediane 0.91, 29 % au-dessus de 1) — c'est le resultat attendu, et la preuve que
le moteur ne fabrique pas d'edge la ou il n'y en a pas.

Une ile de parametres ressort : canal Donchian bidirectionnel de 192 a 336 heures,
20 cellules entre 1.27 et 1.76 de PF, entouree de ~1.00 en dessous (24-96 h) comme
au-dessus (504 h). Configuration gelee au **centre** de l'ile (240 h / 24 h), pas
a son maximum, plus un levier inverse a la volatilite qui ameliore les 20 cellules.

## Resultats

| | PF | net | Sharpe | DD | trades |
|---|---|---|---|---|---|
| IS 2022-01 -> 2023-06 | 1.53 | +61.3 % | 1.27 | -23.6 % | 85 |
| OOS forward | 1.25 | +35.0 % | 0.48 | -24.4 % | 204 |
| OOS backward | 1.09 | -1.4 % | 0.13 | -37.1 % | 140 |

Memes parametres, autres actifs, OOS forward : ETH 1.45, SOL 1.43, XRP 1.44,
BNB 1.09.

## Pourquoi c'est rejete

1. **Le P&L tient a trois trades.** Sur l'OOS forward, les 3 meilleurs trades sur
   204 rapportent +57 %, pour un total de +56 %. Les 201 autres perdent ensemble
   plus que tout ce que la strategie gagne. Une queue epaisse est normale en
   suivi de tendance ; dependre de trois tirages sur trois ans ne l'est pas.
2. **L'intervalle de confiance du PF contient 1.** Bootstrap sur les trades :
   [0.87 ; 1.77] en forward, [0.67 ; 1.64] en backward. Le PF de 1.25 n'est pas
   distinguable de 1.00.
3. **Une heure de retard tue le resultat.** Avec une barre d'execution en plus,
   l'OOS forward passe de +35.0 % a -0.9 %. 26 % du P&L se fait dans la premiere
   heure suivant l'entree : c'est un preneur de burst, pas un suiveur de tendance,
   et le burst est precisement le moment ou le slippage reel se creuse.
4. **Le buy & hold fait mieux.** +104.6 % contre +35.0 %, Sharpe 0.72 contre 0.48.
   Seul le drawdown est deux fois plus petit (-24 % contre -54 %) — insuffisant
   pour justifier le travail.
5. **Le cote short ne sert a rien.** 88 trades, +1.9 % en 38 mois, PF 1.02. Il
   ajoute des couts et du risque, pas du rendement.
6. **Le critere trimestriel pre-enregistre etait deja manque en IS** (4 trimestres
   positifs sur 6, au lieu de 5). Signale avant la mesure OOS, non reecrit apres.

## Ce que le cycle apprend

- Le screen large a fonctionne comme filtre : sur 230 essais, presque tout perd,
  et ce qui survit a l'IS meurt correctement en OOS. L'infrastructure est saine.
- Le suivi de tendance mono-actif sur BTC est **statistiquement sous-dimensionne** :
  204 trades dont 3 comptent. La diversification entre actifs n'est pas un confort
  dans ce style, c'est la condition de son existence — ce que confirment les
  PF ~1.44 obtenus simultanement sur ETH, SOL et XRP avec les memes parametres.
- Le funding (+11.8 %/an paye par les longs sur BTC) n'a PAS ete le probleme ici :
  l'exposition de 29 % et les passages short le ramenent a un cout quasi nul.
  Le vrai cout est transactionnel : 29.8 % de capital en frais sur 38 mois.

---

# Cycle 2 — Cascade de liquidations, BTCUSDT 5 min

Statut : **rejete en in-sample.** Les actifs de validation n'ont pas ete ouverts :
rien n'a atteint le stade du gel, donc AVAX, LINK et DOGE restent vierges pour un
cycle ulterieur.

## Donnee

Le flux des liquidations n'est pas archive par Binance. Substitut retenu :
l'**open interest au pas de 5 minutes** (archives `metrics`, disponibles depuis
2021). Une position liquidee disparait de l'open interest ; une vente deliberee
non. C'est cette difference qui devait separer le signal d'un simple
"acheter les baisses".

## Hypothese 1 — fader la cascade

Acheter apres une chute rapide accompagnee d'une baisse d'open interest.

**Faux, et uniformement faux** : profit factor de 0.51 a 0.79 sur les 27 cellules
de la grille. Avant meme les couts, le gain median par trade est de **-0.018 %**.
Ce n'est donc pas un edge mange par les frais, c'est l'absence d'edge. Les seules
cellules positives en brut (horizon de 5 minutes, cote short) rapportent 4.5 bps
par trade contre 13 bps de couts aller-retour.

## Hypothese 2 — suivre la cascade

Si acheter la cascade perd uniformement, c'est que le mouvement continue : une
liquidation declenche le palier de marge suivant. On teste le miroir.

Premiere lecture encourageante : a fenetre de detection d'une heure, profit factor
de 1.26 a 1.63 sur les huit cellules. Mais le balayage fin de la fenetre et du
seuil montre un damier, pas un plateau, et surtout ceci :

| trades minimum | configs | PF median |
|---|---|---|
| >= 50 | 162 | 1.21 |
| >= 100 | 115 | 1.12 |
| >= 150 | 71 | 1.05 |
| >= 200 | 38 | 1.00 |
| >= 300 | 8 | **0.98** |

**Correlation entre log(nombre de trades) et profit factor : -0.78.** Le profit
factor ne mesure pas un edge, il mesure la raretes des trades. Les cellules a
PF 2.14 et 2.66 comptent 59 et 38 trades. A 300 trades, il ne reste rien.

Zero configuration sur 180 passe les criteres pre-enregistres ; les vingt qui
franchissent le PF et le nombre de trades echouent toutes la coherence
trimestrielle (3 ou 4 trimestres positifs sur 6).

518 configurations testees au total sur ce cycle, toutes familles confondues.

## Ce que les deux cycles disent ensemble

1. **Le mono-actif est la contrainte qui tue, pas le manque d'idees.** Le cycle 1
   a trouve un edge de tendance reel mais sous-dimensionne : 204 trades dont 3
   font tout le resultat. Le cycle 2 a cherche du cote des horizons courts, la ou
   les trades sont nombreux — et a la ou le nombre de trades devient suffisant
   pour conclure (300+), le profit factor vaut 0.98.
2. **Les memes parametres de tendance sortaient PF 1.43-1.45 simultanement sur
   ETH, SOL et XRP.** Un edge faible mesure sur quatre actifs a la fois est plus
   solide qu'un edge fort mesure sur un seul.
3. **Le profit factor seul ne decide de rien.** Les deux cycles ont produit des PF
   superieurs a 1 qui ne valaient rien : l'un porte par trois trades, l'autre par
   la raretes des trades. Un PF doit toujours etre lu avec son nombre de trades,
   son intervalle de confiance et sa sensibilite a une barre de retard.
