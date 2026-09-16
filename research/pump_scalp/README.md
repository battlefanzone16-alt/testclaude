# Scalp de pump sur perps crypto — étude et backtest

**Verdict.** Le mouvement est bien prévisible, faiblement : +8 à +10 bps sur 5
à 15 minutes en temps-tick, avec t ≈ 2,6. Mais ce gisement fait **exactement la
taille de la friction**, et de quel côté de zéro on tombe ne dépend pas du
signal — cela dépend de la grille tarifaire, de la priorité dans la file
d'ordres et de la latence (§1 octies). Aucun discriminant ne permet de trier les
mouvements à l'avance : ni les klines (§1 à §7), ni l'open interest (§1 ter), ni
le flux d'ordres (§1 quater). Trois biais de look-ahead ont fabriqué trois faux
résultats en cours de route ; les débusquer est l'essentiel de ce qu'il y a à
retenir ici. Ce document montre comment j'y arrive et
ce qui est mort en route — quatre stratégies, trois biais de look-ahead dont
deux à moi, et le piège de pondération qui invalidait la moitié de mes chiffres.

Données : 525 perps USDT (univers screené séparément sur chaque période),
bougies 1 minute, **2024-09-01 → 2026-09-01** (24 mois, ~11 Go), plus l'open
interest et les ratios long/short au pas 5 min, la prime perp et les klines
spot. Source : `data.binance.vision`.

---

## 1. Le résultat en une ligne

| | |
|---|---|
| Edge brut de la meilleure règle | **+19,5 bps par trade** |
| Seuil de rentabilité | **9,7 bps par côté** |
| Frais taker Binance seuls | 4,5 bps par côté |
| Budget de slippage restant | **5,2 bps par côté** |

5,2 bps de slippage pour entrer au marché dans une bougie verticale d'un alt —
c'est-à-dire au pire moment du carnet, quand tout le monde achète en même temps.
Ce n'est pas atteignable. Et même en supposant un slippage **nul**, le t-stat de
la stratégie est de 1,14 : non significatif.

Sur 64 combinaisons de règles de sortie testées : 61 sont positives en brut
(médiane +5,8 bps), **1 seule** est positive en net (+0,5 bps, t = 0,0).

Ce n'est pas un problème d'exécution qu'on pourrait régler avec un meilleur
routage. C'est un problème d'alpha : il n'y en a pas assez.

---

## 1 bis. Le résultat à l'horizon visé : positions de 1 h à 4 h

C'est la lecture qui compte, et la première version de ce rapport l'enterrait
sous un aparté journalier. **Toute l'étude est à cet horizon** : les rendements
forward sont mesurés à 5, 15, 30, 60, 120 et 240 minutes, et le backtest tient
des positions de 30 minutes à 4 heures. Rien ici ne tient une position des jours.

Long après ignition, 3 positions simultanées maximum, taker 4,5 bps + 5 bps de
slippage par côté (`scalp_horizons.py`) :

| Durée max | Meilleure règle, brut | Meilleure règle, net | t | Médiane des 8 règles, net | Règles net > 0 | OOS |
|---|---|---|---|---|---|---|
| **1 h** | +10,5 bps | **−8,5 bps** | −1,4 | −11,5 | 0/8 | −17,3 |
| **2 h** | +17,6 bps | **−1,4 bps** | −0,2 | −4,3 | 0/8 | −15,6 |
| **3 h** | +21,1 bps | **+2,1 bps** | 0,2 | −2,1 | 3/8 | −14,8 |
| **4 h** | +19,5 bps | **+0,5 bps** | 0,0 | −6,5 | 1/8 | −8,2 |

Trois lectures :

- **Le brut augmente avec la durée** (+10,5 → +21,1 bps) : le mouvement continue
  bien au-delà de l'heure. La dérive existe, elle est simplement trop lente par
  rapport au péage.
- **1 heure est la pire durée.** Tu paies le coût complet avant que le mouvement
  n'ait eu le temps de payer. Si tu devais en garder une, ce serait 3 h — mais
  à +2,1 bps avec t = 0,2, ce n'est pas un edge, c'est zéro.
- **Hors échantillon, chaque durée est négative** (−8 à −17 bps). Et retirer le
  10 octobre ne change quasiment rien ici (colonne `net_sans_10oct` dans
  `scalp_par_duree.csv`) : contrairement à l'event study brute, le backtest
  sous contrainte de portefeuille n'était déjà pas porté par l'anomalie.

Le win rate tourne autour de 35–42 % avec un trailing stop : profil normal d'un
suiveur de momentum, où l'espérance vit dans la queue droite. Sauf qu'ici la
queue droite ne paie pas le péage.

---

## 1 ter. L'open interest : un discriminant qui n'en était pas un

Cette section a d'abord conclu l'inverse. Je la laisse entière parce que la
façon dont elle s'est effondrée est le résultat le plus utile de l'étude.

### Ce que je croyais avoir trouvé

L'open interest semblait séparer nettement les bons mouvements des mauvais. Un
pump où l'OI explose pendant la rafale continuait ; un pump où l'OI stagne, non.
Avec `ΔOI > +1 %` sur la fenêtre de rafale : **+31,6 bps nets par épisode,
t = 2,44, 17/24 mois positifs**, le contrôle inverse négatif, une dose-réponse
monotone, 16/16 règles de sortie positives y compris après retrait des trois
meilleurs mois. Tous les tests qui avaient tué les candidats précédents, il les
passait.

