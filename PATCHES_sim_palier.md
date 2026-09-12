# Correctifs pour `sim_palier_2.py`

Diffs à appliquer tels quels. Les deux premiers sont des bugs de code ; les
suivants sont des problèmes de protocole.

---

## 1. MDD gonflé par les retraits (`run_one`)

Le `peak` n'est jamais réajusté après un retrait, donc chaque retrait est
compté comme un drawdown permanent. Démontré : à palier 2500$, MDD rapporté
31.8% contre 1.4% réel, sur des trades **identiques**.

```diff
                 retrait = 0.0
                 if palier > 0:
                     while capital >= seuil_retrait:
                         capital      -= palier
                         retrait      += palier
                         total_retire += palier
                         if total_retire >= CAPITAL_INIT and free_run_date is None:
                             free_run_date = t["exit_time"]
+                    # Le capital retiré n'est pas perdu : il sort du compte.
+                    # Sans réajuster le peak, le retrait se comptabilise en
+                    # drawdown et pénalise mécaniquement les gros paliers.
+                    peak -= retrait
```

Variante plus propre — suivre la valeur totale (compte + retraits cumulés) :

```diff
                 capital   += pnl_usd
-                if capital > peak: peak = capital
-                dd = (peak - capital) / peak * 100
+                valeur_totale = capital + total_retire
+                if valeur_totale > peak: peak = valeur_totale
+                dd = (peak - valeur_totale) / peak * 100
                 if dd > max_dd: max_dd = dd
```

---

## 2. Lookahead de 4h dans le filtre BTC (`get_all_signals`)

`btc_h4` est indexé par `open_time`. La ligne dont `open_time == entry_time`
est la bougie qui **vient de s'ouvrir** : son `close` n'existera que 4h plus
tard. Le filtre décide donc en connaissant le futur.

```diff
         if btc_h4 is not None:
-            btc_before = btc_h4[btc_h4.index <= entry_time]
+            # L'index est open_time : la bougie ouvrant à entry_time n'a pas
+            # encore de close. Seules les bougies CLOTUREES sont disponibles.
+            btc_before = btc_h4[btc_h4.index < entry_time]
             if btc_before.empty: continue
```

Relance avec et sans ce correctif : l'écart de PF te dit combien de ton
résultat venait du lookahead.

---

## 3. Spreads live appliqués à 2025 (`fetch_spread` / `main`)

Un backtest doit être déterministe. Là, le résultat dépend du moment où tu
lances le script, et `except: return 0.05` masque silencieusement les échecs.

```diff
-def fetch_spread(coin):
+def fetch_spread(coin, strict=True):
     try:
         r   = requests.post(HL_API, json={"type":"l2Book","coin":coin,"nSigFigs":5}, timeout=5)
         lvl = r.json().get("levels", [])
-        if len(lvl) < 2 or not lvl[0] or not lvl[1]: return 0.05
+        if len(lvl) < 2 or not lvl[0] or not lvl[1]:
+            raise ValueError(f"carnet vide pour {coin}")
         bid = float(lvl[0][0]["px"]); ask = float(lvl[1][0]["px"])
         return round((ask-bid)/bid*100, 6)
-    except: return 0.05
+    except Exception as e:
+        if strict:
+            raise RuntimeError(f"spread indisponible pour {coin}: {e}") from e
+        print(f"{YLW}  ATTENTION {coin}: spread par défaut 0.05%{RST}")
+        return 0.05
```

Puis dans `main()`, figer la table une fois pour toutes :

```diff
     print(f"{BLU}Fetch spreads...{RST}")
-    spreads = {}
-    for symbol, _ in TOKENS:
-        coin = symbol.replace("USDT","").replace("1000PEPE","kPEPE")
-        spreads[symbol] = fetch_spread(coin)
-    print(f"  OK\n")
+    spread_file = DATA_DIR / "spreads_fige.json"
+    if spread_file.exists():
+        import json
+        spreads = json.loads(spread_file.read_text())
+        print(f"  table figée relue ({len(spreads)} tokens)\n")
+    else:
+        import json
+        spreads = {}
+        for symbol, _ in TOKENS:
+            coin = symbol.replace("USDT","").replace("1000PEPE","kPEPE")
+            spreads[symbol] = fetch_spread(coin, strict=False)
+        spread_file.write_text(json.dumps(spreads, indent=2))
+        print(f"  table figée écrite dans {spread_file}\n")
```

