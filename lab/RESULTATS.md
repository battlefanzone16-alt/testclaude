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

---

# Cycle 3 bis — Le prix exact de "a l'oeil je sais ou poser mon VP"

La reserve principale du cycle 3 etait que le profil y est ancre sur une fenetre
glissante, alors qu'un operateur choisit ses bornes : un plus bas, un plus haut.
On a donc ancre le profil exactement comme enonce — entre le dernier plus bas et
le dernier plus haut — et mesure la MEME strategie deux fois :

- **causale** : un swing n'existe qu'une fois confirme par un retracement du seuil ;
- **a l'oeil** : le swing est disponible des la bougie ou il se forme, comme sur
  un graphique termine.

Seule cette disponibilite change. Ni la regle, ni les couts, ni la donnee.

## Ce que l'oeil s'offre : la mesure du decalage

| seuil de swing | swings sur 18 mois | retard median de confirmation | 90e centile |
|---|---|---|---|
| 2 % | 1 440 | 1 barre | 9 |
| 3 % | 658 | 3 barres | 19 |
| 5 % | 245 | **10 barres** | 49 |
| 8 % | 91 | **30 barres** | 137 |
| 12 % | 40 | **82 barres** | 236 |

A 12 %, un plus haut n'est connaissable que **trois jours et demi** apres sa
formation. Sur un graphique termine, il saute aux yeux instantanement.

## Le resultat, ensemble sans parametre (72 variantes par sens)

| actif | periode | PF causal | PF a l'oeil | Sharpe a l'oeil | DD a l'oeil |
|---|---|---|---|---|---|
| BTC | bear 2022 | 1.10 | **3.32** | 6.21 | -5 % |
| BTC | 2023-2026 | 0.74 | **2.61** | 4.37 | -5 % |
| LINK | bear 2022 | 0.78 | **3.07** | 8.47 | -14 % |
| LINK | 2023-2026 | 0.81 | **2.79** | 7.07 | -10 % |
| AVAX | bear 2022 | 0.91 | **2.82** | 7.85 | -10 % |
| AVAX | 2023-2026 | 0.90 | **3.14** | 8.22 | -8 % |

Mediane causale : **0.86**. Mediane a l'oeil : **2.95**, avec des rendements
allant jusqu'a +84 577 % et des Sharpe de 4 a 8.

## Ce qu'il faut en retenir

Un Sharpe de 8 avec 8 % de drawdown maximal sur de l'altcoin perpetuel n'existe
pas. C'est la signature d'une fuite d'information, et ici on sait exactement
laquelle : quelques dizaines d'heures d'avance sur la confirmation d'un swing.

**L'ecart entre 0.86 et 2.95 ne mesure pas une competence de lecture. Il mesure
la valeur de connaitre la suite.** C'est pour cela qu'une conviction batie en
faisant defiler des graphiques passes ne peut pas servir de preuve, quelle que
soit la qualite de l'operateur : le graphique montre le resultat en meme temps
que le setup, et l'oeil ne sait pas separer les deux.

Cela ne demontre pas qu'un placement discretionnaire n'a aucune valeur. Cela
demontre qu'aucun examen retrospectif ne peut l'etablir. Le seul protocole valide
est prospectif : horodater les bornes du profil AVANT le mouvement, puis mesurer.

## Heuristique a garder

Devant un backtest crypto qui affiche un Sharpe superieur a 3 et un drawdown
inferieur a 15 %, ne pas chercher pourquoi il est bon : chercher par ou
l'information fuit. Ici, la fuite tenait en une seule ligne de code — le moment
ou un swing devient connaissable.

---

# Cycle 4 — VP hebdomadaire fixe : un edge reel, plus petit que les frais

Idee de l'utilisateur, et c'est la bonne : au lieu de deviner un plus bas et un
plus haut, **fixer le profil sur la semaine calendaire** — lundi 00h00 au
dimanche 23h59 UTC — et l'appliquer a la semaine suivante. Les bornes sont alors
connues a la seconde ou on s'en sert. Aucune fuite d'information n'est possible,
aucun swing a confirmer, aucun jugement a porter.

## La logique se verifie-t-elle ? Mesure brute, sans strategie ni couts

