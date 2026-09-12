# CONTEXTE SYSTÈME KALMAN — v5 (4 juin 2026)

## Langue & Utilisateur
- Tout en français. Utilisateur = "tarik", retail algo trader crypto sur Hyperliquid (HL).
- Données prix = Binance futures 1-min. Frais: FRAIS_AR=0.086, SPREAD_X=3.

---

## PHASE 1 : ENQUÊTE EMA50 (session précédente, résumé)

**Transcript** : `/mnt/transcripts/2026-06-02-23-07-19-kheirbot-rebuild-risk-model.txt`

- Le rêve original (PF 1.35, 10k→67k) était un **artefact de données** — fenêtres tronquées sur ~28/56 tokens.
- Reconstruction complète des données : `generer_data_1m.py` (58 tokens HL, 0 gaps).
- Tests de 3 sorties (TP fixe, Fibo trail, ATR trail) : médiane PF <1 pour TP/Fibo, ATR ~1.06-1.14.
- Modèle de risque : SL structurel k×ATR + sizing 1%/trade → MDD ~5%.
- Tests sélection (force relative BTC), filtre régime (Choppiness, MA50 BTC), trail asymétrique : **aucun gain persistant**.
- Test Kalman vs EMA50 : même expR, plus de trades.
- **Synthèse Phase 1** : L'entrée EMA50+pente a un edge mince (~0.05 expR), sensible aux coûts (meurt à ×3). Le seul "edge" est la défense (préserve le capital dans le bear).

---

## PHASE 2 : NOUVEAU SYSTÈME KALMAN (session actuelle)

### Indicateurs répliqués (indicateurs.py)

**Donchian Channel "Pivot High-Low"** (© HeWhoMustNotBeNamed, v4) :
- Mode Combined, pvtLenR=4, pvtLenL=2, waitforclose=true.
- Combine Donchian sur pivots (forward-fill) avec Donchian classique.
- Médiane = (middleP + middleC) / 2.

**Kalman Price Filter** (© BackQuant, v5) :
- PN=0.001, MN=1, Filter Order=2 (no-op, le "Filter Order N" ne fait rien dans ce code).
- C'est un Kalman scalaire 1D sur le prix brut (close), gain ~0.03 ≈ EMA-65.

Utilisateur a confirmé concordance visuelle avec TradingView.

---

### Système Kalman complet : systeme_kalman.py (v5)

**Fichiers nécessaires** dans le même dossier :
- `baseline_exits.py` (load_h4, get_arr, fetch_spreads, NPY_DIR, DATA_DIR)
- `baseline_risque.py` (RISK_PCT, MAX_LEV)
- `indicateurs.py` (kalman_bq, donchian_combined)
- `systeme_kalman.py`
- `BTCUSDT_1d.pkl` dans `data\` (pour filtre BTC daily)

#### Règles du système

**ENTRÉE LONG** : clôture H4 croise au-dessus de la ligne Kalman (close[i] > kal[i] et close[i-1] <= kal[i-1]).

**ENTRÉE SHORT** (miroir) : clôture H4 croise en dessous du Kalman.

**SL DUR** :
- Long : sous le low de la bougie de cassure (vérifié intrabar minute par minute).
- Short : au-dessus du high de la bougie de cassure.
- Option `SL_DONCHIAN = True` : SL = borne basse Donchian (long) / haute (short) au lieu de la mèche.

**SIZING** : taille calculée pour que le SL dur coûte 1% du capital (cap levier 3x).

**SORTIE SOUPLE** (2 phases selon position vs médiane Donchian) :
- Phase Kalman (sous médiane) : sortie si clôture H4 < Kalman. Dès qu'une clôture passe AU-DESSUS de la médiane → bascule "phase médiane".
- Phase Médiane (au-dessus) : sortie si clôture H4 < médiane Donchian.
- En `VARIANTE_KALMAN_SEUL = True` : soft stop = toujours Kalman, mais la médiane reste calculée pour `TIME_BELOW_N`.

**SHORT = miroir exact** : SL dur = high, exit quand close > Kalman/médiane, profit = (entry-close)/entry, écart signé, pente signée.

#### Toutes les options (OFF par défaut)

```python
# --- DIRECTION ---
ENABLE_LONG  = True
ENABLE_SHORT = False

