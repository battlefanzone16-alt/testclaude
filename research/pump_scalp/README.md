# Scalp de pump sur perps crypto — étude et backtest

**Verdict : le scalp d'ignition ne passe pas le coût de transaction.** Le
gisement brut existe, il est réel, il est mesurable — et il fait très
exactement la taille du péage. Ce document montre comment j'y arrive, ce que
j'ai essayé, et le seul effet qui a survécu à tous les contrôles (ce n'est ni
la direction ni l'horizon que tu visais).

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

Hors octobre, le même filtre donne **−26 bps**. La cascade de liquidations
d'octobre 2025 suffit, à elle seule, à rendre positive n'importe quelle moyenne
sur 12 mois.

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
médian +5,8 bps, net médian −13,2 bps. Les courbes d'equity finissent à 0,15× le
capital avec 98 % de drawdown — une petite espérance négative, composée 24 fois
par jour, ruine mécaniquement.

---

## 7. Le seul effet qui survit à tout

En refaisant exactement la même event study **au pas journalier** :

**Après un pump quotidien > +15 %, le token rend −3,5 % en moyenne et −11,6 % en
médiane sur les 10 jours suivants** (n = 2 310, t = −3,1), négatif en IS (−441
bps) comme en OOS (−271 bps), avec **10 mois sur 11** dans le même sens. Pour
`> +30 %`, c'est −7,0 % en moyenne.

C'est la statistique la plus robuste de toute l'étude. Mais lis bien ce que ça
dit : c'est l'inverse de ce que tu cherchais, **en direction** (il faut vendre)
et **en horizon** (jours, pas minutes).

Et ce n'est pas exploitable naïvement :

```
distribution à 10 jours : p50 −11,6%   p90 +37%   p99 +175%   pire cas +826%
6,9 % des cas montent encore de plus de 50 %
```

La médiane est très favorable au short, la queue droite est mortelle. Le funding
d'un perp en plein pump est positif, donc **payé au short** — un vent arrière
réel, qui ne compensera jamais une queue à +200 %. Ici le sujet n'est pas le
signal, c'est le dimensionnement et le stop. **Je le donne comme piste, pas
comme stratégie validée** : elle mérite sa propre étude, avec le même niveau de
garde-fous que ci-dessus.

---

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
python3 test_daily.py                       # l'effet journalier
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
| `test_pullback.py` | stratégie C (attention à l'ordre des tests, §5) |
| `ml_search.py` | recherche systématique avec validation OOS |
