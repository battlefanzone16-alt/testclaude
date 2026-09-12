#!/usr/bin/env python3
"""CLI du laboratoire Kalman v6.

    python -m quantlab.run prepare  --src DOSSIER_1M --out data_h4
    python -m quantlab.run ablation --data data_h4
    python -m quantlab.run optimize --data data_h4
    python -m quantlab.run validate --data data_h4
    python -m quantlab.run all      --data data_h4 --holdout 2025-07-01

Utiliser --synthetic à la place de --data pour faire tourner la chaîne sur des
données simulées (vérification du pipeline, pas de la performance).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

from .core.config import Config
from .core.portfolio import run_universe
from .core import metrics
from .data.prepare import prepare_directory, load_universe, align_universe
from .validation import montecarlo as mc
from .validation.walkforward import walk_forward, evaluate_grid, select_plateau

# Grille délibérément PETITE. Chaque axe supplémentaire monte la barre du
# Deflated Sharpe ; 3 axes x 3-4 valeurs = 36 essais, c'est déjà beaucoup.
GRID = {
    "dc_length": [10, 20, 30],
    "sl_atr_mult": [1.5, 2.0, 3.0],
    "max_sl_dist": [0.08, 0.12, None],
}


def _fmt(stats: dict, keys=None) -> str:
    keys = keys or ["sharpe", "sortino", "cagr", "max_drawdown", "calmar",
                    "vol_annual", "n_trades", "win_rate", "profit_factor",
                    "avg_gross", "exposure"]
    parts = []
    for k in keys:
        if k not in stats:
            continue
        v = stats[k]
        parts.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")
    return "  ".join(parts)


def get_universe(args) -> dict:
    if args.synthetic:
        from .data.synth import make_universe
        print(f"[data] univers SYNTHETIQUE : {args.n_tokens} tokens, {args.n_bars} bougies H4")
        print("[data] ATTENTION : bruit calibré. Aucun chiffre de performance ici n'est prédictif.\n")
        return make_universe(n_tokens=args.n_tokens, n_bars=args.n_bars, seed=args.seed)
    uni = load_universe(args.data, exclude=args.exclude.split(",") if args.exclude else None)
    uni = align_universe(uni, args.start, args.end)
    span = [f"{df.index[0]:%Y-%m-%d}->{df.index[-1]:%Y-%m-%d}" for df in uni.values()]
    print(f"[data] {len(uni)} tokens chargés   ex: {span[0] if span else '-'}\n")
    return uni


# --------------------------------------------------------------------------- #
def cmd_prepare(args):
    rep = prepare_directory(args.src, args.out, rule=args.rule)
    ok = sum(1 for v in rep.values() if "bougies" in v and "ignoré" not in v)
    for k, v in sorted(rep.items()):
        print(f"  {k:<16} {v}")
    print(f"\n{ok}/{len(rep)} tokens prêts dans {args.out}")


# --------------------------------------------------------------------------- #
def cmd_ablation(args):
    """Chaque modification ajoutée UNE A LA FOIS, comme l'exige la méthodo v5."""
    uni = get_universe(args)

    # v5 tel que décrit dans le contexte : long seul, sortie 2-phases, pas de
    # portefeuille (pas de vol targeting, pas de cap d'exposition).
    v5 = Config(enable_long=True, enable_short=False, entry_above_median=False,
                exit_on_median=True, exit_on_kalman=True, sl_mode="wick",
                max_sl_dist=None, vol_target_annual=None, max_gross=1e9,
                max_net=None)

    steps = [
        ("0. v5 baseline (long, 2-phases, pas de portefeuille)", v5),
        ("1. + gate entrée au-dessus de la médiane", v5.copy_with(
            entry_above_median=True, exit_on_kalman=False)),
        ("2. + short activé (parité constatée dans le CSV)", v5.copy_with(
            entry_above_median=True, exit_on_kalman=False, enable_short=True)),
        ("3. + cap d'exposition brute portefeuille", v5.copy_with(
            entry_above_median=True, exit_on_kalman=False, enable_short=True,
            max_gross=3.0)),
        ("4. + cap d'exposition nette (bêta marché)", v5.copy_with(
            entry_above_median=True, exit_on_kalman=False, enable_short=True,
            max_gross=3.0, max_net=1.5)),
        ("5. + filtre SL trop large", v5.copy_with(
            entry_above_median=True, exit_on_kalman=False, enable_short=True,
            max_gross=3.0, max_net=1.5, max_sl_dist=0.12)),
        ("6. + vol targeting 20% (= v6 complet)", Config()),
    ]

    rows = []
    print("=" * 100)
    print("ABLATION — contribution marginale de chaque changement")
    print("=" * 100)
    for label, cfg in steps:
        t0 = time.time()
        r = run_universe(uni, cfg)
        s = r["stats"]
        rows.append({"etape": label, **{k: s.get(k) for k in
                     ["sharpe", "cagr", "max_drawdown", "calmar", "n_trades",
                      "win_rate", "profit_factor", "vol_annual", "avg_net",
                      "avg_gross"]}})
        print(f"\n{label}   ({time.time()-t0:.1f}s)")
        print("   " + _fmt(s))
        if len(r["trades"]):
            by = r["trades"].groupby("reason")["net_pct"].agg(["count", "mean"])
            print("   sorties: " + "  ".join(
                f"{i}={int(v['count'])}@{v['mean']:+.2f}%" for i, v in by.iterrows()))

    df = pd.DataFrame(rows)

    # Contribution marginale : ce que chaque étape ajoute ou retire, seule.
    print("\n" + "=" * 100)
    print("CONTRIBUTION MARGINALE (delta de Sharpe vs l'étape précédente)")
    print("=" * 100)
    prev = None
    for _, r in df.iterrows():
        if prev is None:
            print(f"  {r['etape'][:60]:<62} Sharpe {r['sharpe']:+.3f}   (référence)")
        else:
            d = r["sharpe"] - prev
            flag = "GARDER" if d > 0.05 else ("JETER" if d < -0.05 else "neutre")
            print(f"  {r['etape'][:60]:<62} Sharpe {r['sharpe']:+.3f}  "
                  f"delta {d:+.3f}  -> {flag}")
        prev = r["sharpe"]
    print("""
Lecture : une étape marquée JETER dégrade le Sharpe sur TES données — retire-la
de la config plutôt que de la garder par principe. Une étape neutre n'apporte
rien : la retirer réduit le nombre de pièces, donc le risque d'overfitting.""")

    out = os.path.join(args.reports, "ablation.csv")
    os.makedirs(args.reports, exist_ok=True)
    df.to_csv(out, index=False, sep=";")
    print(f"\n[ok] {out}")
    return df