### Comment j'ai daté l'instantané

Restait une question que je ne savais pas trancher : la ligne d'open interest
étiquetée 21:45 décrit-elle l'état **à** 21:45, ou à la fin d'une fenêtre ? Une
corrélation décalée ne départageait pas (0,0439 à k=0 contre 0,0471 à k=+1).

La réponse était dans le fichier lui-même. Il contient l'OI en contrats **et**
en dollars : leur rapport est le **prix au moment exact du relevé**. Il suffit
de comparer ce prix implicite aux klines 1 minute, dont l'horodatage ne souffre
aucune ambiguïté.

| Décalage testé | 0 min | +3 min | **+4 min** | +5 min |
|---|---|---|---|---|
| Écart médian prix implicite / kline | 16,6 bps | 7,8 bps | **1,2 bps** | 9,2 bps |

Le minimum est net, et quasi exact (0,06 bps sur BTC). **La ligne étiquetée T
est un instantané pris à T+5.**

Donc, pour un signal à 21:47, je lisais l'OI de 21:50 comparée à celle de 21:45 :
je mesurais la variation d'open interest dans les cinq minutes **suivant** le
signal. Autrement dit « le pump continue-t-il quand les gens continuent
d'acheter ? ». Oui, évidemment — et c'est injouable.

### Ce qu'il reste une fois l'alignement corrigé

En n'utilisant que les lignes publiées avant le signal (retard de 5 min sur la
série étiquetée) :

| | Fuite (retard 0) | **Causal (retard 5 min)** |
|---|---|---|
| Net par épisode | +31,6 bps | +22,5 bps |
| t | 2,44 | **0,93** |
| Mois positifs | 17/24 | 12/24 |
| Sans les 3 meilleurs mois | +19,5 | **−16,4** |
| 2024-25 / 2025-26 | +18,1 / +43,4 | **−42,4 / +77,6** |
| Sorties positives après retrait des 3 meilleurs mois | 16/16 | **0/16** |
| Sorties positives sur les deux périodes | 16/16 | **0/16** |

La dose-réponse cesse d'être monotone, les deux périodes se contredisent
frontalement, et aucune des seize règles de sortie ne survit. **Il n'y a pas de
discriminant.** Le troisième look-ahead de cette étude, et le plus coûteux.

### Ce qui reste vrai malgré tout

- Le test du prix implicite (`resolve_timestamp.py`) est réutilisable : il date
  n'importe quel instantané d'open interest à la minute près, sans dépendre de
  la documentation.
- La question « l'OI en temps réel porte-t-elle un signal ? » reste **ouverte et
  non tranchée par ces données**. L'archive ne publie que des instantanés au pas
  de 5 minutes ; un opérateur interrogeant l'OI instantanée aurait une donnée
  plus fraîche que mon retard causal, sans pour autant disposer du futur. Mon
  résultat à retard 0 n'est pas un argument en sa faveur : il utilisait des
  informations postérieures au signal, que ce même opérateur n'aurait pas.

---

## 1 quater. Le flux d'ordres tick par tick : rien non plus

Dernière source disponible, et la seule immunisée au biais qui a tué l'open
interest : les `aggTrades` portent un horodatage à la milliseconde, il n'y a
rien à supposer sur leur alignement. 6 209 ignitions, 3 798 jours de trades
streamés (téléchargés, agrégés, jetés — sinon ça ne tient pas sur le disque).

Six hypothèses, direction posée avant le test : déséquilibre agressif à l'achat,
gros ordres acheteurs, print unique dominant, impact par unité de volume,
accélération de l'arrivée des ordres, flux réparti plutôt qu'en à-coups.

**Résultat : 0/10 filtres nets positifs avec IS et OOS positifs à 60 min**, 1/10
à 120 min — et celui-là va dans le sens inverse de l'hypothèse. Les gradients
par quintile sont du bruit pur (pour le déséquilibre acheteur : +15,5, +36,4,
−41,1, +9,3, +25,2 bps).

---

## 1 quinquies. Le chiffre qui clôt la question : le slippage réel

Toute l'étude compare un gisement brut à un péage supposé de 19 bps, dont 5 bps
de slippage par côté. **Ce 5 bps était une hypothèse de travail, jamais
vérifiée** — et c'est le nombre qui décide de tout.

Les ticks permettent enfin de le mesurer : on rejoue un ordre au marché de X
dollars au moment du signal, en consommant les trades agressifs réellement
survenus, et on compare le prix moyen obtenu au dernier prix affiché. Mesuré sur
**1 520 ignitions de plus de 8 %** :

| Taille de l'ordre | Médiane | Moyenne | p75 | p90 |
|---|---|---|---|---|
| 1 000 $ | 1,6 bps | 2,1 | 6,2 | 12,2 |
| 5 000 $ | 4,6 bps | 5,5 | 11,8 | 23,9 |
| **10 000 $** | **6,8 bps** | 8,0 | 17,1 | 32,2 |
| 25 000 $ | 12,5 bps | 16,6 | 29,1 | 55,7 |
| 50 000 $ | 20,7 bps | 33,1 | 49,1 | 88,4 |
| 100 000 $ | 37,9 bps | 56,7 | 79,8 | 146,7 |

