# Scalp de pump sur perps crypto — étude et backtest

**Verdict : le scalp d'ignition ne passe pas le coût de transaction.** Le
gisement brut existe, il est réel, il est mesurable — et il fait très
exactement la taille du péage. Ce document montre comment j'y arrive, ce que
j'ai essayé, et le seul effet qui a survécu aux contrôles — un effet de médiane,
à l'opposé de ce que tu cherchais en direction comme en horizon.

Données : 319 perps USDT, bougies 1 minute, 2025-09-01 → 2026-09-01
(12 mois, ~4,4 Go, 168 M de bougies), source `data.binance.vision`.

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

## 8. Ce qu'il faudrait pour aller plus loin

L'étude est négative sur les données 1 minute OHLCV. Ce n'est pas la même chose
que « le scalp de pump est impossible ». Ce qui manque, par ordre d'importance :

1. **Le carnet et le flux trade-par-trade.** Le seuil de rentabilité est à 9,7
   bps par côté. À cette échelle, le signal utile est *dans* la microstructure —
   déséquilibre du carnet, taille et agressivité des trades, vitesse d'arrivée
   des ordres. Une bougie de 1 minute agrège tout ça en 5 nombres et détruit
   précisément l'information qui décide. C'est le vrai plafond de cette étude.
2. **Une exécution qui ne paie pas le taker.** Toute l'approche consiste à
   franchir le spread au pire moment. Un scalp rentable à cette échelle se joue
   probablement en maker — mais mon test C montre qu'un simple ordre limite sur
   repli est anti-sélectionné, donc ça demande une vraie logique de placement.
3. **L'open interest et le funding en temps réel.** Distinguer un pump porté par
   du spot (achats réels, potentiellement durable) d'un pump porté par du levier
   (squeeze, retombée rapide) est exactement la distinction que mes features
   OHLCV ne savent pas faire — et c'est probablement celle qui compte.
4. **Le flux de news horodaté.** La prémisse de départ est « un pump sur news ».
   Sans la news, on détecte la conséquence avec une minute de retard et sans
   savoir si elle en vaut la peine.

---

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
