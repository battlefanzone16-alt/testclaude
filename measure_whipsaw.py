#!/usr/bin/env python3
"""Mesure le taux de faux départs sur TES données — A LANCER SUR TON PC.

    python measure_whipsaw.py data_h4

Répond à trois questions, toutes sur tes vraies séries :

  1. Le Kalman et l'EMA-63 donnent-ils bien les mêmes signaux chez toi ?
     (la théorie dit oui ; on vérifie plutôt que de croire)

  2. Quel est le taux réel de faux départs du croisement, par token ?

  3. Une entrée par cassure Donchian fait-elle mieux, et de combien ?

Aucun chiffre n'est produit ici sans tes données : le script refuse de tourner
sur du synthétique. C'est volontaire.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quantlab.core.indicators import kalman_bq, ema, donchian_combined, kalman_gain_steady
from quantlab.data.prepare import load_universe


def faux_departs(signal_idx, close, reference, n_bars: int) -> tuple[int, int]:
    """Combien de signaux sont annulés dans les n_bars bougies qui suivent.

    'Annulé' = le close repasse sous la référence (Kalman ou médiane) avant
    d'avoir eu le temps de s'établir. C'est le faux départ au sens de ton CSV :
    la cassure ne tient pas.
    """
    n = len(close)
    tot = faux = 0
    for i in signal_idx:
        j0, j1 = i + 1, min(i + 1 + n_bars, n)
        if j1 <= j0:
            continue
        tot += 1
        seg_c, seg_r = close[j0:j1], reference[j0:j1]
        m = np.isfinite(seg_r)
        if m.any() and np.any(seg_c[m] < seg_r[m]):
            faux += 1
    return faux, tot


def refuser_synthetique(uni: dict) -> None:
    """Garde-fou : ce script ne doit produire de chiffres que sur du marché réel.

    Les séries générées par quantlab.data.synth sont préfixées SYN. Un chiffre
    mesuré dessus décrit le générateur, pas le marché — et ce générateur injecte
    des régimes de tendance, ce qui avantage mécaniquement une entrée par
    cassure. Le laisser passer, c'est fabriquer une preuve circulaire.
    """
    synth = [t for t in uni if t.upper().startswith("SYN")]
    if synth:
        raise SystemExit(
            f"\nREFUS : {len(synth)} tokens synthétiques détectés ({', '.join(synth[:5])}...).\n"
            "Ce script ne mesure que des données de marché réelles. Un taux de faux\n"
            "départs calculé sur des séries simulées ne dit rien de ton marché.\n"
            "Pointe-le sur le dossier produit par `quantlab.run prepare` à partir\n"
            "de tes données Binance.\n")


def main(data_dir: str, dc_length: int = 20, n_bars: int = 3):
    uni = load_universe(data_dir)
    refuser_synthetique(uni)
    print(f"\n{len(uni)} tokens chargés depuis {data_dir}")
    print(f"Faux départ = le close repasse sous la référence dans les "
          f"{n_bars} bougies suivantes.\n")

    print("=" * 92)
    print("1. KALMAN vs EMA-63 SUR TES DONNEES")
    print("=" * 92)
    print(f"  gain stationnaire théorique du Kalman : {kalman_gain_steady(0.001,1.0):.6f}")
    print(f"  alpha d'une EMA-63                    : {2/64:.6f}\n")

    corrs, accords = [], []
    for tok, df in uni.items():
        c = df["close"].to_numpy(float)
        k, e = kalman_bq(c), ema(c, 63)
        m = np.isfinite(k) & np.isfinite(e)
        if m.sum() < 100:
            continue
        corrs.append(np.corrcoef(k[m], e[m])[0, 1])
        sk = (c[1:] > k[1:]) & (c[:-1] <= k[:-1])
        se = (c[1:] > e[1:]) & (c[:-1] <= e[:-1])
        mm = np.isfinite(k[1:]) & np.isfinite(e[1:])
        accords.append((sk[mm] == se[mm]).mean())
    print(f"  corrélation moyenne Kalman / EMA-63   : {np.mean(corrs):.8f}")
    print(f"  accord moyen sur les signaux d'entrée : {np.mean(accords)*100:.3f}%")
    print("  -> si c'est ~100%, le Kalman ne t'apporte rien qu'une EMA n'ait déjà.\n")

    print("=" * 92)
    print("2. FAUX DEPARTS : CROISEMENT vs CASSURE, PAR TOKEN")
    print("=" * 92)
    print(f"  {'token':<16} {'croisements':>12} {'faux':>8} {'%':>7}   "
          f"{'cassures':>10} {'faux':>8} {'%':>7}")
    print("  " + "-" * 88)

    tc = fc = tb = fb = 0
    rows = []
    for tok, df in sorted(uni.items()):
        c = df["close"].to_numpy(float)
        h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float)
        k = kalman_bq(c)
        up, lo, med = donchian_combined(h, l, dc_length, 2, 4)

        idx_cross = np.nonzero((c[1:] > k[1:]) & (c[:-1] <= k[:-1]))[0] + 1
        f1, t1 = faux_departs(idx_cross, c, k, n_bars)

        prev_up = np.concatenate(([np.nan], up[:-1]))
        brk = np.nan_to_num((c > prev_up) &
                            (np.concatenate(([np.nan], c[:-1])) <= prev_up)).astype(bool)
        idx_brk = np.nonzero(brk)[0]
        f2, t2 = faux_departs(idx_brk, c, med, n_bars)

        tc += t1; fc += f1; tb += t2; fb += f2
        p1 = f1 / t1 * 100 if t1 else 0.0
        p2 = f2 / t2 * 100 if t2 else 0.0
        rows.append((tok, t1, f1, p1, t2, f2, p2))
        print(f"  {tok:<16} {t1:>12} {f1:>8} {p1:>6.1f}%   "
              f"{t2:>10} {f2:>8} {p2:>6.1f}%")

    print("  " + "-" * 88)
    pc = fc / tc * 100 if tc else 0.0
    pb = fb / tb * 100 if tb else 0.0
    print(f"  {'TOTAL':<16} {tc:>12} {fc:>8} {pc:>6.1f}%   "
          f"{tb:>10} {fb:>8} {pb:>6.1f}%")

    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    if tc == 0 or tb == 0:
        print("  Pas assez de signaux pour conclure.")
    elif pb < pc - 5:
        print(f"  La cassure réduit les faux départs de {pc-pb:.1f} points "
              f"({pc:.1f}% -> {pb:.1f}%).")
        print("  Sur un système dont la contrainte dominante est le coût, ça vaut le test.")
        print("  Etape suivante : python -m quantlab.run ablation --data " + data_dir)
    elif pb > pc + 5:
        print(f"  La cassure fait PIRE ({pb:.1f}% contre {pc:.1f}%). Garde le croisement.")
    else:
        print(f"  Match nul ({pc:.1f}% vs {pb:.1f}%). Le gain est ailleurs "
              "que dans le type de signal.")

    pd.DataFrame(rows, columns=["token", "croisements", "faux_cross", "pct_cross",
                                "cassures", "faux_brk", "pct_brk"]).to_csv(
        "reports_whipsaw.csv", index=False, sep=";")
    print("\n  détail par token -> reports_whipsaw.csv")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1],
                  int(sys.argv[2]) if len(sys.argv) > 2 else 20,
                  int(sys.argv[3]) if len(sys.argv) > 3 else 3))
