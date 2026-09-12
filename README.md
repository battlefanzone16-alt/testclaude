# Kalman v6 — laboratoire de stratégie

Reprise du système Kalman v5 décrit dans `contexte_kalman_v5_1.md` (tarik, crypto
perp Hyperliquid, 58 tokens, H4 dérivé du 1-min Binance).

Objectif fixé : **Sharpe > 1.5, validé Monte Carlo, sans overfitting.**

---

## 1. Ce que j'ai relu dans ton analyse — et où je ne suis pas d'accord

Ta « découverte majeure » :

| Raison | Trades | WR | PnL moyen |
|---|---|---|---|
| clôt<médiane | 1 392 | 47% | +1.74% |
| **clôt<Kalman** | **778** | **0%** | **−1.48%** |
| SL dur | 266 | 0% | −3.19% |

Tu en conclus que `clôt<Kalman` est « le plus gros saignement du système ».
Le chiffre est juste, l'interprétation mérite d'être corrigée.

**Ce 0% de win rate est une tautologie, pas une découverte de marché.**

Tu entres quand `close > kalman`. Tu sors, en phase Kalman, quand `close < kalman`.
Tu entres donc juste au-dessus d'une ligne lente et tu sors juste en dessous de
cette même ligne. Le trade *ne peut pas* être gagnant : la condition de sortie
définit mécaniquement une perte (au gain de dérive du Kalman près). Exactement
comme `SL dur` affiche 0% de WR — parce qu'un stop est une perte par définition.

La vraie question n'est donc pas « comment rendre ces 778 trades gagnants »
(impossible), mais **« comment ne pas les prendre »**.

Ça invalide au passage une de tes trois pistes. `TIME_BELOW_N = 1` coupe la perte
plus tôt mais **coupe aussi les trades qui seraient passés au-dessus de la médiane
deux bougies plus tard** — c'est-à-dire précisément la population rentable à 47%.
C'est un pansement qui saigne des deux côtés.

Ta piste n°2 est la bonne, et c'est la seule structurelle : **n'entrer que si le
prix est déjà du bon côté de la médiane Donchian**. Un booléen, zéro paramètre à
régler, et la population à 0% de WR disparaît *à la source* au lieu d'être
amputée après coup.

Vérifié dans le code : avec ce gate, le nombre de sorties `clot_kalman` tombe à
**zéro** (`tests/test_bias.py::test_median_gate_removes_kalman_exits`).

### Deuxième correction : ta distribution de R interdit deux de tes options

Tu notes que `R > +3` représente 3.8% des trades et **porte tout le résultat**.
C'est le profil classique d'un suiveur de tendance : l'espérance vit entièrement
dans la queue droite. Conséquence directe :

- **`SORTIE_RR` (TP fixe) détruira le système.** Un TP à +2R coupe par
  construction chaque trade avant qu'il n'atteigne +3R, +5R ou +10R. Tu
  échangerais un win rate flatteur contre une espérance négative.
- **`BE_ACTIVATION_PCT` est déjà réfuté par tes propres données** : 8 trades, 0%
  de WR, −0.35% de moyenne. Remonter le stop à l'entrée transforme les
  respirations normales d'une tendance en sorties à zéro.

Ces deux options sont dans ta liste « à tester une par une ». Tu peux les tester,
mais le prior est très négatif et ton CSV le montre déjà. Je ne les ai pas
implémentées comme réglages par défaut.

### Troisième trouvaille : un second no-op, comme ton « Filter Order N »

J'avais ajouté un filtre « n'entrer que si la pente du Kalman confirme ».
L'ablation l'a montré strictement sans effet — 2015 trades identiques. Démonstration :

```
kal[i] = kal[i-1] + K*(c[i] - kal[i-1]),  0 < K < 1
c[i] > kal[i]      <=>  c[i](1-K) > kal[i-1](1-K)  <=>  c[i] > kal[i-1]
kal[i] > kal[i-1]  <=>  K*(c[i] - kal[i-1]) > 0    <=>  c[i] > kal[i-1]
```

Les deux conditions sont **équivalentes** : tout croisement haussier a déjà, par
construction, une pente Kalman positive. Vérifié sur 1377 croisements, 0 exception.
Filtre retiré du code plutôt que livré en faux réglage. (La pente en *sortie*,
ton Stratagème A, n'est pas concernée — c'est une autre condition, elle reste
testable.)

