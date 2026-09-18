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

---

# Cycle 3 — Rotation de value area (profil de volume), BTC/AVAX/LINK/DOGE

Regle testee, telle qu'enoncee : profil de volume entre un plus bas et un plus
haut ; le prix cloture sous la VAL pendant deux bougies ; des qu'il repasse
au-dessus de la VAL on est long, objectif la VAH. Symetrique au-dessus de la VAH.

Le profil est construit a partir des bougies **5 minutes**, pas des bougies de
signal : douze points de mesure par heure valent mieux qu'un volume horaire pose
au prix typique. Value area a 70 % du volume autour du POC, methode standard.

## Premiere lecture, encourageante

La regle telle quelle (H1, profil 10 jours, deux bougies) donne en plein bear
2022 : **cote long PF 1.15**, 105 trades, 29 % de reussite, duree mediane 7 h,
pendant que le buy & hold perd 39.6 %. Cote short, PF 0.90.

Le balayage de 360 configurations fait mieux : **13 passent tous les criteres
pre-enregistres**, la meilleure a PF 1.59, Sharpe 1.06, drawdown -19 %, 81 trades
et 5 trimestres positifs sur 6. Les cycles 1 et 2 n'en avaient laisse passer
aucune. A ce stade, la regle semblait tenir.

## Ce qui l'a tuee : le nombre de bins

Le nombre de bins du profil est un choix d'affichage. Il ne change pas le marche,
il change la resolution du dessin. Or :

| bins | 30 | 40 | 50 | **60** | 80 | 100 | 150 |
|---|---|---|---|---|---|---|---|
| PF | 1.28 | 1.17 | 1.22 | **1.59** | 1.00 | 1.03 | 1.41 |

Et la meme instabilite sur la profondeur du profil, a un jour pres :

| lookback | 8 j | 9 j | **10 j** | 11 j | 12 j |
|---|---|---|---|---|---|
| PF | 1.14 | 1.08 | **1.59** | 1.11 | 0.98 |

Une regle dont le resultat change quand on redessine le meme graphique n'a pas
d'edge : elle a de la variance. La configuration a 1.59 n'etait pas le bon
reglage, c'etait le sommet d'une distribution.

## Le test qui tranche : l'ensemble sans parametre

Pour savoir si la FAMILLE porte un edge, on cesse d'elire un reglage : 216
variantes (9 profondeurs x 4 resolutions x 2 invalidations x 3 durees maximales)
votent, et la position est la moyenne des votes. Plus aucun parametre n'est
choisi, donc plus aucun accident de grille n'est possible.

Dispersion des 216 variantes prises isolement, cote long, in-sample :
**PF median 1.02, quartiles 0.91-1.17, 55 % au-dessus de 1.** Un pile ou face.

## Le verdict, sur quatre actifs et sept ans

L'ensemble n'ayant aucun parametre libre, il n'y a rien a geler et rien a
consommer : chaque mesure est un test d'hypothese, pas une selection. On peut
donc regarder partout.

Profit factor net, long + short :

| | BTC | AVAX | LINK | DOGE | mediane |
|---|---|---|---|---|---|
| bear 2022 -> mi 2023 | 1.01 | 0.78 | 0.77 | 0.55 | **0.78** |
| mi 2023 -> aout 2026 | 0.68 | 0.95 | 0.90 | 0.77 | **0.83** |

**Huit combinaisons sur huit sont en dessous de 1.** Le seul 1.01 est sur l'actif
et la fenetre ou la regle a ete reglee.

## La nuance qui compte : la regle n'est pas fausse, elle est vide

Avant couts :

| | PF brut | PF net | gain brut par trade |
|---|---|---|---|
| BTC, bear 2022 | 1.21 | 1.01 | +0.074 % |
| BTC, 2023-2026 | 0.87 | 0.68 | -0.038 % |
| LINK, bear 2022 | 0.86 | 0.77 | -0.074 % |
| LINK, 2023-2026 | 1.02 | 0.90 | +0.010 % |

Gain brut moyen par trade : **-0.007 %**, soit zero. La rotation de value area
n'est pas anti-predictive, elle est **non predictive** : la sortie puis le retour
dans la zone ne dit rien de plus que le hasard sur la suite. Les 13 bps de couts
aller-retour font le reste, et ils sont lourds : **45 % du capital en frais** sur
la periode 2023-2026, pour une exposition moyenne de 27 %.

## Ce que ce test ne prouve PAS

Trois reserves honnetes, qui limitent la portee du verdict :

1. **Le profil est ancre sur une fenetre glissante, pas sur un swing choisi.**
   Un operateur qui selectionne a l'oeil "le bon" plus bas et "le bon" plus haut
   fait quelque chose que cette implementation ne reproduit pas. C'est la
   difference la plus serieuse, et elle est testable : il suffit d'ancrer le
   profil sur des points de retournement detectes (ZigZag) plutot que sur les
   N derniers jours.
2. **Crypto perps, H1 et H4, 2022-2026.** La regle vient des futures actions et
   indices, ou la seance a un debut, une fin et une cloture. Un marche ouvert
   24/7 n'a pas de value area quotidienne au sens de Steidlmayer.
3. **Aucun filtre de contexte.** Ni tendance, ni volatilite, ni regime. La regle
   a ete prise seule, comme enoncee.
