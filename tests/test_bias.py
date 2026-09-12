"""Tests anti-biais.

Un backtest qui ne passe pas ces tests ne vaut rien, quel que soit son Sharpe.
Le test central est celui de CAUSALITE : modifier le futur ne doit rien changer
au passé. C'est la seule façon fiable d'attraper un lookahead.
"""
from __future__ import annotations

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantlab.core.config import Config
from quantlab.core.engine import backtest_token, compute_signals
from quantlab.core.indicators import donchian_combined, kalman_bq
from quantlab.core.portfolio import run_universe
from quantlab.data.synth import make_universe, make_token

FAIL = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        FAIL.append(name)


def test_indicator_causality():
    """Modifier les bougies futures ne doit pas changer les valeurs passées."""
    rng = np.random.default_rng(3)
    df = make_token(1200, rng, base_vol=0.012)
    cut = 800

    tampered = df.copy()
    # On détruit complètement le futur.
    tampered.iloc[cut:, :4] *= np.exp(rng.normal(0, 0.3, (len(df) - cut, 4)))

    for label, fn in [
        ("kalman", lambda d: kalman_bq(d["close"].to_numpy(float))),
        ("donchian_median", lambda d: donchian_combined(
            d["high"].to_numpy(float), d["low"].to_numpy(float), 20, 2, 4)[2]),
    ]:
        a, b = fn(df), fn(tampered)
        m = np.isfinite(a[:cut]) & np.isfinite(b[:cut])
        same = bool(np.allclose(a[:cut][m], b[:cut][m]))
        check(f"causalité {label} (futur modifié -> passé inchangé)", same,
              f"{m.sum()} points comparés")


def test_pivot_publication_delay():
    """Un pivot ne doit pas être publié avant pvt_right bougies."""
    h = np.array([1., 2, 3, 10, 3, 2, 1, 1, 1, 1, 1, 1.])
    l = np.ones(12)
    from quantlab.core.indicators import pivot_high
    pv = pivot_high(h, 2, 4)
    # Le sommet est en index 3 ; il ne peut être connu qu'à l'index 7.
    early = np.isfinite(pv[:7]) & (pv[:7] == 10.0)
    check("pivot publié avec le retard pvt_right", not early.any(),
          f"première publication à l'index {int(np.argmax(pv == 10.0)) if (pv == 10.0).any() else -1}")


def test_backtest_causality():
    """Les trades clôturés avant la coupure doivent être identiques
    qu'on donne au moteur l'historique complet ou tronqué."""
    rng = np.random.default_rng(11)
    df = make_token(2000, rng, base_vol=0.014)
    df.index = pd.date_range("2024-01-01", periods=len(df), freq="4h")
    cfg = Config()

    full = backtest_token(df, cfg, "T")["trades"]
    cut_i = 1400
    cut_ts = df.index[cut_i]
    trunc = backtest_token(df.iloc[:cut_i], cfg, "T")["trades"]

    if len(full) == 0 or len(trunc) == 0:
        check("causalité backtest", False, "pas assez de trades")
        return

    a = full[full["exit_time"] < cut_ts].reset_index(drop=True)
    b = trunc[trunc["exit_time"] < cut_ts].reset_index(drop=True)
    n = min(len(a), len(b))
    cols = ["entry_time", "exit_time", "side", "entry", "exit", "reason"]
    same = n > 0 and a.loc[:n-1, cols].equals(b.loc[:n-1, cols])
    check("causalité backtest (trades passés identiques si futur inconnu)", same,
          f"{n} trades comparés")


