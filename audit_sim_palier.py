#!/usr/bin/env python3
"""Audit de sim_palier_2.py — démonstrations chiffrées, pas des affirmations.

Chaque bloc reproduit un bug isolément et montre l'écart entre ce que le code
mesure et ce qu'il croit mesurer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def bug1_mdd_gonfle_par_les_retraits():
    """Le peak n'est jamais réduit après un retrait -> MDD surestimé.

    Dans run_one() :
        capital += pnl_usd
        if capital > peak: peak = capital
        dd = (peak - capital) / peak * 100        # OK, avant retrait
        ...
        while capital >= seuil_retrait:
            capital -= palier                     # peak reste à l'ancien niveau

    Au trade SUIVANT, dd est calculé avec un peak d'avant-retrait contre un
    capital d'après-retrait. Le retrait est compté comme une perte.
    """
    print("=" * 78)
    print("BUG 1 — le MDD est gonflé par les retraits (peak jamais réajusté)")
    print("=" * 78)

    CAPITAL_INIT = 5000.0
    # Une suite de trades identique pour tous les paliers : que du gain régulier
    # puis une petite perte. Aucun vrai drawdown de plus de 2%.
    pnl_pcts = [3.0] * 20 + [-2.0] + [3.0] * 20

    for palier in [0, 250, 500, 1000, 2500]:
        capital = peak = CAPITAL_INIT
        max_dd_code = 0.0                      # ce que calcule le code actuel
        seuil = CAPITAL_INIT + palier if palier > 0 else float("inf")

        cap_corrige = CAPITAL_INIT             # capital + retraits cumulés
        peak_c = CAPITAL_INIT
        max_dd_vrai = 0.0
        retire = 0.0

        for p in pnl_pcts:
            capital *= (1 + p / 100)
            if capital > peak:
                peak = capital
            dd = (peak - capital) / peak * 100
            max_dd_code = max(max_dd_code, dd)

            # référence : on suit la valeur TOTALE (compte + retiré)
            cap_corrige = capital + retire
            if cap_corrige > peak_c:
                peak_c = cap_corrige
            max_dd_vrai = max(max_dd_vrai, (peak_c - cap_corrige) / peak_c * 100)

            if palier > 0:
                while capital >= seuil:
                    capital -= palier
                    retire += palier

        lab = f"{palier}$" if palier else "sans"
        print(f"  palier {lab:>6} | MDD rapporté par le code {max_dd_code:5.1f}% | "
              f"MDD réel {max_dd_vrai:5.1f}% | écart {max_dd_code-max_dd_vrai:+5.1f} pts")

    print("""
  Les trades sont IDENTIQUES dans les 5 lignes. Seul le palier change.
  Le MDD rapporté augmente avec le palier alors que le risque réel est
  strictement le même. Conséquence directe : la colonne MDD de ton tableau
  de résultats ne compare pas ce qu'elle prétend comparer, et elle pénalise
  mécaniquement les gros paliers.
""")


def bug2_lookahead_filtre_btc():
    """btc_h4.index <= entry_time inclut la bougie qui OUVRE à entry_time.

        btc_before = btc_h4[btc_h4.index <= entry_time]
        btc_row    = btc_before.iloc[-1]
        btc_above  = float(btc_row["close"]) > float(btc_row["ema50"])

    L'index est open_time. La ligne dont open_time == entry_time est la bougie
    [entry_time, entry_time+4h] : son close n'existera que 4h plus tard.
    """
    print("=" * 78)
    print("BUG 2 — le filtre BTC lit 4h dans le futur")
    print("=" * 78)

    idx = pd.date_range("2025-01-01", periods=6, freq="4h", tz="UTC")
    btc = pd.DataFrame({"close": [100, 101, 102, 103, 90, 91]}, index=idx)
    btc["ema50"] = btc["close"].ewm(span=3, adjust=False).mean()
    btc.index.name = "open_time"

    entry_time = idx[4]        # la bougie qui s'effondre OUVRE ici

    sel_bug = btc[btc.index <= entry_time].iloc[-1]
    sel_fix = btc[btc.index < entry_time].iloc[-1]

    print(f"\n  entry_time = {entry_time}")
    print(f"  bougie retenue par le code  : open_time={sel_bug.name}  "
          f"close={sel_bug['close']:.1f}  -> close connu à {sel_bug.name + pd.Timedelta('4h')}")
    print(f"  bougie réellement disponible: open_time={sel_fix.name}  "
          f"close={sel_fix['close']:.1f}  -> close connu à {sel_fix.name + pd.Timedelta('4h')}")
    print(f"\n  filtre 'BTC au-dessus EMA' — code : {sel_bug['close'] > sel_bug['ema50']}"
          f"   |  correct : {sel_fix['close'] > sel_fix['ema50']}")
    print("""
  Le code décide d'entrer ou non en connaissant déjà le close d'une bougie
  qui vient tout juste de s'ouvrir. Sur un retournement, il « voit » la chute
  avant qu'elle ne soit publiée et filtre le trade. Correctif : remplacer
  <= entry_time par < entry_time.