# --------------------------------------------------------------------------- #
def cmd_optimize(args):
    uni = get_universe(args)
    base = Config()
    print("=" * 100)
    print(f"WALK-FORWARD  ({len(list(__import__('itertools').product(*GRID.values())))} "
          f"combinaisons, sélection par PLATEAU)")
    print("=" * 100)
    wf = walk_forward(uni, base, GRID, n_folds=args.folds, selector=args.selector)
    s = wf["oos_stats"]
    print("\n--- AGREGAT OUT-OF-SAMPLE (le seul chiffre crédible) ---")
    print("   " + _fmt(s))
    print(f"   deflated_sharpe (P(vrai SR>bruit du meilleur essai)) = {s['deflated_sharpe']:.4f}")
    print(f"   psr = {s['psr']:.4f}    essais comptés = {s['n_trials']}")
    os.makedirs(args.reports, exist_ok=True)
    wf["picks"].to_csv(os.path.join(args.reports, "wf_picks.csv"), index=False, sep=";")
    wf["oos_returns"].to_csv(os.path.join(args.reports, "wf_oos_returns.csv"), sep=";")
    print(f"\n[ok] {args.reports}/wf_picks.csv, wf_oos_returns.csv")
    return wf


# --------------------------------------------------------------------------- #
def cmd_validate(args):
    uni = get_universe(args)
    cfg = Config()
    r = run_universe(uni, cfg)
    s, ret, trades = r["stats"], r["returns"].to_numpy(), r["trades"]

    print("=" * 100)
    print("VALIDATION MONTE CARLO")
    print("=" * 100)
    print("\n[référence] " + _fmt(s))

    print(f"\n[A] bootstrap par blocs ({args.iter_ab} tirages)...", flush=True)
    a = mc.test_a_block_bootstrap(ret, cfg.bars_per_year, n_iter=args.iter_ab, seed=args.seed)
    print(f"    Sharpe observé {a['observed_sharpe']:.2f} | "
          f"p05={a['p05']:.2f} p50={a['p50']:.2f} p95={a['p95']:.2f}")
    print(f"    P(Sharpe<=0) = {a['p_value_le_zero']:.4f}   "
          f"P(Sharpe>1.5) = {a['prob_sharpe_gt_1_5']:.4f}")

    print(f"\n[B] permutation de l'ordre des trades ({args.iter_ab} tirages)...", flush=True)
    b = mc.test_b_trade_shuffle(trades, n_iter=args.iter_ab, seed=args.seed)
    if "error" in b:
        print(f"    {b['error']}")
    else:
        print(f"    MDD observé {b['observed_mdd']:.3f} (percentile {b['observed_mdd_percentile']:.2f}) | "
              f"p50={b['mdd_p50']:.3f} p95={b['mdd_p95']:.3f} p99={b['mdd_p99']:.3f}")
        print(f"    P(drawdown > 50%) = {b['prob_drawdown_gt_50pct']:.4f}")

    print(f"\n[C] entrées aléatoires à exposition égale ({args.iter_cd} tirages)...", flush=True)
    c = mc.test_c_random_entries(uni, cfg, trades, n_iter=args.iter_cd, seed=args.seed)
    pct = float((c["distribution"] < s["sharpe"]).mean())
    print(f"    null: p50={c['p50']:.2f} p95={c['p95']:.2f} p99={c['p99']:.2f}")
    print(f"    Sharpe réel {s['sharpe']:.2f} -> percentile {pct:.4f}  "
          f"(p-value = {1-pct:.4f})")

    print(f"\n[D] chemins de prix rééchantillonnés ({args.iter_cd} tirages)...", flush=True)
    d = mc.test_d_resampled_paths(uni, cfg, n_iter=args.iter_cd, seed=args.seed, progress=True)
    print(f"    p05={d['p05']:.2f} p50={d['p50']:.2f} p95={d['p95']:.2f}  "
          f"P(>0)={d['prob_positive']:.3f}")

    verdict = {
        "A_sharpe_significatif": bool(a["p_value_le_zero"] < 0.05),
        "B_drawdown_soutenable": bool(b.get("prob_drawdown_gt_50pct", 1.0) < 0.05),
        "C_entree_a_un_edge": bool(pct > 0.95),
        "D_regles_robustes": bool(d["p05"] > 0.0),
        "sharpe_sup_1_5": bool(s["sharpe"] > 1.5),
    }
    print("\n" + "=" * 100)
    print("VERDICT")
    for k, v in verdict.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print("=" * 100)

    os.makedirs(args.reports, exist_ok=True)
    with open(os.path.join(args.reports, "montecarlo.json"), "w") as fh:
        json.dump({"stats": {k: (v if not isinstance(v, (np.floating, np.integer)) else float(v))
                             for k, v in s.items()},
                   "A": {k: v for k, v in a.items() if k != "distribution"},
                   "B": {k: v for k, v in b.items() if k != "distribution"},
                   "C": {k: v for k, v in c.items() if k != "distribution"},
                   "D": {k: v for k, v in d.items() if k != "distribution"},
                   "verdict": verdict}, fh, indent=2, default=float)
    print(f"[ok] {args.reports}/montecarlo.json")
    return verdict


