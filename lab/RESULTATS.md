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