C'est une **borne inférieure** : on consomme le flux qui s'est effectivement
produit, sans compter que notre propre ordre aurait déplacé le carnet.

Le coût aller-retour réel devient donc, pour une position de 10 000 $ :
4,5 + 6,8 à l'entrée, autant à la sortie, soit **≈ 23 bps en médiane** et plus
de 40 au p75 — **contre un gisement brut de 19,5 bps**. À 50 000 $ par position,
le péage passe à 50 bps.

**Le coût de prendre la liquidité dans exactement les bougies que cette
stratégie veut trader est supérieur à ce que le mouvement rapporte.** Ce n'est
plus une hypothèse défavorable, c'est une mesure. Et cela fixe le plafond de
capacité : la taille à laquelle l'arithmétique tiendrait encore est de l'ordre
de 1 000 à 5 000 $ par position — ce qui n'est pas une activité.

---

## 1 sexies. Ce que valait ma propre recherche

Après avoir cherché aussi large, la question honnête est : combien d'hypothèses
ai-je testées, et qu'aurait produit le hasard seul ?

**519 tests distincts.** Sous l'hypothèse nulle — aucun edge nulle part — le
meilleur de 519 tests indépendants affiche un t-stat attendu de **3,54**.

| « Trouvaille » | t | Verdict |
|---|---|---|
| Queue `r_burst>8%` | 2,3 | sous le seuil du hasard |
| Fade `vol_mult` 25-60× | 7,7 | biais identifié : octobre 2025 |
| Repli 90 % | 6,0 | biais identifié : ordre des tests intra-barre |
| Grappe > 15 % | 6,0 | biais identifié : pondération par événement |
| Open interest | 2,44 | biais identifié : horodatage décalé de +5 min |
| Flux d'ordres | 1,1 | sous le seuil du hasard |

Aucun résultat de cette étude ne survit **conjointement** au seuil du hasard et
aux contrôles de biais. Les deux qui dépassaient 3,54 s'expliquent par un défaut
précis de mon protocole, pas par un phénomène de marché.

---

## 1 septies. Les trois look-ahead, et comment les attraper

C'est la partie réutilisable. Chacun a produit un résultat spectaculaire et
faux, et chacun se détecte par un test simple.

**1. Utiliser la clôture d'une barre pour décider d'un événement intra-barre.**
Mon test de repli vérifiait l'invalidation du signal (`close < L`) avant le
remplissage, alors qu'un ordre limite au repos s'exécute dès que le prix touche
le niveau. J'écartais donc rétroactivement les barres qui cassaient le niveau et
poursuivaient leur chute — exactement la population perdante. +59 bps devenus
+13.
*Détection :* forcer l'ordre chronologique strict des tests dans la boucle, et
vérifier qu'un filtre ne consulte jamais une valeur postérieure à sa décision.

**2. Pondérer par événement ce qu'un portefeuille prend par épisode.**
Le signal « grappe » affichait +111 bps sur 1 709 événements — qui n'étaient que
473 épisodes indépendants, dont un seul, à 150 événements et +822 bps, portait
la moyenne. Un portefeuille à 3 positions n'en prend que 3. Pondéré par épisode :
−6,3 bps.
*Détection :* regrouper les événements séparés de moins d'une heure et
recalculer. Si la moyenne change de signe, le t-stat initial ne mesurait rien.

**3. Supposer l'alignement d'une source externe.**
Les tranches d'open interest étiquetées T décrivent l'état à T+5. Lire la
tranche du signal, c'était mesurer la variation d'OI **après** le signal.
*Détection :* le fichier contient l'OI en contrats et en dollars — leur rapport
est le prix au moment du relevé. Comparé aux klines 1 minute, il date
l'instantané à la minute près (écart de 0,06 bps sur BTC au bon décalage, contre
16,6 bps au décalage supposé). `resolve_timestamp.py` est réutilisable pour
n'importe quelle source horodatée qui publie deux grandeurs dont le rapport est
observable ailleurs.

---

## 1 octies. En temps-tick : l'edge existe, il fait la taille de la friction

Objection recevable : des bots prives scalpent ces mouvements. Mon étude n'avait
testé qu'**une seule formulation** — détection sur bougies 1 minute, entrée à
l'ouverture de la bougie suivante, au marché. Soit **30 à 60 secondes après
l'information**, en traversant le spread. Un bot agit en millisecondes et ne
traverse pas. J'ai donc reconstruit un moteur entièrement en temps-tick.

Dispositif : détection sur le flux de trades (fenêtre 30 s, z > 6, volume > 8×),
entrée à +L millisecondes du tick déclencheur, exécution par balayage réel du
flux, sortie en temps-tick. **2 500 jours-symboles tirés au hasard** — pas
seulement des jours de pump, sinon les faux positifs disparaissent et le P&L est
un mirage. 2 896 déclenchements, 2 148 épisodes.

### La continuation existe, et la vitesse la renforce