# --------------------------------------------------------------------------- #
def cmd_all(args):
    print("\n########## 1/3 ABLATION ##########\n")
    cmd_ablation(args)
    print("\n########## 2/3 WALK-FORWARD ##########\n")
    cmd_optimize(args)
    print("\n########## 3/3 MONTE CARLO ##########\n")
    cmd_validate(args)
    if args.holdout:
        print(f"\n########## HOLDOUT SCELLE (>= {args.holdout}) ##########\n")
        uni = get_universe(args)
        ho = align_universe(uni, args.holdout, None)
        if ho:
            r = run_universe(ho, Config())
            print("   " + _fmt(r["stats"]))
            print("\n   Ce chiffre ne doit être regardé QU'UNE FOIS.")


def main(argv=None):
    p = argparse.ArgumentParser(description="Laboratoire Kalman v6")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--data", default=None, help="dossier de fichiers H4")
        sp.add_argument("--synthetic", action="store_true")
        sp.add_argument("--n-tokens", type=int, default=25, dest="n_tokens")
        sp.add_argument("--n-bars", type=int, default=4380, dest="n_bars")
        sp.add_argument("--seed", type=int, default=7)
        sp.add_argument("--start", default=None)
        sp.add_argument("--end", default=None)
        sp.add_argument("--exclude", default="")
        sp.add_argument("--reports", default="reports")

    sp = sub.add_parser("prepare"); sp.set_defaults(fn=cmd_prepare)
    sp.add_argument("--src", required=True); sp.add_argument("--out", required=True)
    sp.add_argument("--rule", default="4h")

    for name, fn in [("ablation", cmd_ablation), ("optimize", cmd_optimize),
                     ("validate", cmd_validate), ("all", cmd_all)]:
        sp = sub.add_parser(name); common(sp); sp.set_defaults(fn=fn)
        if name in ("optimize", "all"):
            sp.add_argument("--folds", type=int, default=4)
            sp.add_argument("--selector", default="plateau", choices=["plateau", "best"])
        if name in ("validate", "all"):
            sp.add_argument("--iter-ab", type=int, default=2000, dest="iter_ab")
            sp.add_argument("--iter-cd", type=int, default=200, dest="iter_cd")
        if name == "all":
            sp.add_argument("--holdout", default=None)

    args = p.parse_args(argv)
    if getattr(args, "cmd", None) != "prepare" and not args.synthetic and not args.data:
        p.error("--data DOSSIER ou --synthetic est requis")
    return args.fn(args)


if __name__ == "__main__":
    main()
    sys.exit(0)