""")


def bug3_spreads_actuels_sur_trades_2025():
    """fetch_spread() interroge le carnet L2 LIVE et l'applique à 2025."""
    print("=" * 78)
    print("BUG 3 — spreads d'aujourd'hui appliqués à des trades de 2025")
    print("=" * 78)
    print("""
      spreads[symbol] = fetch_spread(coin)        # carnet L2 maintenant
      spread_c = spreads.get(t["symbol"], 0.05) * SPREAD_X / 100 * trade_size

  Trois problèmes cumulés :

  a) Le spread d'un alt en janvier 2025 n'est pas celui d'aujourd'hui. Pour un
     token récemment listé il était largement plus large. Le backtest sous-estime
     le coût précisément là où il est le plus mordant.

  b) `except: return 0.05` — toute panne réseau, tout ticker renommé
     (kPEPE, coins delistés) retombe silencieusement sur 0.05%. Sans log, tu ne
     sais pas combien de tes 39 tokens tournent sur cette valeur par défaut.

  c) Le résultat dépend du MOMENT où tu lances le script. Deux exécutions à deux
     jours d'intervalle ne sont pas comparables. Un backtest doit être
     déterministe.

  Correctif : figer une table de spreads par token, versionnée sur disque, et
  faire échouer bruyamment le fetch au lieu de retomber sur une constante.
""")


def bug4_pf_moyenne_de_ratios():
    """La moyenne de PF n'est pas le PF agrégé, et 999 contamine la moyenne."""
    print("=" * 78)
    print("BUG 4 — moyenne de ratios + sentinelle 999")
    print("=" * 78)

    runs = [
        {"gains": 1000.0, "pertes": 500.0},
        {"gains": 800.0,  "pertes": 400.0},
        {"gains": 300.0,  "pertes": 0.0},      # aucune perte -> pf = 999
    ]
    pfs = [r["gains"] / r["pertes"] if r["pertes"] > 0 else 999 for r in runs]
    pf_moyen = sum(pfs) / len(pfs)
    pf_agrege = sum(r["gains"] for r in runs) / sum(r["pertes"] for r in runs)

    print(f"\n  PF par run       : {[round(p,2) for p in pfs]}")
    print(f"  moyenne des PF   : {pf_moyen:.2f}   <- ce que calcule le code")
    print(f"  PF agrégé (juste): {pf_agrege:.2f}")
    print("""
  Un seul run sans perte injecte 999 dans la moyenne et fait exploser la ligne.
  Et même sans sentinelle, la moyenne de ratios n'est pas le ratio des totaux :
  il faut agréger gains et pertes AVANT de diviser.
""")


def analyse_selection_tokens():
    """Le point le plus grave n'est pas un bug de code mais de protocole."""
    print("=" * 78)
    print("PROBLEME 5 — les listes de tokens sont-elles choisies sur la période testée ?")
    print("=" * 78)

    LONG = {"1000PEPEUSDT","PENGUUSDT","FARTCOINUSDT","APTUSDT","WIFUSDT","SOLUSDT",
            "LINKUSDT","TAOUSDT","PENDLEUSDT","ADAUSDT","INJUSDT","DASHUSDT","LDOUSDT",
            "SPXUSDT","ETHUSDT","AAVEUSDT","DOGEUSDT","AEROUSDT","ENAUSDT","ZECUSDT"}
    SHORT = {"SEIUSDT","PENGUUSDT","AAVEUSDT","LINKUSDT","ETHUSDT","ARBUSDT","ADAUSDT",
             "BIOUSDT","JUPUSDT","APTUSDT","SPXUSDT","XRPUSDT","DOGEUSDT","SOLUSDT",
             "PENDLEUSDT","TAOUSDT","LTCUSDT","NEARUSDT","SUIUSDT"}

    print(f"\n  long seulement  ({len(LONG-SHORT)}) : {sorted(LONG-SHORT)}")
    print(f"  short seulement ({len(SHORT-LONG)}) : {sorted(SHORT-LONG)}")
    print(f"  les deux        ({len(LONG&SHORT)}) : {sorted(LONG&SHORT)}")
    print(f"""
  START_DATE = 2025-01-01, et les listes portent toutes la date 2025-01-01.
  La question à te poser, et toi seul as la réponse :

    ces 39 tokens, et surtout l'asymétrie long-seul / short-seul,
    ont-ils été choisis APRES avoir regardé les résultats sur 2025 ?

  Si oui — et l'asymétrie le suggère fortement : rien ne prédisposait SEI à
  n'être que short et ZEC qu'à long avant de l'avoir constaté — alors le
  backtest est circulaire. Tu sélectionnes les gagnants puis tu mesures combien
  les gagnants gagnent. Le PF obtenu n'a aucune valeur prédictive, et c'est
  exactement le mécanisme qui a produit le « rêve original PF 1.35, 10k->67k »
  que tu as toi-même identifié comme artefact.

  Test décisif, à faire avant toute autre optimisation :
    lancer la MEME config sur les 58 tokens sans aucune liste de sélection.
    Si le PF s'effondre, la sélection portait tout le résultat.
""")