| Horizon | latence 0,2 s | 2 s | 10 s | 60 s |
|---|---|---|---|---|
| 1 min | **+6,7 bps** (t=2,39) | +4,4 | +3,0 | +2,9 |
| 5 min | **+9,7 bps** (t=2,63) | +8,1 | +7,1 | +6,9 |
| 15 min | **+10,4 bps** (t=2,02) | +8,9 | +7,8 | +8,7 |
| 1 h | −2,9 | −4,7 | −5,9 | −7,0 |

C'est un vrai résultat : le mouvement continue, entre 1 et 15 minutes, et être
rapide vaut environ 4 bps sur l'horizon 1 minute. Mon premier backtest tick
sortait au bout d'une heure en médiane — précisément là où le gain s'est
dissipé. Erreur de conception de ma part, corrigée.

### Mais toutes les exécutions butent sur le même mur

| Exécution | Meilleur net | Combinaisons positives |
|---|---|---|
| Taker aller-retour, 20 réglages (durée × taille) | **−0,0 bps** | 0/20 |
| Entrée passive après l'ignition, 30 réglages | **−8,8 bps** | 0/30 |
| Entrée au marché, sortie en limite, 24 réglages | **−0,7 bps** | 0/24 |

L'entrée passive est le cas le plus instructif : elle est **anti-sélectionnée**,
et les données le chiffrent. Le taux de remplissage à 0-5 bps sous le signal est
de **80 à 90 %** — le prix revient vous chercher presque à chaque fois,
c'est-à-dire qu'on est servi quand le momentum échoue et jamais quand il part.

### Ce qui fait basculer : les frais, pas le signal

La configuration asymétrique (entrer au marché, sortir en limite) comble presque
tout l'écart. Ce qui reste se joue sur la grille tarifaire :

| Palier | Net/trade | t | Mois positifs | Sans les 3 meilleurs mois |
|---|---|---|---|---|
| VIP 0 (base) | +0,79 bps | 0,66 | 12/24 | −1,52 |
| VIP 4 | +3,34 | 2,80 | 18/24 | +1,06 |
| **VIP 6** | **+4,15** | **3,49** | **19/24** | **+1,87** |
| **VIP 9** | **+5,24** | **4,43** | **20/24** | **+2,98** |

### Et le dernier garde-fou remet tout en cause

Ces chiffres supposent d'être servi **dès que le prix touche** la limite de
sortie, c'est-à-dire d'être toujours en tête de file. C'est exactement
l'optimisme qui avait fabriqué mon faux résultat sur le repli en bougies 1 min.
En exigeant que le prix **traverse** la limite :

| Traversée exigée | VIP 6 | VIP 9 | Mois positifs (VIP 6) |
|---|---|---|---|
| 0 bps (premier contact) | +4,15 | +5,24 | 19/24 |
| 5 bps | +0,85 | +1,98 | 14/24 |
| 10 bps | **−1,79** | −0,64 | 10/24 |
| 20 bps | −6,51 | −5,31 | 4/24 |

**0 combinaison positive et robuste avec 10 bps de traversée exigée.**

### La conclusion, qui réconcilie tout

L'edge est réel — +8 à +10 bps sur 5 à 15 minutes, t ≈ 2,6 — et il fait
**exactement la taille de la friction**. De quel côté de zéro on tombe ne dépend
pas du signal mais de trois avantages d'infrastructure :

1. **La grille tarifaire.** De VIP 0 à VIP 9 : 6 bps d'écart par trade, sur un
   gisement de 8. Décisif.
2. **La priorité dans la file.** Premier contact contre 10 bps de traversée :
   6 bps d'écart. Décisif.
3. **La latence.** 0,2 s contre 60 s : ~4 bps sur l'horizon 1 minute.

Aucun des trois ne s'obtient en cherchant un meilleur filtre. Et le point qui
tranche : **cette stratégie ne peut pas financer son propre palier de frais.** À
10 000 $ par trade elle génère de l'ordre de 120 M$ de volume sur 30 jours, là
où les paliers VIP 6-9 en exigent des milliards. Le palier doit venir
d'ailleurs — d'une activité de tenue de marché ou d'un desk qui l'a déjà.

C'est, très précisément, le profil d'un bot privé qui y arrive. Non parce qu'il
a trouvé un signal que je n'ai pas trouvé, mais parce qu'il opère depuis une
structure de coûts et une position dans la file qu'un compte de détail n'a pas.
**Ta prémisse est juste ; ce n'est simplement pas une question de stratégie.**

---

## 2. Le dispositif

**Univers.** 864 perps USDT existent sur Binance. J'en ai retenu 319 :

- *Filtre crypto 24/7.* Binance liste maintenant des actions et matières
  tokenisées (`XAUUSDT`, `SKHYNIXUSDT`, `SPCXUSDT`, `SOXLUSDT`, `MUUSDT`...).
  Elles suivent leur sous-jacent et gappent à l'ouverture des bourses : leur
  dynamique n'a rien à voir avec un pump crypto sur news. Je les identifie sans
  liste en dur — leur volume du week-end s'effondre. 144 instruments écartés.
- *Liquidité.* Volume quote médian ≥ 3 M$/jour, sinon le backtest est une
  fiction d'exécution.
- *Historique.* ≥ 90 jours, pour avoir de quoi normaliser.

**Pas de biais du survivant.** Un token délisté en cours de route reste dans
l'univers jusqu'à sa dernière bougie. Vérifié plutôt que supposé : seuls 4
symboles s'arrêtent avant la fin de la période, tous sous le plancher de
liquidité. Le biais est négligeable *ici* — ce n'était pas acquis d'avance.