# --- FILTRE BTC ---
FILTRE_BTC    = False       # LONG si BTC > EMA50, SHORT si BTC < EMA50
FILTRE_BTC_TF = "daily"     # "daily" ou "h4"

# --- OPTIONS ---
VARIANTE_KALMAN_SEUL = False  # soft stop = Kalman seul (médiane reste pour TIME_BELOW)
SL_DONCHIAN    = False        # SL = borne Donchian au lieu de la mèche
MAX_SL_DIST    = None         # ex 0.08 -> skip si SL dur > 8%
MAX_DIST_KALMAN= None         # ex 0.08 -> skip si bougie trop loin du Kalman

# Sortie fixe RR (intrabar, limit order, pas de slip)
SORTIE_RR      = None         # ex 2.0 = TP à +2R

# Mise à Break-Even (intrabar, SL remonte à l'entrée)
BE_ACTIVATION_PCT = None      # ex 2.0 = BE après +2% de profit

# Time-stops
TIME_BELOW_N   = None         # si parti en zone défavorable (sous médiane) et pas résolu en N bougies
TIME_ABOVE_N   = None         # si parti en zone favorable, après N bougies
TIME_ABOVE_PCT = None         # ... et pas +PCT%

# Stratagème A : sortie sur décélération de la pente Kalman
SORTIE_PENTE   = False
PENTE_MIN_R    = 2.0          # profit min en R pour armer
PENTE_SEUIL    = None         # seuil absolu optionnel

# Stratagème B : trail serré sur surchauffe (écart vertical au Kalman)
SORTIE_SURCHAUFFE  = False
SEUIL_SURCHAUFFE   = 0.08    # écart > 8% -> mode serré (close < low bougie précédente)