def test_zero_edge_gives_negative_sharpe():
    """Sur une marche aléatoire sans dérive, le Sharpe doit être négatif :
    on ne doit récupérer que le coût. Un Sharpe positif = biais."""
    rng = np.random.default_rng(5)
    uni = {}
    for k in range(12):
        n = 4000
        r = rng.normal(0, 0.012, n)          # bruit pur, aucune structure
        c = 100 * np.exp(np.cumsum(r))
        o = np.concatenate(([100.0], c[:-1]))
        w = np.abs(r) * 0.8 + 0.004
        d = pd.DataFrame({"open": o, "high": np.maximum(o, c) * (1 + w),
                          "low": np.minimum(o, c) * (1 - w), "close": c,
                          "volume": 1.0},
                         index=pd.date_range("2024-01-01", periods=n, freq="4h"))
        uni[f"RW{k}"] = d
    s = run_universe(uni, Config())["stats"]
    check("bruit pur -> Sharpe negatif (pas de free lunch)", s["sharpe"] < 0,
          f"sharpe={s['sharpe']:.2f} sur {s['n_trades']} trades")


def test_cost_monotonicity():
    """Augmenter les coûts doit dégrader la performance, strictement."""
    uni = make_universe(n_tokens=8, n_bars=3000, seed=13)
    sharpes = []
    for mult in [0.0, 1.0, 3.0]:
        cfg = Config(fees_roundtrip_pct=0.086 * mult, spread_pct=0.02 * mult)
        sharpes.append(run_universe(uni, cfg)["stats"]["sharpe"])
    mono = sharpes[0] > sharpes[1] > sharpes[2]
    check("monotonie des coûts (0x > 1x > 3x)", mono,
          " > ".join(f"{s:.2f}" for s in sharpes))


def test_median_gate_removes_kalman_exits():
    """Le gate d'entrée doit supprimer TOUTE sortie clot_kalman."""
    uni = make_universe(n_tokens=8, n_bars=3000, seed=17)
    cfg = Config(entry_above_median=True, exit_on_kalman=False)
    tr = run_universe(uni, cfg)["trades"]
    n_kal = int((tr["reason"] == "clot_kalman").sum()) if len(tr) else 0
    check("gate médiane -> zéro sortie clot_kalman", n_kal == 0, f"{n_kal} trouvées")


def test_gross_cap_enforced():
    """Le cap d'exposition brute doit réellement borner le levier appliqué."""
    uni = make_universe(n_tokens=20, n_bars=3000, seed=19)
    cfg = Config(max_gross=1.5, vol_target_annual=None)
    r = run_universe(uni, cfg)
    eff = (r["gross"] * r["scale"]).max()
    check("cap d'exposition brute respecté", eff <= 1.5 + 1e-9,
          f"gross effectif max = {eff:.3f} (cap 1.5)")


def test_net_cap_enforced():
    """Le cap d'exposition nette doit borner le bêta marché."""
    uni = make_universe(n_tokens=20, n_bars=3000, seed=29)
    cfg = Config(max_net=1.0, max_gross=1e9, vol_target_annual=None)
    s = run_universe(uni, cfg)["stats"]
    check("cap d'exposition nette respecté", s["max_net_observed"] <= 1.0 + 1e-6,
          f"net max = {s['max_net_observed']:.3f} (cap 1.0)")


def test_no_reentry_before_exit():
    """Aucun chevauchement de trades sur un même token."""
    uni = make_universe(n_tokens=6, n_bars=3000, seed=23)
    tr = run_universe(uni, Config())["trades"]
    bad = 0
    for _, g in tr.groupby("token"):
        g = g.sort_values("entry_time")
        prev = None
        for _, row in g.iterrows():
            if prev is not None and row["entry_time"] < prev:
                bad += 1
            prev = row["exit_time"]
    check("pas de chevauchement de positions par token", bad == 0, f"{bad} chevauchements")


if __name__ == "__main__":
    print("=" * 78)
    print("TESTS ANTI-BIAIS")
    print("=" * 78)
    for fn in [test_indicator_causality, test_pivot_publication_delay,
               test_backtest_causality, test_zero_edge_gives_negative_sharpe,
               test_cost_monotonicity, test_median_gate_removes_kalman_exits,
               test_gross_cap_enforced, test_net_cap_enforced,
               test_no_reentry_before_exit]:
        print(f"\n{fn.__name__}")
        fn()
    print("\n" + "=" * 78)
    print(f"{'TOUS LES TESTS PASSENT' if not FAIL else 'ECHECS: ' + ', '.join(FAIL)}")
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
