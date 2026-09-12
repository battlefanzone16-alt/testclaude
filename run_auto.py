#!/usr/bin/env python3
"""Pipeline automatique — télécharge, teste, valide, produit un rapport HTML.

Lancé par LANCER.bat. Ne demande rien, ne suppose rien, et écrit toute erreur
dans le rapport plutôt que de planter dans une console que personne ne lira.

    python run_auto.py                       # SOLUSDT, 2 ans
    python run_auto.py SOLUSDT BTCUSDT ETHUSDT
"""
from __future__ import annotations

import os
import sys
import time
import traceback
import webbrowser

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quantlab.core.config import Config
from quantlab.core.portfolio import run_universe
from quantlab.core import metrics
from quantlab.validation import montecarlo as mc
from quantlab.validation.walkforward import walk_forward
from quantlab import report as R

DEFAUT = ["SOLUSDT"]
GRILLE = {"dc_length": [10, 20, 30], "sl_atr_mult": [1.5, 2.0, 3.0]}


def log(msg=""):
    print(msg, flush=True)


def pct(x):
    return f"{x*100:,.1f}%"


def charger(symbols, debut, fin):
    from quantlab.data.binance_vision import fetch_universe, ReseauBloque
    log(f"[1/5] Téléchargement depuis data.binance.vision ({debut} -> {fin})")
    try:
        uni = fetch_universe(symbols, debut, fin, interval="4h", market="futures")
    except ReseauBloque as e:
        raise SystemExit(f"\nRESEAU BLOQUE\n{e}\n")
    if not uni:
        raise SystemExit("\nAucune donnée téléchargée.\n")
    return uni