# Exclusions
EXCLUDE_TOKENS = []           # ex: ["GOATUSDT","FARTCOINUSDT"]
ALL_TOKENS = False            # True -> 58 tokens + journal complet + CSV auto
```

#### Chaîne de priorité des sorties

1. **SL dur / BE** (intrabar, minute) — SL original ou remonté à l'entrée après +X%
2. **TP_RR** (intrabar, limit order) — pas de slip
3. **Time-stops** (clôture H4) — time<méd, time+%
4. **Stratagème A** — ralentissement pente Kalman en profit > PENTE_MIN_R
5. **Stratagème B** — trail serré si surchauffe active (REMPLACE le soft normal)
6. **Soft normal** — clôture < Kalman (phase kalman) ou clôture < médiane (phase médiane)

Le plus tôt dans le temps gagne. Arbitrage par timestamp (intrabar ms vs clôture H4 ms).

#### Sauvegarde CSV automatique

Fichier : `resultats_kalman_YYYYMMDD_HHMMSS.csv` (séparateur `;`, UTF-8-sig pour Excel).
Colonnes : token, date_entree, sens, entree, sl_dur, sortie, raison, pnl_pct, R, capital.

#### Heure d'affichage

Les dates du journal = clôture de la bougie de cassure (= ouverture de la bougie suivante).
Pour retrouver la bougie sur TradingView : heure affichée − 4h = label de la bougie de cassure.

---

### Bugs corrigés

1. **VARIANTE_KALMAN_SEUL + TIME_ABOVE_N** : le code utilisait la médiane pour classifier started_below → TIME_ABOVE jamais vérifié si la cassure était sous la médiane. Fix : `below_resolved` flag séparé, la médiane reste pour TIME_BELOW mais ne bloque plus TIME_ABOVE.

2. **TIME_BELOW_N en VARIANTE_KALMAN_SEUL** : `started_below = False` forçait TIME_BELOW désactivé. Fix : started_below utilise la médiane même en VARIANTE (la médiane est toujours calculée, sert uniquement pour la classification et TIME_BELOW). Le soft stop reste Kalman.

3. **nan dans expR** : tokens récemment listés avec Donchian nan → sl_dist nan → R nan. Fix : `if not (sl_dist > 0): return None` (attrape nan ET négatifs). Agrégation avec `np.nanmedian`.

---

## ANALYSE CSV — DÉCOUVERTE MAJEURE

**Fichier** : `resultats_kalman_20260604_132119.csv` — 2457 trades, 58 tokens, LONG+SHORT.

### Stats globales
- 1189 LONG, 1268 SHORT (performance quasi identique entre les deux sens)
- PnL moyen : +0.18%, R moyen : +0.03, WR : 27%
- Médiane net% par token : +2.7%, médiane MDD : 6%, 41/58 positifs

### La découverte : clôt<Kalman = 100% perdants

| Raison | Trades | WR | PnL moyen | PnL total |
|---|---|---|---|---|
| **clôt<médiane** | 1 392 | **47%** | **+1.74%** | **+2 418%** |
| **clôt<Kalman** | 778 | **0%** | **−1.48%** | **−1 154%** |
| SL dur | 266 | 0% | −3.19% | −849% |
| BE | 8 | 0% | −0.35% | −3% |

**Interprétation** : les trades qui passent au-dessus de la médiane et se font traquer par elle sont rentables (47% WR). Les trades qui restent coincés sous la médiane et sortent via clôture<Kalman sont **TOUS perdants** — 778 faux départs à 0% WR, −1 154% de drain. C'est le plus gros saignement du système.

### Distribution R
- R > +1 : 11.5% des trades
- R > +3 : 3.8% des trades (ces ~93 trades portent TOUT le résultat)
- R > +5 : 1.5%
- R > +10 : 0.2%

### Top/Flop tokens
- **Top** : WLD +24.2%, PENGU +18.8%, ALGO +18.1%, GOAT +17.4%, XLM +16.5%
- **Flop** : AVAX −13.1%, ONDO −12.8%, LTC −12.5%, BNB −11.9%

---

## PROCHAINES ÉTAPES (priorité)

### 1. Couper l'hémorragie clôt<Kalman (778 trades, −1 154%)
Trois pistes à tester :
- **`TIME_BELOW_N = 1`** (couper en 1 bougie si pas passé la médiane — le plus chirurgical)
- **Filtrer à l'entrée** : n'entrer que si prix DÉJÀ au-dessus de la médiane
- **`MAX_DIST_KALMAN`** serré pour virer les fausses cassures timides

### 2. Tester les options une par une
- SORTIE_PENTE (ralentissement pente en profit)
- SORTIE_SURCHAUFFE (trail serré après pump parabolique)
- SORTIE_RR (TP fixe en R)
- BE_ACTIVATION_PCT (mise à BE après +X%)
- SL_DONCHIAN (SL structurel vs mèche)
- DC_LENGTH sweep (7, 10, 20)
- FILTRE_BTC (daily vs h4)

### 3. Validation
- Persistence H1/H2 sur le système Kalman
- Test holdout 2024 (toujours scellé) quand un candidat propre émerge

---

## FICHIERS LIVRÉS (tous dans /mnt/user-data/outputs/)

| Fichier | Rôle |
|---|---|
| `systeme_kalman.py` (v5) | Système principal — tout est dedans |
| `indicateurs.py` | Kalman + Donchian répliqués de TradingView |
| `baseline_exits.py` | Infra données/signaux EMA, load_h4, get_arr |
| `baseline_risque.py` | Modèle de risque chandelier k×ATR |
| `contexte_kalman_v5.md` | Ce fichier |

---

## PRINCIPES MÉTHODOLOGIQUES

- Chaque composant testé **UN À LA FOIS**, OOS-validé, plateau pas pic.
- 2024 = write-once holdout, **jamais touché** tant qu'on n'a pas un candidat pré-engagé.
- Plus d'idées testées → barre du hasard monte (comparaisons multiples).
- Les indicateurs doivent **concorder avec TradingView** avant de bâtir dessus.
- Journal de trades visible (pas que des médianes) — chaque trade est inspecté.
- Le Kalman TradingView (BackQuant) est un simple scalaire 1D, gain ~0.03, "Filter Order" est un no-op.
- **Découverte clé** : clôt<Kalman = 100% perdants → principal levier d'amélioration.