---

## 2. Ce que v6 change, et pourquoi

Chaque changement est **structurel** — une règle ou une transformation de risque,
pas un curseur ajusté sur l'historique. C'est le point : on ne peut pas
overfitter ce qu'on n'optimise pas.

| # | Changement | Justification |
|---|---|---|
| 1 | **Gate d'entrée au-dessus de la médiane** | Supprime la population à 0% de WR à la source. Booléen. |
| 2 | **Sortie = médiane seule** | Le gate rend la phase Kalman inatteignable ; la logique 2-phases devient une pièce morte. Moins de pièces, moins de degrés de liberté. |
| 3 | **Long + Short** | Ton CSV montre la parité (1189 vs 1268, perf quasi identique). v5 tournait long-only : la moitié du signal était jetée. |
| 4 | **Comptabilité PORTEFEUILLE** | Le changement le plus important pour ton objectif. Le Sharpe est une statistique de portefeuille ; v5 mesurait des médianes par token, ce qui jette toute la diversification. **On ne peut pas atteindre un Sharpe cible sans agréger.** |
| 5 | **Cap d'exposition brute + nette** | Borne le bêta marché : sans ça, une cassure synchronisée sur 40 alts devient un pari directionnel géant sur BTC. |
| 6 | **Vol targeting 20%** | Transformation de risque standard, causale (fenêtre passée uniquement), avec le coût de rééquilibrage facturé. |

Le stop dur, le sizing 1%/trade et le cap de levier 3x sont conservés tels quels.

---

## 3. Anti-overfitting : ce qui est en place

Ta méthodologie v5 est déjà la bonne. Elle est ici **exécutable**, pas seulement écrite.

- **Sélection par plateau, jamais par argmax.** `select_plateau()` note chaque
  point par la moyenne de son voisinage pénalisée par sa dispersion. Un pic isolé
  entouré de médiocrité est écarté.
- **Grille délibérément petite** : 3 axes × 3 valeurs = 27 essais. Chaque axe
  ajouté monte la barre du hasard.
- **Deflated Sharpe Ratio** (Bailey & López de Prado) : déflate le Sharpe par le
  maximum attendu de N essais sur du bruit. C'est le chiffre qui répond à « mon
  1.8 n'est-il que le max de 27 combinaisons ? ». Le nombre d'essais est compté
  automatiquement.
- **Walk-forward** : chaque segment OOS est choisi sans voir son propre futur.
  Le Sharpe agrégé OOS est le seul auquel accorder du crédit.
- **Holdout scellé** : `--holdout 2025-07-01`. À ne regarder qu'une fois.
- **Séparation STRUCTUREL / LIBRE** dans `config.py` : seuls les champs LIBRE ont
  le droit d'être balayés.

### Les 4 tests Monte Carlo

Ils ne répondent pas à la même question. Passer A et B seulement ne vaut rien.

| | Test | Question |
|---|---|---|
| **A** | Bootstrap stationnaire par blocs | Le Sharpe est-il significatif vu la taille d'échantillon ? |
| **B** | Permutation de l'ordre des trades | Le drawdown observé est-il de la chance de séquencement ? |
| **C** | Entrées aléatoires à exposition égale | L'**entrée** a-t-elle un edge, ou n'est-on payé que pour de l'exposition ? |
| **D** | Re-run sur chemins de prix rééchantillonnés | Les **règles** tiennent-elles sur un marché qui aurait pu se produire ? |

C et D sont ceux qui tuent les systèmes overfittés. D rejoue toute la stratégie,
indicateurs compris, sur des marchés rééchantillonnés par blocs — ça casse les
coïncidences de dates tout en préservant vol clustering et queues épaisses.

### Tests anti-biais (`tests/test_bias.py`) — 10/10

Le plus important est celui de **causalité** : on détruit le futur de la série et
on vérifie que pas un seul trade passé ne bouge.

```
[PASS] causalité kalman (futur modifié -> passé inchangé)
[PASS] causalité donchian_median (futur modifié -> passé inchangé)
[PASS] pivot publié avec le retard pvt_right
[PASS] causalité backtest (trades passés identiques si futur inconnu)
[PASS] bruit pur -> Sharpe négatif (pas de free lunch)
[PASS] monotonie des coûts (0x > 1x > 3x)
[PASS] gate médiane -> zéro sortie clot_kalman
[PASS] cap d'exposition brute respecté
[PASS] cap d'exposition nette respecté
[PASS] pas de chevauchement de positions par token
```