**Convention temporelle.** Une feature indexée à la barre `t` n'utilise que des
barres ≤ `t`. Un signal calculé à la clôture de `t` est exécuté à l'**ouverture
de `t+1`**. C'est ce que ferait un scanner tournant en live sur la clôture de la
minute. Le gap médian signal → entrée est de 0,0 bps : être une minute en retard
ne coûte rien, ce n'est pas là qu'est le problème.

**Convention intra-barre.** Quand le stop et la cible sont tous deux dans le
range d'une même bougie, je suppose que le **stop** part en premier. L'OHLC 1
minute ne donne pas l'ordre des ticks ; supposer l'inverse reviendrait à
s'offrir le meilleur des deux mondes sur toutes les bougies violentes —
exactement celles où vit cette stratégie.

**Normalisation.** Tout est mesuré en unités du régime propre du token *avant*
la rafale (volatilité et volume de référence décalés de `k` minutes). Sans ce
décalage, un pump vertical gonfle son propre dénominateur et son z-score
s'effondre au moment précis où il devrait exploser.

---

## 3. L'anatomie d'un pump

248 174 ignitions détectées (k = 5 min, z ≥ 2,5, volume ≥ 2×, cooldown 60 min).

**L'événement moyen n'a aucun edge** : ~0 bps brut à tous les horizons, −20 bps
net. Acheter tout pic volume+prix est perdant par construction.

La structure est dans la queue, et elle est contre-intuitive :

| Conditionnement | fwd 60 min |
|---|---|
| `r_burst > 8%` (rafale de 5 min) | **+115 bps** (t = 2,3) |
| `vol_mult` 25–60× | **−36 bps** (t = −3,7) |

Le volume extrême seul est un signal de **retournement**, pas d'ignition : c'est
la signature de la mèche de liquidation. Beaucoup de systèmes de détection de
pump se déclenchent précisément là-dessus.

**Le résidu vaut le brut.** Après retrait du bêta BTC (β médian 1,30, estimé par
symbole), l'effet passe de +31,7 à +30,6 bps : il est **authentiquement
idiosyncratique**. Ta prémisse sur la *nature* du mouvement est juste — les
tokens font bien leur vie indépendamment de BTC. C'est l'exploitabilité qui
coince, pas le diagnostic.

**Mais la forme du chemin dit déjà tout.** À 30 min après une rafale > 5% :
MFE moyen +640 bps, MAE moyen −568 bps. Cette quasi-symétrie est la signature
d'une marche aléatoire très volatile. Le token devient agité, il ne devient pas
directionnel.

---

## 4. Le piège d'octobre 2025, et pourquoi j'ai changé de critère

Première version des résultats : `r_burst > 8%` rapporte +115 bps à 60 min,
t = 2,3. Encourageant. Décomposition mensuelle :

```
2025-10   627 événements   +278 bps      <-- tout est là
les 11 autres mois          ~0 bps
```

Hors octobre, le même filtre donne **−26 bps**.

**Mais exclure 31 jours était trop brutal, et c'est une erreur de ma part.**
L'anomalie ne fait pas un mois, elle fait un jour. Décomposition d'octobre au
jour le jour (`analyze_oct.py`) :

| Exclusion | `r_burst>8%`, fwd 60 min | t | OOS |
|---|---|---|---|
| tout inclus | +115,1 bps | 2,3 | −32,8 |
| sans le **10 octobre seul** | **+19,8 bps** | 0,4 | −32,8 |
| sans tout octobre | −25,6 bps | −0,5 | −32,8 |

Le 10 octobre porte **74 % de l'edge du mois** à lui seul : 152 signaux, dont
**98 dans la seule heure de 22 h UTC**, pour une moyenne de +851 bps. Et même
amputé de ce jour, octobre garde une moyenne de +94 bps pour une **médiane de
−1,2 bps** — le reste du mois est lui aussi porté par une poignée d'événements,
pas par une dérive large.

L'exclusion fine change donc le chiffre (+19,8 au lieu de −25,6) mais pas le
verdict : t = 0,4, net +0,8 bps, OOS −32,8 bps.

Dernier point sur cette anomalie : elle n'était même pas entièrement capturable.
Avec la contrainte de 3 positions simultanées, sur les 228 signaux émis le 10
octobre, le portefeuille n'en prend que **51** — 27 % du P&L total de l'année
pour 0,6 % des trades. Une moyenne poolée d'event study pondère les 152 signaux
à égalité ; un compte de trading n'en voit qu'une fraction.

J'ai donc changé de critère d'évaluation en cours d'étude. Une moyenne poolée et
un t-stat sur des événements fortement clusterisés dans le temps ne mesurent
rien d'exploitable. Tout candidat doit désormais passer trois filtres
(`evaluate.py`) : moyenne **médiane mensuelle** > coût, majorité franche de mois
positifs, et même comportement en IS et en OOS. Un signal qui ne les passe pas
n'est pas un signal, c'est un mois.

---

## 5. Les quatre stratégies testées