def analyse_parametres():
    print("=" * 78)
    print("PROBLEME 6 — FIBO_LEVEL=0.224 et CHECK_TF=H5 sont des pics, pas des plateaux")
    print("=" * 78)
    print("""
  0.224 n'est pas un niveau de Fibonacci. Les niveaux sont 0.236, 0.382, 0.5,
  0.618. 0.224 est une valeur SORTIE D'UNE GRILLE. Idem pour « H5 » : 300
  minutes n'est un timeframe ni chez Binance ni chez Hyperliquid, et il ne
  s'aligne pas sur les signaux H4 — les points de contrôle dépendent de l'heure
  d'entrée de chaque trade, pas de l'horloge.

  Deux paramètres non naturels, tous deux issus d'un balayage, c'est la
  signature d'un surajustement. Ta propre méthodologie le dit : « plateau pas
  pic ».

  Le test qui tranche, et il est immédiat :
    rejouer fibo_level sur [0.15, 0.20, 0.224, 0.25, 0.30, 0.382]
    et check_tf sur [180, 240, 300, 360, 480].
  Si 0.224/300 est un pic isolé entouré de résultats médiocres, c'est du bruit.
  Si c'est le centre d'une zone large et régulière, c'est un effet. Le
  sélecteur par plateau de quantlab/validation/walkforward.py fait exactement
  cet arbitrage.
""")


def comparaison_avec_quantlab():
    print("=" * 78)
    print("CE QUE CE SCRIPT MESURE vs CE QU'IL TE FAUT POUR UN SHARPE")
    print("=" * 78)
    print("""
  Le script est SEQUENTIEL : une seule position à la fois (current_trade), 100%
  du capital dessus. Conséquences pour ton objectif Sharpe > 1.5 :

  1. Aucune diversification. Avec une position unique, la vol du portefeuille
     EST la vol du trade. C'est la configuration qui rend un Sharpe élevé le
     plus difficile à atteindre.

  2. Le PF n'est pas le Sharpe. Le PF ignore complètement la chronologie et la
     taille des positions. Deux systèmes de même PF peuvent avoir des Sharpe de
     0.3 et 2.0. Tu ne peux pas atteindre une cible de Sharpe en optimisant un PF.

  3. Les paliers de retrait ne changent PAS le Sharpe. Retirer de l'argent
     modifie la trajectoire du capital, pas la distribution des rendements par
     unité de risque. Les 140 jobs de ce script optimisent une variable
     orthogonale à l'edge. C'est une question de gestion de trésorerie, à
     traiter APRES avoir établi qu'il y a un edge.

  4. `_random.shuffle(ordered)` + N_RUNS=10 n'est pas un test de robustesse. Il
     ne fait varier que l'ordre de départage entre signaux d'une même bougie.
     Il ne dit rien sur la stabilité des règles, des paramètres, ou du régime
     de marché. Les tests A/B/C/D de quantlab/validation/montecarlo.py couvrent
     ces quatre questions séparément.

  Ce qui est réutilisable tel quel : le modèle de coûts (FRAIS_AR, SPREAD_X)
  est le même que celui repris dans Config.cost_per_side_frac(), et la
  vérification intrabar à la minute est la bonne approche — c'est ce que le
  moteur H4 reproduit à l'identique via low/high (le low H4 EST le min des lows
  1-min).
""")


if __name__ == "__main__":
    bug1_mdd_gonfle_par_les_retraits()
    bug2_lookahead_filtre_btc()
    bug3_spreads_actuels_sur_trades_2025()
    bug4_pf_moyenne_de_ratios()
    analyse_selection_tokens()
    analyse_parametres()
    comparaison_avec_quantlab()