> ⚠️ **Point à vérifier dans ton code v5.** Les pivots Donchian ne sont *connus*
> que `pvtLenR = 4` bougies après la bougie du pivot. Si ton `indicateurs.py`
> forward-remplit depuis la bougie du pivot, ta médiane contient **4 bougies de
> lookahead** — et comme ta sortie principale est `close < médiane`, ce biais
> gonflerait directement ta jambe rentable. Ici la valeur n'est publiée qu'à
> `i + pvt_right` (`indicators.py::pivot_high`). À comparer avec ton implémentation :
> si les courbes diffèrent, le +2418% de la jambe médiane est à recalculer.

---

## 4. Utilisation

```bash
pip install -r requirements.txt

# 1. tes 1-min -> H4  (le low H4 == min des lows 1-min : le stop intrabar
#    est strictement équivalent, pour 100x plus rapide)
python -m quantlab.run prepare --src /chemin/data_1m --out data_h4

# 2. contribution marginale de chaque changement, un à la fois
python -m quantlab.run ablation --data data_h4

# 3. walk-forward, sélection par plateau + Deflated Sharpe
python -m quantlab.run optimize --data data_h4 --folds 4

# 4. les 4 tests Monte Carlo
python -m quantlab.run validate --data data_h4

# 5. tout, avec holdout scellé
python -m quantlab.run all --data data_h4 --holdout 2025-07-01

# vérification du pipeline sans données réelles
python -m quantlab.run ablation --synthetic
python tests/test_bias.py
```

Sorties dans `reports/` : `ablation.csv`, `wf_picks.csv`, `wf_oos_returns.csv`,
`montecarlo.json`.

---

## 5. Où en est l'objectif Sharpe > 1.5

**Honnêtement : je ne peux pas le certifier, et personne ne le peut sans tes données.**

Le conteneur distant n'a pas accès à tes 2 ans de data (elles sont sur ton PC) et
la politique réseau bloque Binance, Bybit, Yahoo et tout le reste — vérifié. Tout
ce qui tourne ici tourne sur du bruit calibré. Annoncer un Sharpe obtenu sur des
données que j'ai moi-même générées n'aurait aucune valeur, et je ne vais pas le faire.

Ce qui est livré et vérifié :

- un moteur dont la causalité est **prouvée par test**, pas affirmée ;
- les changements structurels qui donnent au système sa meilleure chance —
  au premier rang desquels l'agrégation portefeuille, **sans laquelle la question
  du Sharpe n'a littéralement pas de sens** ;
- le harnais qui dira la vérité sur tes données, y compris si la réponse est non.

Ce qui est mesuré ici et qui te concerne quand même : sur données synthétiques,
la monotonie des coûts donne **0.87 → −0.20 → −2.25** pour 0x, 1x, 3x. Je
reproduis ton constat v5 (« meurt à ×3 ») sans l'avoir cherché. Avec ~0.21% de
coût aller-retour, **le coût est ton contrainte dominante, pas le signal.** Le gate
médiane a divisé le nombre de trades par 1.6 dans l'ablation : c'est autant de
drain en moins, et c'est probablement de là que viendra l'essentiel du gain réel.

Lance `ablation` puis `optimize` sur tes données et envoie-moi les sorties —
j'itère à partir de chiffres réels.

---

## 6. Structure

```
quantlab/
  core/
    config.py       # Config, séparation STRUCTUREL / LIBRE
    indicators.py   # Kalman BackQuant, Donchian pivot combiné, ATR
    engine.py       # backtest mono-token, priorité stop dur
    portfolio.py    # agrégation, caps brut/net, vol targeting
    metrics.py      # Sharpe, PSR, Deflated Sharpe, stats de trades
  data/
    loader.py       # OHLCV tolérant aux formats
    prepare.py      # 1-min -> H4, chargement d'univers
    synth.py        # univers synthétique (validation du pipeline uniquement)
  validation/
    montecarlo.py   # tests A, B, C, D
    walkforward.py  # walk-forward + sélection par plateau
  run.py            # CLI
tests/test_bias.py  # 10 tests anti-biais
```