Découpage temporel fixé **avant** de regarder le moindre résultat :
IS = sept. 2025 → fév. 2026, OOS = mars → août 2026. Les pumps ARB d'août 2026
que tu cites tombent en OOS — délibérément : on ne calibre pas sur les exemples
qui ont motivé l'étude.

### A. Acheter l'ignition au marché
Mort. L'edge est entièrement octobre 2025 (§4).

### B. Vendre l'ignition (fade de la mèche)
Le bucket `vol_mult` 25–60× affiche −86 bps à 15 min avec t = −7,7 sur 5 736
événements. Très tentant. Hors octobre : **−4,3 bps**. En OOS : −2,1 bps. Mort.

### C. Acheter le repli en ordre limite
Structurellement différente des deux précédentes : le prix de remplissage n'est
plus la mèche mais un niveau 2 à 5 % plus bas, et un ordre limite paie le maker
(coût aller-retour de 19 → 11,5 bps).

Premiers résultats spectaculaires, et **monotones** en profondeur de repli —
23,6 % → 90 % de retracement fait passer l'edge de −1,2 à +59,4 bps, avec 11/12
mois positifs et les deux moitiés de période positives. Une réponse monotone à
un paramètre est normalement la signature d'un effet réel.

**C'était un bug à moi.** Ma boucle testait l'invalidation du signal
(`close < L`) *avant* le remplissage. Or un ordre limite au repos est exécuté
dès que le prix touche le niveau, intra-barre, sans savoir où la bougie va
clôturer. Tester l'invalidation d'abord revenait à annuler rétroactivement les
remplissages des barres qui cassent le niveau et poursuivent leur chute —
c'est-à-dire à jeter exactement la population perdante, avec une information du
futur. Et l'effet était d'autant plus fort que le repli était profond, ce qui
fabriquait la belle monotonie.

Après correction (`test_pullback.py`, le commentaire sur l'ordre des deux tests
est là pour que personne ne le « simplifie » plus tard) :

| Repli | Avant correction | Après | Après + remplissage réaliste |
|---|---|---|---|
| 61,8 % | +18,4 bps | +7,7 | −2,6 |
| 90 % | **+59,4 bps** | **+13,3** | **+0,9** |

Le « remplissage réaliste » exige que le prix **traverse** la limite de 10 bps
au lieu de l'effleurer. Sans cette exigence, on suppose être servi pile au tick
extrême de la bougie, alors qu'en file d'attente on ne l'est pas. Mort.

### D. Recherche systématique (le test qui tranche)
Mes découpages précédents sont faits à la main : ils explorent mal l'espace et
leurs t-stats sont pollués par le nombre d'essais. J'ai donc inversé la charge
de la preuve — un gradient boosting entraîné sur la première moitié de la
période à prédire le rendement forward à partir des 17 features d'ignition,
évalué sur la seconde.

Cible : rendement à 60 min. Décile supérieur des prédictions :

| Jeu d'événements | En échantillon | Hors échantillon | Corrélation de rang OOS |
|---|---|---|---|
| k = 5 min (11 features, 141 k exemples) | **+93,3 bps** (t = 17,9) | **−2,9 bps** | **−0,037** |
| k = 30 min (17 features, 67 k exemples) | **+76,0 bps** (t = 9,7) | **−2,0 bps** | **−0,021** |

Transfert nul dans les deux cas, corrélation de rang légèrement *négative*. Un
modèle non linéaire, libre de combiner toutes les features sur des dizaines de
milliers d'exemples, ne trouve rien qui survive. Ce n'est plus une question
d'intuition de découpage : **l'edge conditionnel n'existe pas dans cet espace de
features.**

---

## 6. Pourquoi aucune règle de sortie ne pouvait sauver ça

Une objection naturelle : « la dérive moyenne est peut-être nulle, mais avec un
bon trailing stop on coupe les pertes et on laisse courir les gains ».

Non, et c'est démontrable. Si le processus est sans dérive, **toute** règle
d'arrêt a une espérance nulle avant coûts — c'est le théorème d'arrêt optionnel.
Aucun agencement de stop, de cible et de time-stop ne crée d'espérance à partir
d'un martingale. C'est précisément pour ça que toute l'étude mesure des
**moyennes conditionnelles** plutôt que de chercher le bon trailing stop.

La grille de 64 règles (`run_backtest.py`) le confirme empiriquement : brut
médian +5,8 bps, net médian −13,2 bps.

Une précision sur les courbes d'equity, pour ne pas surinterpréter. La meilleure
variante a une espérance arithmétique de **+0,45 bps par trade** — indiscernable
de zéro — avec un écart-type de 8,6 % par trade. Ce qui détruit l'equity n'est
donc pas une espérance négative, c'est le **frein de volatilité** :

| Taille par trade | Equity finale | Max DD | Frein de volatilité |
|---|---|---|---|
| 2 % | 0,995 | 17,5 % | 1,3 pt |
| 5 % | 0,941 | 40,2 % | 8,0 pts |
| 10 % | 0,756 | 68,0 % | 31,9 pts |
| 25 % | 0,157 | 97,6 % | 194,9 pts |

Le message correct est donc : à taille raisonnable on ne gagne ni ne perd rien
(0,995× sur un an), à taille agressive le frein de volatilité ruine. Dans les
deux cas il n'y a pas d'edge à exploiter — mais il ne faut pas lire la courbe à
0,157× comme la preuve d'une espérance fortement négative.