def main(argv):
    symbols = [s.upper() for s in argv[1:]] or DEFAUT
    fin = pd.Timestamp.today().normalize()
    debut = fin - pd.DateOffset(years=2)
    d0, d1 = debut.strftime("%Y-%m-%d"), fin.strftime("%Y-%m-%d")

    log("=" * 72)
    log(f"  KALMAN v6 — test automatique sur {', '.join(symbols)}")
    log("=" * 72 + "\n")

    uni = charger(symbols, d0, d1)
    n_bars = len(next(iter(uni.values())))
    blocks, avert = [], []

    if len(uni) == 1:
        avert.append(
            "Test sur un seul actif : aucune diversification. La volatilité du "
            "portefeuille est celle du token. C'est la configuration la PLUS "
            "défavorable à un Sharpe élevé — un résultat modeste ici ne condamne "
            "pas le système en multi-tokens.")

    # ---------------- 2. comparaison des entrées ----------------
    log("\n[2/5] Comparaison croisement Kalman vs cassure Donchian")
    lignes, resultats = [], {}
    for mode, nom in [("kalman_cross", "Croisement Kalman (v5)"),
                      ("donchian_breakout", "Cassure Donchian (v6)")]:
        cfg = Config(entry_mode=mode)
        r = run_universe(uni, cfg)
        resultats[mode] = r
        s, tr = r["stats"], r["trades"]
        wr = float((tr["net_pct"] > 0).mean()) if len(tr) else 0.0
        lignes.append({"mode": nom, "sharpe": s["sharpe"], "cagr": pct(s["cagr"]),
                       "mdd": pct(s["max_drawdown"]), "trades": s["n_trades"],
                       "wr": pct(wr)})
        log(f"  {nom:<26} Sharpe {s['sharpe']:+.2f}  "
            f"CAGR {pct(s['cagr']):>8}  MDD {pct(s['max_drawdown']):>7}  "
            f"{s['n_trades']:>4} trades")

    meilleur = max(resultats, key=lambda k: resultats[k]["stats"]["sharpe"])
    ref = resultats[meilleur]
    cfg_ref = Config(entry_mode=meilleur)
    s = ref["stats"]

    blocks.append("<h2>Résultat principal</h2>")
    blocks.append('<div class="tiles">' + "".join([
        R.stat_tile("Sharpe", f"{s['sharpe']:+.2f}",
                    "ok" if s["sharpe"] > 1.5 else ("warn" if s["sharpe"] > 0.5 else "bad"),
                    "cible > 1.50"),
        R.stat_tile("CAGR", pct(s["cagr"]), "ok" if s["cagr"] > 0 else "bad"),
        R.stat_tile("Drawdown max", pct(s["max_drawdown"]),
                    "bad" if s["max_drawdown"] > 0.35 else "warn"),
        R.stat_tile("Trades", f"{s['n_trades']:,}"),
    ]) + "</div>")

    blocks.append("<h2>Quelle entrée ?</h2>")
    blocks.append("<p>Même sortie, mêmes coûts, même gestion du risque. "
                  "Seul le signal d'entrée change.</p>")
    blocks.append(R.table(lignes, ["mode", "sharpe", "cagr", "mdd", "trades", "wr"],
                          ["Entrée", "Sharpe", "CAGR", "MDD", "Trades", "% gagnants"]))

    # ---------------- 3. courbe d'équité ----------------
    log("\n[3/5] Courbe d'équité")
    eq = ref["equity"]
    px = next(iter(uni.values()))["close"]
    bh = (px / px.iloc[0]).reindex(eq.index).ffill()
    blocks.append("<h2>Évolution du capital</h2>")
    blocks.append('<div class="card">' + R.line_chart(
        {"Stratégie": (eq.index, eq.to_numpy()),
         "Achat & conservation": (bh.index, bh.to_numpy())},
        "Capital (base 1)", y_fmt="{:.2f}") + "</div>")

    # ---------------- 4. Monte Carlo ----------------
    log("\n[4/5] Monte Carlo (peut prendre quelques minutes)")
    rets = ref["returns"].to_numpy()
    a = mc.test_a_block_bootstrap(rets, cfg_ref.bars_per_year, n_iter=2000, seed=1)
    log(f"  [A] P(Sharpe<=0) = {a['p_value_le_zero']:.3f}")
    b = mc.test_b_trade_shuffle(ref["trades"], n_iter=2000, seed=1)
    d = mc.test_d_resampled_paths(uni, cfg_ref, n_iter=120, seed=1, progress=True)
    log(f"  [D] médiane {d['p50']:+.2f}, P(>0) = {d['prob_positive']:.2f}")

    blocks.append("<h2>Le résultat est-il du hasard ?</h2>")
    blocks.append('<div class="card"><h3>A — rééchantillonnage par blocs</h3>'
                  '<p>On rebat les rendements en préservant leur structure. '
                  'Si le Sharpe observé est banal dans cette distribution, '
                  'il ne prouve rien.</p>'
                  + R.histogram(a["distribution"], s["sharpe"],
                                "Distribution du Sharpe", label_obs="observé")
                  + f'<p>Probabilité que le vrai Sharpe soit négatif : '
                    f'<strong>{a["p_value_le_zero"]:.1%}</strong></p></div>')

    blocks.append('<div class="card"><h3>D — marchés rééchantillonnés</h3>'
                  '<p>Le test le plus dur : on rejoue toute la stratégie, '
                  'indicateurs compris, sur des marchés qui auraient pu se '
                  'produire. Il casse les coïncidences de dates.</p>'
                  + R.histogram(d["distribution"], s["sharpe"],
                                "Sharpe sur marchés simulés", label_obs="réel")
                  + f'<p>Médiane <strong>{d["p50"]:+.2f}</strong> · '
                    f'5e centile <strong>{d["p05"]:+.2f}</strong> · '
                    f'positif dans <strong>{d["prob_positive"]:.0%}</strong> des cas</p></div>')

    if "error" not in b:
        blocks.append('<div class="card"><h3>B — ordre des trades</h3>'
                      '<p>Même P&amp;L, ordre différent. Montre le drawdown que '
                      'tu aurais pu subir avec un peu moins de chance.</p>'
                      + R.histogram(b["distribution"], b["observed_mdd"],
                                    "Drawdown maximal", x_fmt="{:.0%}",
                                    label_obs="subi")
                      + f'<p>Drawdown médian <strong>{b["mdd_p50"]:.1%}</strong>, '
                        f'99e centile <strong>{b["mdd_p99"]:.1%}</strong>. '
                        f'Risque de perdre plus de la moitié du capital : '
                        f'<strong>{b["prob_drawdown_gt_50pct"]:.1%}</strong></p></div>')

    # ---------------- 5. walk-forward ----------------
    log("\n[5/5] Walk-forward")
    wf_ok = False
    try:
        if n_bars >= 1500:
            wf = walk_forward(uni, cfg_ref, GRILLE, n_folds=3, verbose=True)
            w = wf["oos_stats"]
            wf_ok = True
            blocks.append("<h2>Hors échantillon — le seul chiffre crédible</h2>")
            blocks.append("<p>Chaque période est jouée avec des réglages choisis "
                          "<em>sans l'avoir vue</em>. C'est ce que tu obtiendrais "
                          "réellement.</p>")
            blocks.append('<div class="tiles">' + "".join([
                R.stat_tile("Sharpe hors échantillon", f"{w['sharpe']:+.2f}",
                            "ok" if w["sharpe"] > 1.5 else ("warn" if w["sharpe"] > 0.5 else "bad")),
                R.stat_tile("Sharpe dégonflé", f"{w['deflated_sharpe']:.1%}",
                            "ok" if w["deflated_sharpe"] > 0.95 else "bad",
                            f"{w['n_trials']} essais comptés"),
                R.stat_tile("CAGR", pct(w["cagr"])),
                R.stat_tile("MDD", pct(w["max_drawdown"])),
            ]) + "</div>")
            ecart = s["sharpe"] - w["sharpe"]
            if ecart > 0.5:
                avert.append(
                    f"Le Sharpe chute de {s['sharpe']:+.2f} à {w['sharpe']:+.2f} "
                    f"hors échantillon ({ecart:.2f} d'écart). C'est la signature "
                    "d'un surajustement : le vrai chiffre est celui de droite.")
        else:
            avert.append(f"Historique trop court ({n_bars} bougies) pour un "
                         "walk-forward fiable.")
    except Exception as e:
        avert.append(f"Walk-forward non abouti : {e}")

    # ---------------- verdict ----------------
    sharpe_final = wf["oos_stats"]["sharpe"] if wf_ok else s["sharpe"]
    tests = {
        "Sharpe significatif (pas du bruit)": a["p_value_le_zero"] < 0.05,
        "Règles robustes sur marchés simulés": d["p05"] > 0.0,
        "Drawdown soutenable": b.get("prob_drawdown_gt_50pct", 1.0) < 0.05,
        "Sharpe > 1.5": sharpe_final > 1.5,
    }
    passes = sum(tests.values())
    lignes_v = [{"t": k, "r": "PASS" if v else "ECHEC"} for k, v in tests.items()]

    verdict_blocks = ["<h2>Verdict</h2>",
                      R.table(lignes_v, ["t", "r"], ["Test", "Résultat"])]
    if passes == len(tests):
        verdict_blocks.append('<div class="note ok-note">Tous les tests passent. '
                              'Étape suivante : rejouer sur l\'ensemble de tes '
                              'tokens, puis sur le holdout 2024.</div>')
    else:
        verdict_blocks.append(
            f'<div class="note bad-note">{passes}/{len(tests)} tests passés. '
            'Un système qui échoue ici échouera en réel — le backtest est la '
            'version optimiste.</div>')
    blocks = blocks[:2] + verdict_blocks + blocks[2:]

    for a_ in avert:
        blocks.append(f'<div class="note">{R._esc(a_)}</div>')

    blocks.append("<h2>Comment lire ce rapport</h2>")
    blocks.append(
        "<p><strong>Sharpe</strong> : rendement par unité de risque. "
        "Au-dessus de 1 c'est bon, au-dessus de 2 c'est rare et suspect. "
        "<strong>Sharpe dégonflé</strong> : probabilité que le résultat ne soit "
        "pas simplement le meilleur de plusieurs essais sur du bruit — en dessous "
        "de 95%, le chiffre n'est pas fiable. "
        "<strong>Hors échantillon</strong> : mesuré sur des périodes que "
        "l'optimisation n'a pas vues ; c'est le seul chiffre à retenir.</p>")

    sub = (f"{', '.join(symbols)} · {n_bars} bougies H4 · "
           f"{d0} au {d1} · coûts {Config().cost_per_side_frac()*200:.3f}% aller-retour · "
           f"généré le {time.strftime('%d/%m/%Y %H:%M')}")
    page = R.build_page("Rapport stratégie Kalman v6", sub, blocks)

    out = os.path.abspath("rapport.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    log(f"\n{'='*72}\n  RAPPORT : {out}\n{'='*72}")
    try:
        webbrowser.open("file://" + out)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        log("\nUne erreur est survenue. Copie tout ce texte et envoie-le.")
        input("\nAppuie sur Entrée pour fermer...")
        sys.exit(1)