---

## 4. Moyenne de ratios + sentinelle 999

`999` injecté dans une moyenne la fait exploser (démontré : PF moyen 334
au lieu de 2.0). Et la moyenne des PF n'est pas le PF des totaux.

```diff
+            gains_tot  = sum(s["gains"]  for s in sums)
+            pertes_tot = sum(s["pertes"] for s in sums)
             avg = {
                 ...
-                "pf":             round(sum(s["pf"] for s in sums) / len(sums), 3),
+                # PF agrégé : on somme gains et pertes AVANT de diviser.
+                "pf":             round(gains_tot / pertes_tot, 3) if pertes_tot > 0 else float("nan"),
```

Ce qui suppose de remonter `gains` et `pertes` depuis `run_one` :

```diff
     return trades_journal, {
         ...
         "pf":             pf,
+        "gains":          gains,
+        "pertes":         pertes,
```

---

## 5. Sélection des tokens — le point le plus grave

`TOKENS_LONG` (20) et `TOKENS_SHORT` (19) sont asymétriques : SEI/ARB/BIO/JUP/
XRP/LTC/NEAR/SUI en short seul, ZEC/WIF/INJ/DASH/LDO/AERO/ENA/1000PEPE/FARTCOIN
en long seul. Rien ne prédisposait SEI à n'être que short **avant** de l'avoir
constaté sur 2025 — qui est précisément la période testée.

Si ces listes viennent des résultats 2025, le backtest est circulaire :
sélectionner les gagnants puis mesurer combien les gagnants gagnent. C'est le
mécanisme exact qui a produit le « rêve original PF 1.35, 10k→67k » que tu as
toi-même identifié comme artefact de données.

**Test décisif, à faire avant toute autre optimisation :**

```python
TOKENS_LONG  = [(s, "2025-01-01") for s in TOUS_LES_58_TOKENS]
TOKENS_SHORT = [(s, "2025-01-01") for s in TOUS_LES_58_TOKENS]
```

Si le PF s'effondre, la sélection portait tout le résultat.

---

## 6. `FIBO_LEVEL = 0.224` et `CHECK_TF = 300`

0.224 n'est pas un niveau de Fibonacci (0.236, 0.382, 0.5, 0.618). 300 minutes
n'est un timeframe sur aucun exchange et ne s'aligne pas sur les signaux H4 —
les points de contrôle dépendent de l'heure d'entrée de chaque trade, pas de
l'horloge. Deux paramètres non naturels issus d'un balayage : signature d'un
pic, pas d'un plateau.

Balaye `fibo_level` sur `[0.15, 0.20, 0.224, 0.25, 0.30, 0.382]` et `check_tf`
sur `[180, 240, 300, 360, 480]`. Si 0.224/300 est un pic isolé, c'est du bruit.
Le sélecteur par plateau de `quantlab/validation/walkforward.py` fait cet
arbitrage automatiquement.

---

## 7. Ce que ce script ne peut pas mesurer

Il est **séquentiel** : une position à la fois, 100% du capital dessus. Donc :

- **aucune diversification** — la vol du portefeuille est celle du trade unique,
  c'est la configuration la plus défavorable à un Sharpe élevé ;
- **le PF n'est pas le Sharpe** — il ignore la chronologie et la taille des
  positions ; deux systèmes de même PF peuvent avoir des Sharpe de 0.3 et 2.0 ;
- **les paliers de retrait ne changent pas le Sharpe** — retirer de l'argent
  modifie la trajectoire du capital, pas le rendement par unité de risque. Les
  140 jobs optimisent une variable orthogonale à l'edge ;
- **`_random.shuffle` + `N_RUNS=10` n'est pas un test de robustesse** — il ne
  fait varier que le départage entre signaux d'une même bougie.

Réutilisable tel quel : le modèle de coûts (`FRAIS_AR`, `SPREAD_X`), repris à
l'identique dans `Config.cost_per_side_frac()`, et la vérification intrabar à la
minute — reproduite par le moteur H4 via low/high, le low H4 étant le min des
lows 1-min.