---

## 7. Aparté : hors du scalp, à l'horizon de plusieurs jours

> Cette section sort du sujet — elle porte sur des positions de plusieurs
> jours, pas sur du scalp. Je la garde parce que c'est le seul endroit où
> j'ai trouvé une statistique stable, mais ce n'est **pas** une réponse à la
> question posée, et la première version de ce rapport lui donnait beaucoup
> trop de place.

En refaisant exactement la même event study **au pas journalier** : après un pump
quotidien > +15 %, le token rend **−11,4 % en médiane** sur les 10 jours suivants.
Cette médiane est remarquablement stable — elle ne bouge pas de −11 % quelle que
soit la sous-population.

**La moyenne, elle, n'est pas robuste, et j'avais surestimé ce point dans une
première version.** Mon premier script excluait par effet de bord les 30 premiers
jours de cotation de chaque token (le filtre de volume exige une médiane glissante
sur 30 jours, et les lignes sans historique tombaient silencieusement). Ce n'était
pas un choix méthodologique, c'était un accident — et il porte le signe du
résultat :

| Population | n | moyenne | médiane | t | max |
|---|---|---|---|---|---|
| tout, aucune exclusion | 2 662 | **+1,46 %** | −11,4 % | 0,68 | +3 244 % |
| âge ≥ 30 j *(mon run initial)* | 2 310 | **−3,48 %** | −11,6 % | −3,10 | +826 % |
| âge ≥ 60 j | 1 999 | −2,96 % | −11,4 % | −2,45 | +826 % |
| âge < 30 j *(jeunes listings seuls)* | 352 | **+33,90 %** | −9,0 % | 2,34 | +3 244 % |

Les tokens fraîchement listés portent toute la queue droite. Un short à
l'espérance ne gagne que si on les exclut — ce n'est pas un edge, c'est un choix
d'univers, et il doit être annoncé comme tel.

Ce qui reste, honnêtement : **un effet de médiane, pas un effet de moyenne**.
La moitié des pumps quotidiens rendent plus de 11 % dans les 10 jours, de façon
très stable dans le temps. Mais la distribution est telle que

```
p50 −11,4%   p95 +67%   max +826% (et +3 244% si on garde les jeunes listings)
6,9 % des cas montent encore de plus de 50 %
```

qu'un short non protégé a une espérance nulle voire positive pour le token. Le
funding d'un perp en plein pump est positif, donc **payé au short** — un vent
arrière réel, qui ne compensera jamais une queue à +800 %.

Autrement dit : il y a peut-être quelque chose à construire là, mais l'objet
d'étude serait **le stop**, pas le signal. Un short avec coupure stricte peut en
théorie récolter la médiane en payant la queue ; encore faut-il le backtester,
avec le même niveau de garde-fous que ci-dessus. **Je le donne comme piste, pas
comme stratégie validée**, et c'est une piste à l'opposé de ce que tu cherchais —
en direction comme en horizon.

## 8. Ce qu'il faudrait — et ce qui est désormais exclu

Au début de cette étude, je listais quatre manques : le carnet et le flux
trade-par-trade, une exécution qui ne paie pas le taker, l'open interest, et le
flux de news horodaté. Trois ont été traités depuis. Le bilan a changé.

**Exclu par la mesure, pas par l'hypothèse :**

- *Le flux trade-par-trade.* Testé (§1 quater), six hypothèses de microstructure,
  rien qui transfère hors échantillon. C'était mon principal espoir ; il est
  éteint.
- *L'open interest.* Testé (§1 ter). Le signal apparent venait d'un décalage
  d'horodatage de 5 minutes.
- *Le slippage.* Mesuré (§1 quinquies). Il est supérieur au gisement dès
  10 000 $ par position. C'est le verrou dur : même avec un discriminant
  parfait, la taille exploitable serait dérisoire.

**Ce qui reste ouvert, honnêtement :**

- *L'open interest en temps réel.* L'archive ne publie que des instantanés au
  pas de 5 minutes. Un opérateur interrogeant l'OI instantanée disposerait d'une
  donnée plus fraîche que mon meilleur test causal, sans pour autant disposer du
  futur. Je n'ai pas pu trancher, et mon résultat à retard nul n'est pas un
  argument en sa faveur — il utilisait de l'information postérieure au signal.
- *Le carnet d'ordres lui-même.* Binance Vision ne publie pas de `bookTicker`
  mensuel exploitable pour cet univers. La profondeur et sa dynamique restent
  non testées.
- *Le flux de news horodaté.* La prémisse de départ est « un pump sur news ».
  Sans la news, on détecte la conséquence avec une minute de retard et sans
  savoir si elle en vaut la peine. C'est la seule piste qui attaquerait le
  problème par l'amont plutôt que par le signal de prix — et la seule qui, si
  elle donnait un avantage en **temps** plutôt qu'en **prédiction**, changerait
  l'arithmétique du slippage.
- *Le maker plutôt que le taker.* Tout ce qui précède paie le spread au pire
  moment. Un placement passif intelligent changerait l'équation — mais mon test
  C montre qu'un simple ordre limite sur repli est anti-sélectionné, donc ça
  demande une vraie logique de placement, pas un ordre naïf.