3 396 declenchements sur cinq actifs et cinq ans (BTC, ETH, LINK, AVAX, DOGE) :
deux clotures hors de la value area de la semaine precedente, puis retour, puis
on note lequel de l'objectif (le bord oppose) ou de l'invalidation (l'extreme de
l'excursion) arrive le premier.

Taux de reussite global **34.2 %** pour un seuil d'equilibre de 30.1 % au R
median — apparemment gagnant, p < 0.001. **Et pourtant l'esperance vaut
-0.055 R**, negative, IC 90 % bootstrap [-0.103 ; -0.005].

Le piege : le seuil d'equilibre se calcule sur le R MEDIAN, mais le R varie
d'un cas a l'autre, et il varie contre nous.

| quintile de R | cas | reussite | seuil | stop median | esperance |
|---|---|---|---|---|---|
| R tres bas (stop large) | 680 | 68.4 % | 64.6 % | 6.48 % | **+0.006 R** |
| R bas | 679 | 44.3 % | 42.9 % | 3.90 % | **+0.025 R** |
| R moyen | 679 | 30.9 % | 30.1 % | 2.55 % | **+0.016 R** |
| R haut | 679 | 17.8 % | 20.7 % | 1.77 % | -0.136 R |
| R tres haut (stop serre) | 679 | 9.4 % | 11.0 % | 1.01 % | -0.188 R |

Quand le prix n'est descendu qu'a peine sous la VAL, le stop colle a l'entree :
le R affiche est magnifique et le stop saute presque a coup sur. Ce sont ces cas
qui plombent la moyenne. **Les trois premiers quintiles sont positifs.**

## L'edge existe. Il est plus petit que les frais.

Le cout d'un aller-retour Hyperliquid (13 bps) exprime dans l'unite de risque de
chaque quintile :

| quintile | 1 R vaut | cout en R | edge | net |
|---|---|---|---|---|
| R tres bas | 6.48 % | 0.020 R | +0.006 R | **-0.014 R** |
| R bas | 3.90 % | 0.033 R | +0.025 R | **-0.008 R** |
| R moyen | 2.55 % | 0.051 R | +0.016 R | **-0.035 R** |

Le backtest complet, ensemble de 18 variantes par sens sans parametre elu, dit
exactement la meme chose :

| | PF brut | PF net | couts |
|---|---|---|---|
| mediane 2022-01 -> 2023-06 | 1.01 | 0.91 | 22 % du capital |
| mediane 2023-07 -> 2026-08 | **1.10** | 0.99 | **48 % du capital** |

Sur 2023-2026, quatre actifs sur cinq ont un profit factor brut superieur a 1
(ETH 1.17, AVAX 1.19, DOGE 1.10, LINK 1.03, BTC 0.83).

## Ce qui change tout par rapport aux cycles precedents

Les cycles 1 a 3 butaient sur l'absence de signal. Ici le signal existe et le
probleme est **le cout par trade**. C'est un probleme d'ingenierie, pas de
marche, et il a trois leviers connus :

1. **Entrer en limite, pas au marche.** L'entree de cette regle est un NIVEAU DE
   PRIX connu une semaine a l'avance, pas un evenement a poursuivre. C'est le
   seul cas ou supposer un fill maker est defendable : on pose l'ordre a la VAL
   et on attend que le prix vienne. Maker 1.5 bps contre taker 4.5 bps.
2. **Ne prendre que les excursions profondes.** Le quintile "R bas" a une
   esperance de +0.025 R pour un cout de 0.033 R en taker, mais de 0.013 R en
   maker — soit **+0.012 R net**. Reserve : ce quintile a ete choisi apres avoir
   vu les resultats, il lui faut sa propre validation.
3. **Reduire la rotation.** 48 % du capital en frais sur trois ans pour 27 %
   d'exposition moyenne : c'est le nombre de trades qui coute, pas leur taille.

---

# Cycle 5 — Entree en ordre limite : le signe bascule, la significativite non

Le cycle 4 laissait un signal reel mange par les frais taker. L'entree de la
regle etant un NIVEAU connu une semaine a l'avance, on peut la travailler en
passif — c'est le seul cas de toute cette etude ou supposer un fill maker se
defend.

## Le point de microstructure qui commande tout

Un achat limite pose AU-DESSUS du prix courant est marketable : il traverse le
spread et paie le taker. Poser un achat a la VAL pendant que le prix est SOUS la
VAL ne donne donc aucun rabais.

La seule construction reellement passive : attendre que la bougie cloture
au-dessus de la VAL, puis poser l'achat a la VAL — le prix est alors au-dessus du
niveau, l'ordre est passif, et il se remplit si le prix y revient. On entre sur
le repli vers le niveau, pas sur la cassure. **On rate donc les setups qui ne
reviennent jamais**, et le simulateur doit le compter : c'est le prix de la
patience. Taux de remplissage mesure : **73 a 77 %**.

Il en decoule un moteur evenementiel (lab/execution_limite.py) : le moteur
vectoriel suppose qu'une position voulue est obtenue, ce qui est faux pour un
ordre limite. Frais differencies : entree maker 1.5 bps, objectif maker 1.5 bps
(vente limite passive), stop et sortie par le temps en taker 4.5 bps + slippage.

## Ce qui n'a pas marche

- **Le filtre de profondeur d'excursion** : PF median 0.96 / 0.91 / 0.99 / 0.92 /
  0.88 pour des seuils de 0 a 5 %. L'idee tiree du quintile de R ne se transpose
  pas.
- **L'objectif au POC plutot qu'au bord oppose** : 0.92 contre 0.93 sur les
  actifs de conception, 1.09 contre 1.07 sur les autres. Indifferent.
- **L'hypothese volatilite**, avancee pour expliquer pourquoi les actifs jamais
  mesures faisaient mieux (mediane 1.07, 7/9 au-dessus de 1) que les actifs de
  conception (0.93, 4/10) : correlation de rang entre largeur de value area et
  profit factor **-0.15, p = 0.53**. Aucune relation. L'ecart etait du hasard.

## Ce qui a marche

L'ordre limite ameliore 7 cas sur 10 et divise les frais par 1.7. Surtout, il
change le signe de l'esperance.

Agregat de **2 556 trades**, dix actifs, cinq ans :

| | par trade |
|---|---|
| brut | **+0.066 R** |
| frais maker | -0.036 R |
| **net** | **+0.032 R** |

Profit factor global **1.022**. En taker, les frais auraient coute 0.075 R et le
net aurait ete de **-0.009 R**.

## Pourquoi ce n'est pas encore une strategie

Ecart-type de 1.94 R par trade, donc t = +0.83 et **p = 0.404**. L'esperance
n'est pas distinguable de zero. Pour detecter +0.032 R avec cette dispersion a
80 % de puissance, il faudrait environ **29 000 trades** : on en a 2 556.

Et un profit factor de 1.022 tient a l'interieur des barres d'erreur du modele de
couts lui-meme : changer l'hypothese de slippage d'un seul point de base deplace
le resultat de facon comparable a l'edge mesure.

Conclusion : la regle, exécutée en passif sur un profil hebdomadaire fixe, est a
l'equilibre. Ce n'est plus une perte — c'est le premier resultat non negatif de
toute l'etude — mais l'edge devrait environ **tripler** pour sortir du bruit.