**Ce que je ne recommanderais pas de faire :** continuer à chercher un filtre
sur les klines. 519 tests, six familles de features, deux ans de données, trois
biais débusqués — le gisement brut est mesuré à ~19 bps et le péage réel à
23 bps ou plus. Le problème n'est pas qu'on n'a pas trouvé le bon filtre ; c'est
que la marge est plus petite que le coût de l'exécution.

## 9. Reproduire

```bash
pip install -r ../../requirements.txt scikit-learn

python3 list_symbols.py > symbols_all.txt   # 864 perps USDT
python3 screen_liquidity.py                 # screen 1d (~6 min)
python3 build_universe.py                   # -> universe.txt (319 symboles)
python3 dl_1m.py                            # ~4,4 Go, ~5 min

python3 extract_events.py --k 5 --out events_k5.parquet
python3 enrich_btc.py                       # bêta + rendements résiduels
python3 analyze_events.py                   # event study globale
python3 analyze_tail.py                     # la queue + concentration
python3 analyze_resid.py                    # le piège d'octobre

python3 test_pullback.py --frac 0.9 --wait 30 --margin-bps 10   # stratégie C
python3 ml_search.py                        # stratégie D (le test qui tranche)

python3 build_paths.py --events events_tail.parquet
python3 run_backtest.py                     # grille de 64 règles de sortie
python3 cost_sensitivity.py                 # le seuil de rentabilité
python3 scalp_horizons.py                   # le résultat par durée : 1 h / 2 h / 3 h / 4 h

# --- le discriminant : open interest (§1 ter) ---
bash run_hist.sh                            # période 2024-09 -> 2025-09
python3 build_breadth.py                    # largeur de marché
python3 test_micro.py                       # levier vs demande réelle
python3 walkforward_final.py                # la procédure, sélection comprise
python3 check_lag2.py && python3 bt_lag1.py  # sensibilité à la fraîcheur
python3 resolve_timestamp.py                # datation de l'instantané d'OI
python3 bt_aligne.py                        # backtest avec alignement correct

# --- flux d'ordres et coûts réels (§1 quater à 1 sexies) ---
python3 run_flow.py && python3 test_flow.py # microstructure tick par tick
python3 test_slippage.py                    # le slippage réel
python3 dl_funding.py && python3 test_funding.py
python3 bilan_recherche.py                  # combien de tests, quel seuil de hasard

# --- temps-tick : latence, exécution, frais (§1 octies) ---
python3 run_tick.py   && python3 analyse_tick.py   # ce que vaut la vitesse
python3 run_tick2.py                               # durées et tailles
python3 run_passif.py                              # entrée passive : anti-sélection
python3 run_mixte.py  && python3 run_marge.py      # sortie en limite, priorité de file
python3 portefeuille_v2.py                         # P&L par palier de frais
python3 test_daily_v2.py                    # effet journalier (contrôle âge de listing)
python3 analyze_oct.py                      # décomposition du 10 octobre
```

Le cache disque est la règle : rien n'est retéléchargé deux fois.

## Fichiers

| Fichier | Rôle |
|---|---|
| `bvision.py` | téléchargement parallèle + cache parquet |
| `features.py` | features d'ignition, strictement causales |
| `extract_events.py` | détection des ignitions + surface forward |
| `evaluate.py` | **le critère de consistance mensuelle** |
| `simulate.py` / `simulate_vec.py` | moteur de trade + contrainte de portefeuille |
| `analyze_oct.py` | décomposition jour par jour de l'anomalie du 10 octobre |
| `test_daily_v2.py` | effet journalier, avec contrôle explicite de l'âge de listing |
| `scalp_horizons.py` | **le résultat par durée de détention : 1 h, 2 h, 3 h, 4 h** |
| `test_pullback.py` | stratégie C (attention à l'ordre des tests, §5) |
| `ml_search.py` | recherche systématique avec validation OOS |
| `bv_extra.py` | téléchargement OI / prime perp / klines spot |
| `build_breadth.py` | largeur de marché : combien de tokens pumpent ensemble |
| `build_micro.py` | features de microstructure (OI, prime, participation spot) |
| `evaluate2.py` | **pondération par épisode** — la correction qui invalide les moyennes par événement |
| `walkforward_final.py` | walk-forward sur la procédure de sélection elle-même |
| `check_lag2.py` / `check_align.py` | fraîcheur de l'OI et convention d'horodatage |
| `bt_aligne.py` | backtest avec l'open interest correctement alignée |
| `resolve_timestamp.py` | **date un instantané d'OI à la minute, par le prix implicite** |
| `flow_features.py` / `run_flow.py` | flux d'ordres tick par tick, en streaming |
| `test_slippage.py` | **le slippage réel, mesuré sur les trades** |
| `test_funding.py` | coût de funding par durée de détention |
| `bilan_recherche.py` | comptage des tests et seuil du hasard |
| `tick_engine.py` | **moteur en temps-tick : détection, latence, balayage, sorties** |
| `run_tick.py` / `run_tick2.py` | backtest tick, latences et durées de détention |
| `run_passif.py` | entrée en limite : la démonstration de l'anti-sélection |
| `run_mixte.py` / `run_marge.py` | entrée au marché / sortie en limite, et priorité de file |
| `portefeuille_v2.py` | simulation portefeuille par palier de frais |
